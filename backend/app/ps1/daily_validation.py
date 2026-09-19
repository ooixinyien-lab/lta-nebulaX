"""Independent validation for date-first PS1 schedules and their official projections."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    OccupancyScheduleRow,
    ProblemInstance,
)
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    CalendarConflict,
    CalendarValidationSummary,
    OperatingCalendarInput,
)
from backend.app.ps1.calendar_policy import (
    actual_night_limit,
    build_same_date_conflict_pairs,
    line_night,
    location_night,
    nightly_workfront_limit,
    protection_sets,
)
from backend.app.ps1.calendar_validation import validate_calendar_definition
from backend.app.ps1.models import Scenario, coerce_scenario
from backend.app.ps1.scoring import affected_line_codes, build_contract_results
from backend.app.ps1.validation import validate_schedule
from backend.app.topology import FootprintCache


def validate_dated_schedule(
    problem: ProblemInstance,
    scenario: Scenario | str,
    calendar: OperatingCalendarInput,
    calendar_assignments: list[CalendarAssignment],
    projected_access_rows: list[AccessScheduleRow],
    projected_occupancy_rows: list[OccupancyScheduleRow],
    footprints: FootprintCache | None = None,
    enforce_exact_planned_start_date: bool = False,
    selected_window_starts: dict[str, int] | None = None,
) -> CalendarValidationSummary:
    """Independently validate a date-first schedule, its operational assignments, and projected rows."""

    selected_scenario = coerce_scenario(scenario)
    cache = footprints or FootprintCache(problem)
    issues: list[CalendarConflict] = []

    # 1. Calendar definition validation
    issues.extend(validate_calendar_definition(problem, calendar))

    # Index assignments and check consistency with projected access rows
    assignment_by_key: dict[tuple[str, int], CalendarAssignment] = {}
    assignments_by_activity: dict[str, list[CalendarAssignment]] = defaultdict(list)
    for row in calendar_assignments:
        key = (row.activity_id, row.access_seq)
        if key in assignment_by_key:
            issues.append(
                CalendarConflict(
                    rule_code="DUPLICATE_DATE_ASSIGNMENT",
                    message=f"Access {row.activity_id} sequence {row.access_seq} is dated twice.",
                    activity_ids=[row.activity_id],
                )
            )
            continue
        assignment_by_key[key] = row
        assignments_by_activity[row.activity_id].append(row)

    access_row_by_key = {
        (r.activity_id, r.access_seq): r for r in projected_access_rows
    }

    # 2. Completeness & Workload
    for activity in problem.activities:
        act_id = activity.activity_id
        contract = problem.contract(activity.contract_number)
        decs = assignments_by_activity.get(act_id, [])
        if not decs:
            issues.append(
                CalendarConflict(
                    rule_code="MISSING_ACTIVITY_WORKLOAD",
                    message=f"Activity {act_id} has no scheduled date assignments.",
                    activity_ids=[act_id],
                )
            )
            continue

        # Check sequence consecutive from 1
        seqs = sorted(d.access_seq for d in decs)
        expected_seqs = list(range(1, len(decs) + 1))
        if seqs != expected_seqs:
            issues.append(
                CalendarConflict(
                    rule_code="NON_CONSECUTIVE_SEQUENCE",
                    message=f"Activity {act_id} sequence numbers must be consecutive from 1; got {seqs}.",
                    activity_ids=[act_id],
                )
            )

        # Check chronological order of service_date
        ordered_by_seq = sorted(decs, key=lambda d: d.access_seq)
        dates_in_seq = [d.service_date for d in ordered_by_seq]
        if dates_in_seq != sorted(dates_in_seq):
            issues.append(
                CalendarConflict(
                    rule_code="CHRONOLOGICAL_SEQUENCE_MISMATCH",
                    message=f"Activity {act_id} access_seq order does not match chronological date order.",
                    activity_ids=[act_id],
                    service_dates=dates_in_seq,
                )
            )

        # Workload satisfaction
        delivered_workload = sum(3 if d.eclo else 2 for d in decs)
        if delivered_workload < activity.doubled_workload:
            issues.append(
                CalendarConflict(
                    rule_code="INSUFFICIENT_WORKLOAD",
                    message=(
                        f"Activity {act_id} delivered doubled workload {delivered_workload} "
                        f"is below required {activity.doubled_workload}."
                    ),
                    activity_ids=[act_id],
                )
            )

        # Weekly frequency: at most 1 access per activity per week
        weeks_seen: set[int] = set()
        for d in decs:
            if d.week in weeks_seen:
                issues.append(
                    CalendarConflict(
                        rule_code="MULTIPLE_ACCESSES_IN_WEEK",
                        message=f"Activity {act_id} has more than one access in week {d.week}.",
                        activity_ids=[act_id],
                        service_dates=[d.service_date],
                    )
                )
            weeks_seen.add(d.week)

            # Week match
            expected_week = problem.parameters.date_to_week(d.service_date)
            if d.week != expected_week:
                issues.append(
                    CalendarConflict(
                        rule_code="DATE_WEEK_MISMATCH",
                        message=f"Service date {d.service_date} belongs to week {expected_week}, but access recorded week {d.week}.",
                        activity_ids=[act_id],
                        service_dates=[d.service_date],
                    )
                )

            # Horizon bound
            if not (problem.parameters.horizon_start <= d.service_date <= problem.parameters.horizon_end):
                issues.append(
                    CalendarConflict(
                        rule_code="DATE_OUTSIDE_HORIZON",
                        message=f"Service date {d.service_date} is outside the planning horizon.",
                        activity_ids=[act_id],
                        service_dates=[d.service_date],
                    )
                )

            # Planned start week
            release_week = problem.planned_start_week(activity)
            if d.week < release_week:
                issues.append(
                    CalendarConflict(
                        rule_code="PRE_RELEASE_WEEK",
                        message=f"Access week {d.week} precedes release week {release_week} for {act_id}.",
                        activity_ids=[act_id],
                        service_dates=[d.service_date],
                    )
                )

            if enforce_exact_planned_start_date and d.service_date < activity.planned_start_date:
                issues.append(
                    CalendarConflict(
                        rule_code="PRE_PLANNED_START_DATE",
                        message=f"Service date {d.service_date} precedes planned start date {activity.planned_start_date} for {act_id}.",
                        activity_ids=[act_id],
                        service_dates=[d.service_date],
                    )
                )

            # Contract calendar rule: eligible_dates
            rule = next((r for r in calendar.contract_rules if r.contract_number == contract.contract_number), None)
            if rule is not None and rule.eligible_dates is not None:
                if d.service_date not in rule.eligible_dates:
                    issues.append(
                        CalendarConflict(
                            rule_code="INELIGIBLE_CONTRACT_DATE",
                            message=f"Date {d.service_date} is not in contract {contract.contract_number} eligible_dates.",
                            activity_ids=[act_id],
                            service_dates=[d.service_date],
                        )
                    )

            # Line availability
            lines = affected_line_codes(problem, cache, act_id)
            for line in lines:
                maint_avail, eclo_elig = line_night(calendar, line, d.service_date)
                if not maint_avail:
                    issues.append(
                        CalendarConflict(
                            rule_code="LINE_BLACKOUT",
                            message=f"Line {line} unavailable on {d.service_date} for {act_id}.",
                            activity_ids=[act_id],
                            service_dates=[d.service_date],
                        )
                    )
                if d.eclo and not eclo_elig:
                    issues.append(
                        CalendarConflict(
                            rule_code="LINE_ECLO_BLACKOUT",
                            message=f"Line {line} forbids ECLO on {d.service_date} for {act_id}.",
                            activity_ids=[act_id],
                            service_dates=[d.service_date],
                        )
                    )

            # Protected locations availability
            protection = cache.get_protection_footprint(act_id)
            for loc_id in protection.all_protected_locations:
                loc_avail, _ = location_night(calendar, loc_id, d.service_date)
                if not loc_avail:
                    issues.append(
                        CalendarConflict(
                            rule_code="LOCATION_BLACKOUT",
                            message=f"Protected location {loc_id} unavailable on {d.service_date} for {act_id}.",
                            activity_ids=[act_id],
                            service_dates=[d.service_date],
                            location_ids=[loc_id],
                        )
                    )

            # Verify correspondence with projected AccessScheduleRow
            access_row = access_row_by_key.get((act_id, d.access_seq))
            if access_row is None:
                issues.append(
                    CalendarConflict(
                        rule_code="MISSING_PROJECTED_ACCESS_ROW",
                        message=f"No projected access row found for {act_id} sequence {d.access_seq}.",
                        activity_ids=[act_id],
                    )
                )
            else:
                if access_row.week != d.week or access_row.eclo != d.eclo or access_row.access_night != d.access_night:
                    issues.append(
                        CalendarConflict(
                            rule_code="PROJECTED_ROW_FIELD_MISMATCH",
                            message=f"Projected access row mismatch for {act_id} sequence {d.access_seq}.",
                            activity_ids=[act_id],
                        )
                    )

    # 3. Predecessor strictly earlier week
    for activity in problem.activities:
        if not activity.predecessor_activity_id:
            continue
        pred_decs = assignments_by_activity.get(activity.predecessor_activity_id, [])
        succ_decs = assignments_by_activity.get(activity.activity_id, [])
        if pred_decs and succ_decs:
            pred_last_week = max(d.week for d in pred_decs)
            succ_first_week = min(d.week for d in succ_decs)
            if succ_first_week <= pred_last_week:
                issues.append(
                    CalendarConflict(
                        rule_code="PREDECESSOR_WEEK_ORDER",
                        message=(
                            f"Successor {activity.activity_id} first week {succ_first_week} "
                            f"is not strictly after predecessor {activity.predecessor_activity_id} "
                            f"last week {pred_last_week}."
                        ),
                        activity_ids=[activity.predecessor_activity_id, activity.activity_id],
                    )
                )

    # 4. Contract Limits (weekly actual dates & nightly workfronts)
    contract_week_dates: dict[tuple[str, int], set[date]] = defaultdict(set)
    contract_date_activities: dict[tuple[str, date], set[str]] = defaultdict(set)
    for dec in calendar_assignments:
        contract_number = problem.activity(dec.activity_id).contract_number
        contract_week_dates[(contract_number, dec.week)].add(dec.service_date)
        contract_date_activities[(contract_number, dec.service_date)].add(dec.activity_id)

    for (contract_num, week), dates in contract_week_dates.items():
        limit = actual_night_limit(problem, calendar, contract_num)
        if len(dates) > limit:
            issues.append(
                CalendarConflict(
                    rule_code="ACTUAL_NIGHT_LIMIT",
                    message=f"Contract {contract_num} uses {len(dates)} actual dates in week {week}, exceeding limit {limit}.",
                    service_dates=sorted(dates),
                    required_capacity=len(dates),
                    available_capacity=limit,
                )
            )

    for (contract_num, service_date), acts in contract_date_activities.items():
        wf_limit = nightly_workfront_limit(problem, calendar, contract_num)
        if len(acts) > wf_limit:
            issues.append(
                CalendarConflict(
                    rule_code="NIGHTLY_WORKFRONT_LIMIT",
                    message=f"Contract {contract_num} runs {len(acts)} simultaneous activities on {service_date}, exceeding workfront limit {wf_limit}.",
                    activity_ids=sorted(acts),
                    service_dates=[service_date],
                    required_capacity=len(acts),
                    available_capacity=wf_limit,
                )
            )

    # 5. Physical Location / Date Possessions and Legal Mix
    # Group active activities per (location_id, service_date)
    location_date_activities: dict[tuple[str, date], set[str]] = defaultdict(set)
    for dec in calendar_assignments:
        core = cache.get_core_footprint(dec.activity_id)
        for loc_id in core.core_locations:
            location_date_activities[(loc_id, dec.service_date)].add(dec.activity_id)

    for (loc_id, service_date), acts in location_date_activities.items():
        roles = [
            problem.contract(problem.activity(a_id).contract_number).access_type
            for a_id in acts
        ]
        pm_count = sum(1 for r in roles if r == AccessType.PM)
        pc_count = sum(1 for r in roles if r == AccessType.PC)
        c_count = sum(1 for r in roles if r == AccessType.C)

        if pm_count + pc_count > 1 or 4 * pm_count + pc_count + c_count > 4:
            issues.append(
                CalendarConflict(
                    rule_code="LEGAL_MIX_VIOLATION",
                    message=(
                        f"Illegal role mix at {loc_id} on {service_date}: "
                        f"PM={pm_count}, PC={pc_count}, C={c_count}. Allowed: 1 PM, 1 PC + <=3 C, or <=4 C."
                    ),
                    activity_ids=sorted(acts),
                    service_dates=[service_date],
                    location_ids=[loc_id],
                )
            )

    # 6. Protection Footprint Safety Conflicts on Same Date
    by_date: dict[date, list[CalendarAssignment]] = defaultdict(list)
    for dec in calendar_assignments:
        by_date[dec.service_date].append(dec)

    # 6. Protection Footprint Safety Conflicts on Same Date
    conflict_pairs = build_same_date_conflict_pairs(problem, cache)
    for service_date, decs in by_date.items():
        for i, dec_a in enumerate(decs):
            id_a = dec_a.activity_id
            for dec_b in decs[i + 1 :]:
                id_b = dec_b.activity_id
                if id_a == id_b:
                    continue
                if (id_a, id_b) in conflict_pairs or (id_b, id_a) in conflict_pairs:
                    issues.append(
                        CalendarConflict(
                            rule_code="PROTECTION_CONFLICT",
                            message=(
                                f"Safety conflict between {id_a} and {id_b} on {service_date} "
                                "under conservative_demo_v1."
                            ),
                            activity_ids=[id_a, id_b],
                            service_dates=[service_date],
                        )
                    )

    # 7. Scenario Policies
    # Weekly location supply consumption: count distinct occupied dates in each week
    location_week_dates: dict[tuple[str, int], set[date]] = defaultdict(set)
    for (loc_id, service_date) in location_date_activities.keys():
        week = problem.parameters.date_to_week(service_date)
        location_week_dates[(loc_id, week)].add(service_date)

    for loc in problem.locations:
        loc_id = loc.location_id
        capacity = loc.supply_capacity
        for week in range(1, problem.parameters.horizon_weeks + 1):
            occupied_count = len(location_week_dates.get((loc_id, week), set()))
            excess = max(0, occupied_count - capacity)
            if selected_scenario == Scenario.A and excess > 0:
                issues.append(
                    CalendarConflict(
                        rule_code="SCENARIO_A_SUPPLY_EXCESS",
                        message=f"Scenario A forbids supply excess at {loc_id} in week {week} (used {occupied_count}, cap {capacity}).",
                        location_ids=[loc_id],
                    )
                )
            elif selected_scenario == Scenario.C and excess > 1:
                issues.append(
                    CalendarConflict(
                        rule_code="SCENARIO_C_EXCESS_LIMIT",
                        message=f"Scenario C limits excess to at most 1 at {loc_id} in week {week} (used {occupied_count}, cap {capacity}).",
                        location_ids=[loc_id],
                    )
                )

    if selected_scenario == Scenario.A:
        for dec in calendar_assignments:
            if dec.eclo:
                issues.append(
                    CalendarConflict(
                        rule_code="SCENARIO_A_ECLO_FORBIDDEN",
                        message=f"Scenario A forbids ECLO: found ECLO access on {dec.service_date} for {dec.activity_id}.",
                        activity_ids=[dec.activity_id],
                        service_dates=[dec.service_date],
                    )
                )

    if selected_scenario == Scenario.B:
        for activity in problem.activities:
            act_id = activity.activity_id
            contract = problem.contract(activity.contract_number)
            decs = assignments_by_activity.get(act_id, [])
            if decs:
                last_week = max(d.week for d in decs)
                finish_date = problem.parameters.week_end_date(last_week)
                if finish_date > contract.planned_completion_date:
                    issues.append(
                        CalendarConflict(
                            rule_code="SCENARIO_B_DEADLINE_BREACH",
                            message=(
                                f"Scenario B forbids overrun: activity {act_id} finishes {finish_date} "
                                f"after contract planned deadline {contract.planned_completion_date}."
                            ),
                            activity_ids=[act_id],
                        )
                    )

    if selected_scenario == Scenario.C:
        # Check that ECLO on each affected line falls inside a <= 2-week consecutive span
        line_eclo_weeks: dict[str, set[int]] = defaultdict(set)
        for dec in calendar_assignments:
            if not dec.eclo:
                continue
            for line_code in dec.line_codes:
                line_eclo_weeks[line_code].add(dec.week)

        for line_code, weeks in line_eclo_weeks.items():
            if selected_window_starts and line_code in selected_window_starts:
                start_w = selected_window_starts[line_code]
                allowed_weeks = {start_w, start_w + 1}
                if not weeks.issubset(allowed_weeks):
                    issues.append(
                        CalendarConflict(
                            rule_code="SCENARIO_C_ECLO_WINDOW_MISMATCH",
                            message=f"Line {line_code} ECLO weeks {sorted(weeks)} do not fit selected window [{start_w}, {start_w + 1}].",
                        )
                    )
            else:
                # If no explicit window was passed, check if any 2-week window covers all weeks
                sorted_weeks = sorted(weeks)
                if len(sorted_weeks) > 2 or (len(sorted_weeks) == 2 and sorted_weeks[1] - sorted_weeks[0] != 1):
                    issues.append(
                        CalendarConflict(
                            rule_code="SCENARIO_C_ECLO_WINDOW_DISCONTINUOUS",
                            message=f"Line {line_code} ECLO weeks {sorted_weeks} cannot be covered by a single 2-week window.",
                        )
                    )

    # 8. Projection Invariants
    # Check date <-> access_night mapping
    by_contract_type_week: dict[tuple[str, str, int], list[CalendarAssignment]] = defaultdict(list)
    for dec in calendar_assignments:
        act = problem.activity(dec.activity_id)
        key = (act.contract_number, act.activity_type.value, dec.week)
        by_contract_type_week[key].append(dec)

    for key, decs in by_contract_type_week.items():
        date_to_night: dict[date, int] = {}
        night_to_date: dict[int, date] = {}
        for d in decs:
            if d.service_date in date_to_night:
                if date_to_night[d.service_date] != d.access_night:
                    issues.append(
                        CalendarConflict(
                            rule_code="PROJECTION_SAME_DATE_DIFFERENT_NIGHT",
                            message=f"Same date {d.service_date} mapped to multiple access_night values for {key}.",
                            service_dates=[d.service_date],
                        )
                    )
            else:
                date_to_night[d.service_date] = d.access_night

            if d.access_night in night_to_date:
                if night_to_date[d.access_night] != d.service_date:
                    issues.append(
                        CalendarConflict(
                            rule_code="PROJECTION_DIFFERENT_DATE_SAME_NIGHT",
                            message=f"Different dates {night_to_date[d.access_night]} and {d.service_date} mapped to same access_night {d.access_night} for {key}.",
                            service_dates=[d.service_date, night_to_date[d.access_night]],
                        )
                    )
            else:
                night_to_date[d.access_night] = d.service_date

    # Check date <-> co_share_group mapping in projected occupancy rows
    # Map occupancy rows to service_date via assignment_by_key
    occ_by_loc_week: dict[tuple[str, int], list[tuple[OccupancyScheduleRow, date]]] = defaultdict(list)
    for occ in projected_occupancy_rows:
        act_decs = [d for d in assignments_by_activity.get(occ.activity_id, []) if d.week == occ.week]
        if act_decs:
            occ_by_loc_week[(occ.location_id, occ.week)].append((occ, act_decs[0].service_date))

    for (loc_id, week), items in occ_by_loc_week.items():
        date_to_group: dict[date, str] = {}
        group_to_date: dict[str, date] = {}
        for occ, dt in items:
            if dt in date_to_group:
                if date_to_group[dt] != occ.co_share_group:
                    issues.append(
                        CalendarConflict(
                            rule_code="PROJECTION_SAME_DATE_DIFFERENT_GROUP",
                            message=f"Location {loc_id} in week {week} on {dt} mapped to multiple co_share_groups.",
                            service_dates=[dt],
                            location_ids=[loc_id],
                        )
                    )
            else:
                date_to_group[dt] = occ.co_share_group

            if occ.co_share_group in group_to_date:
                if group_to_date[occ.co_share_group] != dt:
                    issues.append(
                        CalendarConflict(
                            rule_code="PROJECTION_DIFFERENT_DATE_SAME_GROUP",
                            message=f"Location {loc_id} in week {week} mapped group {occ.co_share_group} to different dates {group_to_date[occ.co_share_group]} and {dt}.",
                            service_dates=[dt, group_to_date[occ.co_share_group]],
                            location_ids=[loc_id],
                        )
                    )
            else:
                group_to_date[occ.co_share_group] = dt

    # 9. Official-row validation via validate_schedule
    weekly_summary = validate_schedule(
        problem=problem,
        scenario=selected_scenario,
        access_rows=projected_access_rows,
        occupancy_rows=projected_occupancy_rows,
        footprints=cache,
        selected_window_starts=selected_window_starts,
    )
    for issue in weekly_summary.issues:
        issues.append(
            CalendarConflict(
                rule_code=f"OFFICIAL_{issue.rule.upper()}",
                message=issue.detail,
                activity_ids=[issue.activity_id] if issue.activity_id else [],
                location_ids=[issue.location_id] if issue.location_id else [],
            )
        )

    # 10. Check results reconstruction
    results_match = True
    try:
        build_contract_results(problem, selected_scenario, projected_access_rows)
    except Exception as exc:
        results_match = False
        issues.append(
            CalendarConflict(
                rule_code="RESULTS_RECONSTRUCTION_FAILED",
                message=str(exc),
            )
        )

    calendar_passed = not any(issue.severity == "hard" for issue in issues)

    return CalendarValidationSummary(
        passed=calendar_passed and weekly_summary.local_accounting_passed and results_match,
        weekly_validation_passed=weekly_summary.local_accounting_passed,
        calendar_validation_passed=calendar_passed,
        source_results_match=results_match,
        issues=issues,
        validator_version="daily-validator-v1",
        protection_policy="conservative_demo_v1",
        safety_validation_status="UNVERIFIED",
        official_checker_status="UNAVAILABLE",
    )
