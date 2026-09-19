"""Canonical OR-Tools CP-SAT scheduler for the ForRail prototype.

The solver implements the nine approved constraint families in
``constraints_lp_setup.md``. It first attempts a complete strict schedule. A
proven strict infeasibility triggers a separate recovery model that may defer
only eligible work while keeping every safety and operational rule hard.

All data is synthetic. A constraint-valid result is a prototype planning aid,
not approval for live railway operations.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from backend.app.models import PlanningSnapshot
from backend.app.services.full_validator import validate_schedule

try:
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover - only used without optional dependency
    cp_model = None


SGT = ZoneInfo("Asia/Singapore")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DATA_PATH = PROJECT_ROOT / "data" / "comprehensive_synthetic_data.json"
DEFAULT_SOLVE_TIME_SECONDS = 8.0
DETERMINISTIC_RANDOM_SEED = 17
PROTOTYPE_ASSUMPTIONS = [
    "A missing different-sector travel-matrix pair uses planning_rules.different_site_transfer_minutes.",
    "Named equipment IDs are requirements, so the solver never substitutes a different item.",
    "Existing vehicle assignments are preserved; requests contain no field for new vehicle demand.",
]
PROTOTYPE_LIMITATIONS = [
    "One solve covers one explicitly selected engineering night.",
    "Transit routes are fixed reservations rather than routes chosen by the solver.",
    "Synthetic inputs and solver feasibility do not constitute railway operational approval.",
]


class SolverInputError(ValueError):
    """Raised when data cannot safely be converted into a solver model."""


@dataclass
class PreparedProblem:
    """Validated data and indexes shared by strict and recovery models."""

    typed_snapshot: PlanningSnapshot
    snapshot: dict[str, Any]
    planning_date: str
    window: dict[str, Any]
    origin: datetime
    usable_end: datetime
    horizon: int
    requests: list[dict[str, Any]]
    request_map: dict[str, dict[str, Any]]
    sectors: dict[str, dict[str, Any]]
    engineers: dict[str, dict[str, Any]]
    equipment: dict[str, dict[str, Any]]
    pools: dict[str, dict[str, Any]]
    vehicles: dict[str, dict[str, Any]]
    committed: dict[str, dict[str, Any]]


@dataclass
class ModelArtifacts:
    """CP-SAT variables and metadata needed after model construction."""

    problem: PreparedProblem
    model: Any
    mode: str
    presence: dict[str, Any] = field(default_factory=dict)
    starts: dict[str, Any] = field(default_factory=dict)
    ends: dict[str, Any] = field(default_factory=dict)
    intervals: dict[str, Any] = field(default_factory=dict)
    engineer_roles: dict[tuple[str, str, str], Any] = field(default_factory=dict)
    engineer_assigned: dict[tuple[str, str], Any] = field(default_factory=dict)
    movement_flags: dict[str, Any] = field(default_factory=dict)
    movement_minutes: dict[str, Any] = field(default_factory=dict)
    preference_minutes: dict[str, Any] = field(default_factory=dict)
    vehicle_ids: dict[str, list[str]] = field(default_factory=dict)
    fixed_allocations: dict[str, dict[str, Any]] = field(default_factory=dict)
    static_deferral_reasons: dict[str, list[str]] = field(default_factory=dict)
    objective_expressions: dict[str, Any] = field(default_factory=dict)


def _dt(value: str | datetime) -> datetime:
    """Return a timezone-aware Singapore datetime with an actionable error."""
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as exc:
        raise SolverInputError(f"Invalid ISO timestamp {value!r}") from exc
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise SolverInputError(f"Timestamp must include a timezone: {value!r}")
    if parsed.second or parsed.microsecond:
        raise SolverInputError(f"Timestamp must use whole-minute precision: {value!r}")
    return parsed.astimezone(SGT)


def _minutes(value: str | datetime, origin: datetime) -> int:
    """Convert a timestamp to integer minutes from the planning-window start."""
    return int((_dt(value) - origin).total_seconds() // 60)


def _clock(origin: datetime, minute: int) -> str:
    """Convert a solver minute back into an ISO timestamp."""
    return (origin + timedelta(minutes=minute)).isoformat()


def _duration(request: dict[str, Any]) -> int:
    """Return the complete setup/work/test/handback reservation."""
    return sum(phase["duration_minutes"] for phase in request["phases"])


def _travel_minutes(
    problem: PreparedProblem,
    from_sector: str,
    to_sector: str,
) -> int:
    """Return directional travel or the documented synthetic fallback.

    The canonical matrix intentionally contains only relevant benchmark pairs.
    A missing different-site pair therefore uses the configured prototype
    transfer allowance rather than inventing a new operational travel time.
    """
    if from_sector == to_sector:
        return 0
    for entry in problem.snapshot["travel_time_matrix"]["entries"]:
        if (
            entry["from_sector"] == from_sector
            and entry["to_sector"] == to_sector
        ):
            return entry["travel_minutes"]
    return problem.snapshot["planning_rules"]["different_site_transfer_minutes"]


def _power_zones(
    problem: PreparedProblem,
    request: dict[str, Any],
) -> set[str]:
    """Return every traction-power zone touched by a protection footprint."""
    zones = {
        problem.sectors[sector_id]["power_zone"]
        for sector_id in request["protected_sectors"]
    }
    if request.get("power_zone"):
        zones.add(request["power_zone"])
    return zones


def load_dataset(path: str | Path = CANONICAL_DATA_PATH) -> PlanningSnapshot:
    """Load and validate a JSON planning snapshot with controlled errors."""
    source = Path(path)
    try:
        payload = source.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SolverInputError(f"Dataset file does not exist: {source}") from exc
    except OSError as exc:
        raise SolverInputError(f"Dataset file could not be read: {source}: {exc}") from exc

    try:
        return PlanningSnapshot.from_json(payload)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SolverInputError(
            f"Dataset validation failed at {location}: {first['msg']}"
        ) from exc


def prepare_problem(
    snapshot: dict[str, Any] | PlanningSnapshot,
    planning_date: str | None,
) -> PreparedProblem:
    """Validate and index one explicitly selected planning night."""
    try:
        typed = (
            snapshot
            if isinstance(snapshot, PlanningSnapshot)
            else PlanningSnapshot.from_dict(snapshot)
        )
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SolverInputError(
            f"Dataset validation failed at {location}: {first['msg']}"
        ) from exc

    data = typed.to_dict()
    selected_date = planning_date or data["metadata"].get("planning_date")
    if not selected_date:
        raise SolverInputError(
            "Select a planning night explicitly or provide metadata.planning_date"
        )

    matching_windows = [
        window
        for window in data["engineering_windows"]
        if window["date"] == selected_date
    ]
    if len(matching_windows) != 1:
        raise SolverInputError(
            f"Expected exactly one engineering window for {selected_date}; "
            f"found {len(matching_windows)}"
        )
    window = matching_windows[0]
    if window["handback_buffer_minutes"] != 20:
        raise SolverInputError(
            f"Approved prototype handback is 20 minutes, but {selected_date} "
            f"declares {window['handback_buffer_minutes']}"
        )

    origin = _dt(window["start"])
    usable_end = _dt(window["end"]) - timedelta(
        minutes=window["handback_buffer_minutes"]
    )
    horizon = _minutes(usable_end, origin)
    if horizon <= 0:
        raise SolverInputError(
            f"Handback leaves no usable engineering time on {selected_date}"
        )

    rules = data["planning_rules"]
    if rules["start_grid_minutes"] <= 0:
        raise SolverInputError("planning_rules.start_grid_minutes must be positive")
    if rules["morning_buffer_minutes"] != window["handback_buffer_minutes"]:
        raise SolverInputError("Window and planning-rule handback buffers must match")

    requests = [
        request
        for request in data["requests"]
        if request["status"] != "cancelled"
        and selected_date in request["allowed_dates"]
    ]
    request_map = {request["id"]: request for request in requests}
    sectors = {sector["id"]: sector for sector in data["sectors"]}
    engineers = {engineer["id"]: engineer for engineer in data["engineers"]}
    equipment = {item["id"]: item for item in data["equipment"]}
    pools = {pool["id"]: pool for pool in data["resource_pools"]}
    vehicles = {vehicle["id"]: vehicle for vehicle in data.get("vehicles", [])}
    committed = {
        allocation["request_id"]: allocation
        for allocation in data["committed_allocations"]
        if _dt(allocation["start"]).date().isoformat() == selected_date
    }

    catalogue_types = {entry["work_type"] for entry in data.get("job_catalogue", [])}
    for request in requests:
        request_id = request["id"]
        if request.get("work_type") not in catalogue_types:
            raise SolverInputError(
                f"Request {request_id} has no job_catalogue entry for "
                f"work_type {request.get('work_type')!r}"
            )
        for pool_id in request.get("pooled_resources", {}):
            if pool_id not in pools:
                raise SolverInputError(
                    f"Request {request_id} references unknown resource pool {pool_id}"
                )
        if request.get("approved") and request_id not in committed:
            raise SolverInputError(
                f"Approved request {request_id} has no committed allocation"
            )
        if request.get("frozen"):
            allocation = committed.get(request_id)
            if allocation is None or not allocation.get("locked"):
                raise SolverInputError(
                    f"Frozen request {request_id} requires a locked committed allocation"
                )

    used_power_values = {request["power_requirement"] for request in requests}
    compatibility = rules["power_compatibility"]
    for value_a in used_power_values:
        for value_b in used_power_values:
            if value_b not in compatibility.get(value_a, {}):
                raise SolverInputError(
                    f"Missing power compatibility rule for {value_a}/{value_b}"
                )

    return PreparedProblem(
        typed_snapshot=typed,
        snapshot=data,
        planning_date=selected_date,
        window=window,
        origin=origin,
        usable_end=usable_end,
        horizon=horizon,
        requests=requests,
        request_map=request_map,
        sectors=sectors,
        engineers=engineers,
        equipment=equipment,
        pools=pools,
        vehicles=vehicles,
        committed=committed,
    )


def _normalize_locked_allocations(
    problem: PreparedProblem,
    locked_allocations: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Merge frozen/committed locks with optional API-supplied locks."""
    locked = {
        request_id: allocation.copy()
        for request_id, allocation in problem.committed.items()
        if allocation.get("locked")
        or problem.request_map.get(request_id, {}).get("frozen")
    }
    for raw in locked_allocations or []:
        request_id = raw.get("request_id")
        if request_id not in problem.request_map:
            raise SolverInputError(
                f"Locked allocation references unknown request {request_id!r}"
            )
        request = problem.request_map[request_id]
        if "start" not in raw or "engineer_id" not in raw:
            raise SolverInputError(
                f"Locked allocation {request_id} needs start and engineer_id"
            )
        start = _dt(raw["start"])
        duration = _duration(request)
        normalized = {
            "request_id": request_id,
            "start": start.isoformat(),
            "end": raw.get("end", (start + timedelta(minutes=duration)).isoformat()),
            "engineer_id": raw["engineer_id"],
            "engineer_assignments": raw.get("engineer_assignments", {}),
            "equipment_ids": raw.get(
                "equipment_ids", list(request["required_equipment_ids"])
            ),
            "vehicle_ids": raw.get("vehicle_ids", []),
            "locked": True,
            "moved": False,
        }
        if _dt(normalized["end"]) - start != timedelta(minutes=duration):
            raise SolverInputError(
                f"Locked allocation {request_id} duration does not match its phases"
            )
        if start.date().isoformat() != problem.planning_date:
            raise SolverInputError(
                f"Locked allocation {request_id} is not on {problem.planning_date}"
            )
        locked[request_id] = normalized
    return locked


