"""Unit tests for deterministic projection from dated decisions to official PS1 CSV rows."""

from datetime import date
from pathlib import Path

from backend.app.domain_models import ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.ps1.calendar_models import DatedAccessDecision
from backend.app.ps1.models import Scenario
from backend.app.ps1.schedule_projection import (
    build_calendar_assignments,
    project_dated_schedule,
)
from backend.app.topology import FootprintCache

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_access_sequence_is_chronological() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    # A001 has planned_start_date in week 21 (around May 2027)
    decisions = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 6, 15),
            week=24,
            eclo=False,
        ),
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
            eclo=True,
        ),
    ]

    projected = project_dated_schedule(problem, Scenario.A, decisions)
    assert len(projected.access_rows) == 3
    assert [r.access_seq for r in projected.access_rows] == [1, 2, 3]
    assert [r.week for r in projected.access_rows] == [21, 22, 24]
    assert [r.eclo for r in projected.access_rows] == [False, True, False]


def test_access_night_is_contract_type_week_local() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    # A001 and A002 belong to C001 (Renewal)
    # A008 belongs to C002 (Renewal)
    # Both operate in week 21
    # Dates: Mon 2027-05-24, Tue 2027-05-25, Wed 2027-05-26
    decisions = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 5, 24),  # Monday
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A002",
            service_date=date(2027, 5, 26),  # Wednesday
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A008",
            service_date=date(2027, 5, 26),  # Wednesday for C002
            week=21,
            eclo=False,
        ),
    ]

    projected = project_dated_schedule(problem, Scenario.A, decisions)
    rows_by_act = {r.activity_id: r for r in projected.access_rows}

    # For C001: Monday is earliest date -> 1, Wednesday is second date -> 2
    assert rows_by_act["A001"].access_night == 1
    assert rows_by_act["A002"].access_night == 2

    # For C002: Wednesday is the ONLY date -> 1 (not 2 or 3!)
    assert rows_by_act["A008"].access_night == 1


def test_co_share_group_maps_by_location_and_date() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    cache = FootprintCache(problem)
    # Pick two activities sharing core locations
    # A001 core: SEC:BET:S15_S16:EB, SEC:BET:S16_S17:EB
    # A011 (C002) core: SEC:BET:S15_S16:EB, SEC:BET:S16_S17:EB
    # If both operate on Tuesday 2027-05-25, they must get the same co_share_group
    # If A001 operates Tuesday and A011 operates Thursday, they get different groups.

    # Case 1: Same date -> same group
    decisions_same_date = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 5, 25),
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A011",
            service_date=date(2027, 5, 25),
            week=21,
            eclo=False,
        ),
    ]
    projected = project_dated_schedule(problem, Scenario.A, decisions_same_date, cache)
    occ_a001 = {r.location_id: r.co_share_group for r in projected.occupancy_rows if r.activity_id == "A001"}
    occ_a011 = {r.location_id: r.co_share_group for r in projected.occupancy_rows if r.activity_id == "A011"}
    for loc in occ_a001:
        if loc in occ_a011:
            assert occ_a001[loc] == occ_a011[loc] == "g1"

    # Case 2: Different dates -> different groups
    decisions_diff_date = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 5, 25),  # Tuesday
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A011",
            service_date=date(2027, 5, 27),  # Thursday
            week=21,
            eclo=False,
        ),
    ]
    projected2 = project_dated_schedule(problem, Scenario.A, decisions_diff_date, cache)
    occ2_a001 = {r.location_id: r.co_share_group for r in projected2.occupancy_rows if r.activity_id == "A001"}
    occ2_a011 = {r.location_id: r.co_share_group for r in projected2.occupancy_rows if r.activity_id == "A011"}
    for loc in occ2_a001:
        if loc in occ2_a011:
            assert occ2_a001[loc] == "g1"
            assert occ2_a011[loc] == "g2"
            assert occ2_a001[loc] != occ2_a011[loc]


def test_projection_is_deterministic() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    decisions = [
        DatedAccessDecision(
            activity_id="A001",
            service_date=date(2027, 5, 25),
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A002",
            service_date=date(2027, 5, 24),
            week=21,
            eclo=False,
        ),
        DatedAccessDecision(
            activity_id="A011",
            service_date=date(2027, 5, 27),
            week=21,
            eclo=False,
        ),
    ]

    p1 = project_dated_schedule(problem, Scenario.A, decisions)
    p2 = project_dated_schedule(problem, Scenario.A, list(reversed(decisions)))

    assert [r.model_dump() for r in p1.access_rows] == [r.model_dump() for r in p2.access_rows]
    assert [r.model_dump() for r in p1.occupancy_rows] == [r.model_dump() for r in p2.occupancy_rows]


def test_build_calendar_assignments() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    decisions = [
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
            eclo=True,
        ),
    ]
    projected = project_dated_schedule(problem, Scenario.C, decisions)
    assignments = build_calendar_assignments(problem, projected, calendar_id="test-cal")

    assert len(assignments) == 2
    assert assignments[0].access_id == "test-cal:A001:1"
    assert assignments[0].service_date == date(2027, 5, 25)
    assert assignments[0].week == 21
    assert assignments[0].eclo is False
    assert assignments[1].access_id == "test-cal:A001:2"
    assert assignments[1].service_date == date(2027, 6, 1)
    assert assignments[1].week == 22
    assert assignments[1].eclo is True
