"""Unit tests for independent daily validation."""

from datetime import date
from pathlib import Path

from backend.app.domain_models import ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    DatedAccessDecision,
    LineNightRule,
    LocationNightRule,
    demo_calendar,
)
from backend.app.ps1.daily_validation import validate_dated_schedule
from backend.app.ps1.models import Scenario
from backend.app.ps1.schedule_projection import (
    build_calendar_assignments,
    project_dated_schedule,
)
from backend.app.topology import FootprintCache

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _build_valid_small_schedule(problem: ProblemInstance) -> tuple[list[CalendarAssignment], list, list]:
    # Use single activity A001 for small valid fixture
    # A001 has total_accesses = 2, planned_start_date = 2027-05-24 (week 21)
    decs = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 5, 25),
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 6, 1),
            week=22,
            eclo=False,
        ),
    ]
    cache = FootprintCache(problem)
    projected = project_dated_schedule(problem, Scenario.A, decs, cache)
    assignments = build_calendar_assignments(problem, projected, calendar_id="test", footprints=cache)
    return assignments, projected.access_rows, projected.occupancy_rows


def test_validator_detects_altered_week() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    act = problem.activity("A001")
    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract(act.contract_number)],
        activities=[act],
    )
    calendar = demo_calendar("test-rev")
    assignments, access_rows, occ_rows = _build_valid_small_schedule(small_problem)

    # Corrupt assignment week: 21 -> 20
    assignments[0].week = 20
    summary = validate_dated_schedule(
        small_problem,
        Scenario.A,
        calendar,
        assignments,
        access_rows,
        occ_rows,
    )
    assert not summary.passed
    assert any(i.rule_code == "DATE_WEEK_MISMATCH" for i in summary.issues)


def test_validator_detects_insufficient_workload() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    act = problem.activity("A001")  # needs 2 accesses
    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract(act.contract_number)],
        activities=[act],
    )
    calendar = demo_calendar("test-rev")
    # Only supply 1 access
    decs = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 5, 25),
            week=21,
            eclo=False,
        ),
    ]
    projected = project_dated_schedule(small_problem, Scenario.A, decs)
    assignments = build_calendar_assignments(small_problem, projected, calendar_id="test")

    summary = validate_dated_schedule(
        small_problem,
        Scenario.A,
        calendar,
        assignments,
        projected.access_rows,
        projected.occupancy_rows,
    )
    assert not summary.passed
    assert any(i.rule_code == "INSUFFICIENT_WORKLOAD" for i in summary.issues)


def test_validator_detects_line_blackout() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    act = problem.activity("A001")
    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract(act.contract_number)],
        activities=[act],
    )
    calendar = demo_calendar("test-rev")
    # A001 is on line BET
    calendar.line_nights.append(
        LineNightRule(
            service_date=date(2027, 5, 25),
            line_code="BET",
            maintenance_available=False,
        )
    )
    assignments, access_rows, occ_rows = _build_valid_small_schedule(small_problem)

    summary = validate_dated_schedule(
        small_problem,
        Scenario.A,
        calendar,
        assignments,
        access_rows,
        occ_rows,
    )
    assert not summary.passed
    assert any(i.rule_code == "LINE_BLACKOUT" for i in summary.issues)


def test_validator_detects_workfront_limit_exceeded() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    # C001 has number_of_workfronts = 2.
    # If 3 activities of C001 operate on the same date -> violation!
    c1_acts = [a for a in problem.activities if a.contract_number == "C001"][:3]
    test_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract("C001")],
        activities=c1_acts,
    )
    calendar = demo_calendar("test-rev")
    decs = [
        DatedAccessDecision(activity_id=c1_acts[0].activity_id, service_date=date(2027, 5, 25), week=21, eclo=False),
        DatedAccessDecision(activity_id=c1_acts[1].activity_id, service_date=date(2027, 5, 25), week=21, eclo=False),
        DatedAccessDecision(activity_id=c1_acts[2].activity_id, service_date=date(2027, 5, 25), week=21, eclo=False),
    ]
    # Also add remaining workload for each so workload passes
    for i, act in enumerate(c1_acts):
        remaining = act.total_accesses - 1
        for w_offset in range(1, remaining + 1):
            decs.append(
                DatedAccessDecision(
                    activity_id=act.activity_id,
                    service_date=date(2027, 5, 25) + date.resolution * (7 * w_offset),
                    week=21 + w_offset,
                    eclo=False,
                )
            )

    projected = project_dated_schedule(test_problem, Scenario.A, decs)
    assignments = build_calendar_assignments(test_problem, projected, calendar_id="test")

    summary = validate_dated_schedule(
        test_problem,
        Scenario.A,
        calendar,
        assignments,
        projected.access_rows,
        projected.occupancy_rows,
    )
    assert not summary.passed
    assert any(i.rule_code == "NIGHTLY_WORKFRONT_LIMIT" for i in summary.issues)


def test_validator_detects_projection_inconsistency() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    act = problem.activity("A001")
    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract(act.contract_number)],
        activities=[act],
    )
    calendar = demo_calendar("test-rev")
    assignments, access_rows, occ_rows = _build_valid_small_schedule(small_problem)

    # Corrupt projected access_night
    access_rows[0].access_night = 99
    summary = validate_dated_schedule(
        small_problem,
        Scenario.A,
        calendar,
        assignments,
        access_rows,
        occ_rows,
    )
    assert not summary.passed
    assert any(i.rule_code == "PROJECTED_ROW_FIELD_MISMATCH" for i in summary.issues)