def _add_containment_choice(
    model: Any,
    start: Any,
    end: Any,
    active: Any,
    periods: list[dict[str, Any]],
    problem: PreparedProblem,
    name: str,
) -> None:
    """Require an active interval to fit wholly inside one availability period."""
    choices = []
    for index, period in enumerate(periods):
        choice = model.new_bool_var(f"{name}_availability_{index}")
        model.add(start >= _minutes(period["start"], problem.origin)).only_enforce_if(choice)
        model.add(end <= _minutes(period["end"], problem.origin)).only_enforce_if(choice)
        choices.append(choice)
    if choices:
        model.add(sum(choices) == active)
    else:
        model.add(active == 0)


def _add_avoid_fixed_interval(
    model: Any,
    start: Any,
    end: Any,
    active: Any,
    blocked_start: int,
    blocked_end: int,
    name: str,
) -> None:
    """Place an active job wholly before or after a fixed blocked interval."""
    before = model.new_bool_var(f"{name}_before")
    model.add(end <= blocked_start).only_enforce_if([active, before])
    model.add(start >= blocked_end).only_enforce_if([active, before.Not()])


def _add_separation(
    model: Any,
    start_a: Any,
    end_a: Any,
    present_a: Any,
    start_b: Any,
    end_b: Any,
    present_b: Any,
    gap_a_to_b: int,
    gap_b_to_a: int,
    name: str,
    extra_conditions: list[Any] | None = None,
) -> None:
    """Enforce one of two directional orders when all conditions are true."""
    order = model.new_bool_var(f"{name}_a_before_b")
    conditions = [present_a, present_b, *(extra_conditions or [])]
    model.add(end_a + gap_a_to_b <= start_b).only_enforce_if([*conditions, order])
    model.add(end_b + gap_b_to_a <= start_a).only_enforce_if([*conditions, order.Not()])


