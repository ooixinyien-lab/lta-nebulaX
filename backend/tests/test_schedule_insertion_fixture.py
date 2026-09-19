"""Deterministic operational fixture and independent maintenance checks."""

from pathlib import Path

from backend.app.domain_models import ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.schedule_insertion.fixture_generator import build_fixture
from backend.app.schedule_insertion.io import load_baseline_bundle
from backend.app.schedule_insertion.validation import validate_maintenance_fixture


ROOT = Path(__file__).resolve().parents[2]


def test_fixture_generation_is_deterministic_and_uses_actual_topology() -> None:
    problem = load_problem_from_directory(ROOT / "data")
    first = build_fixture(problem)
    second = build_fixture(problem)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert len(first.maintenance_jobs) >= len(problem.sectors) * 3
    assert {job.sector_id for job in first.maintenance_jobs} == {sector.sector_id for sector in problem.sectors}
    assert all(visit.visit_id.endswith(f":VISIT:{visit.visit_seq}") for visit in first.maintenance_visits)


def test_checked_in_fixture_passes_rolling_coverage_and_daily_capacity() -> None:
    problem = load_problem_from_directory(ROOT / "data")
    bundle = load_baseline_bundle(ROOT / "data" / "schedule_insertion")
    validation = validate_maintenance_fixture(problem, bundle)

    assert validation.passed, validation.findings
    assert validation.maintenance_coverage_checked
    assert len(bundle.maintenance_visits) == len(bundle.maintenance_jobs) * 3
    assert {visit.status.value for visit in bundle.maintenance_visits} >= {"historical", "scheduled", "committed"}
