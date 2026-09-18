"""Tests for provider outages, quota exhaustion, and citation grounding verification."""
from pathlib import Path
from unittest.mock import MagicMock
from backend.app.auth.resource_access import ChatScope
from backend.app.config import Settings
from backend.app.integrations.gemini import GeminiChatProvider
from backend.app.ps1.chat_models import ChatScopeModel
from backend.app.ps1.chat_tools import ScheduleReadTools
from backend.app.ps1.explanations import ExplanationFactBuilder, FixtureExplanationSource

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "chat"


def test_missing_api_key_returns_deterministic_fallback():
    settings = Settings(gemini_api_key="")
    provider = GeminiChatProvider(settings)

    source = FixtureExplanationSource(FIXTURES_DIR)
    builder = ExplanationFactBuilder(source)
    scope = ChatScope(
        instance_id="inst-1",
        instance_revision_id="rev-1",
        run_id="run-disrupted-002",
        baseline_run_id="run-baseline-001",
        scenario="A",
        user_id="officer",
        user_role="officer",
    )
    scope_model = ChatScopeModel(
        instance_id=scope.instance_id,
        instance_revision_id=scope.instance_revision_id,
        run_id=scope.run_id,
        baseline_run_id=scope.baseline_run_id,
        scenario=scope.scenario,
        data_source="solver",
    )
    fact_pack = builder.build_fact_pack(scope_model, "A017")
    read_tools = ScheduleReadTools(source)

    answer, mode, citations, uncertainty, tools_used = provider.answer(
        scope=scope,
        fact_pack=fact_pack,
        question="Why was A017 moved?",
        conversation_history=[],
        read_tools=read_tools,
    )

    assert mode == "deterministic_fallback"
    assert answer == fact_pack.fallback_summary
    assert "provider_unavailable" in uncertainty
    assert len(citations) > 0


def test_provider_exception_falls_back_cleanly():
    settings = Settings(gemini_api_key="fake-key-for-mock")
    provider = GeminiChatProvider(settings)
    # Mock client to simulate a 429 quota exhaustion or network timeout
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Gemini call timed out")
    provider.client = mock_client

    source = FixtureExplanationSource(FIXTURES_DIR)
    builder = ExplanationFactBuilder(source)
    scope = ChatScope(
        instance_id="inst-1",
        instance_revision_id="rev-1",
        run_id="run-disrupted-002",
        baseline_run_id="run-baseline-001",
        scenario="A",
        user_id="officer",
        user_role="officer",
    )
    scope_model = ChatScopeModel(
        instance_id=scope.instance_id,
        instance_revision_id=scope.instance_revision_id,
        run_id=scope.run_id,
        baseline_run_id=scope.baseline_run_id,
        scenario=scope.scenario,
        data_source="solver",
    )
    fact_pack = builder.build_fact_pack(scope_model, "A017")
    read_tools = ScheduleReadTools(source)

    answer, mode, citations, uncertainty, tools_used = provider.answer(
        scope=scope,
        fact_pack=fact_pack,
        question="Why was A017 moved?",
        conversation_history=[],
        read_tools=read_tools,
    )

    assert mode == "deterministic_fallback"
    assert answer == fact_pack.fallback_summary
    assert any("provider_error" in u for u in uncertainty)


def test_unsupported_citations_trigger_grounding_fallback():
    settings = Settings(gemini_api_key="fake-key-for-mock")
    provider = GeminiChatProvider(settings)

    # Mock response candidate where the model hallucinated an unknown entity [A999]
    mock_client = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "Activity [A017] was delayed because of fictitious conflict with [A999]."
    mock_part.function_call = None
    mock_candidate.content.parts = [mock_part]
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_client.models.generate_content.return_value = mock_response
    provider.client = mock_client

    source = FixtureExplanationSource(FIXTURES_DIR)
    builder = ExplanationFactBuilder(source)
    scope = ChatScope(
        instance_id="inst-1",
        instance_revision_id="rev-1",
        run_id="run-disrupted-002",
        baseline_run_id="run-baseline-001",
        scenario="A",
        user_id="officer",
        user_role="officer",
    )
    scope_model = ChatScopeModel(
        instance_id=scope.instance_id,
        instance_revision_id=scope.instance_revision_id,
        run_id=scope.run_id,
        baseline_run_id=scope.baseline_run_id,
        scenario=scope.scenario,
        data_source="solver",
    )
    fact_pack = builder.build_fact_pack(scope_model, "A017")
    read_tools = ScheduleReadTools(source)

    answer, mode, citations, uncertainty, tools_used = provider.answer(
        scope=scope,
        fact_pack=fact_pack,
        question="Why was A017 moved?",
        conversation_history=[],
        read_tools=read_tools,
    )

    # Hallucinated [A999] must trigger grounding failure and revert to fallback!
    assert mode == "deterministic_fallback"
    assert answer == fact_pack.fallback_summary
    assert any("unsupported_citation:A999" in u for u in uncertainty)
