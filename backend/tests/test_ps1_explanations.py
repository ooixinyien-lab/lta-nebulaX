"""Tests for explanation fact pack builder, evidence provenance, and deterministic fallbacks."""
from pathlib import Path
from backend.app.config import ROOT
from backend.app.ps1.chat_models import ChatScopeModel
from backend.app.ps1.explanations import (
    ExplanationFactBuilder,
    FixtureExplanationSource,
    SampleOutputExplanationSource,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "chat"


def test_sample_output_fact_pack_fidelity():
    source = SampleOutputExplanationSource(sample_dir=ROOT / "sample_outputs", data_dir=ROOT / "data")
    builder = ExplanationFactBuilder(source)
    scope = ChatScopeModel(
        instance_id="mock-inst",
        instance_revision_id="mock-rev",
        run_id="sample-run",
        scenario="A",
        data_source="mock",
    )
    fact_pack = builder.build_fact_pack(scope, "A001")

    assert fact_pack.scope.data_source == "mock"
    assert fact_pack.activity.activity_id == "A001"
    assert fact_pack.activity.contract_number == "C001"
    assert len(fact_pack.current.placements) == 2
    # Access 1 is in week 22, access 2 is in week 23
    assert fact_pack.current.placements[0].week == 22
    assert fact_pack.current.placements[1].week == 23
    assert fact_pack.availability["mock_data"] is True
    assert fact_pack.availability["baseline_available"] is False
    assert fact_pack.availability["cause_recorded"] is False

    # Deterministic fallback must not invent an unrecorded cause
    assert "does not contain a baseline run or recorded replan cause" in fact_pack.fallback_summary
    assert "[A001]" in fact_pack.fallback_summary


def test_displaced_activity_with_conflicts_and_counterfactuals():
    source = FixtureExplanationSource(FIXTURES_DIR)
    builder = ExplanationFactBuilder(source)
    scope = ChatScopeModel(
        instance_id="fixture-inst",
        instance_revision_id="fixture-rev",
        run_id="run-disrupted-002",
        baseline_run_id="run-baseline-001",
        scenario="A",
        data_source="solver",
    )
    fact_pack = builder.build_fact_pack(scope, "A017")

    # Verify baseline & current diff
    assert fact_pack.baseline.available is True
    assert fact_pack.current.available is True
    assert fact_pack.diff.changed is True
    assert fact_pack.diff.week_displacement == 2

    # Verify conflict identification
    assert len(fact_pack.conflicts) == 1
    conflict = fact_pack.conflicts[0]
    assert conflict["conflicting_activity_id"] == "A044"
    assert conflict["location_id"] == "SEC:BET:S15_S16"
    assert conflict["rule_code"] == "LOCATION_CAPACITY"

    # Verify counterfactual alternative
    assert len(fact_pack.counterfactuals) == 1
    cf = fact_pack.counterfactuals[0]
    assert cf["proposal"]["week"] == 18
    assert cf["result"] == "INFEASIBLE"

    # Verify structured explanation format: Reason -> Impact -> Alternatives -> Evidence
    summary = fact_pack.fallback_summary
    assert "LOCATION_CAPACITY conflict at [SEC:BET:S15_S16]" in summary
    assert "involving [A044]" in summary
    assert "delays [A017] by 2 week(s)" in summary
    assert "week-18 placement was INFEASIBLE" in summary
    assert "Evidence:" in summary
    assert "[A017]" in summary
    assert "[A044]" in summary
    assert "[SEC:BET:S15_S16]" in summary
    assert "[run-disrupted-002]" in summary
    assert "[run-baseline-001]" in summary


def test_missing_cause_behavior_when_baseline_differs_without_conflict():
    source = FixtureExplanationSource(FIXTURES_DIR)
    # Clear conflicts to test missing-cause behavior
    source.conflicts_data = []
    source.counterfactuals_data = []

    builder = ExplanationFactBuilder(source)
    scope = ChatScopeModel(
        instance_id="fixture-inst",
        instance_revision_id="fixture-rev",
        run_id="run-disrupted-002",
        baseline_run_id="run-baseline-001",
        scenario="A",
        data_source="solver",
    )
    fact_pack = builder.build_fact_pack(scope, "A017")

    assert fact_pack.availability["cause_recorded"] is False
    summary = fact_pack.fallback_summary
    assert "does not contain a recorded replan cause or conflict bottleneck" in summary
    assert "No validated alternative placement is stored" in summary
