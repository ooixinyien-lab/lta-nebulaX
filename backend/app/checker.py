"""Stateless Conflict Checker evaluating MaintenanceRequests against a PlanningSnapshot state."""

from datetime import datetime, timedelta
from typing import Optional
from models import (
    Allocation,
    Blackout,
    Conflict,
    ConflictCode,
    EngineeringWindow,
    MaintenanceRequest,
    PlanningSnapshot,
    PowerRequirement,
    RequestStatus,
)


def create_conflict(
    code: ConflictCode,
    request_ids: list[str],
    message: str,
    resource: Optional[str] = None,
    severity: str = "error",
) -> Conflict:
    """Creates a validated Pydantic Conflict domain model instance."""
    return Conflict(
        code=code,
        request_ids=sorted(set(request_ids)),
        message=message,
        resource=resource,
        severity=severity,  # type: ignore[arg-type]
    )


def conflict_checker(snapshot: PlanningSnapshot, target_request: MaintenanceRequest) -> list[Conflict]:
    """Evaluates a MaintenanceRequest against active allocations and topology in PlanningSnapshot."""
    conflicts: list[Conflict] = []

    # Filter active allocations excluding target request (if re-evaluating an existing request)
    active_allocations: list[tuple[MaintenanceRequest, Allocation]] = []
    req_map = {r.id: r for r in snapshot.requests if r.status != RequestStatus.cancelled}

    for alloc in snapshot.committed_allocations:
        if alloc.request_id != target_request.id and alloc.request_id in req_map:
            active_allocations.append((req_map[alloc.request_id], alloc))

    # -------------------------------------------------------------
    # 1. Engineering Window & Blackout Checks (Constraint 1)
    # -------------------------------------------------------------
    target_dates = target_request.allowed_dates
    target_duration = target_request.duration_minutes

    for date_str in target_dates:
        matching_windows = [w for w in snapshot.engineering_windows if w.date == date_str]
        for w in matching_windows:
            usable_minutes = int((w.usable_end - w.start).total_seconds() // 60)
            if target_duration > usable_minutes:
                conflicts.append(
                    create_conflict(
                        code=ConflictCode.ENGINEERING_WINDOW,
                        request_ids=[target_request.id],
                        message=(
                            f"Total request duration ({target_duration} mins) exceeds usable "
                            f"engineering window ({usable_minutes} mins after {w.handback_buffer_minutes}m handback buffer) on {date_str}."
                        ),
                        resource="ENGINEERING_WINDOW",
                    )
                )

    # -------------------------------------------------------------
    # 2. Check Allocation Overlaps (Time + Space / Power / Resources)
    # -------------------------------------------------------------
    t_start = target_request.existing_start or target_request.earliest_start
    t_end = t_start + timedelta(minutes=target_duration)

    for other_req, alloc in active_allocations:
        # Check time overlap between target request window and active allocation
        time_overlaps = max(t_start, alloc.start) < min(t_end, alloc.end)
        pair_ids = [target_request.id, other_req.id]

        if time_overlaps:
            # Constraint 2: Spatial Track & Safety Footprint Overlap
            common_sectors = set(target_request.protected_sectors) & set(other_req.protected_sectors)
            if common_sectors:
                label = ", ".join(sorted(common_sectors))
                conflicts.append(
                    create_conflict(
                        code=ConflictCode.SPACE,
                        request_ids=pair_ids,
                        message=f"Exclusive safety footprint conflict on sector(s): {label} with active allocation for Request '{other_req.id}'.",
                        resource=label,
                    )
                )

            # Constraint 3: Power Compatibility Check
            p1 = target_request.power_requirement
            p2 = other_req.power_requirement
            if (
                (p1 == PowerRequirement.ON and p2 == PowerRequirement.OFF)
                or (p1 == PowerRequirement.OFF and p2 == PowerRequirement.ON)
            ):
                conflicts.append(
                    create_conflict(
                        code=ConflictCode.POWER,
                        request_ids=pair_ids,
                        message=f"Traction power conflict ({p1.value} vs {p2.value}) with active Request '{other_req.id}'.",
                        resource="POWER_ZONE",
                    )
                )

            # Constraint 4: Equipment Assignment & Overlap
            target_eq = set(target_request.required_equipment_ids)
            alloc_eq = set(alloc.equipment_ids)
            common_eq = target_eq & alloc_eq
            if common_eq:
                eq_label = ", ".join(sorted(common_eq))
                conflicts.append(
                    create_conflict(
                        code=ConflictCode.EQUIPMENT,
                        request_ids=pair_ids,
                        message=f"Equipment '{eq_label}' double-booked with active allocation for Request '{other_req.id}'.",
                        resource=eq_label,
                    )
                )

    # -------------------------------------------------------------
    # 3. Blackout Window Overlaps
    # -------------------------------------------------------------
    for b in snapshot.blackouts:
        sector_overlap = set(target_request.protected_sectors) & set(b.sector_ids)
        if sector_overlap:
            time_overlap = max(t_start, b.start) < min(t_end, b.end)
            if time_overlap:
                label = ", ".join(sorted(sector_overlap))
                conflicts.append(
                    create_conflict(
                        code=ConflictCode.BLACKOUT,
                        request_ids=[target_request.id],
                        message=f"Request overlaps active blackout '{b.id}' ({b.reason}) on sector(s): {label}.",
                        resource=b.id,
                    )
                )

    # -------------------------------------------------------------
    # 4. Dependency Sequence Checks (Constraint 6)
    # -------------------------------------------------------------
    for prereq_id in target_request.depends_on:
        prereq_alloc = next((a for a in snapshot.committed_allocations if a.request_id == prereq_id), None)
        if prereq_alloc:
            if t_start < prereq_alloc.end:
                conflicts.append(
                    create_conflict(
                        code=ConflictCode.DEPENDENCY,
                        request_ids=[target_request.id, prereq_id],
                        message=(
                            f"Sequence conflict: Request '{target_request.id}' ({t_start.isoformat()}) "
                            f"starts before prerequisite Request '{prereq_id}' finishes ({prereq_alloc.end.isoformat()})."
                        ),
                        resource=prereq_id,
                    )
                )

    return conflicts