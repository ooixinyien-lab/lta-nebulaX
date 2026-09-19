"""Independent validation for exact-date assignments over immutable CSV rows."""

from __future__ import annotations

from collections import defaultdict

from backend.app.domain_models import ProblemInstance
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    CalendarConflict,
    CalendarValidationSummary,
    DateCommitment,
    FixedScheduleBundle,
    OperatingCalendarInput,
)
from backend.app.ps1.calendar_policy import (
    actual_night_limit,
    can_share_service_date,
    candidate_dates,
    location_night,
    nightly_workfront_limit,
    scope_problem_to_bundle,
)
from backend.app.ps1.scoring import build_contract_results
from backend.app.ps1.validation import validate_schedule
from backend.app.topology import FootprintCache


def validate_fixed_bundle(
    problem: ProblemInstance, bundle: FixedScheduleBundle
) -> CalendarValidationSummary:
    """Validate all official rows before any operational mapping is attempted."""

    effective_problem = scope_problem_to_bundle(problem, bundle)
    weekly = validate_schedule(
        effective_problem, bundle.scenario, bundle.access_rows, bundle.occupancy_rows
    )
    issues = [
        CalendarConflict(
            rule_code=f"SOURCE_{issue.rule.upper()}",
            message=issue.detail,
            activity_ids=[issue.activity_id] if issue.activity_id else [],
            location_ids=[issue.location_id] if issue.location_id else [],
        )
        for issue in weekly.issues
    ]
    try:
        expected_results = build_contract_results(
            effective_problem, bundle.scenario, bundle.access_rows
        )
        results_match = sorted(
            bundle.result_rows, key=lambda row: row.contract_number
        ) == sorted(expected_results, key=lambda row: row.contract_number)
    except ValueError as exc:
        results_match = False
        issues.append(
            CalendarConflict(
                rule_code="SOURCE_RESULTS_UNCHECKABLE",
                message=str(exc),
            )
        )
    if not results_match:
        issues.append(
            CalendarConflict(
                rule_code="SOURCE_RESULTS_MISMATCH",
                message="RESULTS.csv does not match the fixed weekly access rows.",
            )
        )
    return CalendarValidationSummary(
        passed=weekly.local_accounting_passed and results_match,
        weekly_validation_passed=weekly.local_accounting_passed,
        calendar_validation_passed=False,
        source_results_match=results_match,
        issues=issues,
    )


def validate_calendar_definition(
    problem: ProblemInstance, calendar: OperatingCalendarInput
) -> list[CalendarConflict]:
    issues: list[CalendarConflict] = []
    if calendar.instance_revision_id == "":
        issues.append(
            CalendarConflict(
                rule_code="CALENDAR_REVISION_REQUIRED",
                message="Calendar must reference an instance revision.",
            )
        )
    valid_locations = set(problem._locations_by_id)
    valid_lines = set(problem._lines_by_code)
    valid_contracts = set(problem._contracts_by_number)
    start = problem.parameters.horizon_start
    end = problem.parameters.horizon_end
    for rule in calendar.location_nights:
        if rule.location_id not in valid_locations:
            issues.append(
                CalendarConflict(
                    rule_code="UNKNOWN_CALENDAR_LOCATION",
                    message=f"Calendar refers to unknown location {rule.location_id}.",
                    location_ids=[rule.location_id],
                    service_dates=[rule.service_date],
                )
            )
        if not start <= rule.service_date <= end:
            issues.append(
                CalendarConflict(
                    rule_code="CALENDAR_DATE_OUTSIDE_HORIZON",
                    message=f"Calendar date {rule.service_date} is outside the horizon.",
                    location_ids=[rule.location_id],
                    service_dates=[rule.service_date],
                )
            )
    for rule in calendar.line_nights:
        if rule.line_code not in valid_lines:
            issues.append(
                CalendarConflict(
                    rule_code="UNKNOWN_CALENDAR_LINE",
                    message=f"Calendar refers to unknown line {rule.line_code}.",
                    service_dates=[rule.service_date],
                )
            )
        if not start <= rule.service_date <= end:
            issues.append(
                CalendarConflict(
                    rule_code="CALENDAR_DATE_OUTSIDE_HORIZON",
                    message=f"Calendar date {rule.service_date} is outside the horizon.",
                    service_dates=[rule.service_date],
                )
            )
    for rule in calendar.contract_rules:
        if rule.contract_number not in valid_contracts:
            issues.append(
                CalendarConflict(
                    rule_code="UNKNOWN_CALENDAR_CONTRACT",
                    message=f"Calendar refers to unknown contract {rule.contract_number}.",
                )
            )
        all_dates = list(rule.eligible_dates or []) + [
            item
            for values in rule.local_slot_eligible_dates.values()
            for item in values
        ]
        if any(not start <= item <= end for item in all_dates):
            issues.append(
                CalendarConflict(
                    rule_code="CALENDAR_DATE_OUTSIDE_HORIZON",
                    message=(
                        f"Contract calendar for {rule.contract_number} includes a date "
                        "outside the planning horizon."
                    ),
                )
            )
    return issues