def build_model(
    problem: PreparedProblem,
    *,
    mode: str,
    locked_allocations: list[dict[str, Any]] | None = None,
) -> ModelArtifacts:
    """Build either the strict or recovery CP-SAT model."""
    if cp_model is None:
        raise SolverInputError(
            "Google OR-Tools is unavailable; install requirements-cpsat.txt"
        )
    if mode not in {"strict", "recovery"}:
        raise ValueError("Mode must be 'strict' or 'recovery'")

    model = cp_model.CpModel()
    artifacts = ModelArtifacts(problem=problem, model=model, mode=mode)
    artifacts.fixed_allocations = _normalize_locked_allocations(problem, locked_allocations)
    grid = problem.snapshot["planning_rules"]["start_grid_minutes"]
    max_duration = max((_duration(request) for request in problem.requests), default=0)

    # Constraint 1 and 8: allowed start domains and optional job presence.
    for request in problem.requests:
        request_id = request["id"]
        duration = _duration(request)
        earliest = max(0, _minutes(request["earliest_start"], problem.origin))
        latest_finish = min(problem.horizon, _minutes(request["deadline"], problem.origin))
        latest_start = latest_finish - duration
        first_grid_start = earliest + (-earliest % grid)
        allowed_starts = list(range(first_grid_start, latest_start + 1, grid))

        presence = model.new_bool_var(f"scheduled_{request_id}")
        if allowed_starts:
            start = model.new_int_var_from_domain(
                cp_model.Domain.from_values(allowed_starts), f"start_{request_id}"
            )
        else:
            start = model.new_int_var(0, 0, f"start_{request_id}")
            model.add(presence == 0)
            artifacts.static_deferral_reasons.setdefault(request_id, []).append(
                "The complete phase duration cannot fit inside the usable request window."
            )
        end = model.new_int_var(0, problem.horizon + max_duration, f"end_{request_id}")
        model.add(end == start + duration)
        interval = model.new_optional_interval_var(
            start, duration, end, presence, f"interval_{request_id}"
        )

        artifacts.presence[request_id] = presence
        artifacts.starts[request_id] = start
        artifacts.ends[request_id] = end
        artifacts.intervals[request_id] = interval

        must_schedule = (
            mode == "strict"
            or request.get("mandatory", False)
            or not request.get("deferrable", True)
            or request.get("approved", False)
            or request.get("frozen", False)
            or request_id in artifacts.fixed_allocations
        )
        if must_schedule:
            model.add(presence == 1)

    # Constraint 7: fixed starts and approved-but-movable disruption measures.
    for request_id, fixed in artifacts.fixed_allocations.items():
        model.add(artifacts.presence[request_id] == 1)
        model.add(artifacts.starts[request_id] == _minutes(fixed["start"], problem.origin))

    for request in problem.requests:
        request_id = request["id"]
        baseline = problem.committed.get(request_id)
        if request.get("approved") and not request.get("frozen") and baseline:
            existing_start = _minutes(baseline["start"], problem.origin)
            distance = model.new_int_var(0, problem.horizon, f"movement_minutes_{request_id}")
            moved = model.new_bool_var(f"moved_{request_id}")
            model.add_abs_equality(distance, artifacts.starts[request_id] - existing_start)
            model.add(distance == 0).only_enforce_if(moved.Not())
            model.add(distance >= 1).only_enforce_if(moved)
            model.add(distance <= problem.horizon * moved)
            artifacts.movement_flags[request_id] = moved
            artifacts.movement_minutes[request_id] = distance

    # Constraint 2: fixed unavailability and mutually exclusive footprints.
    unavailable_by_sector: dict[str, list[tuple[str, int, int]]] = {
        sector_id: [] for sector_id in problem.sectors
    }
    for blackout in problem.snapshot.get("blackouts", []):
        for sector_id in blackout["sector_ids"]:
            unavailable_by_sector[sector_id].append(
                (
                    blackout["id"],
                    _minutes(blackout["start"], problem.origin),
                    _minutes(blackout["end"], problem.origin),
                )
            )
    for sector_id, sector in problem.sectors.items():
        for index, blocked in enumerate(sector.get("fixed_unavailable_intervals", []), 1):
            unavailable_by_sector[sector_id].append(
                (
                    f"{sector_id}_fixed_{index}",
                    _minutes(blocked["start"], problem.origin),
                    _minutes(blocked["end"], problem.origin),
                )
            )

    for request in problem.requests:
        request_id = request["id"]
        for sector_id in request["protected_sectors"]:
            for block_id, blocked_start, blocked_end in unavailable_by_sector[sector_id]:
                if blocked_end <= 0 or blocked_start >= problem.horizon:
                    continue
                _add_avoid_fixed_interval(
                    model,
                    artifacts.starts[request_id],
                    artifacts.ends[request_id],
                    artifacts.presence[request_id],
                    blocked_start,
                    blocked_end,
                    f"{request_id}_{block_id}",
                )
        for transit_index, transit in enumerate(problem.snapshot.get("transit_schedules", [])):
            if transit["sector_id"] not in request["protected_sectors"]:
                continue
            _add_avoid_fixed_interval(
                model,
                artifacts.starts[request_id],
                artifacts.ends[request_id],
                artifacts.presence[request_id],
                _minutes(transit["start"], problem.origin),
                _minutes(transit["end"], problem.origin),
                f"{request_id}_transit_{transit_index}",
            )

    work_rules = {
        frozenset((rule["work_type_a"], rule["work_type_b"])): rule
        for rule in problem.snapshot["planning_rules"].get("work_compatibility_rules", [])
    }
    for index, request_a in enumerate(problem.requests):
        for request_b in problem.requests[index + 1 :]:
            request_a_id, request_b_id = request_a["id"], request_b["id"]
            gap = 0
            conflict = bool(
                set(request_a["protected_sectors"])
                & set(request_b["protected_sectors"])
            )

            # Constraint 3: opposing traction power and explicit work rules.
            if _power_zones(problem, request_a) & _power_zones(problem, request_b):
                compatible = problem.snapshot["planning_rules"]["power_compatibility"][
                    request_a["power_requirement"]
                ][request_b["power_requirement"]]
                if not compatible:
                    conflict = True
                    gap = max(
                        gap,
                        problem.snapshot["planning_rules"]["opposed_power_transition_minutes"],
                    )
            work_rule = work_rules.get(
                frozenset((request_a.get("work_type"), request_b.get("work_type")))
            )
            if work_rule and not work_rule["compatible"]:
                conflict = True
                gap = max(gap, work_rule["transition_minutes"])

            if conflict:
                _add_separation(
                    model,
                    artifacts.starts[request_a_id],
                    artifacts.ends[request_a_id],
                    artifacts.presence[request_a_id],
                    artifacts.starts[request_b_id],
                    artifacts.ends[request_b_id],
                    artifacts.presence[request_b_id],
                    gap,
                    gap,
                    f"operational_{request_a_id}_{request_b_id}",
                )

    # Constraint 4A: qualified individual specialist engineers.
    engineer_intervals: dict[str, list[Any]] = {
        engineer_id: [] for engineer_id in problem.engineers
    }
    for request in problem.requests:
        request_id = request["id"]
        role_variables_by_engineer: dict[str, list[Any]] = {
            engineer_id: [] for engineer_id in problem.engineers
        }
        for role, count in request["required_engineer_roles"].items():
            role_variables = []
            for engineer_id, engineer in problem.engineers.items():
                if engineer_id not in request["eligible_engineers"] or role not in engineer["skills"]:
                    continue
                assigned_role = model.new_bool_var(f"assign_{request_id}_{role}_{engineer_id}")
                artifacts.engineer_roles[(request_id, role, engineer_id)] = assigned_role
                role_variables.append(assigned_role)
                role_variables_by_engineer[engineer_id].append(assigned_role)
            model.add(sum(role_variables) == count * artifacts.presence[request_id])
            if len(role_variables) < count:
                artifacts.static_deferral_reasons.setdefault(request_id, []).append(
                    f"Fewer than {count} eligible engineer(s) are qualified for role {role}."
                )

        for engineer_id, role_variables in role_variables_by_engineer.items():
            if not role_variables:
                continue
            assigned = model.new_bool_var(f"assigned_{request_id}_{engineer_id}")
            model.add(sum(role_variables) == assigned)
            artifacts.engineer_assigned[(request_id, engineer_id)] = assigned
            assignment_interval = model.new_optional_interval_var(
                artifacts.starts[request_id],
                _duration(request),
                artifacts.ends[request_id],
                assigned,
                f"engineer_interval_{request_id}_{engineer_id}",
            )
            engineer_intervals[engineer_id].append(assignment_interval)
            engineer = problem.engineers[engineer_id]
            _add_containment_choice(
                model,
                artifacts.starts[request_id],
                artifacts.ends[request_id],
                assigned,
                engineer["availability"],
                problem,
                f"{request_id}_{engineer_id}",
            )
            for block_index, blocked in enumerate(engineer.get("unavailable", [])):
                _add_avoid_fixed_interval(
                    model,
                    artifacts.starts[request_id],
                    artifacts.ends[request_id],
                    assigned,
                    _minutes(blocked["start"], problem.origin),
                    _minutes(blocked["end"], problem.origin),
                    f"{request_id}_{engineer_id}_blocked_{block_index}",
                )

    for intervals in engineer_intervals.values():
        if intervals:
            model.add_no_overlap(intervals)

    # Freeze stored specialist assignments when a locked allocation supplies them.
    for request_id, fixed in artifacts.fixed_allocations.items():
        request = problem.request_map[request_id]
        fixed_roles = fixed.get("engineer_assignments") or {}
        if not fixed_roles and fixed.get("engineer_id") and sum(request["required_engineer_roles"].values()) == 1:
            role = next(
                role for role, count in request["required_engineer_roles"].items() if count == 1
            )
            fixed_roles = {role: [fixed["engineer_id"]]}
        for role, engineer_ids in fixed_roles.items():
            for engineer_id in engineer_ids:
                variable = artifacts.engineer_roles.get((request_id, role, engineer_id))
                if variable is None:
                    model.add(artifacts.presence[request_id] == 0)
                else:
                    model.add(variable == 1)

    # Constraint 4B: named equipment and cumulative pooled resources.
    equipment_intervals: dict[str, list[Any]] = {
        equipment_id: [] for equipment_id in problem.equipment
    }
    for request in problem.requests:
        request_id = request["id"]
        for equipment_id in request["required_equipment_ids"]:
            item = problem.equipment[equipment_id]
            equipment_intervals[equipment_id].append(artifacts.intervals[request_id])
            if not item["serviceable"]:
                model.add(artifacts.presence[request_id] == 0)
                artifacts.static_deferral_reasons.setdefault(request_id, []).append(
                    f"Required equipment {equipment_id} is not serviceable."
                )
            _add_containment_choice(
                model,
                artifacts.starts[request_id],
                artifacts.ends[request_id],
                artifacts.presence[request_id],
                item["availability"],
                problem,
                f"{request_id}_{equipment_id}",
            )
            for block_index, blocked in enumerate(item.get("unavailable", [])):
                _add_avoid_fixed_interval(
                    model,
                    artifacts.starts[request_id],
                    artifacts.ends[request_id],
                    artifacts.presence[request_id],
                    _minutes(blocked["start"], problem.origin),
                    _minutes(blocked["end"], problem.origin),
                    f"{request_id}_{equipment_id}_blocked_{block_index}",
                )
    for equipment_id, intervals in equipment_intervals.items():
        if not intervals:
            continue
        capacity = problem.equipment[equipment_id]["capacity"]
        if capacity <= 0:
            raise SolverInputError(f"Equipment {equipment_id} must have positive capacity")
        if capacity == 1:
            model.add_no_overlap(intervals)
        else:
            model.add_cumulative(intervals, [1] * len(intervals), capacity)

    for pool_id, pool in problem.pools.items():
        intervals = []
        demands = []
        for request in problem.requests:
            demand = request.get("pooled_resources", {}).get(pool_id, 0)
            if demand:
                intervals.append(artifacts.intervals[request["id"]])
                demands.append(demand)
        if intervals:
            model.add_cumulative(intervals, demands, pool["capacity"])

    # Constraint 5: directional travel for consecutive named resources.
    for index, request_a in enumerate(problem.requests):
        for request_b in problem.requests[index + 1 :]:
            request_a_id, request_b_id = request_a["id"], request_b["id"]
            travel_a_to_b = _travel_minutes(problem, request_a["work_sector"], request_b["work_sector"])
            travel_b_to_a = _travel_minutes(problem, request_b["work_sector"], request_a["work_sector"])
            for engineer_id in problem.engineers:
                assigned_a = artifacts.engineer_assigned.get((request_a_id, engineer_id))
                assigned_b = artifacts.engineer_assigned.get((request_b_id, engineer_id))
                if assigned_a is None or assigned_b is None:
                    continue
                _add_separation(
                    model,
                    artifacts.starts[request_a_id],
                    artifacts.ends[request_a_id],
                    artifacts.presence[request_a_id],
                    artifacts.starts[request_b_id],
                    artifacts.ends[request_b_id],
                    artifacts.presence[request_b_id],
                    travel_a_to_b,
                    travel_b_to_a,
                    f"engineer_travel_{request_a_id}_{request_b_id}_{engineer_id}",
                    [assigned_a, assigned_b],
                )
            for equipment_id in set(request_a["required_equipment_ids"]) & set(request_b["required_equipment_ids"]):
                _add_separation(
                    model,
                    artifacts.starts[request_a_id],
                    artifacts.ends[request_a_id],
                    artifacts.presence[request_a_id],
                    artifacts.starts[request_b_id],
                    artifacts.ends[request_b_id],
                    artifacts.presence[request_b_id],
                    travel_a_to_b,
                    travel_b_to_a,
                    f"equipment_travel_{request_a_id}_{request_b_id}_{equipment_id}",
                )

    # Existing vehicle allocations are preserved; requests have no vehicle-demand field.
    vehicle_intervals: dict[str, list[Any]] = {
        vehicle_id: [] for vehicle_id in problem.vehicles
    }
    for request in problem.requests:
        request_id = request["id"]
        source = artifacts.fixed_allocations.get(request_id) or problem.committed.get(request_id, {})
        vehicle_ids = list(source.get("vehicle_ids", []))
        artifacts.vehicle_ids[request_id] = vehicle_ids
        for vehicle_id in vehicle_ids:
            if vehicle_id not in problem.vehicles:
                raise SolverInputError(
                    f"Allocation for {request_id} references unknown vehicle {vehicle_id}"
                )
            vehicle_intervals[vehicle_id].append(artifacts.intervals[request_id])
            vehicle = problem.vehicles[vehicle_id]
            _add_containment_choice(
                model,
                artifacts.starts[request_id],
                artifacts.ends[request_id],
                artifacts.presence[request_id],
                vehicle["availability"],
                problem,
                f"{request_id}_{vehicle_id}",
            )
            for transit_index, transit in enumerate(problem.snapshot.get("transit_schedules", [])):
                if transit["vehicle_id"] != vehicle_id:
                    continue
                _add_avoid_fixed_interval(
                    model,
                    artifacts.starts[request_id],
                    artifacts.ends[request_id],
                    artifacts.presence[request_id],
                    _minutes(transit["start"], problem.origin),
                    _minutes(transit["end"], problem.origin),
                    f"{request_id}_{vehicle_id}_transit_{transit_index}",
                )
    for intervals in vehicle_intervals.values():
        if intervals:
            model.add_no_overlap(intervals)
    for index, request_a in enumerate(problem.requests):
        for request_b in problem.requests[index + 1 :]:
            request_a_id, request_b_id = request_a["id"], request_b["id"]
            shared_vehicles = set(artifacts.vehicle_ids[request_a_id]) & set(
                artifacts.vehicle_ids[request_b_id]
            )
            if not shared_vehicles:
                continue
            _add_separation(
                model,
                artifacts.starts[request_a_id],
                artifacts.ends[request_a_id],
                artifacts.presence[request_a_id],
                artifacts.starts[request_b_id],
                artifacts.ends[request_b_id],
                artifacts.presence[request_b_id],
                _travel_minutes(
                    problem, request_a["work_sector"], request_b["work_sector"]
                ),
                _travel_minutes(
                    problem, request_b["work_sector"], request_a["work_sector"]
                ),
                f"vehicle_travel_{request_a_id}_{request_b_id}",
            )

    # Constraint 6: dependencies require presence and buffered precedence.
    for request in problem.requests:
        request_id = request["id"]
        for predecessor_id in request["depends_on"]:
            if predecessor_id not in artifacts.presence:
                model.add(artifacts.presence[request_id] == 0)
                artifacts.static_deferral_reasons.setdefault(request_id, []).append(
                    f"Dependency {predecessor_id} is unavailable on the selected night."
                )
                continue
            model.add(artifacts.presence[request_id] <= artifacts.presence[predecessor_id])
            buffer_minutes = request.get("handover_buffers", {}).get(
                predecessor_id, request["handover_buffer_minutes"]
            )
            model.add(
                artifacts.starts[request_id]
                >= artifacts.ends[predecessor_id] + buffer_minutes
            ).only_enforce_if(artifacts.presence[request_id])

    # Preference and compactness measures are soft objective components only.
    for request in problem.requests:
        request_id = request["id"]
        preferred = request.get("preferred_start")
        if preferred is None:
            continue
        preferred_minute = _minutes(preferred, problem.origin)
        maximum_deviation = max(
            abs(preferred_minute),
            abs(problem.horizon - preferred_minute),
        )
        raw_deviation = model.new_int_var(
            0, maximum_deviation, f"raw_preference_{request_id}"
        )
        contribution = model.new_int_var(
            0, maximum_deviation, f"preference_{request_id}"
        )
        model.add_abs_equality(
            raw_deviation,
            artifacts.starts[request_id] - preferred_minute,
        )
        model.add(contribution == raw_deviation).only_enforce_if(artifacts.presence[request_id])
        model.add(contribution == 0).only_enforce_if(artifacts.presence[request_id].Not())
        artifacts.preference_minutes[request_id] = contribution

    latest_completion = model.new_int_var(0, problem.horizon, "latest_completion")
    for request in problem.requests:
        request_id = request["id"]
        model.add(latest_completion >= artifacts.ends[request_id]).only_enforce_if(
            artifacts.presence[request_id]
        )

    artifacts.objective_expressions = {
        "scheduled_priority": sum(
            request["urgency_score"] * artifacts.presence[request["id"]]
            for request in problem.requests
        ),
        "scheduled_count": sum(artifacts.presence.values()),
        "moved_count": sum(artifacts.movement_flags.values()),
        "movement_minutes": sum(artifacts.movement_minutes.values()),
        "preference_deviation_minutes": sum(artifacts.preference_minutes.values()),
        "latest_completion_minute": latest_completion,
    }
    return artifacts


