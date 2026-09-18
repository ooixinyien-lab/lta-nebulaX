"""Shared OR-Tools CP-SAT solver for official PS1 Scenarios A, B, and C."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from time import monotonic

from ortools.sat.python import cp_model

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    OccupancyScheduleRow,
    ProblemInstance,
)
from backend.app.io import export_bundle
from backend.app.ps1.artifacts import verify_export_round_trip
from backend.app.ps1.models import (
    PS1SolveOptions,
    PS1SolveResult,
    PS1SolverStatus,
    Scenario,
    SolveMetrics,
    ValidationSummary,
    coerce_scenario,
)
from backend.app.ps1.scoring import (
    affected_line_codes,
    build_contract_results,
    build_eclo_summary,
    compute_score,
)
from backend.app.ps1.validation import (
    validate_schedule,
)
from backend.app.topology import FootprintCache


class SolverExportError(ValueError):
    """Raised when a result is not safe to export as a complete bundle."""


@dataclass
class _ModelArtifacts:
    model: cp_model.CpModel
    scenario: Scenario
    footprints: FootprintCache
    x: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    eclo: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    night: dict[tuple[str, int, int], cp_model.IntVar] = field(default_factory=dict)
    group_assignment: dict[tuple[str, int, str, int], cp_model.IntVar] = field(
        default_factory=dict
    )
    group_used: dict[tuple[str, int, int], cp_model.IntVar] = field(default_factory=dict)
    group_counts: dict[tuple[str, int], int] = field(default_factory=dict)
    first_week: dict[str, cp_model.IntVar] = field(default_factory=dict)
    last_week: dict[str, cp_model.IntVar] = field(default_factory=dict)
    lateness_days: dict[str, cp_model.IntVar] = field(default_factory=dict)
    excess: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    window_start: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    eligible: dict[tuple[str, int], bool] = field(default_factory=dict)
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


def _build_model(
    problem: ProblemInstance,
    scenario: Scenario,
) -> _ModelArtifacts:
    """Build all common constraints and the selected scenario policy."""

    model = cp_model.CpModel()
    footprints = FootprintCache(problem)
    artifacts = _ModelArtifacts(model=model, scenario=scenario, footprints=footprints)
    horizon = problem.parameters.horizon_weeks

    def new_bool(name: str) -> cp_model.IntVar:
        variable = model.new_bool_var(name)
        artifacts.hint_variables.append(variable)
        return variable

    def new_int(lower: int, upper: int, name: str) -> cp_model.IntVar:
        variable = model.new_int_var(lower, upper, name)
        artifacts.hint_variables.append(variable)
        return variable

    # Weekly placement, ECLO, exact completion, and release/deadline domains.
    for activity in problem.activities:
        contract = problem.contract(activity.contract_number)
        release_week = problem.planned_start_week(activity)
        activity_id = activity.activity_id
        artifacts.affected_lines[activity_id] = affected_line_codes(
            problem, footprints, activity_id
        )
        for week in range(1, horizon + 1):
            eligible = week >= release_week
            if scenario == Scenario.B:
                eligible = eligible and (
                    problem.parameters.week_end_date(week)
                    <= contract.planned_completion_date
                )
            artifacts.eligible[(activity_id, week)] = eligible
            x = new_bool(f"x[{activity_id},{week}]")
            eclo = new_bool(f"eclo[{activity_id},{week}]")
            artifacts.x[(activity_id, week)] = x
            artifacts.eclo[(activity_id, week)] = eclo
            model.add(eclo <= x)
            if not eligible:
                model.add(x == 0)
            if scenario == Scenario.A:
                model.add(eclo == 0)

        access_vars = [artifacts.x[(activity_id, week)] for week in range(1, horizon + 1)]
        eclo_vars = [
            artifacts.eclo[(activity_id, week)] for week in range(1, horizon + 1)
        ]
        model.add(
            2 * cp_model.LinearExpr.sum(access_vars)
            + cp_model.LinearExpr.sum(eclo_vars)
            >= activity.doubled_workload
        )

        first = new_int(1, horizon, f"first_week[{activity_id}]")
        last = new_int(1, horizon, f"last_week[{activity_id}]")
        artifacts.first_week[activity_id] = first
        artifacts.last_week[activity_id] = last
        model.add_min_equality(
            first,
            [
                (horizon + 1) - (horizon + 1 - week) * artifacts.x[(activity_id, week)]
                for week in range(1, horizon + 1)
            ],
        )
        model.add_max_equality(
            last,
            [week * artifacts.x[(activity_id, week)] for week in range(1, horizon + 1)],
        )

        maximum_lateness = max(
            0,
            (problem.parameters.horizon_end - contract.planned_completion_date).days,
        )
        lateness = new_int(0, maximum_lateness, f"lateness_days[{activity_id}]")
        artifacts.lateness_days[activity_id] = lateness
        deadline_offset = (
            contract.planned_completion_date - problem.parameters.horizon_start
        ).days
        model.add_max_equality(lateness, [0, 7 * last - 1 - deadline_offset])
        if scenario == Scenario.B:
            model.add(lateness == 0)

    # Provisional strict-week predecessor semantics are isolated here.
    for activity in problem.activities:
        if activity.predecessor_activity_id:
            model.add(
                artifacts.first_week[activity.activity_id]
                > artifacts.last_week[activity.predecessor_activity_id]
            )

    # Contract/type-local night assignment and workfront caps.
    for activity in problem.activities:
        contract = problem.contract(activity.contract_number)
        for week in range(1, horizon + 1):
            night_vars: list[cp_model.IntVar] = []
            for night in range(1, contract.number_of_maximum_access_per_week + 1):
                variable = new_bool(f"night[{activity.activity_id},{week},{night}]")
                artifacts.night[(activity.activity_id, week, night)] = variable
                night_vars.append(variable)
            model.add(
                cp_model.LinearExpr.sum(night_vars)
                == artifacts.x[(activity.activity_id, week)]
            )

    activities_by_contract: dict[str, list[str]] = defaultdict(list)
    for activity in problem.activities:
        activities_by_contract[activity.contract_number].append(activity.activity_id)
    for contract in problem.contracts:
        for week in range(1, horizon + 1):
            for night in range(1, contract.number_of_maximum_access_per_week + 1):
                model.add(
                    cp_model.LinearExpr.sum(
                        [
                            artifacts.night[(activity_id, week, night)]
                            for activity_id in activities_by_contract.get(
                                contract.contract_number, []
                            )
                        ]
                    )
                    <= contract.number_of_workfronts
                )

    # Location/week-local possession groups and legal role mixes.
    activities_by_location: dict[str, list[str]] = defaultdict(list)
    for activity in problem.activities:
        for location_id in footprints.get_core_footprint(activity.activity_id).core_locations:
            activities_by_location[location_id].append(activity.activity_id)

    for location in problem.locations:
        location_id = location.location_id
        for week in range(1, horizon + 1):
            candidates = [
                activity_id
                for activity_id in activities_by_location.get(location_id, [])
                if artifacts.eligible[(activity_id, week)]
            ]
            if scenario == Scenario.A:
                group_count = min(len(candidates), location.supply_capacity)
            elif scenario == Scenario.C:
                group_count = min(len(candidates), location.supply_capacity + 1)
            else:
                group_count = len(candidates)
            artifacts.group_counts[(location_id, week)] = group_count

            used_vars: list[cp_model.IntVar] = []
            for group in range(group_count):
                used = new_bool(f"group_used[{location_id},{week},{group}]")
                artifacts.group_used[(location_id, week, group)] = used
                used_vars.append(used)
                members_by_role: dict[AccessType, list[cp_model.IntVar]] = {
                    AccessType.PM: [],
                    AccessType.PC: [],
                    AccessType.C: [],
                }
                all_members: list[cp_model.IntVar] = []
                for activity_id in candidates:
                    assignment = new_bool(
                        f"group[{activity_id},{week},{location_id},{group}]"
                    )
                    artifacts.group_assignment[
                        (activity_id, week, location_id, group)
                    ] = assignment
                    role = problem.contract(
                        problem.activity(activity_id).contract_number
                    ).access_type
                    members_by_role[role].append(assignment)
                    all_members.append(assignment)

                pm = cp_model.LinearExpr.sum(members_by_role[AccessType.PM])
                pc = cp_model.LinearExpr.sum(members_by_role[AccessType.PC])
                co = cp_model.LinearExpr.sum(members_by_role[AccessType.C])
                model.add(pm + pc <= used)
                model.add(4 * pm + pc + co <= 4 * used)
                model.add(used <= cp_model.LinearExpr.sum(all_members))

            for previous, current in zip(used_vars, used_vars[1:]):
                model.add(previous >= current)

            for activity_id in candidates:
                assignments = [
                    artifacts.group_assignment[(activity_id, week, location_id, group)]
                    for group in range(group_count)
                ]
                model.add(
                    cp_model.LinearExpr.sum(assignments)
                    == artifacts.x[(activity_id, week)]
                )

            if used_vars:
                if scenario == Scenario.A:
                    model.add(
                        cp_model.LinearExpr.sum(used_vars) <= location.supply_capacity
                    )
                elif scenario == Scenario.C:
                    model.add(
                        cp_model.LinearExpr.sum(used_vars)
                        <= location.supply_capacity + 1
                    )
                excess_upper = max(0, group_count - location.supply_capacity)
                excess = new_int(
                    0,
                    excess_upper,
                    f"excess[{location_id},{week}]",
                )
                model.add_max_equality(
                    excess,
                    [0, cp_model.LinearExpr.sum(used_vars) - location.supply_capacity],
                )
                artifacts.excess[(location_id, week)] = excess

    # Scenario C chooses at most one two-week ECLO window for every affected line.
    if scenario == Scenario.C:
        for line in problem.lines:
            line_code = line.line_code
            starts: list[cp_model.IntVar] = []
            for start_week in range(1, horizon + 1):
                variable = new_bool(f"eclo_window[{line_code},{start_week}]")
                artifacts.window_start[(line_code, start_week)] = variable
                starts.append(variable)
                relevant_eclo = [
                    artifacts.eclo[(activity.activity_id, week)]
                    for activity in problem.activities
                    if line_code in artifacts.affected_lines[activity.activity_id]
                    for week in (start_week, start_week + 1)
                    if week <= horizon
                ]
                if relevant_eclo:
                    model.add(variable <= cp_model.LinearExpr.sum(relevant_eclo))
                else:
                    model.add(variable == 0)
            model.add(cp_model.LinearExpr.sum(starts) <= 1)

        for activity in problem.activities:
            for week in range(1, horizon + 1):
                if not artifacts.eligible[(activity.activity_id, week)]:
                    continue
                for line_code in artifacts.affected_lines[activity.activity_id]:
                    containing_windows = [artifacts.window_start[(line_code, week)]]
                    if week > 1:
                        containing_windows.append(
                            artifacts.window_start[(line_code, week - 1)]
                        )
                    model.add(
                        artifacts.eclo[(activity.activity_id, week)]
                        <= cp_model.LinearExpr.sum(containing_windows)
                    )

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

    # Fewer access rows are an operational tie-breaker only. Scaling makes one
    # point of official objective strictly more important than every possible
    # difference in access count, so the published optimum is unchanged.
    total_accesses = cp_model.LinearExpr.sum(list(artifacts.x.values()))
    maximum_accesses = sum(artifacts.eligible.values())
    artifacts.maximum_secondary_cost = maximum_accesses
    artifacts.objective_scale = maximum_accesses + 1
    artifacts.search_objective = (
        artifacts.objective_scale * artifacts.objective_scaled + total_accesses
    )
    return artifacts


def _extract_rows(
    problem: ProblemInstance,
    artifacts: _ModelArtifacts,
    solver: cp_model.CpSolver,
) -> tuple[
    list[AccessScheduleRow],
    list[OccupancyScheduleRow],
    dict[str, int],
]:
    access_rows: list[AccessScheduleRow] = []
    occupancy_rows: list[OccupancyScheduleRow] = []
    horizon = problem.parameters.horizon_weeks

    for activity in sorted(problem.activities, key=lambda item: item.activity_id):
        scheduled_weeks = [
            week
            for week in range(1, horizon + 1)
            if solver.value(artifacts.x[(activity.activity_id, week)])
        ]
        contract = problem.contract(activity.contract_number)
        for access_seq, week in enumerate(scheduled_weeks, start=1):
            access_night = next(
                night
                for night in range(1, contract.number_of_maximum_access_per_week + 1)
                if solver.value(artifacts.night[(activity.activity_id, week, night)])
            )
            access_rows.append(
                AccessScheduleRow(
                    activity_id=activity.activity_id,
                    access_seq=access_seq,
                    week=week,
                    eclo=bool(
                        solver.value(artifacts.eclo[(activity.activity_id, week)])
                    ),
                    access_night=access_night,
                )
            )
            core = artifacts.footprints.get_core_footprint(activity.activity_id)
            for location_id in core.core_locations:
                groups = [
                    group
                    for group in range(artifacts.group_counts[(location_id, week)])
                    if solver.value(
                        artifacts.group_assignment[
                            (activity.activity_id, week, location_id, group)
                        ]
                    )
                ]
                if len(groups) != 1:
                    raise RuntimeError(
                        f"Expected one group for {activity.activity_id}/week {week}/"
                        f"{location_id}, found {groups}"
                    )
                occupancy_rows.append(
                    OccupancyScheduleRow(
                        activity_id=activity.activity_id,
                        week=week,
                        location_id=location_id,
                        co_share_group=f"g{groups[0] + 1}",
                    )
                )

    selected_windows = {
        line_code: start_week
        for (line_code, start_week), variable in artifacts.window_start.items()
        if solver.value(variable)
    }
    return access_rows, occupancy_rows, selected_windows


def _empty_result(
    problem: ProblemInstance,
    scenario: Scenario,
    status: PS1SolverStatus,
    feasibility_status: PS1SolverStatus,
    feasibility_seconds: float,
    wall_seconds: float,
) -> PS1SolveResult:
    validation = validate_schedule(problem, scenario, [], [])
    return PS1SolveResult(
        scenario=scenario,
        status=status,
        has_incumbent=False,
        validation=validation,
        solve_metrics=SolveMetrics(
            wall_time_seconds=wall_seconds,
            feasibility_time_seconds=feasibility_seconds,
            improvement_time_seconds=0.0,
            feasibility_status=feasibility_status,
        ),
    )


def solve_ps1(
    problem: ProblemInstance,
    scenario: Scenario | str,
    options: PS1SolveOptions | None = None,
) -> PS1SolveResult:
    """Solve one PS1 scenario using shared constraints and policy switches."""

    selected_scenario = coerce_scenario(scenario)
    solve_options = options or PS1SolveOptions()
    started = monotonic()
    artifacts = _build_model(problem, selected_scenario)

    remaining_before_feasibility = max(
        0.001,
        solve_options.time_limit_seconds - (monotonic() - started),
    )
    feasibility_limit = min(
        remaining_before_feasibility,
        solve_options.feasibility_time_limit_seconds,
    )
    feasibility_solver = _configure_solver(solve_options, feasibility_limit)
    feasibility_started = monotonic()
    feasibility_raw_status = feasibility_solver.solve(artifacts.model)
    feasibility_seconds = monotonic() - feasibility_started
    feasibility_status = _status(feasibility_raw_status)

    # A short first-feasible allocation is useful when it succeeds, but a
    # timeout in that phase must not strand the unused total budget. Continue
    # the satisfaction search before reporting UNKNOWN.
    remaining_after_feasibility = solve_options.time_limit_seconds - (
        monotonic() - started
    )
    if (
        feasibility_raw_status == cp_model.UNKNOWN
        and remaining_after_feasibility > 0.001
    ):
        retry_solver = _configure_solver(solve_options, remaining_after_feasibility)
        retry_started = monotonic()
        feasibility_raw_status = retry_solver.solve(artifacts.model)
        feasibility_seconds += monotonic() - retry_started
        feasibility_solver = retry_solver
        feasibility_status = _status(feasibility_raw_status)

    if not _has_solution(feasibility_raw_status):
        return _empty_result(
            problem,
            selected_scenario,
            feasibility_status,
            feasibility_status,
            feasibility_seconds,
            monotonic() - started,
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
        improvement_solver = _configure_solver(solve_options, remaining)
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

    access_rows, occupancy_rows, selected_windows = _extract_rows(
        problem, artifacts, chosen_solver
    )
    validation = validate_schedule(
        problem,
        selected_scenario,
        access_rows,
        occupancy_rows,
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

    if not validation.local_accounting_passed:
        return PS1SolveResult(
            scenario=selected_scenario,
            status=PS1SolverStatus.MODEL_INVALID,
            has_incumbent=False,
            validation=validation,
            solve_metrics=metrics,
        )

    score = compute_score(
        problem, selected_scenario, access_rows, occupancy_rows
    )
    if metrics.objective_bound_scaled is not None:
        gap = score.objective_scaled - metrics.objective_bound_scaled
        metrics.relative_gap = (
            0.0
            if gap <= 0
            else gap / max(1.0, abs(float(score.objective_scaled)))
        )
    contract_results = build_contract_results(
        problem, selected_scenario, access_rows
    )
    eclo_summary = build_eclo_summary(
        problem,
        selected_scenario,
        access_rows,
        artifacts.footprints,
        selected_windows,
    )
    return PS1SolveResult(
        scenario=selected_scenario,
        status=result_status,
        has_incumbent=True,
        access_rows=access_rows,
        occupancy_rows=occupancy_rows,
        contract_results=contract_results,
        score=score,
        eclo_summary=eclo_summary,
        validation=validation,
        solve_metrics=metrics,
    )


def export_solve_result(
    result: PS1SolveResult,
    output_dir: Path | str,
) -> dict[str, Path]:
    """Write one complete result using the exact three official CSV schemas."""

    if not result.has_incumbent or not result.validation.local_accounting_passed:
        raise SolverExportError("Cannot export a result without a locally valid incumbent")
    paths = export_bundle(
        result.access_rows,
        result.occupancy_rows,
        result.contract_results,
        output_dir,
    )
    verify_export_round_trip(result, paths)
    return paths


def solve_all_scenarios(
    problem: ProblemInstance,
    options: PS1SolveOptions | None = None,
    output_root: Path | str | None = None,
) -> dict[Scenario, PS1SolveResult]:
    """Run the same solver independently for A, B, and C."""

    results: dict[Scenario, PS1SolveResult] = {}
    for scenario in Scenario:
        result = solve_ps1(problem, scenario, options)
        results[scenario] = result
        if output_root is not None and result.has_incumbent:
            export_solve_result(result, Path(output_root) / scenario.value)
    return results
