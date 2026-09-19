"""Service layer coordinating explanation fact packs, authorization, Gemini execution, and persistence."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from backend.app.auth.resource_access import (
    ChatScope,
    authorize_activity_read,
    build_chat_scope,
)
from backend.app.config import ROOT, Settings
from backend.app.db.models import ChatTurnRow, ExplanationFactPackRow
from backend.app.db.repositories.audit import record_event
from backend.app.db.repositories.chat import (
    create_chat_session,
    get_chat_session,
    list_session_turns,
    record_chat_turn,
)
from backend.app.db.repositories.explanations import find_fact_pack, save_fact_pack
from backend.app.integrations.gemini import GeminiChatProvider
from backend.app.ps1.chat_models import (
    ChatRequest,
    ChatResponse,
    ChatScopeModel,
    EvidenceItem,
    ExplanationFactPack,
    ExplanationResponse,
    ProvenanceModel,
)
from backend.app.ps1.chat_tools import ScheduleReadTools
from backend.app.ps1.explanations import (
    ExplanationFactBuilder,
    ExplanationScheduleSource,
    PersistedRunExplanationSource,
    SampleOutputExplanationSource,
)
from backend.app.schemas import User

logger = logging.getLogger(__name__)


def redact_text(text: str, mode: str) -> str:
    """Redacts sensitive credentials, tokens, and personal identifiers from logs according to policy."""
    if mode == "metadata":
        return "[REDACTED_BY_METADATA_POLICY]"
    if mode == "full":
        return text

    # Redacted mode: remove bearer tokens, API keys, and sensitive authorization patterns
    cleaned = re.sub(r'(?i)(bearer\s+[a-zA-Z0-9_\-\.]{15,})', '[REDACTED_TOKEN]', text)
    cleaned = re.sub(r'(?i)(AIza[0-9A-Za-z\-_]{35})', '[REDACTED_API_KEY]', cleaned)
    cleaned = re.sub(r'(?i)(sk-[a-zA-Z0-9]{20,})', '[REDACTED_SECRET]', cleaned)
    cleaned = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', '[REDACTED_EMAIL]', cleaned)
    return cleaned


class ChatService:
    """Coordinates grounded schedule explanations and conversations."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = GeminiChatProvider(settings)

    def _get_source(
        self,
        session: sqlite3.Connection,
        scope: ChatScope,
    ) -> ExplanationScheduleSource:
        if scope.is_mock:
            sample_dir = ROOT / "sample_outputs"
            data_dir = ROOT / "data"
            return SampleOutputExplanationSource(sample_dir=sample_dir, data_dir=data_dir)
        return PersistedRunExplanationSource(session=session, revision_id=scope.instance_revision_id)

    def get_or_build_explanation(
        self,
        session: sqlite3.Connection,
        run_id: str,
        activity_id: str,
        user: User,
        baseline_run_id: str | None = None,
    ) -> ExplanationResponse:
        """Retrieves or deterministically constructs an immutable explanation fact pack."""
        # 1. Authorize scope and run
        scope = build_chat_scope(session, run_id, user, baseline_run_id)

        # 2. Validate activity belongs to instance revision (if not mock)
        if not scope.is_mock:
            authorize_activity_read(session, scope.instance_revision_id, activity_id)

        # 3. Check cache in database
        cached = find_fact_pack(session, run_id, activity_id, baseline_run_id)
        if cached is not None:
            fact_pack = ExplanationFactPack.model_validate(cached.facts_json)
            provenance = ProvenanceModel(
                provider="nebula-x-deterministic",
                model=cached.builder_version,
                prompt_template_version=self.settings.chat_prompt_template_version,
                instance_revision_id=scope.instance_revision_id,
                run_id=scope.run_id,
                baseline_run_id=scope.baseline_run_id,
            )
            return ExplanationResponse(
                fact_pack=fact_pack,
                fallback_summary=cached.fallback_summary,
                provenance=provenance,
            )

        # 4. Build fact pack
        source = self._get_source(session, scope)
        builder = ExplanationFactBuilder(source)
        scope_model = ChatScopeModel(
            instance_id=scope.instance_id,
            instance_revision_id=scope.instance_revision_id,
            run_id=scope.run_id,
            baseline_run_id=scope.baseline_run_id,
            scenario=scope.scenario,
            data_source=source.data_source,
        )
        fact_pack = builder.build_fact_pack(scope_model, activity_id)

        # 5. Persist immutable fact pack if non-mock and run_id is a valid solver_runs FK.
        # Operational runs (prefix "sir-") and empty run_ids do NOT exist in solver_runs,
        # so persisting with those would violate the FOREIGN KEY constraint.
        _can_persist = not scope.is_mock and bool(scope.run_id) and scope.run_id.startswith("run-")
        if _can_persist:
            save_fact_pack(
                session,
                ExplanationFactPackRow(
                    id=fact_pack.fact_pack_id,
                    instance_id=scope.instance_id,
                    instance_revision_id=scope.instance_revision_id,
                    run_id=scope.run_id,
                    baseline_run_id=scope.baseline_run_id,
                    activity_id=activity_id,
                    facts_json=fact_pack.model_dump(),
                    fallback_summary=fact_pack.fallback_summary,
                    evidence_hash=fact_pack.fact_pack_id.replace("efp-", ""),
                    builder_version=builder.BUILDER_VERSION,
                    created_at=datetime.now(timezone.utc),
                ),
            )
            record_event(
                session,
                actor=user.id,
                action="explanation_fact_pack_created",
                entity_type="explanation_fact_pack",
                entity_id=fact_pack.fact_pack_id,
                detail={"run_id": run_id, "activity_id": activity_id},
            )

        provenance = ProvenanceModel(
            provider="nebula-x-deterministic",
            model=builder.BUILDER_VERSION,
            prompt_template_version=self.settings.chat_prompt_template_version,
            instance_revision_id=scope.instance_revision_id,
            run_id=scope.run_id,
            baseline_run_id=scope.baseline_run_id,
        )
        return ExplanationResponse(
            fact_pack=fact_pack,
            fallback_summary=fact_pack.fallback_summary,
            provenance=provenance,
        )

    def handle_chat_turn(
        self,
        session: sqlite3.Connection,
        payload: ChatRequest,
        user: User,
    ) -> ChatResponse:
        """Processes a single grounded chat turn with security authorization, rate limiting, and persistence."""
        if len(payload.question) > self.settings.chat_max_question_chars:
            raise HTTPException(
                status_code=400,
                detail=f"Question exceeds maximum allowed length ({self.settings.chat_max_question_chars} chars)",
            )

        # 1. Authorize scope
        scope = build_chat_scope(
            session=session,
            run_id=payload.run_id,
            user=user,
            baseline_run_id=payload.baseline_run_id,
            instance_id=payload.instance_id,
            scenario=payload.scenario or "A",
            instance_revision_id=payload.instance_revision_id,
        )

        # 2. Validate activity if provided
        act_id = payload.selected_activity_id or "A001"
        if not scope.is_mock and payload.selected_activity_id:
            authorize_activity_read(session, scope.instance_revision_id, payload.selected_activity_id)

        # 3. Obtain schedule source and fact pack
        source = self._get_source(session, scope)
        builder = ExplanationFactBuilder(source)
        scope_model = ChatScopeModel(
            instance_id=scope.instance_id,
            instance_revision_id=scope.instance_revision_id,
            run_id=scope.run_id,
            baseline_run_id=scope.baseline_run_id,
            scenario=scope.scenario,
            data_source=source.data_source,
        )
        fact_pack = builder.build_fact_pack(scope_model, act_id)

        # 4. Session resolution
        session_id = payload.session_id or f"chat-{uuid4().hex[:12]}"
        # Only persist if run_id is a valid solver_runs FK.
        # Operational runs (prefix "sir-") and empty/unresolved run_ids live in
        # different tables and must NOT be stored in chat_sessions or explanation_fact_packs.
        _can_persist_session = (
            not scope.is_mock
            and bool(scope.run_id)
            and scope.run_id.startswith("run-")
        )

        existing_session = get_chat_session(session, session_id)
        if existing_session is None:
            if _can_persist_session:
                create_chat_session(
                    session,
                    session_id=session_id,
                    instance_id=scope.instance_id,
                    run_id=scope.run_id,
                    baseline_run_id=scope.baseline_run_id,
                    created_by=user.id,
                )
                record_event(
                    session,
                    actor=user.id,
                    action="chat_session_created",
                    entity_type="chat_session",
                    entity_id=session_id,
                    detail={"run_id": scope.run_id},
                )

        # 5. Load bounded conversation history
        past_turns = list_session_turns(session, session_id, limit=self.settings.chat_history_turns) if not scope.is_mock else []
        history = []
        for t in past_turns:
            history.append({"role": "user", "content": t.question_redacted})
            history.append({"role": "model", "content": t.answer_redacted})

        # 6. Call provider or fallback
        read_tools = ScheduleReadTools(source)
        answer, response_mode, citations, uncertainty, tools_used = self.provider.answer(
            scope=scope,
            fact_pack=fact_pack,
            question=payload.question,
            conversation_history=history,
            read_tools=read_tools,
        )

        # 7. Redact and record turn in database
        q_redacted = redact_text(payload.question, self.settings.chat_log_mode)
        a_redacted = redact_text(answer, self.settings.chat_log_mode)

        if _can_persist_session:
            turn_row = ChatTurnRow(
                id=f"turn-{uuid4().hex[:12]}",
                session_id=session_id,
                user_id=user.id,
                question_redacted=q_redacted,
                answer_redacted=a_redacted,
                response_mode=response_mode,
                provider="gemini" if response_mode == "gemini" else "deterministic",
                model=self.settings.gemini_model if response_mode == "gemini" else builder.BUILDER_VERSION,
                prompt_template_version=self.settings.chat_prompt_template_version,
                fact_pack_id=fact_pack.fact_pack_id,
                tool_trace_json=[{"tool": t} for t in tools_used],
                citation_json=[c.model_dump() for c in citations],
                uncertainty_json=uncertainty,
                created_at=datetime.now(timezone.utc),
            )
            record_chat_turn(session, turn_row)
            record_event(
                session,
                actor=user.id,
                action="chat_turn_completed",
                entity_type="chat_turn",
                entity_id=turn_row.id,
                detail={
                    "provider": turn_row.provider,
                    "response_mode": response_mode,
                    "run_id": scope.run_id,
                    "activity_id": act_id,
                    "tools_used": tools_used,
                },
            )

        provenance = ProvenanceModel(
            provider="gemini" if response_mode == "gemini" else "google",
            model=self.settings.gemini_model if response_mode == "gemini" else "deterministic-v1",
            prompt_template_version=self.settings.chat_prompt_template_version,
            instance_revision_id=scope.instance_revision_id,
            run_id=scope.run_id,
            baseline_run_id=scope.baseline_run_id,
        )

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            response_mode=response_mode,
            fact_pack_id=fact_pack.fact_pack_id,
            citations=citations,
            uncertainty=uncertainty,
            provenance=provenance,
            tools_used=tools_used,
        )
