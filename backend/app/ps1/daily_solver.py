"""Date-first daily-integrated OR-Tools CP-SAT solver for official PS1 Scenarios A, B, and C."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from math import ceil
from time import monotonic

from ortools.sat.python import cp_model

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    OccupancyScheduleRow,
    ProblemInstance,
)
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    DatedAccessDecision,
    OperatingCalendarInput,
    demo_calendar,
)
from backend.app.ps1.calendar_policy import (
    actual_night_limit,
    build_candidate_date_sets,
    build_same_date_conflict_pairs,
    location_night,
    nightly_workfront_limit,
    week_dates,
)
from backend.app.ps1.daily_validation import validate_dated_schedule
from backend.app.ps1.models import (
    PS1SolveOptions,
    PS1SolveResult,
    PS1SolverStatus,
    Scenario,
    SolveMetrics,
    ValidationSummary,
    coerce_scenario,
)
from backend.app.ps1.schedule_projection import (
    ProjectedSchedule,
    build_calendar_assignments,
    project_dated_schedule,
)
from backend.app.ps1.scoring import (
    affected_line_codes,
    build_contract_results,
    build_eclo_summary,
    compute_score,
)
from backend.app.ps1.validation import validate_schedule
from backend.app.topology import FootprintCache


@dataclass
class _DailyModelArtifacts:
    model: cp_model.CpModel
    scenario: Scenario
    footprints: FootprintCache
    calendar: OperatingCalendarInput

    # Primary date decisions: scheduled[(activity_id, service_date)], eclo[(activity_id, service_date)]
    scheduled: dict[tuple[str, date], cp_model.IntVar] = field(default_factory=dict)
    eclo: dict[tuple[str, date], cp_model.IntVar] = field(default_factory=dict)

    # Derived weekly state
    active_week: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    first_week: dict[str, cp_model.IntVar] = field(default_factory=dict)
    last_week: dict[str, cp_model.IntVar] = field(default_factory=dict)

    # Contract/date state
    contract_date_used: dict[tuple[str, date], cp_model.IntVar] = field(default_factory=dict)

    # Physical possession state
    location_date_used: dict[tuple[str, date], cp_model.IntVar] = field(default_factory=dict)

    # Scenario scoring
    excess: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    lateness_days: dict[str, cp_model.IntVar] = field(default_factory=dict)
    window_start: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)

    # Metadata & helpers
    eligible_dates: dict[str, list[date]] = field(default_factory=dict)
    eligible_eclo_dates: dict[str, set[date]] = field(default_factory=dict)
    affected_lines: dict[str, list[str]] = field(default_factory=dict)
    hint_variables: list[cp_model.IntVar] = field(default_factory=list)

    objective_scaled: cp_model.LinearExpr | int = 0
    search_objective: cp_model.LinearExpr | int = 0
    objective_scale: int = 1
    maximum_secondary_cost: int = 0


def _status(status: cp_model.CpSolverStatus) -> PS1SolverStatus:
    mapping = {
        cp_model.OPTIMAL: PS1SolverStatus.OPTIMAL,
        cp_model.FEASIBLE: PS1SolverStatus.FEASIBLE,
        cp_model.INFEASIBLE: PS1SolverStatus.INFEASIBLE,
        cp_model.MODEL_INVALID: PS1SolverStatus.MODEL_INVALID,
        cp_model.UNKNOWN: PS1SolverStatus.UNKNOWN,
    }
    return mapping.get(status, PS1SolverStatus.UNKNOWN)


def _has_solution(status: cp_model.CpSolverStatus) -> bool:
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def _configure_solver(
    options: PS1SolveOptions,
    time_limit_seconds: float,
) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, time_limit_seconds)
    solver.parameters.num_search_workers = options.num_search_workers
    solver.parameters.random_seed = options.random_seed
    solver.parameters.log_search_progress = options.log_search_progress
    return solver


def _get_configure_solver():
    import sys
    solver_mod = sys.modules.get("backend.app.ps1.solver")
    if solver_mod and hasattr(solver_mod, "_configure_solver"):
        return getattr(solver_mod, "_configure_solver")
    return _configure_solver


def _build_daily_model(
    problem: ProblemInstance,
    scenario: Scenario,
    calendar: OperatingCalendarInput,
    footprints: FootprintCache,
    eligible_dates: dict[str, list[date]],
    eligible_eclo_dates: dict[str, set[date]],
    conflict_pairs: set[tuple[str, str]],
) -> _DailyModelArtifacts:
    """Build the single date-first CP-SAT optimization model."""

    model = cp_model.CpModel()
    horizon = problem.parameters.horizon_weeks
    artifacts = _DailyModelArtifacts(
        model=model,
        scenario=scenario,
        footprints=footprints,
        calendar=calendar,
        eligible_dates=eligible_dates,
        eligible_eclo_dates=eligible_eclo_dates,
    )

    def new_bool(name: str) -> cp_model.IntVar:
        var = model.new_bool_var(name)
        artifacts.hint_variables.append(var)
        return var

    def new_int(lower: int, upper: int, name: str) -> cp_model.IntVar:
        var = model.new_int_var(lower, upper, name)
        artifacts.hint_variables.append(var)
        return var

    # 1. Decision variables per eligible activity and date
    for activity in problem.activities:
        act_id = activity.activity_id
        contract = problem.contract(activity.contract_number)
        dates = eligible_dates.get(act_id, [])
        eclo_dates = eligible_eclo_dates.get(act_id, set())
        artifacts.affected_lines[act_id] = affected_line_codes(problem, footprints, act_id)

        all_z: list[cp_model.IntVar] = []
        all_e: list[cp_model.IntVar] = []
        dates_by_week: dict[int, list[cp_model.IntVar]] = defaultdict(list)

        for dt in dates:
            z = new_bool(f"scheduled[{act_id},{dt.isoformat()}]")
            artifacts.scheduled[(act_id, dt)] = z
            all_z.append(z)

            w = problem.parameters.date_to_week(dt)
            dates_by_week[w].append(z)

            e = new_bool(f"eclo[{act_id},{dt.isoformat()}]")
            artifacts.eclo[(act_id, dt)] = e
            all_e.append(e)

            model.add(e <= z)
            if dt not in eclo_dates or scenario == Scenario.A:
                model.add(e == 0)

        # Workload satisfaction
        model.add(
            2 * cp_model.LinearExpr.sum(all_z) + cp_model.LinearExpr.sum(all_e)
            >= activity.doubled_workload
        )

        # At most one access per activity per week + derived active_week[act, w]
        for w in range(1, horizon + 1):
            x_w = new_bool(f"active_week[{act_id},{w}]")
            artifacts.active_week[(act_id, w)] = x_w
            week_vars = dates_by_week.get(w, [])
            if week_vars:
                model.add(cp_model.LinearExpr.sum(week_vars) == x_w)
            else:
                model.add(x_w == 0)

        # First and last week
        first = new_int(1, horizon, f"first_week[{act_id}]")
        last = new_int(1, horizon, f"last_week[{act_id}]")
        artifacts.first_week[act_id] = first
        artifacts.last_week[act_id] = last
        model.add_min_equality(
            first,
            [
                (horizon + 1) - (horizon + 1 - w) * artifacts.active_week[(act_id, w)]
                for w in range(1, horizon + 1)
            ],
        )
        model.add_max_equality(
            last,
            [w * artifacts.active_week[(act_id, w)] for w in range(1, horizon + 1)],
        )

        # Completion lateness
        max_lateness = max(
            0,
            (problem.parameters.horizon_end - contract.planned_completion_date).days,
        )
        lateness = new_int(0, max_lateness, f"lateness_days[{act_id}]")
        artifacts.lateness_days[act_id] = lateness
        deadline_offset = (
            contract.planned_completion_date - problem.parameters.horizon_start
        ).days
        model.add_max_equality(lateness, [0, 7 * last - 1 - deadline_offset])
        if scenario == Scenario.B:
            model.add(lateness == 0)

    # 2. Strict-week predecessor constraints
    for activity in problem.activities:
        if activity.predecessor_activity_id:
            model.add(
                artifacts.first_week[activity.activity_id]
                > artifacts.last_week[activity.predecessor_activity_id]
            )

    # 3. Contract date usage, weekly limits, and nightly workfronts
    for contract in problem.contracts:
        c_num = contract.contract_number
        c_acts = [a for a in problem.activities if a.contract_number == c_num]
        k_limit = actual_night_limit(problem, calendar, c_num)
        wf_limit = nightly_workfront_limit(problem, calendar, c_num)

        for w in range(1, horizon + 1):
            week_u_vars: list[cp_model.IntVar] = []
            for dt in week_dates(problem, w):
                possible_acts = [
                    a.activity_id
                    for a in c_acts
                    if (a.activity_id, dt) in artifacts.scheduled
                ]
                if not possible_acts:
                    continue

                u = new_bool(f"contract_date[{c_num},{dt.isoformat()}]")
                artifacts.contract_date_used[(c_num, dt)] = u
                week_u_vars.append(u)

                z_vars = [artifacts.scheduled[(a_id, dt)] for a_id in possible_acts]
                for z in z_vars:
                    model.add(z <= u)
                model.add(u <= cp_model.LinearExpr.sum(z_vars))
                # Nightly workfront limit
                model.add(cp_model.LinearExpr.sum(z_vars) <= wf_limit)

            # Weekly actual-night limit
            if week_u_vars:
                model.add(cp_model.LinearExpr.sum(week_u_vars) <= k_limit)

    # 4. Physical location-date possessions, legal mix, and weekly supply
    activities_by_location: dict[str, list[str]] = defaultdict(list)
    for activity in problem.activities:
        core = footprints.get_core_footprint(activity.activity_id)
        for loc_id in core.core_locations:
            activities_by_location[loc_id].append(activity.activity_id)

    for loc in problem.locations:
        loc_id = loc.location_id
        supply = loc.supply_capacity
        candidates = activities_by_location.get(loc_id, [])

        for w in range(1, horizon + 1):
            week_loc_vars: list[cp_model.IntVar] = []
            for dt in week_dates(problem, w):
                available, _ = location_night(calendar, loc_id, dt)
                possible_acts = [
                    a_id
                    for a_id in candidates
                    if (a_id, dt) in artifacts.scheduled
                ]
                if not possible_acts or not available:
                    continue

                loc_used = new_bool(f"loc_used[{loc_id},{dt.isoformat()}]")
                artifacts.location_date_used[(loc_id, dt)] = loc_used
                week_loc_vars.append(loc_used)

                all_z: list[cp_model.IntVar] = []
                pm_vars: list[cp_model.IntVar] = []
                pc_vars: list[cp_model.IntVar] = []
                c_vars: list[cp_model.IntVar] = []

                for a_id in possible_acts:
                    z = artifacts.scheduled[(a_id, dt)]
                    all_z.append(z)
                    model.add(z <= loc_used)
                    role = problem.contract(problem.activity(a_id).contract_number).access_type
                    if role == AccessType.PM:
                        pm_vars.append(z)
                    elif role == AccessType.PC:
                        pc_vars.append(z)
                    else:
                        c_vars.append(z)

                model.add(loc_used <= cp_model.LinearExpr.sum(all_z))

                # Legal mix constraints:
                # PM + PC <= loc_used
                # 4 PM + PC + C <= 4 loc_used
                pm_expr = cp_model.LinearExpr.sum(pm_vars)
                pc_expr = cp_model.LinearExpr.sum(pc_vars)
                c_expr = cp_model.LinearExpr.sum(c_vars)
                model.add(pm_expr + pc_expr <= loc_used)
                model.add(4 * pm_expr + pc_expr + c_expr <= 4 * loc_used)

            # Weekly location supply consumption
            occupied_expr = cp_model.LinearExpr.sum(week_loc_vars)
            if scenario == Scenario.A:
                model.add(occupied_expr <= supply)
                excess = new_int(0, 0, f"excess[{loc_id},{w}]")
                model.add(excess == 0)
                artifacts.excess[(loc_id, w)] = excess
            elif scenario == Scenario.C:
                model.add(occupied_expr <= supply + 1)
                excess = new_int(0, 1, f"excess[{loc_id},{w}]")
                model.add_max_equality(excess, [0, occupied_expr - supply])
                artifacts.excess[(loc_id, w)] = excess
            else:  # Scenario B
                max_excess = max(0, 7 - supply)
                excess = new_int(0, max_excess, f"excess[{loc_id},{w}]")
                model.add_max_equality(excess, [0, occupied_expr - supply])
                artifacts.excess[(loc_id, w)] = excess

    # 5. Protection Footprint Conflicts on Same Date
    for (id_a, id_b) in conflict_pairs:
        common_dates = set(eligible_dates.get(id_a, [])) & set(eligible_dates.get(id_b, []))
        for dt in common_dates:
            if (id_a, dt) in artifacts.scheduled and (id_b, dt) in artifacts.scheduled:
                model.add(artifacts.scheduled[(id_a, dt)] + artifacts.scheduled[(id_b, dt)] <= 1)

    # 6. Scenario C Line-Specific ECLO Windows
    if scenario == Scenario.C:
        for line in problem.lines:
            line_code = line.line_code
            starts: list[cp_model.IntVar] = []
            for start_week in range(1, horizon + 1):
                window_var = new_bool(f"eclo_window[{line_code},{start_week}]")
                artifacts.window_start[(line_code, start_week)] = window_var
                starts.append(window_var)

                relevant_eclo = [
                    artifacts.eclo[(a.activity_id, dt)]
                    for a in problem.activities
                    if line_code in artifacts.affected_lines[a.activity_id]
                    for dt in eligible_dates.get(a.activity_id, [])
                    if problem.parameters.date_to_week(dt) in (start_week, start_week + 1)
                    and (a.activity_id, dt) in artifacts.eclo
                ]
                if relevant_eclo:
                    model.add(window_var <= cp_model.LinearExpr.sum(relevant_eclo))
                else:
                    model.add(window_var == 0)
            model.add(cp_model.LinearExpr.sum(starts) <= 1)

        for activity in problem.activities:
            act_id = activity.activity_id
            for dt in eligible_dates.get(act_id, []):
                if (act_id, dt) not in artifacts.eclo:
                    continue
                w = problem.parameters.date_to_week(dt)
                for line_code in artifacts.affected_lines[act_id]:
                    containing_windows = [artifacts.window_start[(line_code, w)]]
                    if w > 1:
                        containing_windows.append(artifacts.window_start[(line_code, w - 1)])
                    model.add(
                        artifacts.eclo[(act_id, dt)] <= cp_model.LinearExpr.sum(containing_windows)
                    )

    # 7. Objectives and Scaling
    weighted_lateness_scaled = cp_model.LinearExpr.sum(
        [
            problem.contract(activity.contract_number).score_weight
            * (10 + {1: 3, 2: 2, 3: 0}[int(activity.activity_priority)])
            * artifacts.lateness_days[activity.activity_id]
            for activity in problem.activities
        ]
    )
    total_excess = cp_model.LinearExpr.sum(list(artifacts.excess.values()))
    total_eclo = cp_model.LinearExpr.sum(list(artifacts.eclo.values()))
    if scenario == Scenario.A:
        artifacts.objective_scaled = weighted_lateness_scaled
    elif scenario == Scenario.B:
        artifacts.objective_scaled = 70 * total_excess + 50 * total_eclo
    else:
        artifacts.objective_scaled = (
            weighted_lateness_scaled + 70 * total_excess + 50 * total_eclo
        )

    # Secondary tie-breakers:
    # Level 2: minimize total access rows (prefer ECLO efficiency when official score is tied)
    # Level 3: deterministic early-date tie-breaker
    total_accesses = cp_model.LinearExpr.sum(list(artifacts.scheduled.values()))
    maximum_accesses = sum(len(d) for d in artifacts.eligible_dates.values())

    max_day_offset = horizon * 7
    date_pref_terms: list[cp_model.LinearExpr] = []
    for (act_id, dt), z_var in artifacts.scheduled.items():
        offset = (dt - problem.parameters.horizon_start).days
        date_pref_terms.append(offset * z_var)

    max_date_pref = maximum_accesses * max_day_offset
    calendar_secondary = cp_model.LinearExpr.sum(date_pref_terms)

    access_secondary = (max_date_pref + 1) * total_accesses + calendar_secondary
    access_secondary_max = (max_date_pref + 1) * maximum_accesses + max_date_pref

    artifacts.maximum_secondary_cost = access_secondary_max
    artifacts.objective_scale = access_secondary_max + 1
    artifacts.search_objective = (
        artifacts.objective_scale * artifacts.objective_scaled + access_secondary
    )

    return artifacts


def _extract_dated_decisions(
    problem: ProblemInstance,
    artifacts: _DailyModelArtifacts,
    solver: cp_model.CpSolver,
) -> list[DatedAccessDecision]:
    dated_decisions: list[DatedAccessDecision] = []
    for activity in problem.activities:
        act_id = activity.activity_id
        for dt in sorted(artifacts.eligible_dates.get(act_id, [])):
            if solver.value(artifacts.scheduled[(act_id, dt)]):
                is_eclo = bool(
                    (act_id, dt) in artifacts.eclo
                    and solver.value(artifacts.eclo[(act_id, dt)])
                )
                week = problem.parameters.date_to_week(dt)
                dated_decisions.append(
                    DatedAccessDecision(
                        activity_id=act_id,
                        service_date=dt,
                        week=week,
                        eclo=is_eclo,
                    )
                )
    return dated_decisions


def _empty_daily_result(
    problem: ProblemInstance,
    scenario: Scenario,
    status: PS1SolverStatus,
    feasibility_status: PS1SolverStatus,
    feasibility_seconds: float,
    wall_seconds: float,
    calendar_assumed: bool = False,
    calendar_assumptions: list[str] | None = None,
) -> PS1SolveResult:
    validation = validate_schedule(problem, scenario, [], [])
    return PS1SolveResult(
        scenario=scenario,
        status=status,
        has_incumbent=False,
        validation=validation,
        calendar_assumed=calendar_assumed,
        calendar_assumptions=calendar_assumptions or [],
        solve_metrics=SolveMetrics(
            wall_time_seconds=wall_seconds,
            feasibility_time_seconds=feasibility_seconds,
            improvement_time_seconds=0.0,
            feasibility_status=feasibility_status,
        ),
    )


def solve_daily_ps1(
    problem: ProblemInstance,
    scenario: Scenario | str,
    options: PS1SolveOptions | None = None,
    calendar: OperatingCalendarInput | None = None,
) -> PS1SolveResult:
    """Solve one PS1 scenario directly in the real calendar date space."""

    selected_scenario = coerce_scenario(scenario)
    solve_options = options or PS1SolveOptions()
    started = monotonic()

    calendar_assumed = False
    calendar_assumptions: list[str] = []
    if calendar is None:
        calendar = demo_calendar("assumed_demo")
        calendar_assumed = True
        calendar_assumptions = list(calendar.assumptions)
    else:
        calendar_assumed = calendar.assumed_calendar
        calendar_assumptions = list(calendar.assumptions)

    footprints = FootprintCache(problem)

    eligible_dates, eligible_eclo_dates = build_candidate_date_sets(
        problem=problem,
        footprints=footprints,
        calendar=calendar,
        scenario=selected_scenario,
        enforce_exact_planned_start_date=solve_options.enforce_exact_planned_start_date,
    )

    conflict_pairs = build_same_date_conflict_pairs(problem, footprints)

    artifacts = _build_daily_model(
        problem=problem,
        scenario=selected_scenario,
        calendar=calendar,
        footprints=footprints,
        eligible_dates=eligible_dates,
        eligible_eclo_dates=eligible_eclo_dates,
        conflict_pairs=conflict_pairs,
    )

    remaining_before_feasibility = max(
        0.001,
        solve_options.time_limit_seconds - (monotonic() - started),
    )
    feasibility_limit = min(
        remaining_before_feasibility,
        solve_options.feasibility_time_limit_seconds,
    )
    configure_solver = _get_configure_solver()
    feasibility_solver = configure_solver(solve_options, feasibility_limit)
    feasibility_started = monotonic()
    feasibility_raw_status = feasibility_solver.solve(artifacts.model)
    feasibility_seconds = monotonic() - feasibility_started
    feasibility_status = _status(feasibility_raw_status)

    remaining_after_feasibility = solve_options.time_limit_seconds - (
        monotonic() - started
    )
    if (
        feasibility_raw_status == cp_model.UNKNOWN
        and remaining_after_feasibility > 0.001
    ):
        retry_solver = configure_solver(solve_options, remaining_after_feasibility)
        retry_started = monotonic()
        feasibility_raw_status = retry_solver.solve(artifacts.model)
        feasibility_seconds += monotonic() - retry_started
        feasibility_solver = retry_solver
        feasibility_status = _status(feasibility_raw_status)

    if not _has_solution(feasibility_raw_status):
        return _empty_daily_result(
            problem,
            selected_scenario,
            feasibility_status,
            feasibility_status,
            feasibility_seconds,
            monotonic() - started,
            calendar_assumed=calendar_assumed,
            calendar_assumptions=calendar_assumptions,
        )

    chosen_solver = feasibility_solver
    result_status = PS1SolverStatus.FEASIBLE
    improvement_status: PS1SolverStatus | None = None
    improvement_seconds = 0.0
    objective_bound_scaled: float | None = None

    remaining = solve_options.time_limit_seconds - (monotonic() - started)
    if solve_options.optimize and remaining > 0.001:
        for variable in artifacts.hint_variables:
            artifacts.model.add_hint(variable, feasibility_solver.value(variable))
        artifacts.model.minimize(artifacts.search_objective)
        improvement_solver = configure_solver(solve_options, remaining)
        improvement_started = monotonic()
        improvement_raw_status = improvement_solver.solve(artifacts.model)
        improvement_seconds = monotonic() - improvement_started
        improvement_status = _status(improvement_raw_status)
        if _has_solution(improvement_raw_status):
            chosen_solver = improvement_solver
            result_status = improvement_status
        if improvement_raw_status in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
            cp_model.UNKNOWN,
        ):
            combined_bound = improvement_solver.best_objective_bound
            objective_bound_scaled = float(
                max(
                    0,
                    ceil(
                        (
                            combined_bound
                            - artifacts.maximum_secondary_cost
                        )
                        / artifacts.objective_scale
                        - 1e-9
                    ),
                )
            )

    dated_decisions = _extract_dated_decisions(problem, artifacts, chosen_solver)

    projected = project_dated_schedule(
        problem=problem,
        scenario=selected_scenario,
        dated_accesses=dated_decisions,
        footprints=artifacts.footprints,
    )

    calendar_assignments = build_calendar_assignments(
        problem=problem,
        projected=projected,
        calendar_id=calendar.instance_revision_id or "integrated",
        footprints=artifacts.footprints,
    )

    selected_windows = {
        line_code: start_week
        for (line_code, start_week), variable in artifacts.window_start.items()
        if chosen_solver.value(variable)
    }

    daily_validation = validate_dated_schedule(
        problem=problem,
        scenario=selected_scenario,
        calendar=calendar,
        calendar_assignments=calendar_assignments,
        projected_access_rows=projected.access_rows,
        projected_occupancy_rows=projected.occupancy_rows,
        footprints=artifacts.footprints,
        enforce_exact_planned_start_date=solve_options.enforce_exact_planned_start_date,
        selected_window_starts=selected_windows,
    )

    official_validation = validate_schedule(
        problem=problem,
        scenario=selected_scenario,
        access_rows=projected.access_rows,
        occupancy_rows=projected.occupancy_rows,
        footprints=artifacts.footprints,
        selected_window_starts=selected_windows,
    )

    total_seconds = monotonic() - started
    metrics = SolveMetrics(
        wall_time_seconds=total_seconds,
        feasibility_time_seconds=feasibility_seconds,
        improvement_time_seconds=improvement_seconds,
        feasibility_status=feasibility_status,
        improvement_status=improvement_status,
        objective_bound_scaled=objective_bound_scaled,
        objective_bound_score=(
            objective_bound_scaled / 10 if objective_bound_scaled is not None else None
        ),
    )

    if not daily_validation.passed or not official_validation.local_accounting_passed:
        return PS1SolveResult(
            scenario=selected_scenario,
            status=PS1SolverStatus.MODEL_INVALID,
            has_incumbent=False,
            validation=official_validation,
            calendar_validation=daily_validation,
            calendar_assumed=calendar_assumed,
            calendar_assumptions=calendar_assumptions,
            solve_metrics=metrics,
        )

    score = compute_score(
        problem, selected_scenario, projected.access_rows, projected.occupancy_rows
    )
    if metrics.objective_bound_scaled is not None:
        gap = score.objective_scaled - metrics.objective_bound_scaled
        metrics.relative_gap = (
            0.0
            if gap <= 0
            else gap / max(1.0, abs(float(score.objective_scaled)))
        )

    contract_results = build_contract_results(
        problem, selected_scenario, projected.access_rows
    )
    eclo_summary = build_eclo_summary(
        problem,
        selected_scenario,
        projected.access_rows,
        artifacts.footprints,
        selected_windows,
    )

    return PS1SolveResult(
        scenario=selected_scenario,
        status=result_status,
        has_incumbent=True,
        access_rows=projected.access_rows,
        occupancy_rows=projected.occupancy_rows,
        contract_results=contract_results,
        calendar_assignments=calendar_assignments,
        calendar_validation=daily_validation,
        calendar_assumed=calendar_assumed,
        calendar_assumptions=calendar_assumptions,
        score=score,
        eclo_summary=eclo_summary,
        validation=official_validation,
        solve_metrics=metrics,
    )
