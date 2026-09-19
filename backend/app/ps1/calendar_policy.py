"""Inspectable operational calendar policy helpers shared by solver and validator."""

from __future__ import annotations

from datetime import date, timedelta

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    NatureOfWorks,
    ProblemInstance,
)
from backend.app.ps1.calendar_models import (
    ContractCalendarRule,
    FixedScheduleBundle,
    OperatingCalendarInput,
)
from backend.app.ps1.models import Scenario
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
    """Apply conservative_demo_v1 with intra-possession buffer exemptions."""

    first_core, first_restricted, first_full = protection_sets(
        footprints, first.activity_id
    )
    second_core, second_restricted, second_full = protection_sets(
        footprints, second.activity_id
    )

    shared_core = first_core & second_core
    if shared_core:
        for location_id in shared_core:
            first_group = groups_by_access_location.get(
                (first.activity_id, first.week, location_id)
            )
            second_group = groups_by_access_location.get(
                (second.activity_id, second.week, location_id)
            )
            if first_group is None or first_group != second_group:
                return False
        ext_restr_a = first_restricted - second_core
        ext_restr_b = second_restricted - first_core
        ext_core_a = first_core - second_core
        ext_core_b = second_core - first_core
        if (ext_restr_a & ext_core_b) or (ext_restr_b & ext_core_a):
            return False
        return True

    if first_restricted & second_full or second_restricted & first_full:
        return False
    return True


def scope_problem_to_bundle(
    problem: ProblemInstance, bundle: FixedScheduleBundle
) -> ProblemInstance:
    """Scope problem instance to activities present in the bundle for mocked/partial inputs."""
    active_ids = {row.activity_id for row in bundle.access_rows}
    problem_ids = {a.activity_id for a in problem.activities}
    if not active_ids or active_ids == problem_ids:
        return problem
    acts_subset = [a for a in problem.activities if a.activity_id in active_ids]
    contracts_subset = [
        c for c in problem.contracts if c.contract_number in {a.contract_number for a in acts_subset}
    ]
    return ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=contracts_subset,
        activities=acts_subset,
    )


def activity_date_available(
    problem: ProblemInstance,
    footprints: FootprintCache,
    calendar: OperatingCalendarInput,
    activity_id: str,
    service_date: date,
    scenario: Scenario,
    enforce_exact_planned_start_date: bool = False,
) -> bool:
    """Check whether service_date is physically and contractually eligible for activity."""
    activity = problem.activity(activity_id)
    contract = problem.contract(activity.contract_number)

    if not (problem.parameters.horizon_start <= service_date <= problem.parameters.horizon_end):
        return False

    week = problem.parameters.date_to_week(service_date)
    release_week = problem.planned_start_week(activity)
    if week < release_week:
        return False

    if enforce_exact_planned_start_date and service_date < activity.planned_start_date:
        return False

    if scenario == Scenario.B:
        if problem.parameters.week_end_date(week) > contract.planned_completion_date:
            return False

    rule = contract_rule(calendar, contract.contract_number)
    if rule is not None and rule.eligible_dates is not None:
        if service_date not in rule.eligible_dates:
            return False

    lines = affected_line_codes(problem, footprints, activity_id)
    for line in lines:
        available, _ = line_night(calendar, line, service_date)
        if not available:
            return False

    protection = footprints.get_protection_footprint(activity_id)
    for loc_id in protection.all_protected_locations:
        available, _ = location_night(calendar, loc_id, service_date)
        if not available:
            return False

    return True


def activity_eclo_available(
    problem: ProblemInstance,
    footprints: FootprintCache,
    calendar: OperatingCalendarInput,
    activity_id: str,
    service_date: date,
    scenario: Scenario,
) -> bool:
    """Check whether ECLO is eligible for this activity and service date."""
    if scenario == Scenario.A:
        return False
    lines = affected_line_codes(problem, footprints, activity_id)
    for line in lines:
        _, eclo_eligible = line_night(calendar, line, service_date)
        if not eclo_eligible:
            return False
    return True


def base_candidate_dates(
    problem: ProblemInstance,
    footprints: FootprintCache,
    calendar: OperatingCalendarInput,
    activity_id: str,
    scenario: Scenario,
    enforce_exact_planned_start_date: bool = False,
) -> list[date]:
    """Return all calendar dates eligible for base access for this activity."""
    horizon = problem.parameters.horizon_weeks
    candidates: list[date] = []
    for week in range(1, horizon + 1):
        for service_date in week_dates(problem, week):
            if activity_date_available(
                problem,
                footprints,
                calendar,
                activity_id,
                service_date,
                scenario,
                enforce_exact_planned_start_date,
            ):
                candidates.append(service_date)
    return candidates


