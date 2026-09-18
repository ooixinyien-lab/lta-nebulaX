"""Inspectable operational calendar policy helpers shared by solver and validator."""

from __future__ import annotations

from datetime import date, timedelta

from backend.app.domain_models import AccessScheduleRow, ProblemInstance
from backend.app.ps1.calendar_models import (
    ContractCalendarRule,
    OperatingCalendarInput,
)
from backend.app.ps1.scoring import affected_line_codes
from backend.app.topology import FootprintCache


def week_dates(problem: ProblemInstance, week: int) -> list[date]:
    start = problem.parameters.week_start_date(week)
    return [start + timedelta(days=offset) for offset in range(7)]


def contract_rule(
    calendar: OperatingCalendarInput, contract_number: str
) -> ContractCalendarRule | None:
    return next(
        (
            rule
            for rule in calendar.contract_rules
            if rule.contract_number == contract_number
        ),
        None,
    )


def location_night(
    calendar: OperatingCalendarInput, location_id: str, service_date: date
) -> tuple[bool, int]:
    rule = next(
        (
            item
            for item in calendar.location_nights
            if item.location_id == location_id and item.service_date == service_date
        ),
        None,
    )
    if rule is None:
        return (
            calendar.default_maintenance_available,
            calendar.default_location_possession_capacity,
        )
    return rule.maintenance_available, rule.possession_capacity


def line_night(
    calendar: OperatingCalendarInput, line_code: str, service_date: date
) -> tuple[bool, bool]:
    rule = next(
        (
            item
            for item in calendar.line_nights
            if item.line_code == line_code and item.service_date == service_date
        ),
        None,
    )
    if rule is None:
        return calendar.default_maintenance_available, calendar.default_eclo_eligible
    return rule.maintenance_available, rule.eclo_eligible


def candidate_dates(
    problem: ProblemInstance,
    footprints: FootprintCache,
    calendar: OperatingCalendarInput,
    access: AccessScheduleRow,
) -> list[date]:
    """Return dates permitted by explicit inputs, before multi-access constraints."""

    activity = problem.activity(access.activity_id)
    contract = problem.contract(activity.contract_number)
    rule = contract_rule(calendar, contract.contract_number)
    protection = footprints.get_protection_footprint(access.activity_id)
    lines = affected_line_codes(problem, footprints, access.activity_id)

    candidates: list[date] = []
    for service_date in week_dates(problem, access.week):
        if service_date < activity.planned_start_date:
            continue
        if rule is not None and rule.eligible_dates is not None:
            if service_date not in rule.eligible_dates:
                continue
        if rule is not None and access.access_night in rule.local_slot_eligible_dates:
            if service_date not in rule.local_slot_eligible_dates[access.access_night]:
                continue
        if any(not line_night(calendar, line, service_date)[0] for line in lines):
            continue
        if access.eclo and any(
            not line_night(calendar, line, service_date)[1] for line in lines
        ):
            continue
        if any(
            not location_night(calendar, location_id, service_date)[0]
            for location_id in protection.all_protected_locations
        ):
            continue
        candidates.append(service_date)
    return candidates


def actual_night_limit(
    problem: ProblemInstance,
    calendar: OperatingCalendarInput,
    contract_number: str,
) -> int:
    contract = problem.contract(contract_number)
    rule = contract_rule(calendar, contract_number)
    return (
        rule.actual_night_limit_per_week
        if rule is not None and rule.actual_night_limit_per_week is not None
        else contract.number_of_maximum_access_per_week
    )


def nightly_workfront_limit(
    problem: ProblemInstance,
    calendar: OperatingCalendarInput,
    contract_number: str,
) -> int:
    contract = problem.contract(contract_number)
    rule = contract_rule(calendar, contract_number)
    return (
        rule.nightly_workfront_limit
        if rule is not None and rule.nightly_workfront_limit is not None
        else contract.number_of_workfronts
    )


def protection_sets(
    footprints: FootprintCache, activity_id: str
) -> tuple[set[str], set[str], set[str]]:
    core = set(footprints.get_core_footprint(activity_id).core_locations)
    protection = footprints.get_protection_footprint(activity_id)
    restricted = set(
        protection.buffer_locations
        + protection.mirrored_locations
        + protection.cross_line_locations
    )
    return core, restricted, core | restricted


def can_share_service_date(
    footprints: FootprintCache,
    first: AccessScheduleRow,
    second: AccessScheduleRow,
    groups_by_access_location: dict[tuple[str, int, str], str],
) -> bool:
    """Apply conservative_demo_v1 exactly as documented in the plan."""

    first_core, first_restricted, first_full = protection_sets(
        footprints, first.activity_id
    )
    second_core, second_restricted, second_full = protection_sets(
        footprints, second.activity_id
    )
    if first_restricted & second_full or second_restricted & first_full:
        return False
    for location_id in first_core & second_core:
        first_group = groups_by_access_location.get(
            (first.activity_id, first.week, location_id)
        )
        second_group = groups_by_access_location.get(
            (second.activity_id, second.week, location_id)
        )
        if first_group is None or first_group != second_group:
            return False
    return True
