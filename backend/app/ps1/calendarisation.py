"""Assign exact service dates to a fixed, immutable weekly PS1 schedule."""

from __future__ import annotations

from collections import defaultdict
from time import monotonic

from ortools.sat.python import cp_model

from backend.app.domain_models import AccessScheduleRow, ProblemInstance
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    CalendarConflict,
    CalendarisationResult,
    CalendariseOptions,
    CalendarSolverStatus,
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
    week_dates,
)
from backend.app.ps1.scoring import affected_line_codes
from backend.app.topology import FootprintCache


def source_access_id(bundle_id: str, activity_id: str, access_seq: int) -> str:
    return f"{bundle_id}:{activity_id}:{access_seq}"


def _status(raw: cp_model.CpSolverStatus) -> CalendarSolverStatus:
    return {
        cp_model.OPTIMAL: CalendarSolverStatus.OPTIMAL,
        cp_model.FEASIBLE: CalendarSolverStatus.FEASIBLE,
        cp_model.INFEASIBLE: CalendarSolverStatus.INFEASIBLE,
        cp_model.UNKNOWN: CalendarSolverStatus.UNKNOWN,
        cp_model.MODEL_INVALID: CalendarSolverStatus.MODEL_INVALID,
    }.get(raw, CalendarSolverStatus.UNKNOWN)


def _source_maps(bundle: FixedScheduleBundle):
    accesses = {
        (row.activity_id, row.week): row for row in bundle.access_rows
    }
    groups: dict[tuple[str, int, str], str] = {}
    group_members: dict[tuple[str, int, str], list[AccessScheduleRow]] = defaultdict(list)
    for row in bundle.occupancy_rows:
        access = accesses.get((row.activity_id, row.week))
        if access is None:
            continue
        groups[(row.activity_id, row.week, row.location_id)] = row.co_share_group
        group_members[(row.location_id, row.week, row.co_share_group)].append(access)
    for members in group_members.values():
        members.sort(key=lambda item: (item.activity_id, item.access_seq))
    return groups, group_members