def validate_calendarisation(
    problem: ProblemInstance,
    bundle: FixedScheduleBundle,
    calendar: OperatingCalendarInput,
    commitments: list[DateCommitment],
    assignments: list[CalendarAssignment],
) -> CalendarValidationSummary:
    problem = scope_problem_to_bundle(problem, bundle)
    footprints = FootprintCache(problem)
    source_validation = validate_fixed_bundle(problem, bundle)
    issues = list(source_validation.issues)
    source_issue_count = len(issues)
    issues.extend(validate_calendar_definition(problem, calendar))

    source = {
        (row.activity_id, row.access_seq): row for row in bundle.access_rows
    }
    assigned: dict[tuple[str, int], CalendarAssignment] = {}
    for row in assignments:
        key = (row.activity_id, row.access_seq)
        if key in assigned:
            issues.append(
                CalendarConflict(
                    rule_code="DUPLICATE_DATE_ASSIGNMENT",
                    message=f"Access {row.activity_id} sequence {row.access_seq} is dated twice.",
                    activity_ids=[row.activity_id],
                    access_ids=[row.access_id],
                )
            )
            continue
        assigned[key] = row
        original = source.get(key)
        if original is None:
            issues.append(
                CalendarConflict(
                    rule_code="UNKNOWN_DATE_ASSIGNMENT",
                    message=f"Dated row {row.activity_id} sequence {row.access_seq} is not in the source.",
                    activity_ids=[row.activity_id],
                    access_ids=[row.access_id],
                )
            )
            continue
        if (
            row.week != original.week
            or row.access_night != original.access_night
            or row.eclo != original.eclo
        ):
            issues.append(
                CalendarConflict(
                    rule_code="SOURCE_ACCESS_CHANGED",
                    message=f"Operational row changed fixed fields for {row.activity_id} sequence {row.access_seq}.",
                    activity_ids=[row.activity_id],
                    access_ids=[row.access_id],
                )
            )
        if row.service_date not in candidate_dates(
            problem, footprints, calendar, original
        ):
            issues.append(
                CalendarConflict(
                    rule_code="INELIGIBLE_DATE",
                    message=f"{row.service_date} is not eligible for {row.activity_id} sequence {row.access_seq}.",
                    activity_ids=[row.activity_id],
                    access_ids=[row.access_id],
                    service_dates=[row.service_date],
                )
            )

    missing = sorted(set(source) - set(assigned))
    if missing:
        issues.append(
            CalendarConflict(
                rule_code="MISSING_DATE_ASSIGNMENTS",
                message=f"{len(missing)} fixed source accesses have no service date.",
                activity_ids=sorted({key[0] for key in missing}),
            )
        )

    for commitment in commitments:
        row = assigned.get((commitment.activity_id, commitment.access_seq))
        if row is None or row.service_date != commitment.service_date:
            issues.append(
                CalendarConflict(
                    rule_code="COMMITMENT_CHANGED",
                    message=f"Date commitment for {commitment.activity_id} sequence {commitment.access_seq} was not honoured.",
                    activity_ids=[commitment.activity_id],
                    service_dates=[commitment.service_date],
                )
            )

    access_by_activity_week = {
        (row.activity_id, row.week): row for row in bundle.access_rows
    }
    groups_by_access_location: dict[tuple[str, int, str], str] = {}
    group_members: dict[tuple[str, int, str], list] = defaultdict(list)
    for occupancy in bundle.occupancy_rows:
        original = access_by_activity_week.get((occupancy.activity_id, occupancy.week))
        if original is None:
            continue
        groups_by_access_location[
            (occupancy.activity_id, occupancy.week, occupancy.location_id)
        ] = occupancy.co_share_group
        group_members[
            (occupancy.location_id, occupancy.week, occupancy.co_share_group)
        ].append(original)

    for (location_id, week, group), members in group_members.items():
        dates = {
            assigned[(member.activity_id, member.access_seq)].service_date
            for member in members
            if (member.activity_id, member.access_seq) in assigned
        }
        if len(dates) > 1:
            issues.append(
                CalendarConflict(
                    rule_code="SHARED_GROUP_DATE_MISMATCH",
                    message=f"Shared group {group} at {location_id} in week {week} spans multiple dates.",
                    activity_ids=sorted({member.activity_id for member in members}),
                    service_dates=sorted(dates),
                    location_ids=[location_id],
                )
            )

    occupied: dict[tuple[str, object], set[tuple[int, str]]] = defaultdict(set)
    for (location_id, week, group), members in group_members.items():
        dated_member = next(
            (
                assigned[(member.activity_id, member.access_seq)]
                for member in members
                if (member.activity_id, member.access_seq) in assigned
            ),
            None,
        )
        if dated_member is not None:
            occupied[(location_id, dated_member.service_date)].add((week, group))
    for (location_id, service_date), groups in occupied.items():
        _available, capacity = location_night(calendar, location_id, service_date)
        if len(groups) > capacity:
            issues.append(
                CalendarConflict(
                    rule_code="NIGHTLY_POSSESSION_CAPACITY",
                    message=f"{location_id} uses {len(groups)} groups on {service_date}, above capacity {capacity}.",
                    service_dates=[service_date],
                    location_ids=[location_id],
                    required_capacity=len(groups),
                    available_capacity=capacity,
                )
            )

    by_contract_week_date: dict[tuple[str, int, object], int] = defaultdict(int)
    dates_by_contract_week: dict[tuple[str, int], set] = defaultdict(set)
    for key, dated in assigned.items():
        if key not in source:
            continue
        contract = problem.activity(dated.activity_id).contract_number
        by_contract_week_date[(contract, dated.week, dated.service_date)] += 1
        dates_by_contract_week[(contract, dated.week)].add(dated.service_date)
    for (contract, _week, service_date), count in by_contract_week_date.items():
        limit = nightly_workfront_limit(problem, calendar, contract)
        if count > limit:
            issues.append(
                CalendarConflict(
                    rule_code="NIGHTLY_WORKFRONT_LIMIT",
                    message=f"Contract {contract} uses {count} workfronts on {service_date}, above {limit}.",
                    service_dates=[service_date],
                    required_capacity=count,
                    available_capacity=limit,
                )
            )
    for (contract, week), dates in dates_by_contract_week.items():
        limit = actual_night_limit(problem, calendar, contract)
        if len(dates) > limit:
            issues.append(
                CalendarConflict(
                    rule_code="ACTUAL_NIGHT_LIMIT",
                    message=f"Contract {contract} uses {len(dates)} actual nights in week {week}, above {limit}.",
                    service_dates=sorted(dates),
                    required_capacity=len(dates),
                    available_capacity=limit,
                )
            )

    by_week = defaultdict(list)
    for original in bundle.access_rows:
        by_week[original.week].append(original)
    for originals in by_week.values():
        for index, first in enumerate(originals):
            for second in originals[index + 1 :]:
                first_dated = assigned.get((first.activity_id, first.access_seq))
                second_dated = assigned.get((second.activity_id, second.access_seq))
                if (
                    first_dated is not None
                    and second_dated is not None
                    and first_dated.service_date == second_dated.service_date
                    and not can_share_service_date(
                        footprints, first, second, groups_by_access_location
                    )
                ):
                    issues.append(
                        CalendarConflict(
                            rule_code="PROTECTION_CONFLICT",
                            message=(
                                f"{first.activity_id} and {second.activity_id} conflict under "
                                "conservative_demo_v1."
                            ),
                            activity_ids=[first.activity_id, second.activity_id],
                            service_dates=[first_dated.service_date],
                        )
                    )

    rows_by_activity: dict[str, list[CalendarAssignment]] = defaultdict(list)
    for row in assignments:
        rows_by_activity[row.activity_id].append(row)
    for activity in problem.activities:
        if not activity.predecessor_activity_id:
            continue
        predecessor = rows_by_activity.get(activity.predecessor_activity_id, [])
        successor = rows_by_activity.get(activity.activity_id, [])
        if predecessor and successor and max(
            row.service_date for row in predecessor
        ) >= min(row.service_date for row in successor):
            issues.append(
                CalendarConflict(
                    rule_code="DATE_PREDECESSOR",
                    message=f"{activity.activity_id} does not start after {activity.predecessor_activity_id} completes.",
                    activity_ids=[activity.predecessor_activity_id, activity.activity_id],
                )
            )

    calendar_passed = not any(
        issue.severity == "hard" for issue in issues[source_issue_count:]
    )
    return CalendarValidationSummary(
        passed=source_validation.passed and calendar_passed,
        weekly_validation_passed=source_validation.weekly_validation_passed,
        calendar_validation_passed=calendar_passed,
        source_results_match=source_validation.source_results_match,
        issues=issues,
    )
