"""End-to-end tests for the canonical full CP-SAT scheduler.

The focused generator scenarios keep failures understandable: each one makes a
small number of scheduling rules decisive, while the comprehensive snapshot is
reserved for the final integration check.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest

from backend.app.services import cp_sat
from backend.app.services.cp_sat import (
    CANONICAL_DATA_PATH,
    load_dataset,
    print_result,
    solve,
)
from scripts.generate_synthetic_dataset import (
    build_compound_conflict_scenario,
    build_feasible_snapshot,
    build_infeasible_deadlock_scenario,
    build_lexicographic_tradeoff_scenario,
    build_trivial_fastpath_scenario,
)


PLANNING_DATE = "2026-09-14"


def _solve(snapshot, *, seconds: float = 5.0) -> dict:
    """Solve one typed scenario on its explicitly declared planning night."""
    return solve(
        snapshot,
        planning_date=snapshot.metadata.planning_date,
        time_limit=seconds,
    )


def _make_exact_capacity_tradeoff(*, equal_priority: bool = False):
    """Make eight jobs compete for two available engineers in one exact slot."""
    data = build_lexicographic_tradeoff_scenario("load").to_dict()
    for request in data["requests"]:
        start = request["preferred_start"]
        duration = sum(phase["duration_minutes"] for phase in request["phases"])
        request["timing_mode"] = "EXACT"
        request["earliest_start"] = start
        request["deadline"] = (
            cp_sat._dt(start) + timedelta(minutes=duration)
        ).isoformat()
        if equal_priority:
            request["urgency_score"] = 3
    return cp_sat.PlanningSnapshot.from_dict(data)


def test_loads_the_comprehensive_dataset() -> None:
    """The canonical path must resolve to the typed comprehensive snapshot."""
    snapshot = load_dataset()

    assert CANONICAL_DATA_PATH.name == "comprehensive_synthetic_data.json"
    assert snapshot.metadata.synthetic is True
    assert len(snapshot.requests) == 12


def test_feasible_complete_schedule_has_known_optimal_objective() -> None:
    """A small complete case proves all strict objective levels exactly."""
    result = _solve(build_feasible_snapshot())

    assert result["status"] == "OPTIMAL"
    assert result["mode"] == "strict"
    assert result["validation"]["valid"] is True
    assert len(result["allocations"]) == 4
    assert result["objective_components"] == {
        "scheduled_priority": 15,
        "scheduled_count": 4,
        "moved_count": 0,
        "movement_minutes": 0,
        "preference_deviation_minutes": 0,
        "latest_completion_minute": 150,
    }


def test_comprehensive_dataset_uses_recovery_only_after_strict_infeasibility() -> None:
    """The ground-truth night returns an independently valid partial schedule."""
    result = solve(load_dataset(), planning_date=PLANNING_DATE, time_limit=8)
    scheduled = {item["request_id"] for item in result["allocations"]}
    deferred = {item["request_id"] for item in result["deferred_requests"]}

    assert result["strict_status"] == "INFEASIBLE"
    assert result["recovery_status"] == "OPTIMAL"
    assert result["mode"] == "recovery"
    assert result["validation"]["valid"] is True
    assert "R09" in scheduled
    assert scheduled | deferred == {
        request.id
        for request in load_dataset().requests
        if PLANNING_DATE in request.allowed_dates and request.status.value != "cancelled"
    }
    assert "R05" in deferred


def test_planning_night_is_selected_explicitly_and_filters_allowed_dates() -> None:
    """Passing the second date selects its window rather than the first one."""
    result = solve(load_dataset(), planning_date="2026-09-15", time_limit=5)

    assert result["planning_date"] == "2026-09-15"
    assert all(item["planning_date"] == "2026-09-15" for item in result["schedule_details"])
    assert {item["request_id"] for item in result["allocations"]} == {"R12"}


@pytest.mark.parametrize("deadlock", ["frozen", "manpower", "blackout"])
def test_mandatory_deadlocks_remain_infeasible_in_recovery(deadlock: str) -> None:
    """Recovery never relaxes locks, resource capacity, blackouts or mandatory work."""
    result = _solve(build_infeasible_deadlock_scenario(deadlock))

    assert result["strict_status"] == "INFEASIBLE"
    assert result["recovery_status"] == "INFEASIBLE"
    assert result["allocations"] == []
    assert result["validation"] is None
    assert result["mandatory_blockers"]
    assert all("not this request alone" in item["reason"] for item in result["mandatory_blockers"])


def test_nexus_enforces_dependency_power_transition_and_directional_travel() -> None:
    """All three guards independently imply the known 02:55 earliest start."""
    result = _solve(build_compound_conflict_scenario("nexus"))
    allocation = next(item for item in result["allocations"] if item["request_id"] == "R03")

    assert result["status"] == "OPTIMAL"
    assert allocation["start"] == "2026-09-14T02:55:00+08:00"
    assert allocation["engineer_id"] == "E04"


def test_vehicle_transit_moves_an_unlocked_existing_allocation() -> None:
    """An existing vehicle booking moves past transit instead of overlapping it."""
    result = _solve(build_compound_conflict_scenario("vehicle_corridor"))
    allocation = result["allocations"][0]

    assert result["validation"]["valid"] is True
    assert allocation["start"] == "2026-09-14T01:45:00+08:00"
    assert allocation["moved"] is True
    assert result["objective_components"]["movement_minutes"] == 15


def test_shared_vehicle_has_directional_travel_between_jobs() -> None:
    """NoOverlap alone is insufficient when one vehicle changes sectors."""
    data = build_feasible_snapshot().to_dict()
    for allocation in data["committed_allocations"]:
        if allocation["request_id"] in {"R02", "R03"}:
            allocation["vehicle_ids"] = ["V01"]
    snapshot = cp_sat.PlanningSnapshot.from_dict(data)

    result = _solve(snapshot)
    allocations = {
        item["request_id"]: item for item in result["allocations"]
    }
    r02_end = cp_sat._dt(allocations["R02"]["end"])
    r03_start = cp_sat._dt(allocations["R03"]["start"])

    assert result["validation"]["valid"] is True
    assert (r03_start - r02_end).total_seconds() // 60 >= 25


def test_impossible_optional_work_is_deferred_without_shortening_it() -> None:
    """A 240-minute job cannot be squeezed into the 190-minute usable window."""
    result = _solve(build_trivial_fastpath_scenario("domain_impossible"))

    assert result["strict_status"] == "INFEASIBLE"
    assert result["recovery_status"] == "OPTIMAL"
    assert result["allocations"] == []
    assert result["deferred_requests"][0]["request_id"] == "REQ_IMPOSSIBLE"
    assert "complete phase duration" in result["deferred_requests"][0]["reason"]


def test_null_preferences_add_no_penalty_and_compact_the_schedule() -> None:
    """ANY_TIME jobs use the final tie-breaker without inventing preferences."""
    result = _solve(build_lexicographic_tradeoff_scenario("handback"))

    assert result["objective_components"]["preference_deviation_minutes"] == 0
    assert result["objective_components"]["latest_completion_minute"] == 40
    assert all(
        item["preferred_deviation_minutes"] is None
        for item in result["schedule_details"]
    )


def test_preference_on_an_earlier_allowed_night_remains_a_soft_penalty() -> None:
    """A large cross-night deviation must not make an otherwise valid job infeasible."""
    data = build_trivial_fastpath_scenario("orthogonal").to_dict()
    for request in data["requests"]:
        request["allowed_dates"].append("2026-09-15")
        request["deadline"] = "2026-09-15T04:25:00+08:00"
    snapshot = cp_sat.PlanningSnapshot.from_dict(data)

    result = solve(snapshot, planning_date="2026-09-15", time_limit=5)

    assert result["status"] == "OPTIMAL"
    assert result["validation"]["valid"] is True
    assert result["objective_components"]["preference_deviation_minutes"] > 190


def test_recovery_selects_the_highest_documented_priority_subset() -> None:
    """Urgency is maximised before recovery considers request count."""
    result = _solve(_make_exact_capacity_tradeoff())
    scheduled = {item["request_id"] for item in result["allocations"]}

    assert result["strict_status"] == "INFEASIBLE"
    assert result["recovery_status"] == "OPTIMAL"
    # E07 is unavailable until 02:30, leaving E01 and E02 for this exact slot.
    assert result["objective_components"]["scheduled_count"] == 2
    assert result["objective_components"]["scheduled_priority"] == 10
    assert "REQ_LOAD_1" in scheduled  # mandatory and urgency 5
    assert "REQ_LOAD_2" in scheduled  # highest-priority deferrable job


def test_equal_default_priorities_fall_back_to_maximum_request_count() -> None:
    """Equal urgency values make the second recovery objective decisive."""
    snapshot = _make_exact_capacity_tradeoff(equal_priority=True)
    for request in snapshot.requests:
        request.mandatory = False
        request.deferrable = True
    result = _solve(snapshot)

    assert result["strict_status"] == "INFEASIBLE"
    assert result["objective_components"]["scheduled_count"] == 2
    assert result["objective_components"]["scheduled_priority"] == 6


def test_solver_output_is_deterministic_for_the_reference_case() -> None:
    """One worker and a fixed seed produce stable demonstration output."""
    snapshot = build_feasible_snapshot()

    first = _solve(snapshot)
    second = _solve(snapshot)

    assert first["allocations"] == second["allocations"]
    assert first["objective_components"] == second["objective_components"]


def test_console_output_reports_each_stage_bound_and_gap(capsys) -> None:
    """Developers can distinguish a proven optimum from an incomplete stage."""
    result = _solve(build_feasible_snapshot())

    print_result(result)
    output = capsys.readouterr().out

    assert "Lexicographic objective stages" in output
    assert "best_bound=" in output
    assert "gap=" in output
    assert "not approved for live railway operations" in output


def test_invalid_cross_reference_returns_an_actionable_input_error() -> None:
    """Typed input validation identifies the request field that is invalid."""
    data = build_feasible_snapshot().to_dict()
    data["requests"][0]["eligible_engineers"] = ["E_DOES_NOT_EXIST"]

    result = solve(data, planning_date=PLANNING_DATE)

    assert result["status"] == "INPUT_ERROR"
    assert "unknown eligible engineer" in result["message"].lower()


def test_missing_required_data_returns_an_input_error() -> None:
    """Missing collections are rejected instead of causing an opaque traceback."""
    data = build_feasible_snapshot().to_dict()
    del data["engineering_windows"]

    result = solve(data, planning_date=PLANNING_DATE)

    assert result["status"] == "INPUT_ERROR"
    assert "engineering_windows" in result["message"]


def test_unknown_strict_outcome_does_not_start_recovery(monkeypatch) -> None:
    """UNKNOWN is inconclusive, so it must never be treated as infeasibility."""
    outcome = {
        "mode": "strict",
        "status": "UNKNOWN",
        "message": "The solver stopped without a schedule or proof",
        "elapsed_seconds": 0.1,
        "stage_results": [],
        "allocations": [],
        "schedule_details": [],
        "objective_components": {},
        "validation": None,
        "deferred_requests": [],
    }
    monkeypatch.setattr(cp_sat, "_solve_mode", lambda *args, **kwargs: deepcopy(outcome))

    result = solve(build_feasible_snapshot(), planning_date=PLANNING_DATE)

    assert result["status"] == "UNKNOWN"
    assert result["recovery"] is None
    assert result["allocations"] == []


def test_feasible_incumbent_is_not_described_as_proven_optimal(monkeypatch) -> None:
    """FEASIBLE has valid variable values but an incomplete optimality proof."""
    baseline = _solve(build_feasible_snapshot())["strict"]
    incomplete = deepcopy(baseline)
    incomplete["status"] = "FEASIBLE"
    incomplete["message"] = "A valid incumbent was found; optimality was not proven"
    monkeypatch.setattr(
        cp_sat,
        "_solve_mode",
        lambda *args, **kwargs: deepcopy(incomplete),
    )

    result = solve(build_feasible_snapshot(), planning_date=PLANNING_DATE)

    assert result["status"] == "FEASIBLE"
    assert result["validation"]["valid"] is True
    assert result["recovery"] is None
    assert "not proven" in result["message"].lower()
