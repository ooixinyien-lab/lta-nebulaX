"""Focused CP-SAT tests for the shared official PS1 solver."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.domain_models import ContractPriority, ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.ps1.models import PS1SolveOptions, PS1SolverStatus, Scenario
from backend.app.ps1 import solver as solver_module
from backend.app.ps1.solver import export_solve_result, solve_all_scenarios, solve_ps1
from ortools.sat.python import cp_model


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _single_activity_problem(activity_id: str) -> ProblemInstance:
    problem = load_problem_from_directory(DATA_DIR)
    activity = problem.activity(activity_id)
    contract = problem.contract(activity.contract_number)
    return ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[contract],
        activities=[activity],
    )


def _options(*, optimize: bool = True) -> PS1SolveOptions:
    return PS1SolveOptions(
        time_limit_seconds=5,
        feasibility_time_limit_seconds=2,
        num_search_workers=1,
        random_seed=7,
        optimize=optimize,
    )


def test_one_solver_applies_a_b_c_policies() -> None:
    problem = _single_activity_problem("A036")

    scenario_a = solve_ps1(problem, Scenario.A, _options())
    scenario_b = solve_ps1(problem, Scenario.B, _options())
    scenario_c = solve_ps1(problem, Scenario.C, _options())

    assert scenario_a.status == PS1SolverStatus.OPTIMAL
    assert scenario_a.score is not None
    assert scenario_a.score.objective_score == 18.2
    assert scenario_a.score.eclo_accesses == 0
    assert max(row.week for row in scenario_a.access_rows) == 28

    assert scenario_b.status == PS1SolverStatus.OPTIMAL
    assert scenario_b.score is not None
    assert scenario_b.score.objective_score == 20
    assert scenario_b.score.eclo_accesses == 4
    assert len(scenario_b.access_rows) == 5
    assert len({row.week for row in scenario_b.access_rows}) == 5
    assert max(row.week for row in scenario_b.access_rows) == 26

    assert scenario_c.status == PS1SolverStatus.OPTIMAL
    assert scenario_c.score is not None
    assert scenario_c.score.objective_score == 18.2
    assert scenario_c.score.eclo_accesses == 0

    for result in (scenario_a, scenario_b, scenario_c):
        assert result.has_incumbent
        assert result.validation.local_accounting_passed
        assert result.validation.safety_status.value == "unverified"
        assert result.validation.official_checker_status.value == "unavailable"


def test_scenario_c_selects_and_reports_two_week_eclo_window() -> None:
    original = load_problem_from_directory(DATA_DIR)
    activity = original.activity("A036")
    contract = original.contract(activity.contract_number).model_copy(
        update={"contract_priority": ContractPriority.P1}
    )
    problem = ProblemInstance(
        lines=original.lines,
        stations=original.stations,
        sectors=original.sectors,
        locations=original.locations,
        buffer_rules=original.buffer_rules,
        parameters=original.parameters,
        contracts=[contract],
        activities=[activity],
    )

    result = solve_ps1(problem, Scenario.C, _options())

    assert result.status == PS1SolverStatus.OPTIMAL
    assert result.eclo_summary is not None
    assert result.eclo_summary.eclo_accesses_total == 2
    assert result.eclo_summary.selected_windows is not None
    assert len(result.eclo_summary.selected_windows) == 1
    window = result.eclo_summary.selected_windows[0]
    assert window.line_code == "BET"
    assert window.end_week - window.start_week == 1
    assert set(result.eclo_summary.by_line[0].usage_weeks) <= {
        window.start_week,
        window.end_week,
    }


def test_explicit_local_nights_allow_two_workfronts_per_night() -> None:
    original = load_problem_from_directory(DATA_DIR)
    week = 20
    activity_ids = ["A001", "A002", "A003", "A004", "A006", "A007"]
    activities = [
        original.activity(activity_id).model_copy(
            update={
                "total_accesses": 1,
                "planned_start_date": original.parameters.week_start_date(week),
                "predecessor_activity_id": None,
            }
        )
        for activity_id in activity_ids
    ]
    contract = original.contract("C001").model_copy(
        update={"planned_completion_date": original.parameters.week_end_date(week)}
    )
    problem = ProblemInstance(
        lines=original.lines,
        stations=original.stations,
        sectors=original.sectors,
        locations=original.locations,
        buffer_rules=original.buffer_rules,
        parameters=original.parameters,
        contracts=[contract],
        activities=activities,
    )

    result = solve_ps1(problem, Scenario.B, _options())

    assert result.status == PS1SolverStatus.OPTIMAL
    assert {row.week for row in result.access_rows} == {week}
    counts_by_night = {
        night: sum(row.access_night == night for row in result.access_rows)
        for night in range(1, contract.number_of_maximum_access_per_week + 1)
    }
    assert counts_by_night == {1: 2, 2: 2, 3: 2}


@pytest.mark.parametrize(
    ("activity_ids", "must_share"),
    [
        (("A025", "A040"), True),   # PC + C is legal.
        (("A075", "A040"), False),  # PM must be alone.
        (("A025", "A074"), False),  # Two PCs cannot share.
    ],
)
def test_solver_enforces_possession_group_role_mix(
    activity_ids: tuple[str, str],
    must_share: bool,
) -> None:
    original = load_problem_from_directory(DATA_DIR)
    week = 20
    target = original.activity("A025")
    activities = [
        original.activity(activity_id).model_copy(
            update={
                "start_location_id": target.start_location_id,
                "end_location_id": target.end_location_id,
                "total_accesses": 1,
                "planned_start_date": original.parameters.week_start_date(week),
                "predecessor_activity_id": None,
            }
        )
        for activity_id in activity_ids
    ]
    contracts = [
        original.contract(activity.contract_number).model_copy(
            update={"planned_completion_date": original.parameters.week_end_date(week)}
        )
        for activity in activities
    ]
    problem = ProblemInstance(
        lines=original.lines,
        stations=original.stations,
        sectors=original.sectors,
        locations=[
            location.model_copy(update={"supply_capacity": 1})
            for location in original.locations
        ],
        buffer_rules=original.buffer_rules,
        parameters=original.parameters,
        contracts=contracts,
        activities=activities,
    )

    result = solve_ps1(problem, Scenario.B, _options())

    assert result.status == PS1SolverStatus.OPTIMAL
    groups = {
        (row.activity_id, row.location_id): row.co_share_group
        for row in result.occupancy_rows
    }
    common_locations = {
        row.location_id
        for row in result.occupancy_rows
        if row.activity_id == activity_ids[0]
    } & {
        row.location_id
        for row in result.occupancy_rows
        if row.activity_id == activity_ids[1]
    }
    assert common_locations
    for location_id in common_locations:
        assert (
            groups[(activity_ids[0], location_id)]
            == groups[(activity_ids[1], location_id)]
        ) is must_share


def test_feasibility_only_run_retains_complete_incumbent() -> None:
    problem = _single_activity_problem("A036")

    result = solve_ps1(problem, Scenario.A, _options(optimize=False))

    assert result.status == PS1SolverStatus.FEASIBLE
    assert result.has_incumbent
    assert result.solve_metrics.improvement_status is None
    assert result.validation.local_accounting_passed


def test_initial_feasibility_timeout_uses_remaining_total_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _single_activity_problem("A036")
    original_configure = solver_module._configure_solver
    call_count = 0

    class InitialTimeoutSolver:
        def solve(self, _model: cp_model.CpModel) -> cp_model.CpSolverStatus:
            return cp_model.UNKNOWN

    def configure(
        options: PS1SolveOptions,
        time_limit_seconds: float,
    ) -> cp_model.CpSolver | InitialTimeoutSolver:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return InitialTimeoutSolver()
        return original_configure(options, time_limit_seconds)

    monkeypatch.setattr(solver_module, "_configure_solver", configure)

    result = solve_ps1(problem, Scenario.A, _options())

    assert call_count >= 2
    assert result.has_incumbent
    assert result.validation.local_accounting_passed


def test_proven_infeasible_has_no_incumbent_or_score() -> None:
    original = load_problem_from_directory(DATA_DIR)
    activity = original.activity("A036").model_copy(update={"total_accesses": 8})
    contract = original.contract(activity.contract_number)
    problem = ProblemInstance(
        lines=original.lines,
        stations=original.stations,
        sectors=original.sectors,
        locations=original.locations,
        buffer_rules=original.buffer_rules,
        parameters=original.parameters,
        contracts=[contract],
        activities=[activity],
    )

    result = solve_ps1(problem, Scenario.B, _options())

    assert result.status == PS1SolverStatus.INFEASIBLE
    assert not result.has_incumbent
    assert result.score is None
    assert result.eclo_summary is None
    assert result.access_rows == []


def test_export_writes_exact_three_file_bundle(tmp_path: Path) -> None:
    problem = _single_activity_problem("A036")
    result = solve_ps1(problem, Scenario.B, _options())

    paths = export_solve_result(result, tmp_path / "B")

    assert set(paths) == {"access", "occupancy", "results"}
    assert {path.name for path in paths.values()} == {
        "SCHEDULE_ACCESS.csv",
        "SCHEDULE_OCCUPANCY.csv",
        "RESULTS.csv",
    }
    assert paths["access"].read_text(encoding="utf-8").splitlines()[0] == (
        "activity_id,access_seq,week,eclo,access_night"
    )


def test_solve_all_scenarios_exports_separate_bundles(tmp_path: Path) -> None:
    problem = _single_activity_problem("A036")

    results = solve_all_scenarios(problem, _options(), tmp_path)

    assert set(results) == {Scenario.A, Scenario.B, Scenario.C}
    for scenario in Scenario:
        assert results[scenario].has_incumbent
        assert {
            path.name for path in (tmp_path / scenario.value).iterdir()
        } == {
            "SCHEDULE_ACCESS.csv",
            "SCHEDULE_OCCUPANCY.csv",
            "RESULTS.csv",
        }
