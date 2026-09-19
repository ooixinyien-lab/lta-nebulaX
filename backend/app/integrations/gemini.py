"""Provider adapter for Google Gemini LLM using the google-genai SDK, with graceful offline fallback."""
from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
from pathlib import Path
import re
from typing import Any, Literal

from backend.app.auth.resource_access import ChatScope
from backend.app.config import Settings
from backend.app.ps1.chat_models import EvidenceItem, ExplanationFactPack
from backend.app.ps1.chat_tools import ScheduleReadTools, TOOL_DECLARATIONS

logger = logging.getLogger(__name__)

# Conditional import of google-genai SDK
try:
    from google import genai
    from google.genai import types
    GENAI_SDK_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    GENAI_SDK_AVAILABLE = False


class _FallbackTypes:
    class Tool:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FunctionDeclaration:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Content:
        def __init__(self, role=None, parts=None):
            self.role = role
            self.parts = parts or []

    class Part:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        @classmethod
        def from_text(cls, text: str = "", **kwargs):
            p = cls()
            p.text = text or kwargs.get("text", "")
            p.function_call = None
            return p

        @classmethod
        def from_function_response(cls, name: str = "", response: dict | None = None, **kwargs):
            p = cls()
            p.name = name or kwargs.get("name", "")
            p.response = response if response is not None else kwargs.get("response", {})
            return p

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


if types is None:
    types = _FallbackTypes  # type: ignore


class ChatProvider(ABC):
    """Abstract interface for LLM explanation providers."""

    @abstractmethod
    def answer(
        self,
        scope: ChatScope,
        fact_pack: ExplanationFactPack,
        question: str,
        conversation_history: list[dict[str, str]],
        read_tools: ScheduleReadTools,
    ) -> tuple[str, Literal["gemini", "deterministic_fallback"], list[EvidenceItem], list[str], list[str]]:
        """Returns (answer, response_mode, citations, uncertainty_flags, tools_used)."""
        pass