def eclo_candidate_dates(
    problem: ProblemInstance,
    footprints: FootprintCache,
    calendar: OperatingCalendarInput,
    activity_id: str,
    scenario: Scenario,
    base_dates: list[date] | None = None,
    enforce_exact_planned_start_date: bool = False,
) -> set[date]:
    """Return candidate dates that permit ECLO yield for this activity."""
    if scenario == Scenario.A:
        return set()
    dates = (
        base_dates
        if base_dates is not None
        else base_candidate_dates(
            problem,
            footprints,
            calendar,
            activity_id,
            scenario,
            enforce_exact_planned_start_date,
        )
    )
    eclo_dates: set[date] = set()
    for service_date in dates:
        if activity_eclo_available(
            problem, footprints, calendar, activity_id, service_date, scenario
        ):
            eclo_dates.add(service_date)
    return eclo_dates


def build_candidate_date_sets(
    problem: ProblemInstance,
    footprints: FootprintCache,
    calendar: OperatingCalendarInput,
    scenario: Scenario,
    enforce_exact_planned_start_date: bool = False,
) -> tuple[dict[str, list[date]], dict[str, set[date]]]:
    """Precompute base and ECLO candidate dates for all activities in the problem."""
    for rule in calendar.contract_rules:
        if rule.local_slot_eligible_dates:
            raise ValueError(
                f"UNSUPPORTED_LEGACY_SLOT_RULE: Contract {rule.contract_number} has "
                "local_slot_eligible_dates. The date-first solver requires date-level rules (eligible_dates)."
            )

    base_candidates: dict[str, list[date]] = {}
    eclo_candidates: dict[str, set[date]] = {}
    for activity in problem.activities:
        act_id = activity.activity_id
        base_dates = base_candidate_dates(
            problem,
            footprints,
            calendar,
            act_id,
            scenario,
            enforce_exact_planned_start_date,
        )
        base_candidates[act_id] = base_dates
        eclo_candidates[act_id] = eclo_candidate_dates(
            problem,
            footprints,
            calendar,
            act_id,
            scenario,
            base_dates=base_dates,
            enforce_exact_planned_start_date=enforce_exact_planned_start_date,
        )
    return base_candidates, eclo_candidates


def build_same_date_conflict_pairs(
    problem: ProblemInstance,
    footprints: FootprintCache,
) -> set[tuple[str, str]]:
    """Identify pairs of activities that cannot run on the same date under conservative_demo_v1."""
    conflict_pairs: set[tuple[str, str]] = set()
    activities = sorted(problem.activities, key=lambda a: a.activity_id)
    protection_data = {
        act.activity_id: protection_sets(footprints, act.activity_id)
        for act in activities
    }
    for i, act_a in enumerate(activities):
        id_a = act_a.activity_id
        core_a, restricted_a, full_a = protection_data[id_a]
        contract_a = problem.contract(act_a.contract_number)
        role_a = contract_a.access_type
        nature_a = contract_a.nature_of_activity

        for act_b in activities[i + 1 :]:
            id_b = act_b.activity_id
            core_b, restricted_b, full_b = protection_data[id_b]
            contract_b = problem.contract(act_b.contract_number)
            role_b = contract_b.access_type
            nature_b = contract_b.nature_of_activity

            shared_core = core_a & core_b
            if shared_core:
                if role_a == AccessType.PM or role_b == AccessType.PM:
                    conflict_pairs.add((id_a, id_b))
                elif role_a == AccessType.PC and role_b == AccessType.PC:
                    conflict_pairs.add((id_a, id_b))
                elif (nature_a == NatureOfWorks.LIVE) != (nature_b == NatureOfWorks.LIVE):
                    conflict_pairs.add((id_a, id_b))
                else:
                    ext_restr_a = restricted_a - core_b
                    ext_restr_b = restricted_b - core_a
                    ext_core_a = core_a - core_b
                    ext_core_b = core_b - core_a
                    if (ext_restr_a & ext_core_b) or (ext_restr_b & ext_core_a):
                        conflict_pairs.add((id_a, id_b))
            else:
                if (restricted_a & full_b) or (restricted_b & full_a):
                    conflict_pairs.add((id_a, id_b))
    return conflict_pairs