def _configure_solver(time_limit: float) -> Any:
    """Create a bounded, repeatable single-worker CP-SAT search."""
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.01, time_limit)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = DETERMINISTIC_RANDOM_SEED
    return solver


def _expression_value(solver: Any, expression: Any) -> int:
    """Read an integer expression, including the empty-sum integer zero."""
    return expression if isinstance(expression, int) else int(solver.value(expression))


def _optimality_gap(value: float, bound: float) -> float:
    """Return a non-negative relative gap between incumbent and best bound."""
    return abs(value - bound) / max(1.0, abs(value))


def _run_lexicographic(artifacts: ModelArtifacts, time_limit: float) -> dict[str, Any]:
    """Optimize one priority at a time and preserve every proven optimum."""
    if artifacts.mode == "strict":
        stages = [
            ("moved_count", "min"),
            ("movement_minutes", "min"),
            ("preference_deviation_minutes", "min"),
            ("latest_completion_minute", "min"),
        ]
    else:
        stages = [
            ("scheduled_priority", "max"),
            ("scheduled_count", "max"),
            ("moved_count", "min"),
            ("movement_minutes", "min"),
            ("preference_deviation_minutes", "min"),
            ("latest_completion_minute", "min"),
        ]

    validation_error = artifacts.model.validate()
    if validation_error:
        return {
            "status": "MODEL_INVALID",
            "message": validation_error,
            "solver": None,
            "stage_results": [],
            "elapsed_seconds": 0.0,
        }

    started = monotonic()
    deadline = started + time_limit
    last_solver = None
    stage_results = []

    for stage_name, direction in stages:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {
                "status": "FEASIBLE" if last_solver is not None else "UNKNOWN",
                "message": f"Time limit reached before completing stage {stage_name}",
                "solver": last_solver,
                "stage_results": stage_results,
                "elapsed_seconds": monotonic() - started,
            }

        expression = artifacts.objective_expressions[stage_name]
        artifacts.model.clear_objective()
        if direction == "min":
            artifacts.model.minimize(expression)
        else:
            artifacts.model.maximize(expression)

        solver = _configure_solver(remaining)
        stage_started = monotonic()
        status_code = solver.solve(artifacts.model)
        status = solver.status_name(status_code)
        stage_elapsed = monotonic() - stage_started

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            value = _expression_value(solver, expression)
            bound = float(solver.best_objective_bound)
            stage_results.append(
                {
                    "name": stage_name,
                    "direction": direction,
                    "status": status,
                    "value": value,
                    "best_bound": bound,
                    "optimality_gap": _optimality_gap(float(value), bound),
                    "elapsed_seconds": round(stage_elapsed, 6),
                }
            )
            last_solver = solver
            if status_code == cp_model.FEASIBLE:
                return {
                    "status": "FEASIBLE",
                    "message": f"A valid incumbent was found at stage {stage_name}; optimality was not proven",
                    "solver": solver,
                    "stage_results": stage_results,
                    "elapsed_seconds": monotonic() - started,
                }
            artifacts.model.add(expression == value)
            continue

        if status_code == cp_model.UNKNOWN and last_solver is not None:
            return {
                "status": "FEASIBLE",
                "message": f"Stage {stage_name} was incomplete; returning the last proven valid incumbent",
                "solver": last_solver,
                "stage_results": stage_results,
                "elapsed_seconds": monotonic() - started,
            }
        return {
            "status": status,
            "message": (
                "No schedule satisfies the hard constraints"
                if status_code == cp_model.INFEASIBLE
                else "The solver stopped without a schedule or proof"
            ),
            "solver": None,
            "stage_results": stage_results,
            "elapsed_seconds": monotonic() - started,
        }

    return {
        "status": "OPTIMAL",
        "message": "Every lexicographic objective stage was proven optimal",
        "solver": last_solver,
        "stage_results": stage_results,
        "elapsed_seconds": monotonic() - started,
    }


