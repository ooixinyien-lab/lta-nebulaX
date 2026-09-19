"""Deterministic projection of dated schedule decisions into official PS1 CSV rows."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    ProblemInstance,
)
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    DatedAccessDecision,
)
from backend.app.ps1.models import Scenario
from backend.app.ps1.scoring import affected_line_codes
from backend.app.topology import FootprintCache


@dataclass
class ProjectedSchedule:
    access_rows: list[AccessScheduleRow]
    occupancy_rows: list[OccupancyScheduleRow]
    dated_accesses: list[DatedAccessDecision]


def project_dated_schedule(
    problem: ProblemInstance,
    scenario: Scenario,
    dated_accesses: list[DatedAccessDecision],
    footprints: FootprintCache | None = None,
) -> ProjectedSchedule:
    """Project real calendar service dates to official access and occupancy rows.

    Invariants enforced:
    1. access_seq is chronological (1..N) per activity.
    2. access_night is a local chronological index within (contract_number, activity_type, week).
       Same service_date -> same access_night.
       Different service_date -> different access_night.
    3. co_share_group is a local index within (location_id, week) mapped from service_date.
       Same location + same service_date -> same co_share_group.
       Different service_dates at same location/week -> different co_share_group.
    4. Deterministic sorting across calls.
    """
    cache = footprints or FootprintCache(problem)

    # 1. Sort dated accesses per activity chronologically and assign sequence
    accesses_by_activity: dict[str, list[DatedAccessDecision]] = defaultdict(list)
    for dec in dated_accesses:
        accesses_by_activity[dec.activity_id].append(dec)

    ordered_decisions: list[tuple[DatedAccessDecision, int]] = []
    for activity_id in sorted(accesses_by_activity.keys()):
        acts = sorted(accesses_by_activity[activity_id], key=lambda item: item.service_date)
        for seq, dec in enumerate(acts, start=1):
            ordered_decisions.append((dec, seq))

    # 2. Map service_date to local access_night per (contract_number, activity_type, week)
    contract_type_week_dates: dict[tuple[str, str, int], set[date]] = defaultdict(set)
    for dec, _ in ordered_decisions:
        activity = problem.activity(dec.activity_id)
        contract = problem.contract(activity.contract_number)
        key = (contract.contract_number, activity.activity_type.value, dec.week)
        contract_type_week_dates[key].add(dec.service_date)

    date_to_access_night: dict[tuple[str, str, int, date], int] = {}
    for key, dates in contract_type_week_dates.items():
        for idx, dt in enumerate(sorted(dates), start=1):
            date_to_access_night[(key[0], key[1], key[2], dt)] = idx

    access_rows: list[AccessScheduleRow] = []
    for dec, seq in ordered_decisions:
        activity = problem.activity(dec.activity_id)
        contract = problem.contract(activity.contract_number)
        night = date_to_access_night[(contract.contract_number, activity.activity_type.value, dec.week, dec.service_date)]
        access_rows.append(
            AccessScheduleRow(
                activity_id=dec.activity_id,
                access_seq=seq,
                week=dec.week,
                eclo=dec.eclo,
                access_night=night,
            )
        )
    access_rows.sort(key=lambda r: (r.activity_id, r.access_seq))

    # 3. Map service_date to local co_share_group per (location_id, week)
    location_week_dates: dict[tuple[str, int], set[date]] = defaultdict(set)
    for dec, _ in ordered_decisions:
        core = cache.get_core_footprint(dec.activity_id)
        for loc_id in core.core_locations:
            location_week_dates[(loc_id, dec.week)].add(dec.service_date)

    date_to_group: dict[tuple[str, int, date], str] = {}
    for (loc_id, week), dates in location_week_dates.items():
        for idx, dt in enumerate(sorted(dates), start=1):
            date_to_group[(loc_id, week, dt)] = f"g{idx}"

    occupancy_rows: list[OccupancyScheduleRow] = []
    for dec, _ in ordered_decisions:
        core = cache.get_core_footprint(dec.activity_id)
        for loc_id in core.core_locations:
            grp = date_to_group[(loc_id, dec.week, dec.service_date)]
            occupancy_rows.append(
                OccupancyScheduleRow(
                    activity_id=dec.activity_id,
                    week=dec.week,
                    location_id=loc_id,
                    co_share_group=grp,
                )
            )
    occupancy_rows.sort(key=lambda r: (r.activity_id, r.week, r.location_id))

    return ProjectedSchedule(
        access_rows=access_rows,
        occupancy_rows=occupancy_rows,
        dated_accesses=[d for d, _ in ordered_decisions],
    )


def build_calendar_assignments(
    problem: ProblemInstance,
    projected: ProjectedSchedule,
    calendar_id: str = "integrated",
    footprints: FootprintCache | None = None,
) -> list[CalendarAssignment]:
    """Convert projected rows and their underlying dates into CalendarAssignment records."""
    cache = footprints or FootprintCache(problem)

    # Match by (activity_id, access_seq)
    access_by_key = {
        (row.activity_id, row.access_seq): row
        for row in projected.access_rows
    }

    # Order decisions by activity_id, service_date to match access_seq 1..N
    decisions_by_activity: dict[str, list[DatedAccessDecision]] = defaultdict(list)
    for dec in projected.dated_accesses:
        decisions_by_activity[dec.activity_id].append(dec)

    assignments: list[CalendarAssignment] = []
    for activity_id in sorted(decisions_by_activity.keys()):
        activity = problem.activity(activity_id)
        contract = problem.contract(activity.contract_number)
        core = cache.get_core_footprint(activity_id)
        lines = affected_line_codes(problem, cache, activity_id)
        sorted_decs = sorted(decisions_by_activity[activity_id], key=lambda d: d.service_date)
        for seq, dec in enumerate(sorted_decs, start=1):
            access_row = access_by_key[(activity_id, seq)]
            assignments.append(
                CalendarAssignment(
                    access_id=f"{calendar_id}:{activity_id}:{seq}",
                    activity_id=activity_id,
                    access_seq=seq,
                    week=access_row.week,
                    access_night=access_row.access_night,
                    eclo=access_row.eclo,
                    service_date=dec.service_date,
                    global_night_id=f"{calendar_id}:{dec.service_date.isoformat()}",
                    contract_number=contract.contract_number,
                    contract_description=contract.contract_description,
                    line_codes=lines,
                    location_ids=core.core_locations,
                )
            )

    assignments.sort(key=lambda item: (item.week, item.service_date, item.activity_id, item.access_seq))
    return assignments