def calendarise(
    problem: ProblemInstance,
    bundle: FixedScheduleBundle,
    calendar_id: str,
    calendar: OperatingCalendarInput,
    commitments: list[DateCommitment] | None = None,
    options: CalendariseOptions | None = None,
) -> CalendarisationResult:
    """Fit dates without changing any field in the source schedule bundle."""

    started = monotonic()
    problem = scope_problem_to_bundle(problem, bundle)
    solve_options = options or CalendariseOptions()
    footprints = FootprintCache(problem)
    commitments = commitments or []
    commitment_map: dict[tuple[str, int], DateCommitment] = {}
    conflicts: list[CalendarConflict] = []

    from backend.app.ps1.calendar_validation import (
        validate_calendar_definition,
        validate_fixed_bundle,
    )

    source_validation = validate_fixed_bundle(problem, bundle)
    if not source_validation.passed:
        conflicts.extend(source_validation.issues)
    conflicts.extend(validate_calendar_definition(problem, calendar))

    if calendar.instance_revision_id != bundle.instance_revision_id:
        conflicts.append(
            CalendarConflict(
                rule_code="REVISION_MISMATCH",
                message="Calendar and schedule bundle refer to different instance revisions.",
            )
        )
    source_keys = {(row.activity_id, row.access_seq) for row in bundle.access_rows}
    for commitment in commitments:
        key = (commitment.activity_id, commitment.access_seq)
        if key in commitment_map:
            conflicts.append(
                CalendarConflict(
                    rule_code="DUPLICATE_COMMITMENT",
                    message=f"Access {key[0]} sequence {key[1]} has multiple commitments.",
                    activity_ids=[key[0]],
                )
            )
        elif key not in source_keys:
            conflicts.append(
                CalendarConflict(
                    rule_code="UNKNOWN_COMMITMENT",
                    message=f"Commitment refers to unknown access {key[0]} sequence {key[1]}.",
                    activity_ids=[key[0]],
                )
            )
        else:
            commitment_map[key] = commitment

    candidate_map: dict[tuple[str, int], list] = {}
    for access in bundle.access_rows:
        key = (access.activity_id, access.access_seq)
        dates = candidate_dates(problem, footprints, calendar, access)
        commitment = commitment_map.get(key)
        if commitment is not None:
            dates = [item for item in dates if item == commitment.service_date]
        candidate_map[key] = dates
        if not dates:
            conflicts.append(
                CalendarConflict(
                    rule_code="NO_ELIGIBLE_DATE",
                    message=(
                        f"{access.activity_id} access {access.access_seq} has no eligible "
                        f"service date in week {access.week}."
                    ),
                    activity_ids=[access.activity_id],
                    access_ids=[source_access_id(bundle.bundle_id, *key)],
                    service_dates=(
                        [commitment.service_date] if commitment is not None else []
                    ),
                )
            )

    groups_by_access_location, group_members = _source_maps(bundle)
    for (location_id, week, group), members in group_members.items():
        common = set(candidate_map[(members[0].activity_id, members[0].access_seq)])
        for member in members[1:]:
            common &= set(candidate_map[(member.activity_id, member.access_seq)])
        if not common:
            conflicts.append(
                CalendarConflict(
                    rule_code="SHARED_GROUP_NO_COMMON_DATE",
                    message=(
                        f"Shared group {group} at {location_id} in week {week} has no "
                        "date eligible for every member."
                    ),
                    activity_ids=sorted({member.activity_id for member in members}),
                    location_ids=[location_id],
                )
            )

    # Resolve the transitive equality created by possession groups before the
    # solver so fixed-source contradictions produce useful evidence.
    parent = {
        (row.activity_id, row.access_seq): (row.activity_id, row.access_seq)
        for row in bundle.access_rows
    }

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(first, second):
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parent[second_root] = first_root

    for members in group_members.values():
        first_key = (members[0].activity_id, members[0].access_seq)
        for member in members[1:]:
            union(first_key, (member.activity_id, member.access_seq))
    components: dict[tuple[str, int], list[AccessScheduleRow]] = defaultdict(list)
    for access in bundle.access_rows:
        components[find((access.activity_id, access.access_seq))].append(access)
    for members in components.values():
        if len(members) < 2:
            continue
        common_dates = set(candidate_map[(members[0].activity_id, members[0].access_seq)])
        for member in members[1:]:
            common_dates &= set(candidate_map[(member.activity_id, member.access_seq)])
        if not common_dates:
            conflicts.append(
                CalendarConflict(
                    rule_code="SHARING_COMPONENT_NO_COMMON_DATE",
                    message="Transitively linked possession groups have no common eligible date.",
                    activity_ids=sorted({member.activity_id for member in members}),
                )
            )
        by_contract = defaultdict(list)
        for member in members:
            by_contract[problem.activity(member.activity_id).contract_number].append(member)
        for contract_number, contract_members in by_contract.items():
            limit = nightly_workfront_limit(problem, calendar, contract_number)
            if len(contract_members) > limit:
                conflicts.append(
                    CalendarConflict(
                        rule_code="SHARING_EXCEEDS_WORKFRONTS",
                        message=(
                            f"Fixed sharing forces {len(contract_members)} accesses for "
                            f"contract {contract_number} onto one date, above its limit {limit}."
                        ),
                        activity_ids=sorted(
                            {member.activity_id for member in contract_members}
                        ),
                        required_capacity=len(contract_members),
                        available_capacity=limit,
                    )
                )
        for index, first in enumerate(members):
            for second in members[index + 1 :]:
                if not can_share_service_date(
                    footprints, first, second, groups_by_access_location
                ):
                    conflicts.append(
                        CalendarConflict(
                            rule_code="FIXED_SHARING_PROTECTION_CONFLICT",
                            message=(
                                f"Fixed sharing aligns {first.activity_id} and "
                                f"{second.activity_id}, but conservative_demo_v1 forbids "
                                "them from using one service date."
                            ),
                            activity_ids=[first.activity_id, second.activity_id],
                        )
                    )

    if conflicts:
        return CalendarisationResult(
            solver_status=CalendarSolverStatus.PRECHECK_FAILED,
            complete=False,
            conflicts=conflicts,
            wall_time_seconds=monotonic() - started,
            assumed_calendar=calendar.assumed_calendar,
            assumptions=calendar.assumptions,
        )

    model = cp_model.CpModel()
    assignment: dict[tuple[str, int, object], cp_model.IntVar] = {}
    day_var: dict[tuple[str, int], cp_model.IntVar] = {}

    for access in bundle.access_rows:
        key = (access.activity_id, access.access_seq)
        week_start = problem.parameters.week_start_date(access.week)
        vars_for_access: list[cp_model.IntVar] = []
        weighted_days = []
        for service_date in candidate_map[key]:
            variable = model.new_bool_var(
                f"date[{access.activity_id},{access.access_seq},{service_date}]"
            )
            assignment[(access.activity_id, access.access_seq, service_date)] = variable
            vars_for_access.append(variable)
            weighted_days.append((service_date - week_start).days * variable)
        model.add(sum(vars_for_access) == 1)
        selected_day = model.new_int_var(0, 6, f"day[{access.activity_id},{access.access_seq}]")
        model.add(selected_day == sum(weighted_days))
        day_var[key] = selected_day

    # A scoped possession group's members must use one global night.
    for members in group_members.values():
        first = members[0]
        for member in members[1:]:
            model.add(
                day_var[(first.activity_id, first.access_seq)]
                == day_var[(member.activity_id, member.access_seq)]
            )

    # Each occupied source group counts once against its location/date capacity.
    groups_by_location_week: dict[tuple[str, int], list] = defaultdict(list)
    for group_key in group_members:
        groups_by_location_week[(group_key[0], group_key[1])].append(group_key)
    for (location_id, week), group_keys in groups_by_location_week.items():
        for service_date in week_dates(problem, week):
            group_on_date: list[cp_model.IntVar] = []
            for group_key in group_keys:
                representative = group_members[group_key][0]
                variable = assignment.get(
                    (representative.activity_id, representative.access_seq, service_date)
                )
                if variable is not None:
                    group_on_date.append(variable)
            _available, capacity = location_night(calendar, location_id, service_date)
            model.add(sum(group_on_date) <= capacity)

    accesses_by_contract_week: dict[tuple[str, int], list[AccessScheduleRow]] = defaultdict(list)
    for access in bundle.access_rows:
        contract_number = problem.activity(access.activity_id).contract_number
        accesses_by_contract_week[(contract_number, access.week)].append(access)
    for (contract_number, week), accesses in accesses_by_contract_week.items():
        date_used: list[cp_model.IntVar] = []
        for service_date in week_dates(problem, week):
            on_date = [
                assignment[(access.activity_id, access.access_seq, service_date)]
                for access in accesses
                if (access.activity_id, access.access_seq, service_date) in assignment
            ]
            if not on_date:
                continue
            model.add(
                sum(on_date)
                <= nightly_workfront_limit(problem, calendar, contract_number)
            )
            used = model.new_bool_var(
                f"contract_date[{contract_number},{week},{service_date}]"
            )
            for variable in on_date:
                model.add(variable <= used)
            model.add(used <= sum(on_date))
            date_used.append(used)
        model.add(
            sum(date_used) <= actual_night_limit(problem, calendar, contract_number)
        )

    # Conservative date-level protection conflicts.
    accesses_by_week: dict[int, list[AccessScheduleRow]] = defaultdict(list)
    for access in bundle.access_rows:
        accesses_by_week[access.week].append(access)
    for accesses in accesses_by_week.values():
        for index, first in enumerate(accesses):
            for second in accesses[index + 1 :]:
                if not can_share_service_date(
                    footprints, first, second, groups_by_access_location
                ):
                    model.add(
                        day_var[(first.activity_id, first.access_seq)]
                        != day_var[(second.activity_id, second.access_seq)]
                    )

    # The weekly source already uses strict predecessor weeks. Keep an explicit
    # exact-date condition so future source readers cannot weaken it silently.
    rows_by_activity: dict[str, list[AccessScheduleRow]] = defaultdict(list)
    for access in bundle.access_rows:
        rows_by_activity[access.activity_id].append(access)
    for activity in problem.activities:
        if not activity.predecessor_activity_id:
            continue
        for predecessor in rows_by_activity[activity.predecessor_activity_id]:
            for successor in rows_by_activity[activity.activity_id]:
                pred_start = problem.parameters.week_start_date(predecessor.week).toordinal()
                succ_start = problem.parameters.week_start_date(successor.week).toordinal()
                model.add(
                    pred_start + day_var[(predecessor.activity_id, predecessor.access_seq)]
                    < succ_start + day_var[(successor.activity_id, successor.access_seq)]
                )

    # Multi-objective operational dispatch:
    # 1. Workload Leveling: Minimize peak nightly access load per week.
    # 2. Inter-Access Spacing: Penalize consecutive nights for the same contract in a week.
    # 3. Weekend ECLO: Prioritize Friday and Saturday nights for ECLO possessions.
    # 4. Tie-Breaker: Maintain minimal early-week bias for reproducible determinism.
    obj_terms: list = []

    # 1. Workload Leveling (Peak Night Load Minimization & Nightly Dispersion)
    for week, accesses in accesses_by_week.items():
        peak_load = model.new_int_var(0, len(accesses), f"peak_load[{week}]")
        for service_date in week_dates(problem, week):
            on_date = [
                assignment[(a.activity_id, a.access_seq, service_date)]
                for a in accesses
                if (a.activity_id, a.access_seq, service_date) in assignment
            ]
            if on_date:
                model.add(peak_load >= sum(on_date))
                overload = model.new_int_var(0, len(on_date), f"overload[{service_date}]")
                model.add(overload >= sum(on_date) - 1)
                obj_terms.append(overload * 10)
        obj_terms.append(peak_load * 30)

    # 2. Contract Inter-Access Spacing (Prevent Fatigue & Allow Curing/Repositioning)
    for (contract_number, week), accesses in accesses_by_contract_week.items():
        dates_in_week = sorted(week_dates(problem, week))
        for i in range(len(dates_in_week) - 1):
            d1, d2 = dates_in_week[i], dates_in_week[i + 1]
            for a1 in accesses:
                for a2 in accesses:
                    if (a1.activity_id, a1.access_seq) >= (a2.activity_id, a2.access_seq):
                        continue
                    v1 = assignment.get((a1.activity_id, a1.access_seq, d1))
                    v2 = assignment.get((a2.activity_id, a2.access_seq, d2))
                    if v1 is not None and v2 is not None:
                        consecutive = model.new_bool_var(
                            f"consec[{contract_number},{week},{d1},{a1.activity_id},{a2.activity_id}]"
                        )
                        model.add(consecutive >= v1 + v2 - 1)
                        obj_terms.append(consecutive * 20)

    # 3. Weekend / ECLO Preferences (Friday & Saturday Preferred)
    for access in bundle.access_rows:
        if access.eclo:
            for sdate in candidate_map[(access.activity_id, access.access_seq)]:
                if sdate.weekday() not in (4, 5):  # 4 = Friday, 5 = Saturday
                    var = assignment[(access.activity_id, access.access_seq, sdate)]
                    obj_terms.append(var * 25)

    model.minimize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solve_options.time_limit_seconds
    solver.parameters.num_search_workers = solve_options.num_search_workers
    solver.parameters.random_seed = solve_options.random_seed
    raw_status = solver.solve(model)
    solver_status = _status(raw_status)
    if raw_status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return CalendarisationResult(
            solver_status=solver_status,
            complete=False,
            conflicts=[
                CalendarConflict(
                    rule_code=(
                        "FIXED_SCHEDULE_INFEASIBLE"
                        if raw_status == cp_model.INFEASIBLE
                        else "CALENDAR_SEARCH_INCOMPLETE"
                    ),
                    message=(
                        "The fixed source schedule cannot fit the selected calendar."
                        if raw_status == cp_model.INFEASIBLE
                        else "The date solver stopped without finding a complete assignment."
                    ),
                    activity_ids=sorted({row.activity_id for row in bundle.access_rows}),
                )
            ],
            wall_time_seconds=monotonic() - started,
            assumed_calendar=calendar.assumed_calendar,
            assumptions=calendar.assumptions,
        )

    result_rows: list[CalendarAssignment] = []
    for access in sorted(
        bundle.access_rows, key=lambda item: (item.week, item.activity_id, item.access_seq)
    ):
        key = (access.activity_id, access.access_seq)
        service_date = next(
            item
            for item in candidate_map[key]
            if solver.value(assignment[(access.activity_id, access.access_seq, item)])
        )
        activity = problem.activity(access.activity_id)
        contract = problem.contract(activity.contract_number)
        core = footprints.get_core_footprint(access.activity_id)
        result_rows.append(
            CalendarAssignment(
                access_id=source_access_id(bundle.bundle_id, *key),
                activity_id=access.activity_id,
                access_seq=access.access_seq,
                week=access.week,
                access_night=access.access_night,
                eclo=access.eclo,
                service_date=service_date,
                global_night_id=f"{calendar_id}:{service_date.isoformat()}",
                contract_number=contract.contract_number,
                contract_description=contract.contract_description,
                line_codes=affected_line_codes(problem, footprints, access.activity_id),
                location_ids=core.core_locations,
            )
        )

    from backend.app.ps1.calendar_validation import validate_calendarisation

    validation = validate_calendarisation(
        problem, bundle, calendar, commitments, result_rows
    )
    if not validation.passed:
        return CalendarisationResult(
            solver_status=solver_status,
            complete=False,
            conflicts=validation.issues,
            validation=validation,
            wall_time_seconds=monotonic() - started,
            assumed_calendar=calendar.assumed_calendar,
            assumptions=calendar.assumptions,
        )
    return CalendarisationResult(
        solver_status=solver_status,
        complete=True,
        assignments=result_rows,
        validation=validation,
        wall_time_seconds=monotonic() - started,
        preference_value=int(round(solver.objective_value)),
        assumed_calendar=calendar.assumed_calendar,
        assumptions=calendar.assumptions,
    )