def _extract_solution(
    artifacts: ModelArtifacts, solver: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert a valid CP-SAT incumbent into stable integration records."""
    allocations = []
    details = []
    for request in artifacts.problem.requests:
        request_id = request["id"]
        if solver.value(artifacts.presence[request_id]) != 1:
            continue
        start_minute = solver.value(artifacts.starts[request_id])
        end_minute = solver.value(artifacts.ends[request_id])
        role_assignments: dict[str, list[str]] = {}
        for role in sorted(request["required_engineer_roles"]):
            role_assignments[role] = [
                engineer_id
                for engineer_id in sorted(artifacts.problem.engineers)
                if (request_id, role, engineer_id) in artifacts.engineer_roles
                and solver.value(artifacts.engineer_roles[(request_id, role, engineer_id)]) == 1
            ]
        flattened_engineers = [
            engineer_id
            for role in sorted(role_assignments)
            for engineer_id in role_assignments[role]
        ]
        fixed = artifacts.fixed_allocations.get(request_id)
        moved = bool(
            request_id in artifacts.movement_flags
            and solver.value(artifacts.movement_flags[request_id])
        )
        allocation = {
            "request_id": request_id,
            "start": _clock(artifacts.problem.origin, start_minute),
            "end": _clock(artifacts.problem.origin, end_minute),
            "engineer_id": flattened_engineers[0] if flattened_engineers else None,
            "engineer_assignments": role_assignments,
            "equipment_ids": list(request["required_equipment_ids"]),
            "vehicle_ids": list(artifacts.vehicle_ids.get(request_id, [])),
            "locked": fixed is not None,
            "moved": moved,
        }
        allocations.append(allocation)
        preferred = request.get("preferred_start")
        preferred_deviation = None
        if preferred is not None:
            preferred_deviation = abs(
                start_minute - _minutes(preferred, artifacts.problem.origin)
            )
        details.append(
            {
                **allocation,
                "planning_date": artifacts.problem.planning_date,
                "title": request["title"],
                "duration_minutes": _duration(request),
                "phases": list(request["phases"]),
                "work_sector": request["work_sector"],
                "protected_sectors": list(request["protected_sectors"]),
                "power_zone": request.get("power_zone"),
                "power_requirement": request["power_requirement"],
                "pooled_resources": dict(request.get("pooled_resources", {})),
                "preferred_deviation_minutes": preferred_deviation,
            }
        )
    allocations.sort(key=lambda item: (item["start"], item["request_id"]))
    details.sort(key=lambda item: (item["start"], item["request_id"]))
    return allocations, details


def _objective_values(artifacts: ModelArtifacts, solver: Any) -> dict[str, int]:
    """Return every objective component separately for explainability."""
    return {
        name: _expression_value(solver, expression)
        for name, expression in artifacts.objective_expressions.items()
    }


def _deferred_requests(
    artifacts: ModelArtifacts, allocations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Explain proven static exclusions and avoid fabricating global causes."""
    scheduled = {allocation["request_id"] for allocation in allocations}
    deferred = []
    for request in artifacts.problem.requests:
        if request["id"] in scheduled:
            continue
        static_reasons = artifacts.static_deferral_reasons.get(request["id"], [])
        deferred.append(
            {
                "request_id": request["id"],
                "urgency_score": request["urgency_score"],
                "reason": (
                    " ".join(static_reasons)
                    if static_reasons
                    else "Excluded by the global hard-constraint combination; no single cause was proven."
                ),
            }
        )
    return deferred


def _mandatory_blockers(problem: PreparedProblem) -> list[dict[str, str]]:
    """List forced requests when recovery is infeasible without inventing a culprit.

    CP-SAT proves that the forced set and other hard constraints cannot coexist,
    but that proof does not necessarily identify one request as the sole cause.
    """
    blockers = []
    for request in problem.requests:
        request_id = request["id"]
        forced_reasons = []
        if request.get("mandatory"):
            forced_reasons.append("mandatory")
        if not request.get("deferrable", True):
            forced_reasons.append("non-deferrable")
        if request.get("approved"):
            forced_reasons.append("approved")
        if request.get("frozen") or problem.committed.get(request_id, {}).get("locked"):
            forced_reasons.append("locked/frozen")
        if forced_reasons:
            blockers.append(
                {
                    "request_id": request_id,
                    "reason": (
                        f"Forced by {', '.join(forced_reasons)} status; recovery infeasibility "
                        "was proven for the combined hard constraints, not this request alone."
                    ),
                }
            )
    return blockers


def _solve_mode(
    problem: PreparedProblem,
    mode: str,
    time_limit: float,
    locked_allocations: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build, optimize, extract and independently validate one solve mode."""
    artifacts = build_model(
        problem, mode=mode, locked_allocations=locked_allocations
    )
    outcome = _run_lexicographic(artifacts, time_limit)
    result = {
        "mode": mode,
        "status": outcome["status"],
        "message": outcome["message"],
        "elapsed_seconds": round(outcome["elapsed_seconds"], 6),
        "stage_results": outcome["stage_results"],
        "allocations": [],
        "schedule_details": [],
        "objective_components": {},
        "validation": None,
        "deferred_requests": [],
    }
    solver = outcome["solver"]
    if solver is None:
        return result

    allocations, details = _extract_solution(artifacts, solver)
    validation = validate_schedule(
        problem.typed_snapshot,
        allocations,
        problem.planning_date,
        mode=mode,
        locked_allocations=list(artifacts.fixed_allocations.values()),
    )
    result.update(
        allocations=allocations,
        schedule_details=details,
        objective_components=_objective_values(artifacts, solver),
        validation=validation,
        deferred_requests=(
            _deferred_requests(artifacts, allocations) if mode == "recovery" else []
        ),
    )
    if not validation["valid"]:
        result["status"] = "VALIDATION_FAILED"
        result["message"] = "The independent validator rejected the exported schedule"
        result["allocations"] = []
        result["schedule_details"] = []
    return result


def solve(
    snapshot: dict[str, Any] | PlanningSnapshot,
    time_limit: float = DEFAULT_SOLVE_TIME_SECONDS,
    locked_allocations: list[dict[str, Any]] | None = None,
    planning_date: str | None = None,
) -> dict[str, Any]:
    """Run strict mode and recovery only after proven strict infeasibility."""
    if cp_model is None:
        return {
            "status": "UNAVAILABLE",
            "engine": "cp_sat",
            "solver_version": "full",
            "allocations": [],
            "message": "Install requirements-cpsat.txt to enable Google OR-Tools.",
            "elapsed_seconds": 0.0,
        }
    if not isinstance(time_limit, (int, float)) or not 0.1 <= time_limit <= 60:
        return {
            "status": "INPUT_ERROR",
            "engine": "cp_sat",
            "solver_version": "full",
            "allocations": [],
            "message": "time_limit must be between 0.1 and 60 seconds per mode",
            "elapsed_seconds": 0.0,
        }

    try:
        problem = prepare_problem(snapshot, planning_date)
        strict = _solve_mode(problem, "strict", float(time_limit), locked_allocations)
    except (SolverInputError, KeyError, TypeError) as exc:
        return {
            "status": "INPUT_ERROR",
            "engine": "cp_sat",
            "solver_version": "full",
            "allocations": [],
            "message": str(exc),
            "elapsed_seconds": 0.0,
        }

    result = {
        "engine": "cp_sat",
        "solver_version": "full",
        "planning_date": problem.planning_date,
        "synthetic": problem.snapshot["metadata"]["synthetic"],
        "operational_warning": (
            "Synthetic prototype only; this schedule is not approved for live railway operations."
        ),
        "prototype_assumptions": PROTOTYPE_ASSUMPTIONS,
        "prototype_limitations": PROTOTYPE_LIMITATIONS,
        "strict_status": strict["status"],
        "recovery_status": None,
        "recovery_partial": False,
        "mandatory_blockers": [],
        "strict": strict,
        "recovery": None,
    }

    if strict["status"] in {"OPTIMAL", "FEASIBLE"}:
        result.update(
            status=strict["status"],
            mode="strict",
            allocations=strict["allocations"],
            schedule_details=strict["schedule_details"],
            objective_components=strict["objective_components"],
            validation=strict["validation"],
            deferred_requests=[],
            elapsed_seconds=strict["elapsed_seconds"],
            message=(
                "Complete schedule proven optimal under the documented strict objective hierarchy."
                if strict["status"] == "OPTIMAL"
                else "Complete constraint-valid schedule found; optimality was not proven."
            ),
        )
        return result

    if strict["status"] != "INFEASIBLE":
        result.update(
            status=strict["status"],
            mode="strict",
            allocations=[],
            schedule_details=[],
            objective_components={},
            validation=strict["validation"],
            deferred_requests=[],
            elapsed_seconds=strict["elapsed_seconds"],
            message=strict["message"],
        )
        return result

    try:
        recovery = _solve_mode(problem, "recovery", float(time_limit), locked_allocations)
    except (SolverInputError, KeyError, TypeError) as exc:
        recovery = {
            "mode": "recovery",
            "status": "INPUT_ERROR",
            "message": str(exc),
            "elapsed_seconds": 0.0,
            "allocations": [],
            "schedule_details": [],
            "objective_components": {},
            "validation": None,
            "deferred_requests": [],
            "stage_results": [],
        }
    result["recovery"] = recovery
    result["recovery_status"] = recovery["status"]
    result.update(
        status=recovery["status"],
        mode="recovery",
        allocations=recovery["allocations"],
        schedule_details=recovery["schedule_details"],
        objective_components=recovery["objective_components"],
        validation=recovery["validation"],
        deferred_requests=recovery["deferred_requests"],
        recovery_partial=recovery["status"] in {"OPTIMAL", "FEASIBLE"},
        mandatory_blockers=(
            _mandatory_blockers(problem)
            if recovery["status"] == "INFEASIBLE"
            else []
        ),
        elapsed_seconds=round(strict["elapsed_seconds"] + recovery["elapsed_seconds"], 6),
        message=(
            "Strict scheduling was proven infeasible. This is the best valid partial schedule under the recovery objective hierarchy."
            if recovery["status"] == "OPTIMAL"
            else recovery["message"]
        ),
    )
    return result


def print_result(result: dict[str, Any]) -> None:
    """Print a concise human-readable explanation of a structured result."""
    print("ForRail canonical CP-SAT scheduler")
    print(result.get("operational_warning", "Synthetic prototype data only."))
    print(f"Planning date: {result.get('planning_date', 'unavailable')}")
    print(f"Strict status: {result.get('strict_status', result.get('status'))}")
    if result.get("recovery_status") is not None:
        print(f"Recovery status: {result['recovery_status']}")
    print(f"Returned mode: {result.get('mode', 'none')}")
    print(f"Result status: {result['status']}")
    print(f"Message: {result.get('message', '')}")
    print(f"Solve time: {result.get('elapsed_seconds', 0):.6f}s")
    validation = result.get("validation")
    if validation is not None:
        print(f"Independent validation: {'PASSED' if validation['valid'] else 'FAILED'}")

    if result.get("objective_components"):
        print("\nObjective components")
        for name, value in result["objective_components"].items():
            print(f"  {name}: {value}")

    selected_mode = result.get(result.get("mode", ""))
    if selected_mode and selected_mode.get("stage_results"):
        print("\nLexicographic objective stages")
        for stage in selected_mode["stage_results"]:
            print(
                f"  {stage['name']} ({stage['direction']}): status={stage['status']}, "
                f"value={stage['value']}, best_bound={stage['best_bound']}, "
                f"gap={stage['optimality_gap']:.6f}"
            )

    if result.get("schedule_details"):
        print("\nScheduled requests")
        for item in result["schedule_details"]:
            assignments = ", ".join(
                f"{role}={','.join(engineers)}"
                for role, engineers in item["engineer_assignments"].items()
            )
            print(
                f"  {item['request_id']}: {item['start']} -> {item['end']} "
                f"({item['duration_minutes']}m), sector={item['work_sector']}, "
                f"engineers=[{assignments}], equipment={item['equipment_ids']}, "
                f"pools={item['pooled_resources']}, power={item['power_requirement']}, "
                f"locked={item['locked']}, moved={item['moved']}, "
                f"preference_deviation={item['preferred_deviation_minutes']}"
            )

    if result.get("deferred_requests"):
        print("\nDeferred requests (recovery mode is partial)")
        for item in result["deferred_requests"]:
            print(f"  {item['request_id']}: {item['reason']}")

    if result.get("mandatory_blockers"):
        print("\nForced requests in the infeasible recovery model")
        for item in result["mandatory_blockers"]:
            print(f"  {item['request_id']}: {item['reason']}")

    if result.get("prototype_assumptions"):
        print("\nPrototype assumptions")
        for assumption in result["prototype_assumptions"]:
            print(f"  - {assumption}")

    if result.get("prototype_limitations"):
        print("\nLimitations")
        for limitation in result["prototype_limitations"]:
            print(f"  - {limitation}")


def main() -> int:
    """Run the canonical dataset from the command line."""
    parser = argparse.ArgumentParser(
        description="Run the canonical ForRail CP-SAT railway-work scheduler."
    )
    parser.add_argument(
        "--data", type=Path, default=CANONICAL_DATA_PATH, help="PlanningSnapshot JSON path"
    )
    parser.add_argument(
        "--planning-date", required=True, help="Engineering night in YYYY-MM-DD form"
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=DEFAULT_SOLVE_TIME_SECONDS,
        help="Maximum seconds for each strict or recovery mode",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured result as JSON instead of formatted text",
    )
    args = parser.parse_args()

    try:
        snapshot = load_dataset(args.data)
    except SolverInputError as exc:
        result = {
            "status": "INPUT_ERROR",
            "engine": "cp_sat",
            "allocations": [],
            "message": str(exc),
        }
    else:
        result = solve(
            snapshot,
            time_limit=args.time_limit,
            planning_date=args.planning_date,
        )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_result(result)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
