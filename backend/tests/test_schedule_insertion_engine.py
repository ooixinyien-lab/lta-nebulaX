"""Focused engine tests using a one-activity official-domain slice."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.domain_models import ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.schedule_insertion.io import load_baseline_bundle
from backend.app.schedule_insertion.models import (
    ProjectAddition,
    ProjectJob,
    ReplanRequest,
    ScheduleScenario,
    SolveOptions,
)
from backend.app.schedule_insertion.solver import _official_jobs, solve_schedule_insertion


ROOT = Path(__file__).resolve().parents[2]


def _slice() -> tuple[ProblemInstance, object, ProjectJob]:
    original = load_problem_from_directory(ROOT / "data")
    problem = ProblemInstance(
        lines=original.lines,
        stations=original.stations,
        sectors=original.sectors,
        locations=original.locations,
        buffer_rules=original.buffer_rules,
        parameters=original.parameters,
        contracts=[original.contracts[0]],
        activities=[original.activities[0]],
    )
    bundle = load_baseline_bundle(ROOT / "data" / "schedule_insertion").model_copy(update={"horizon_weeks": 30})
    return problem, bundle, _official_jobs(problem)[0]


@pytest.mark.parametrize("scenario", [ScheduleScenario.A, ScheduleScenario.B, ScheduleScenario.C])
def test_one_shared_engine_solves_all_scenario_policies(scenario: ScheduleScenario) -> None:
    problem, baseline, _job = _slice()
    request = ReplanRequest(
        baseline_id=baseline.baseline_id,
        baseline_revision=baseline.revision,
        scenario=scenario,
        as_of=datetime(2027, 1, 1, tzinfo=timezone.utc),
        options=SolveOptions(time_limit_seconds=2, num_search_workers=1, optimize=False),
    )
    result = solve_schedule_insertion(problem, baseline, request)

    assert result.status == "SUCCEEDED"
    assert result.reference_candidate is not None
    assert result.reference_candidate.validation.passed
    assert len(result.reference_candidate.projects) == 2
    if scenario == ScheduleScenario.A:
        assert all(not access.eclo for access in result.reference_candidate.projects)


def test_emergency_insertion_keeps_previous_access_identity_and_freezes_occurred_work() -> None:
    problem, baseline, job = _slice()
    first_request = ReplanRequest(
        baseline_id=baseline.baseline_id,
        baseline_revision=baseline.revision,
        scenario=ScheduleScenario.C,
        as_of=datetime(2027, 1, 1, tzinfo=timezone.utc),
        options=SolveOptions(time_limit_seconds=2, num_search_workers=1, optimize=False),
    )
    first = solve_schedule_insertion(problem, baseline, first_request)
    assert first.reference_candidate and first.reference_candidate.validation.passed
    baseline2 = baseline.model_copy(update={"revision": 2, "project_jobs": [job], "project_accesses": first.reference_candidate.projects})
    frozen = first.reference_candidate.projects[0]
    emergency = job.model_copy(update={
        "job_id": "EM-001",
        "contract_number": "EM-001",
        "total_accesses": 1,
        "planned_start_date": baseline.horizon_start,
        "planned_completion_date": baseline.horizon_start + timedelta(days=70),
        "hard_completion_date": baseline.horizon_start + timedelta(days=70),
        "source": "emergency",
    })
    second_request = ReplanRequest(
        baseline_id=baseline2.baseline_id,
        baseline_revision=baseline2.revision,
        scenario=ScheduleScenario.C,
        as_of=datetime.combine(frozen.service_date, datetime.min.time(), tzinfo=timezone.utc),
        additions=[ProjectAddition(job=emergency, requested_source="emergency")],
        options=SolveOptions(time_limit_seconds=2, num_search_workers=1, optimize=False),
    )
    second = solve_schedule_insertion(problem, baseline2, second_request)

    assert second.status == "SUCCEEDED"
    assert second.reference_candidate is not None
    retained = next(access for access in second.reference_candidate.projects if access.access_id == frozen.access_id)
    assert retained.week == frozen.week
    assert retained.service_date == frozen.service_date


def test_infeasibility_and_stale_baseline_are_truthful() -> None:
    problem, baseline, job = _slice()
    impossible = job.model_copy(update={
        "job_id": "EM-IMPOSSIBLE",
        "contract_number": "EM-IMPOSSIBLE",
        "planned_start_date": baseline.horizon_start,
        "planned_completion_date": baseline.horizon_start,
        "hard_completion_date": baseline.horizon_start - timedelta(days=1),
        "source": "emergency",
    })
    request = ReplanRequest(
        baseline_id=baseline.baseline_id,
        baseline_revision=baseline.revision,
        scenario=ScheduleScenario.B,
        as_of=datetime(2027, 1, 1, tzinfo=timezone.utc),
        additions=[ProjectAddition(job=impossible, requested_source="emergency")],
        options=SolveOptions(time_limit_seconds=1, num_search_workers=1, optimize=False),
    )
    result = solve_schedule_insertion(problem, baseline, request)
    assert result.status == "INFEASIBLE"
    assert result.reference_candidate is None

    stale = request.model_copy(update={"baseline_revision": baseline.revision + 1, "additions": []})
    stale_result = solve_schedule_insertion(problem, baseline, stale)
    assert stale_result.status == "FAILED"
