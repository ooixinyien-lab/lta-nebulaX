"""Independent-validator coverage for all nine approved constraints."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest

from backend.app.services.cp_sat import solve
from backend.app.services.full_validator import validate_schedule
from scripts.generate_synthetic_dataset import build_feasible_snapshot


PLANNING_DATE = "2026-09-14"


@pytest.fixture(scope="module")
def valid_case() -> tuple[dict, list[dict]]:
    """Return a known-valid snapshot and its canonical strict allocations."""
    snapshot = build_feasible_snapshot()
    result = solve(snapshot, planning_date=PLANNING_DATE, time_limit=5)
    assert result["validation"]["valid"] is True
    return snapshot.to_dict(), result["allocations"]


def _allocation(allocations: list[dict], request_id: str) -> dict:
    """Find one allocation by request identifier."""
    return next(item for item in allocations if item["request_id"] == request_id)


def _constraint_failed(result: dict, number: int) -> bool:
    """Return whether a numbered rule contains at least one issue."""
    constraint = next(
        item for item in result["constraint_results"] if item["number"] == number
    )
    return not constraint["passed"] and bool(constraint["issues"])


def _validate(snapshot: dict, allocations: list[dict], *, mode: str = "strict") -> dict:
    """Call the validator with the common planning date used by this fixture."""
    return validate_schedule(snapshot, allocations, PLANNING_DATE, mode=mode)


def test_valid_complete_export_passes_all_nine_constraints(valid_case) -> None:
    """The independent checker reports one explicit pass per approved rule."""
    snapshot, allocations = valid_case

    result = _validate(snapshot, allocations)

    assert result["valid"] is True
    assert len(result["constraint_results"]) == 9
    assert all(item["passed"] for item in result["constraint_results"])


def test_constraint_1_rejects_incomplete_duration_and_handback(valid_case) -> None:
    """Exported start/end values must reserve all four phases inside the window."""
    snapshot, allocations = deepcopy(valid_case)
    _allocation(allocations, "R03")["end"] = "2026-09-14T04:30:00+08:00"

    assert _constraint_failed(_validate(snapshot, allocations), 1)


def test_constraint_2_rejects_overlapping_protection_footprints(valid_case) -> None:
    """Two jobs cannot hold the same protected sector simultaneously."""
    snapshot, allocations = deepcopy(valid_case)
    r03 = _allocation(allocations, "R03")
    r03["start"] = "2026-09-14T02:35:00+08:00"
    r03["end"] = "2026-09-14T03:25:00+08:00"

    assert _constraint_failed(_validate(snapshot, allocations), 2)


def test_constraint_3_rejects_missing_power_transition(valid_case) -> None:
    """Opposed traction-power states retain their ten-minute transition guard."""
    snapshot, allocations = deepcopy(valid_case)
    request = next(item for item in snapshot["requests"] if item["id"] == "R03")
    request["handover_buffer_minutes"] = 0
    r03 = _allocation(allocations, "R03")
    r03["start"] = "2026-09-14T02:45:00+08:00"
    r03["end"] = "2026-09-14T03:35:00+08:00"

    assert _constraint_failed(_validate(snapshot, allocations), 3)


def test_constraint_4_rejects_an_unqualified_engineer(valid_case) -> None:
    """Role assignments must use eligible people with the named competency."""
    snapshot, allocations = deepcopy(valid_case)
    r02 = _allocation(allocations, "R02")
    r02["engineer_id"] = "E01"
    r02["engineer_assignments"] = {"inspection": ["E01"]}

    assert _constraint_failed(_validate(snapshot, allocations), 4)


def test_constraint_5_rejects_insufficient_directional_travel(valid_case) -> None:
    """A shared engineer needs travel time between consecutive work sectors."""
    snapshot, allocations = deepcopy(valid_case)
    for request_id, role in (("R02", "inspection"), ("R03", "signalling")):
        allocation = _allocation(allocations, request_id)
        allocation["engineer_id"] = "E04"
        allocation["engineer_assignments"] = {role: ["E04"]}

    assert _constraint_failed(_validate(snapshot, allocations), 5)


def test_constraint_6_rejects_a_broken_handover_buffer(valid_case) -> None:
    """A dependent job starts only after predecessor completion plus handover."""
    snapshot, allocations = deepcopy(valid_case)
    r03 = _allocation(allocations, "R03")
    r03["start"] = "2026-09-14T02:50:00+08:00"
    r03["end"] = "2026-09-14T03:40:00+08:00"

    assert _constraint_failed(_validate(snapshot, allocations), 6)


def test_constraint_7_rejects_a_changed_frozen_assignment(valid_case) -> None:
    """A frozen allocation retains its committed resource assignment."""
    snapshot, allocations = deepcopy(valid_case)
    r01 = _allocation(allocations, "R01")
    r01["engineer_id"] = "E02"
    r01["engineer_assignments"] = {"track": ["E02"]}

    assert _constraint_failed(_validate(snapshot, allocations), 7)


def test_constraint_8_rejects_moving_an_exact_request(valid_case) -> None:
    """EXACT timing is hard even though RANGE preferred starts are soft."""
    snapshot, allocations = deepcopy(valid_case)
    request = next(item for item in snapshot["requests"] if item["id"] == "R02")
    request["timing_mode"] = "EXACT"
    request["earliest_start"] = request["preferred_start"]
    request["deadline"] = "2026-09-14T02:50:00+08:00"
    r02 = _allocation(allocations, "R02")
    r02["start"] = "2026-09-14T02:05:00+08:00"
    r02["end"] = "2026-09-14T02:55:00+08:00"

    assert _constraint_failed(_validate(snapshot, allocations), 8)


def test_constraint_9_rejects_a_missing_mandatory_request(valid_case) -> None:
    """A recovery export cannot silently omit service-critical work."""
    snapshot, allocations = deepcopy(valid_case)
    allocations = [item for item in allocations if item["request_id"] != "R09"]

    assert _constraint_failed(_validate(snapshot, allocations, mode="recovery"), 9)


def test_partial_recovery_export_can_be_independently_validated() -> None:
    """Deferral is accepted only for optional work and never relaxes hard rules."""
    snapshot = build_feasible_snapshot().to_dict()
    optional_id = "R03"
    request = next(item for item in snapshot["requests"] if item["id"] == optional_id)
    request["approved"] = False
    request["status"] = "submitted"
    request["existing_start"] = None
    snapshot["committed_allocations"] = [
        item
        for item in snapshot["committed_allocations"]
        if item["request_id"] != optional_id
    ]
    complete = solve(snapshot, planning_date=PLANNING_DATE, time_limit=5)
    allocations = [
        item for item in complete["allocations"] if item["request_id"] != optional_id
    ]

    result = _validate(snapshot, allocations, mode="recovery")

    assert result["valid"] is True


def test_validator_rejects_an_unknown_exported_request(valid_case) -> None:
    """A result-conversion bug cannot introduce an unknown request identifier."""
    snapshot, allocations = deepcopy(valid_case)
    allocations.append(
        {
            "request_id": "UNKNOWN",
            "start": "2026-09-14T01:15:00+08:00",
            "end": "2026-09-14T01:20:00+08:00",
        }
    )

    result = _validate(snapshot, allocations)

    assert result["valid"] is False
    assert any(issue["code"] == "UNKNOWN_REQUEST" for issue in result["issues"])