class GeminiChatProvider(ChatProvider):
    """Grounded Gemini provider with bounded function-calling loop and citation verification."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.system_prompt = self._load_system_prompt()
        self.client = None
        if GENAI_SDK_AVAILABLE and self.settings.gemini_api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.settings.gemini_api_key)
            except Exception as exc:
                logger.warning("Failed to initialize Google GenAI client: %s", exc)

    def _load_system_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parent.parent / "ps1" / "prompts" / f"{self.settings.chat_prompt_template_version}.txt"
        )
        if prompt_path.is_file():
            return prompt_path.read_text(encoding="utf-8")
        return "You are the ForRail Schedule Explainer. Ground answers in provided facts."

    @property
    def is_available(self) -> bool:
        if self.client is not None and bool(self.settings.gemini_api_key):
            return True
        return bool(GENAI_SDK_AVAILABLE and self.settings.gemini_api_key)


    def answer(
        self,
        scope: ChatScope,
        fact_pack: ExplanationFactPack,
        question: str,
        conversation_history: list[dict[str, str]],
        read_tools: ScheduleReadTools,
    ) -> tuple[str, Literal["gemini", "deterministic_fallback"], list[EvidenceItem], list[str], list[str]]:
        if not self.is_available:
            logger.info("Gemini provider not configured or SDK missing; using deterministic fallback.")
            return (
                fact_pack.fallback_summary,
                "deterministic_fallback",
                fact_pack.evidence,
                ["provider_unavailable"] + ([k for k, v in fact_pack.availability.items() if not v]),
                [],
            )

        # Allowed evidence pool for grounding verification
        known_evidence_map: dict[str, EvidenceItem] = {
            item.entity_id: item for item in fact_pack.evidence
        }
        for item in fact_pack.evidence:
            known_evidence_map[item.evidence_id] = item
        allowed_entity_ids = set(known_evidence_map.keys())
        allowed_entity_ids.update([
            scope.run_id,
            fact_pack.activity.activity_id,
            fact_pack.activity.contract_number,
        ])
        if scope.baseline_run_id:
            allowed_entity_ids.add(scope.baseline_run_id)
        for p in fact_pack.current.placements:
            allowed_entity_ids.update(p.locations)
            if p.co_share_group:
                allowed_entity_ids.add(p.co_share_group)
        for c in fact_pack.conflicts:
            if c.get("conflicting_activity_id"):
                allowed_entity_ids.add(c["conflicting_activity_id"])
            if c.get("location_id"):
                allowed_entity_ids.add(c["location_id"])
            if c.get("conflict_id"):
                allowed_entity_ids.add(c["conflict_id"])

        tools_used: list[str] = []
        max_tool_calls = self.settings.chat_max_tool_calls

        try:
            # Build initial context prompt
            initial_context = (
                f"SCHEDULE FACT PACK:\n{json.dumps(fact_pack.model_dump(), indent=2)}\n\n"
                "INSTRUCTIONS FOR YOUR RESPONSE:\n"
                "- Explain in clear, simple, professional plain English for railway planners and maintenance teams.\n"
                "- Explain penalties in terms of real-world operational factors (e.g. activity completion lateness, extra track possession slots, weekend closures) rather than formula variables.\n"
                "- Do NOT use raw math symbols like ($P$), ($V$), or ($E$).\n"
                "- Do NOT output internal code tokens or debug flags like `cause_recorded: false` or `baseline_available: false`.\n"
                "- Provide a direct, easy-to-understand explanation first before giving supporting details.\n\n"
                f"CURRENT QUESTION:\n{question}"
            )

            # Convert tools to genai FunctionDeclarations if supported
            genai_tools = []
            for t in TOOL_DECLARATIONS:
                genai_tools.append(
                    types.Tool(
                        function_declarations=[
                            types.FunctionDeclaration(
                                name=t["name"],
                                description=t["description"],
                                parameters=t["parameters"],
                            )
                        ]
                    )
                )

            # Initial contents
            contents = []
            for h in conversation_history[-self.settings.chat_history_turns:]:
                role = "user" if h.get("role") == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h.get("content", ""))]))

            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=initial_context)]))

            # Bounded tool execution loop
            tool_call_count = 0
            final_text = ""

            while tool_call_count < max_tool_calls:
                response = self.client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        tools=genai_tools,
                        temperature=0.1,
                        max_output_tokens=self.settings.chat_max_output_tokens,
                    ),
                )

                candidate = response.candidates[0] if response.candidates else None
                if not candidate:
                    raise RuntimeError("No candidate received from Gemini")

                # Check for function calls
                function_calls = [
                    part.function_call for part in candidate.content.parts if part.function_call is not None
                ]

                if not function_calls:
                    # Model produced final answer
                    final_text = "".join(part.text for part in candidate.content.parts if part.text)
                    break

                # Execute requested tool calls
                contents.append(candidate.content)
                function_responses = []

                for fc in function_calls:
                    tool_call_count += 1
                    tools_used.append(fc.name)
                    args = dict(fc.args) if fc.args else {}
                    tool_result, new_evidence = read_tools.execute_tool(scope, fc.name, args)

                    for item in new_evidence:
                        known_evidence_map[item.entity_id] = item
                        known_evidence_map[item.evidence_id] = item
                        allowed_entity_ids.add(item.entity_id)

                    function_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": tool_result},
                        )
                    )

                contents.append(types.Content(role="user", parts=function_responses))

            if not final_text:
                # If tool calls loop exhausted without text
                final_text = fact_pack.fallback_summary
                return (
                    final_text,
                    "deterministic_fallback",
                    fact_pack.evidence,
                    ["max_tool_calls_reached"],
                    tools_used,
                )

            # Grounding verification on bracketed citations: e.g. [A017], [run-123]
            bracketed_citations = set(re.findall(r'\[([A-Za-z0-9_:\-]+)\]', final_text))
            unsupported_citations = []
            matched_evidence: list[EvidenceItem] = []

            for cit in bracketed_citations:
                if cit in allowed_entity_ids:
                    if cit in known_evidence_map:
                        matched_evidence.append(known_evidence_map[cit])
                else:
                    # Check if it looks like an entity identifier
                    if (
                        cit.startswith("A")
                        or cit.startswith("C")
                        or cit.startswith("run-")
                        or "SEC:" in cit
                        or "PLAT:" in cit
                        or cit.startswith("cf-")
                    ):
                        unsupported_citations.append(cit)

            if unsupported_citations:
                logger.warning(
                    "Gemini cited unsupported entities %s not in evidence set; falling back to deterministic summary.",
                    unsupported_citations,
                )
                return (
                    fact_pack.fallback_summary,
                    "deterministic_fallback",
                    fact_pack.evidence,
                    [f"unsupported_citation:{c}" for c in unsupported_citations],
                    tools_used,
                )

            # Deduplicate matched citations
            dedup_citations = list({e.evidence_id: e for e in matched_evidence}.values())
            uncertainty_flags = [k for k, v in fact_pack.availability.items() if not v]

            return (
                final_text,
                "gemini",
                dedup_citations or fact_pack.evidence,
                uncertainty_flags,
                tools_used,
            )

        except Exception as exc:
            logger.warning("Gemini call failed with error: %s; falling back to deterministic explanation.", exc)
            return (
                fact_pack.fallback_summary,
                "deterministic_fallback",
                fact_pack.evidence,
                [f"provider_error:{type(exc).__name__}"],
                tools_used,
            )
