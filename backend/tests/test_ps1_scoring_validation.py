"""Focused regression tests for independent PS1 scoring and validation."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow, ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.ps1.models import Scenario
from backend.app.ps1.scoring import build_contract_results, build_eclo_summary, compute_score
from backend.app.ps1.validation import validate_schedule
from backend.app.topology import FootprintCache


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SAMPLE_DIR = (
    ROOT / "NebulaX-Hackathon-ProblemStatement-main" / "PS1" / "03_submission_sample"
)


def _sample_access_rows() -> list[AccessScheduleRow]:
    with (SAMPLE_DIR / "SCHEDULE_ACCESS.csv").open(encoding="utf-8", newline="") as stream:
        return [AccessScheduleRow.model_validate(row) for row in csv.DictReader(stream)]


def _sample_occupancy_rows() -> list[OccupancyScheduleRow]:
    with (SAMPLE_DIR / "SCHEDULE_OCCUPANCY.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        return [OccupancyScheduleRow.model_validate(row) for row in csv.DictReader(stream)]


def test_public_sample_reconstructs_adopted_scenario_a_score() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    access_rows = _sample_access_rows()
    occupancy_rows = _sample_occupancy_rows()

    score = compute_score(problem, Scenario.A, access_rows, occupancy_rows)
    validation = validate_schedule(problem, Scenario.A, access_rows, occupancy_rows)
    results = build_contract_results(problem, Scenario.A, access_rows)

    assert score.weighted_activity_lateness_scaled == 483
    assert score.objective_score == pytest.approx(48.3)
    assert score.excess_slots == 0
    assert score.eclo_accesses == 0
    assert sum(row.overrun_days for row in results) == 28
    assert validation.local_accounting_passed
    assert validation.safety_status.value == "unverified"
    assert validation.official_checker_status.value == "unavailable"


def test_excess_counts_distinct_groups_per_location_week() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    access_rows = _sample_access_rows()
    occupancy_rows = _sample_occupancy_rows()
    target = occupancy_rows[0]
    supply = problem.location(target.location_id).supply_capacity

    # Add enough arbitrary local groups at one location/week to exceed supply by one.
    mutated = list(occupancy_rows)
    existing = {
        row.co_share_group
        for row in mutated
        if row.location_id == target.location_id and row.week == target.week
    }
    for index in range(supply + 1 - len(existing)):
        mutated.append(
            OccupancyScheduleRow(
                activity_id=target.activity_id,
                week=target.week,
                location_id=target.location_id,
                co_share_group=f"extra-{index}",
            )
        )

    score = compute_score(problem, Scenario.B, access_rows, mutated)
    assert score.excess_slots == 1
    assert score.excess_penalty_scaled == 70


def test_validator_rejects_duplicate_activity_week() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    access_rows = _sample_access_rows()
    occupancy_rows = _sample_occupancy_rows()
    activity_id = "A007"
    reduced = [
        row
        for row in access_rows
        if not (row.activity_id == activity_id and row.access_seq == 7)
    ]
    duplicate = next(row for row in reduced if row.activity_id == activity_id)
    reduced.append(duplicate.model_copy(update={"access_seq": 99}))

    validation = validate_schedule(problem, Scenario.A, reduced, occupancy_rows)

    assert not validation.local_accounting_passed
    rules = {issue.rule for issue in validation.issues}
    assert "weekly_frequency" in rules
    assert "artifact" in rules


def test_validator_rejects_two_pc_activities_in_one_group() -> None:
    original = load_problem_from_directory(DATA_DIR)
    first = original.activity("A025").model_copy(update={"total_accesses": 1})
    second = original.activity("A074").model_copy(
        update={
            "start_location_id": first.start_location_id,
            "end_location_id": first.end_location_id,
        }
    )
    problem = ProblemInstance(
        lines=original.lines,
        stations=original.stations,
        sectors=original.sectors,
        locations=original.locations,
        buffer_rules=original.buffer_rules,
        parameters=original.parameters,
        contracts=[
            original.contract(first.contract_number),
            original.contract(second.contract_number),
        ],
        activities=[first, second],
    )
    week = 19
    accesses = [
        AccessScheduleRow(
            activity_id=first.activity_id,
            access_seq=1,
            week=week,
            eclo=False,
            access_night=1,
        ),
        AccessScheduleRow(
            activity_id=second.activity_id,
            access_seq=1,
            week=week,
            eclo=False,
            access_night=1,
        ),
    ]
    core_locations = FootprintCache(problem).get_core_footprint(first.activity_id).core_locations
    occupancy = [
        OccupancyScheduleRow(
            activity_id=activity.activity_id,
            week=week,
            location_id=location_id,
            co_share_group="shared",
        )
        for activity in (first, second)
        for location_id in core_locations
    ]

    validation = validate_schedule(problem, Scenario.A, accesses, occupancy)

    assert any(issue.rule == "legal_mix" for issue in validation.issues)


def test_scenario_c_validator_rejects_discontinuous_eclo_weeks() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    access_rows = _sample_access_rows()
    occupancy_rows = _sample_occupancy_rows()
    chosen = [row for row in access_rows if row.activity_id == "A009"]
    modified = []
    for row in access_rows:
        if row.activity_id == "A009" and row.week in (chosen[0].week, chosen[-1].week):
            modified.append(row.model_copy(update={"eclo": True}))
        else:
            modified.append(row)

    validation = validate_schedule(problem, Scenario.C, modified, occupancy_rows)

    assert any(issue.rule == "eclo_window" for issue in validation.issues)


def test_scenario_c_validator_requires_selected_window_for_each_used_line() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    access_rows = _sample_access_rows()
    occupancy_rows = _sample_occupancy_rows()
    modified = [
        row.model_copy(update={"eclo": True})
        if row.activity_id == "A074" and row.access_seq == 1
        else row
        for row in access_rows
    ]

    validation = validate_schedule(
        problem,
        Scenario.C,
        modified,
        occupancy_rows,
        selected_window_starts={"ALP": 19},
    )

    assert any(
        issue.rule == "eclo_window" and "BET" in issue.detail
        for issue in validation.issues
    )


def test_cross_line_live_eclo_counts_once_but_reports_both_lines() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    row = AccessScheduleRow(
        activity_id="A074",
        access_seq=1,
        week=19,
        eclo=True,
        access_night=1,
    )

    summary = build_eclo_summary(
        problem,
        Scenario.B,
        [row],
        FootprintCache(problem),
    )

    assert summary.eclo_accesses_total == 1
    assert summary.eclo_penalty == 5
    assert summary.selected_windows is None
    assert summary.accesses[0].affected_line_codes == ["ALP", "BET"]
    assert {line.line_code for line in summary.by_line} == {"ALP", "BET"}
