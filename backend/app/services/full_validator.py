"""Independent validation for canonical CP-SAT schedule results.

The validator deliberately does not import or inspect the solver model. It
recalculates the approved rules from the input snapshot and exported
allocations so a modelling or result-conversion error cannot be hidden by a
successful CP-SAT status.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import combinations
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.models import PlanningSnapshot


SGT = ZoneInfo("Asia/Singapore")

CONSTRAINT_NAMES = {
    1: "Engineering Window & Handback",
    2: "Sector Availability & Safety Footprint",
    3: "Work & Traction-Power Compatibility",
    4: "Resource Requirements, Qualification & Capacity",
    5: "Resource Transfer / Travel Time",
    6: "Dependencies & Required Sequence",
    7: "Booking Commitment & Freeze Horizon",
    8: "Request Timing Flexibility & Deferral Eligibility",
    9: "Service-Critical / Mandatory Work",
}


def _dt(value: str | datetime) -> datetime:
    """Return a timezone-aware Singapore datetime."""
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError(f"Expected a timezone-aware timestamp, got {value!r}")
    return parsed.astimezone(SGT)


def _overlap(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    """Return True only when two half-open intervals overlap."""
    return start_a < end_b and start_b < end_a


def _duration(request: dict[str, Any]) -> int:
    """Return the complete reserved setup/work/test/handback duration."""
    return sum(phase["duration_minutes"] for phase in request["phases"])


def _engineer_assignments(
    request: dict[str, Any],
    allocation: dict[str, Any],
) -> dict[str, list[str]]:
    """Normalize the exported role assignments for independent checking."""
    assignments = allocation.get("engineer_assignments") or {}
    if assignments:
        return {
            role: list(engineer_ids)
            for role, engineer_ids in assignments.items()
        }

    # The integration API historically exported one engineer_id. It remains
    # unambiguous when the request requires exactly one specialist role-slot.
    roles = request.get("required_engineer_roles", {})
    if allocation.get("engineer_id") and sum(roles.values()) == 1:
        role = next(role for role, count in roles.items() if count == 1)
        return {role: [allocation["engineer_id"]]}
    return {}


def _allocation_field(allocation: dict[str, Any], field: str) -> Any:
    """Normalize optional allocation lists before commitment comparison."""
    if field in {"equipment_ids", "vehicle_ids"}:
        return allocation.get(field, [])
    return allocation.get(field)


def _travel_minutes(
    snapshot: dict[str, Any],
    from_sector: str,
    to_sector: str,
) -> int:
    """Look up directional travel, using the documented prototype fallback."""
    if from_sector == to_sector:
        return 0
    for entry in snapshot.get("travel_time_matrix", {}).get("entries", []):
        if (
            entry["from_sector"] == from_sector
            and entry["to_sector"] == to_sector
        ):
            return entry["travel_minutes"]
    return snapshot["planning_rules"]["different_site_transfer_minutes"]


def _power_zones(
    request: dict[str, Any],
    sectors: dict[str, dict[str, Any]],
) -> set[str]:
    """Return every power zone touched by the request footprint."""
    zones = {sectors[sid]["power_zone"] for sid in request["protected_sectors"]}
    if request.get("power_zone"):
        zones.add(request["power_zone"])
    return zones


def validate_schedule(
    snapshot: dict[str, Any] | PlanningSnapshot,
    allocations: list[dict[str, Any]],
    planning_date: str,
    *,
    mode: str,
    locked_allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate an exported strict or recovery schedule against all nine rules.

    ``mode`` must be ``strict`` or ``recovery``. Strict validation requires
    every request selected for the night. Recovery validation permits only
    documented deferrable work to be absent.
    """
    if mode not in {"strict", "recovery"}:
        raise ValueError("Validation mode must be 'strict' or 'recovery'")

    typed = (
        snapshot
        if isinstance(snapshot, PlanningSnapshot)
        else PlanningSnapshot.from_dict(snapshot)
    )
    data = typed.to_dict()

    windows = [w for w in data["engineering_windows"] if w["date"] == planning_date]
    if len(windows) != 1:
        raise ValueError(
            f"Expected exactly one engineering window for {planning_date}, "
            f"found {len(windows)}"
        )
    window = windows[0]
    window_start = _dt(window["start"])
    usable_end = _dt(window["end"]) - timedelta(
        minutes=window["handback_buffer_minutes"]
    )

    requests = {
        request["id"]: request
        for request in data["requests"]
        if request["status"] != "cancelled"
        and planning_date in request["allowed_dates"]
    }
    sectors = {sector["id"]: sector for sector in data["sectors"]}
    engineers = {engineer["id"]: engineer for engineer in data["engineers"]}
    equipment = {item["id"]: item for item in data["equipment"]}
    pools = {pool["id"]: pool for pool in data["resource_pools"]}
    vehicles = {vehicle["id"]: vehicle for vehicle in data.get("vehicles", [])}
    committed = {
        allocation["request_id"]: allocation
        for allocation in data["committed_allocations"]
        if _dt(allocation["start"]).date().isoformat() == planning_date
    }
    locked = {rid: allocation for rid, allocation in committed.items() if allocation.get("locked")}
    for allocation in locked_allocations or []:
        locked[allocation["request_id"]] = allocation

    issues: dict[int, list[dict[str, Any]]] = {
        number: [] for number in CONSTRAINT_NAMES
    }

    def add_issue(
        constraint: int,
        code: str,
        request_ids: list[str],
        message: str,
        resource: str | None = None,
    ) -> None:
        issues[constraint].append(
            {
                "constraint": constraint,
                "code": code,
                "request_ids": sorted(set(request_ids)),
                "resource": resource,
                "message": message,
            }
        )

    allocation_map: dict[str, dict[str, Any]] = {}
    parsed_times: dict[str, tuple[datetime, datetime]] = {}
    for allocation in allocations:
        request_id = allocation.get("request_id")
        if not isinstance(request_id, str):
            add_issue(8, "UNKNOWN_REQUEST", [], "Allocation has no string request_id")
            continue
        if request_id in allocation_map:
            add_issue(8, "DUPLICATE", [request_id], "Request appears more than once")
            continue
        if request_id not in requests:
            add_issue(
                8,
                "UNKNOWN_REQUEST",
                [request_id],
                "Allocation references a request outside the selected planning night",
            )
            continue
        try:
            start = _dt(allocation["start"])
            end = _dt(allocation["end"])
        except (KeyError, TypeError, ValueError) as exc:
            add_issue(1, "INVALID_TIME", [request_id], str(exc))
            continue
        allocation_map[request_id] = allocation
        parsed_times[request_id] = (start, end)

    selected_ids = set(requests)
    scheduled_ids = set(allocation_map)

    # Constraint 1: complete duration, selected engineering window and handback.
    for request_id, allocation in allocation_map.items():
        request = requests[request_id]
        start, end = parsed_times[request_id]
        expected_duration = _duration(request)
        actual_duration = int((end - start).total_seconds() // 60)
        if end <= start or actual_duration != expected_duration:
            add_issue(
                1,
                "DURATION",
                [request_id],
                f"Allocated {actual_duration} minutes; complete phase duration is {expected_duration}",
            )
        if start < window_start or end > usable_end:
            add_issue(
                1,
                "ENGINEERING_WINDOW",
                [request_id],
                f"Work must remain inside {window_start.isoformat()} to {usable_end.isoformat()}",
            )
        if not set(request["protected_sectors"]).issubset(set(window["sector_ids"])):
            add_issue(
                1,
                "ENGINEERING_WINDOW",
                [request_id],
                "The selected window does not cover the complete protection footprint",
            )
        grid = data["planning_rules"]["start_grid_minutes"]
        offset = int((start - window_start).total_seconds() // 60)
        if offset < 0 or offset % grid:
            add_issue(
                1,
                "START_GRID",
                [request_id],
                f"Start must lie on the configured {grid}-minute grid",
            )

    # Constraint 2: blackouts, fixed sector unavailability and footprint overlap.
    unavailable_by_sector: dict[str, list[tuple[str, datetime, datetime]]] = {
        sector_id: [] for sector_id in sectors
    }
    for blackout in data.get("blackouts", []):
        for sector_id in blackout["sector_ids"]:
            unavailable_by_sector[sector_id].append(
                (blackout["id"], _dt(blackout["start"]), _dt(blackout["end"]))
            )
    for sector_id, sector in sectors.items():
        for index, blocked in enumerate(sector.get("fixed_unavailable_intervals", []), 1):
            unavailable_by_sector[sector_id].append(
                (f"{sector_id}:fixed:{index}", _dt(blocked["start"]), _dt(blocked["end"]))
            )

    for request_id in scheduled_ids:
        request = requests[request_id]
        start, end = parsed_times[request_id]
        for sector_id in request["protected_sectors"]:
            for block_id, blocked_start, blocked_end in unavailable_by_sector[sector_id]:
                if _overlap(start, end, blocked_start, blocked_end):
                    add_issue(
                        2,
                        "BLACKOUT",
                        [request_id],
                        f"Protection footprint overlaps unavailable interval {block_id}",
                        block_id,
                    )
        for transit in data.get("transit_schedules", []):
            if (
                transit["sector_id"] in request["protected_sectors"]
                and _overlap(start, end, _dt(transit["start"]), _dt(transit["end"]))
            ):
                add_issue(
                    2,
                    "VEHICLE_TRANSIT",
                    [request_id],
                    f"Protection footprint overlaps {transit['vehicle_id']} transit in {transit['sector_id']}",
                    transit["vehicle_id"],
                )

    for request_a_id, request_b_id in combinations(sorted(scheduled_ids), 2):
        request_a, request_b = requests[request_a_id], requests[request_b_id]
        common = set(request_a["protected_sectors"]) & set(request_b["protected_sectors"])
        if common and _overlap(*parsed_times[request_a_id], *parsed_times[request_b_id]):
            add_issue(
                2,
                "SPACE",
                [request_a_id, request_b_id],
                f"Exclusive protection footprints overlap in {', '.join(sorted(common))}",
                ",".join(sorted(common)),
            )

    # Constraint 3: traction-power and explicit work-type compatibility guards.
    work_rules: dict[frozenset[str], dict[str, Any]] = {}
    for rule in data["planning_rules"].get("work_compatibility_rules", []):
        work_rules[frozenset((rule["work_type_a"], rule["work_type_b"]))] = rule

    for request_a_id, request_b_id in combinations(sorted(scheduled_ids), 2):
        request_a, request_b = requests[request_a_id], requests[request_b_id]
        start_a, end_a = parsed_times[request_a_id]
        start_b, end_b = parsed_times[request_b_id]
        common_zones = _power_zones(request_a, sectors) & _power_zones(request_b, sectors)
        if common_zones:
            compatibility = data["planning_rules"]["power_compatibility"].get(
                request_a["power_requirement"], {}
            ).get(request_b["power_requirement"])
            if compatibility is None:
                add_issue(
                    3,
                    "REVIEW_REQUIRED",
                    [request_a_id, request_b_id],
                    "Traction-power compatibility rule is missing",
                )
            elif not compatibility:
                guard = data["planning_rules"]["opposed_power_transition_minutes"]
                separated = (
                    end_a + timedelta(minutes=guard) <= start_b
                    or end_b + timedelta(minutes=guard) <= start_a
                )
                if not separated:
                    add_issue(
                        3,
                        "POWER",
                        [request_a_id, request_b_id],
                        f"Opposed power states require a {guard}-minute transition",
                        ",".join(sorted(common_zones)),
                    )

        rule = work_rules.get(
            frozenset((request_a.get("work_type"), request_b.get("work_type")))
        )
        if rule and not rule["compatible"]:
            guard = rule["transition_minutes"]
            separated = (
                end_a + timedelta(minutes=guard) <= start_b
                or end_b + timedelta(minutes=guard) <= start_a
            )
            if not separated:
                add_issue(
                    3,
                    "WORK_COMPATIBILITY",
                    [request_a_id, request_b_id],
                    f"Incompatible work types require a {guard}-minute transition",
                )

    # Constraint 4: specialists, equipment and cumulative resource pools.
    assigned_engineers: dict[str, set[str]] = {}
    for request_id, allocation in allocation_map.items():
        request = requests[request_id]
        start, end = parsed_times[request_id]
        role_assignments = _engineer_assignments(request, allocation)
        flattened = [engineer_id for ids in role_assignments.values() for engineer_id in ids]
        assigned_engineers[request_id] = set(flattened)
        lead_engineer = allocation.get("engineer_id")
        if (flattened and lead_engineer not in flattened) or (
            not flattened and lead_engineer is not None
        ):
            add_issue(
                4,
                "QUALIFICATION",
                [request_id],
                "engineer_id is inconsistent with engineer_assignments",
                lead_engineer,
            )

        expected_roles = request.get("required_engineer_roles", {})
        for role, count in expected_roles.items():
            actual = role_assignments.get(role, [])
            if len(actual) != count:
                add_issue(
                    4,
                    "QUALIFICATION",
                    [request_id],
                    f"Role {role} requires {count} engineer(s), received {len(actual)}",
                    role,
                )
        unexpected_roles = set(role_assignments) - set(expected_roles)
        if unexpected_roles or len(flattened) != len(set(flattened)):
            add_issue(
                4,
                "QUALIFICATION",
                [request_id],
                "Engineer assignments contain unexpected roles or duplicate people",
            )
        for role, engineer_ids in role_assignments.items():
            for engineer_id in engineer_ids:
                engineer = engineers.get(engineer_id)
                if (
                    engineer is None
                    or engineer_id not in request["eligible_engineers"]
                    or role not in engineer["skills"]
                ):
                    add_issue(
                        4,
                        "QUALIFICATION",
                        [request_id],
                        f"{engineer_id} is not eligible and qualified for {role}",
                        engineer_id,
                    )
                    continue
                if not any(
                    _dt(period["start"]) <= start and end <= _dt(period["end"])
                    for period in engineer["availability"]
                ):
                    add_issue(
                        4,
                        "RESOURCE_WINDOW",
                        [request_id],
                        f"Engineer {engineer_id} is not available for the full allocation",
                        engineer_id,
                    )
                if any(
                    _overlap(start, end, _dt(period["start"]), _dt(period["end"]))
                    for period in engineer.get("unavailable", [])
                ):
                    add_issue(
                        4,
                        "RESOURCE_UNAVAILABLE",
                        [request_id],
                        f"Engineer {engineer_id} overlaps an unavailable period",
                        engineer_id,
                    )

        actual_equipment = allocation.get("equipment_ids", [])
        if sorted(actual_equipment) != sorted(request["required_equipment_ids"]):
            add_issue(
                4,
                "EQUIPMENT_ASSIGNMENT",
                [request_id],
                "Allocation does not contain exactly the required equipment IDs",
            )
        for equipment_id in actual_equipment:
            item = equipment.get(equipment_id)
            if item is None or not item["serviceable"]:
                add_issue(
                    4,
                    "EQUIPMENT_UNAVAILABLE",
                    [request_id],
                    f"Equipment {equipment_id} is unknown or not serviceable",
                    equipment_id,
                )
                continue
            if not any(
                _dt(period["start"]) <= start and end <= _dt(period["end"])
                for period in item["availability"]
            ):
                add_issue(
                    4,
                    "RESOURCE_WINDOW",
                    [request_id],
                    f"Equipment {equipment_id} is not available for the full allocation",
                    equipment_id,
                )
            if any(
                _overlap(start, end, _dt(period["start"]), _dt(period["end"]))
                for period in item.get("unavailable", [])
            ):
                add_issue(
                    4,
                    "RESOURCE_UNAVAILABLE",
                    [request_id],
                    f"Equipment {equipment_id} overlaps an unavailable period",
                    equipment_id,
                )

    for request_a_id, request_b_id in combinations(sorted(scheduled_ids), 2):
        if not _overlap(*parsed_times[request_a_id], *parsed_times[request_b_id]):
            continue
        shared_engineers = assigned_engineers.get(request_a_id, set()) & assigned_engineers.get(request_b_id, set())
        for engineer_id in shared_engineers:
            add_issue(
                4,
                "ENGINEER",
                [request_a_id, request_b_id],
                f"Engineer {engineer_id} is assigned to overlapping work",
                engineer_id,
            )
        shared_equipment = set(allocation_map[request_a_id].get("equipment_ids", [])) & set(
            allocation_map[request_b_id].get("equipment_ids", [])
        )
        for equipment_id in shared_equipment:
            add_issue(
                4,
                "EQUIPMENT",
                [request_a_id, request_b_id],
                f"Equipment {equipment_id} is assigned to overlapping work",
                equipment_id,
            )

    ticks = sorted(
        {time for request_id in scheduled_ids for time in parsed_times[request_id]}
    )
    for pool_id, pool in pools.items():
        for start, end in zip(ticks, ticks[1:]):
            active = [
                request_id
                for request_id in scheduled_ids
                if _overlap(start, end, *parsed_times[request_id])
            ]
            demand = sum(
                requests[request_id].get("pooled_resources", {}).get(pool_id, 0)
                for request_id in active
            )
            if demand > pool["capacity"]:
                add_issue(
                    4,
                    "MANPOWER",
                    active,
                    f"{pool_id} demand {demand} exceeds capacity {pool['capacity']}",
                    pool_id,
                )

    # Constraint 5: directional travel between consecutive named resources.
    for request_a_id, request_b_id in combinations(sorted(scheduled_ids), 2):
        request_a, request_b = requests[request_a_id], requests[request_b_id]
        start_a, end_a = parsed_times[request_a_id]
        start_b, end_b = parsed_times[request_b_id]
        shared_resources = (
            assigned_engineers.get(request_a_id, set())
            & assigned_engineers.get(request_b_id, set())
        ) | (
            set(allocation_map[request_a_id].get("equipment_ids", []))
            & set(allocation_map[request_b_id].get("equipment_ids", []))
        ) | (
            set(allocation_map[request_a_id].get("vehicle_ids", []))
            & set(allocation_map[request_b_id].get("vehicle_ids", []))
        )
        if not shared_resources:
            continue
        if start_a <= start_b:
            travel = _travel_minutes(data, request_a["work_sector"], request_b["work_sector"])
            valid_transfer = end_a + timedelta(minutes=travel) <= start_b
        else:
            travel = _travel_minutes(data, request_b["work_sector"], request_a["work_sector"])
            valid_transfer = end_b + timedelta(minutes=travel) <= start_a
        if not valid_transfer:
            add_issue(
                5,
                "TRANSFER_TIME",
                [request_a_id, request_b_id],
                f"Shared named resource requires {travel} minutes of directional travel",
                ",".join(sorted(shared_resources)),
            )

    for request_id, allocation in allocation_map.items():
        start, end = parsed_times[request_id]
        for vehicle_id in allocation.get("vehicle_ids", []):
            vehicle = vehicles.get(vehicle_id)
            if vehicle is None:
                add_issue(5, "VEHICLE_TRANSIT", [request_id], "Unknown vehicle", vehicle_id)
                continue
            if not any(
                _dt(period["start"]) <= start and end <= _dt(period["end"])
                for period in vehicle["availability"]
            ):
                add_issue(
                    5,
                    "VEHICLE_TRANSIT",
                    [request_id],
                    f"Vehicle {vehicle_id} is not available for the full allocation",
                    vehicle_id,
                )
            for transit in data.get("transit_schedules", []):
                if transit["vehicle_id"] == vehicle_id and _overlap(
                    start, end, _dt(transit["start"]), _dt(transit["end"])
                ):
                    add_issue(
                        5,
                        "VEHICLE_TRANSIT",
                        [request_id],
                        f"Vehicle {vehicle_id} is already in transit",
                        vehicle_id,
                    )

    # Constraint 6: dependency presence and predecessor-specific handover.
    for request_id in scheduled_ids:
        request = requests[request_id]
        start, _ = parsed_times[request_id]
        for predecessor_id in request["depends_on"]:
            if predecessor_id not in allocation_map:
                add_issue(
                    6,
                    "DEPENDENCY",
                    [request_id, predecessor_id],
                    "Scheduled dependent work is missing its predecessor",
                )
                continue
            _, predecessor_end = parsed_times[predecessor_id]
            buffer_minutes = request.get("handover_buffers", {}).get(
                predecessor_id,
                request.get("handover_buffer_minutes", 0),
            )
            if start < predecessor_end + timedelta(minutes=buffer_minutes):
                add_issue(
                    6,
                    "DEPENDENCY",
                    [request_id, predecessor_id],
                    f"Dependent work requires a {buffer_minutes}-minute handover",
                )

    # Constraint 7: approved jobs remain; frozen and explicit locks do not move.
    for request_id, request in requests.items():
        if request.get("approved") and request_id not in scheduled_ids:
            add_issue(
                7,
                "MISSING_WORK",
                [request_id],
                "Approved work must remain scheduled",
            )
        if request.get("frozen"):
            baseline = committed.get(request_id)
            actual = allocation_map.get(request_id)
            if baseline is None or actual is None:
                add_issue(
                    7,
                    "LOCKED_BOOKING",
                    [request_id],
                    "Frozen work must retain its committed allocation",
                )
            else:
                for field in (
                    "start",
                    "end",
                    "engineer_id",
                    "equipment_ids",
                    "vehicle_ids",
                ):
                    if _allocation_field(actual, field) != _allocation_field(
                        baseline, field
                    ):
                        add_issue(
                            7,
                            "LOCKED_BOOKING",
                            [request_id],
                            f"Frozen allocation changed field {field}",
                        )
                if _engineer_assignments(request, actual) != _engineer_assignments(
                    request, baseline
                ):
                    add_issue(
                        7,
                        "LOCKED_BOOKING",
                        [request_id],
                        "Frozen allocation changed engineer role assignments",
                    )
    for request_id, baseline in locked.items():
        actual = allocation_map.get(request_id)
        if actual is None:
            add_issue(7, "LOCKED_BOOKING", [request_id], "Locked allocation was removed")
            continue
        for field in (
            "start",
            "end",
            "engineer_id",
            "equipment_ids",
            "vehicle_ids",
        ):
            if field in baseline and _allocation_field(
                actual, field
            ) != _allocation_field(baseline, field):
                add_issue(
                    7,
                    "LOCKED_BOOKING",
                    [request_id],
                    f"Locked allocation changed field {field}",
                )
        request = requests.get(request_id)
        if request and _engineer_assignments(request, actual) != _engineer_assignments(
            request, baseline
        ):
            add_issue(
                7,
                "LOCKED_BOOKING",
                [request_id],
                "Locked allocation changed engineer role assignments",
            )

    # Constraint 8: request timing semantics and deferral eligibility.
    if mode == "strict":
        missing = selected_ids - scheduled_ids
        for request_id in sorted(missing):
            add_issue(8, "MISSING_WORK", [request_id], "Strict mode requires every selected request")
    for request_id, request in requests.items():
        if not request.get("deferrable", True) and request_id not in scheduled_ids:
            add_issue(8, "MISSING_WORK", [request_id], "Non-deferrable work was omitted")
    for request_id in scheduled_ids:
        request = requests[request_id]
        start, end = parsed_times[request_id]
        if (
            planning_date not in request["allowed_dates"]
            or start.date().isoformat() != planning_date
            or start < _dt(request["earliest_start"])
            or end > _dt(request["deadline"])
        ):
            add_issue(
                8,
                "REQUEST_WINDOW",
                [request_id],
                "Allocation lies outside the request's allowed date or time range",
            )
        if request["timing_mode"] == "EXACT" and start != _dt(request["preferred_start"]):
            add_issue(8, "REQUEST_WINDOW", [request_id], "EXACT request moved from its required start")
        if request["timing_mode"] == "ANY_TIME" and request["preferred_start"] is not None:
            add_issue(8, "REQUEST_WINDOW", [request_id], "ANY_TIME request has an artificial preference")

    # Constraint 9: service-critical work is always present.
    for request_id, request in requests.items():
        if request.get("mandatory") and request_id not in scheduled_ids:
            add_issue(
                9,
                "MANDATORY_DROPPED",
                [request_id],
                "Mandatory service-critical work was omitted",
            )

    results = [
        {
            "number": number,
            "name": name,
            "passed": not issues[number],
            "issues": issues[number],
        }
        for number, name in CONSTRAINT_NAMES.items()
    ]
    all_issues = [issue for result in results for issue in result["issues"]]
    return {
        "valid": not all_issues,
        "mode": mode,
        "planning_date": planning_date,
        "constraint_results": results,
        "issues": all_issues,
    }
