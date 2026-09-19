"""Comprehensive test suite for the date-first daily-integrated PS1 CP-SAT solver."""

from datetime import date
from pathlib import Path

import pytest

from backend.app.domain_models import AccessType, ContractPriority, NatureOfWorks, ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.ps1.calendar_models import (
    ContractCalendarRule,
    LineNightRule,
    LocationNightRule,
    OperatingCalendarInput,
    demo_calendar,
)
from backend.app.ps1.daily_solver import solve_daily_ps1
from backend.app.ps1.models import (
    PS1SolveOptions,
    PS1SolverStatus,
    Scenario,
)
from backend.app.ps1.scoring import compute_score
from backend.app.ps1.solver import solve_ps1

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _options(*, optimize: bool = True, time_limit: float = 10.0) -> PS1SolveOptions:
    return PS1SolveOptions(
        time_limit_seconds=time_limit,
        feasibility_time_limit_seconds=5.0,
        num_search_workers=4,
        random_seed=42,
        optimize=optimize,
    )


def test_date_first_solver_produces_real_calendar_dates() -> None:
    problem = load_problem_from_directory(DATA_DIR)
    act = problem.activity("A001")
    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract(act.contract_number)],
        activities=[act],
    )

    result = solve_daily_ps1(small_problem, Scenario.A, _options())
    assert result.status in (PS1SolverStatus.OPTIMAL, PS1SolverStatus.FEASIBLE)
    assert result.has_incumbent
    assert len(result.calendar_assignments) == act.total_accesses

    for assignment in result.calendar_assignments:
        assert isinstance(assignment.service_date, date)
        assert small_problem.parameters.horizon_start <= assignment.service_date <= small_problem.parameters.horizon_end
        assert small_problem.parameters.date_to_week(assignment.service_date) == assignment.week
        assert 1 <= assignment.access_night <= 7


def test_access_night_local_mapping_across_contracts() -> None:
    """Verify that access_night is local to contract/type/week, not a weekday index."""
    problem = load_problem_from_directory(DATA_DIR)
    # Pick two activities from C001 and one from C002
    act_c1_a = problem.activity("A001")  # C001
    act_c1_b = problem.activity("A002")  # C001
    act_c2 = problem.activity("A008")  # C002
    week = 21

    # Restrict C001 to Tuesday and Friday, C002 to Friday only in week 21
    tue = problem.parameters.week_start_date(week) + date.resolution  # Tuesday
    fri = problem.parameters.week_start_date(week) + date.resolution * 4  # Friday

    calendar = OperatingCalendarInput(
        instance_revision_id="rev-local-test",
        contract_rules=[
            ContractCalendarRule(
                contract_number="C001",
                eligible_dates=[tue, fri],
            ),
            ContractCalendarRule(
                contract_number="C002",
                eligible_dates=[fri],
            ),
        ],
    )

    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[
            problem.contract("C001").model_copy(update={"number_of_maximum_access_per_week": 2, "number_of_workfronts": 1}),
            problem.contract("C002").model_copy(update={"number_of_maximum_access_per_week": 2, "number_of_workfronts": 1}),
        ],
        activities=[
            act_c1_a.model_copy(update={"total_accesses": 1, "planned_start_date": problem.parameters.week_start_date(week), "predecessor_activity_id": None}),
            act_c1_b.model_copy(update={"total_accesses": 1, "planned_start_date": problem.parameters.week_start_date(week), "predecessor_activity_id": None}),
            act_c2.model_copy(update={"total_accesses": 1, "planned_start_date": problem.parameters.week_start_date(week), "predecessor_activity_id": None}),
        ],
    )

    result = solve_daily_ps1(small_problem, Scenario.A, _options(), calendar=calendar)
    assert result.status in (PS1SolverStatus.OPTIMAL, PS1SolverStatus.FEASIBLE)

    # For C001: Tue -> access_night 1, Fri -> access_night 2
    c1_rows = [r for r in result.access_rows if r.activity_id in ("A001", "A002")]
    assert len(c1_rows) == 2
    c1_nights = {r.access_night for r in c1_rows}
    assert c1_nights == {1, 2}

    # For C002: Fri is only access -> access_night 1 (NOT Friday weekday 5!)
    c2_rows = [r for r in result.access_rows if r.activity_id == act_c2.activity_id]
    assert len(c2_rows) == 1
    assert c2_rows[0].access_night == 1


def test_contract_weekly_actual_date_limit() -> None:
    """A contract with number_of_maximum_access_per_week=2 cannot use 3 dates in a week."""
    problem = load_problem_from_directory(DATA_DIR)
    acts = [a for a in problem.activities if a.contract_number == "C001"][:3]
    week = 20
    test_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[
            problem.contract("C001").model_copy(
                update={"number_of_maximum_access_per_week": 2, "number_of_workfronts": 2}
            )
        ],
        activities=[
            a.model_copy(
                update={
                    "total_accesses": 1,
                    "planned_start_date": problem.parameters.week_start_date(week),
                    "predecessor_activity_id": None,
                }
            )
            for a in acts
        ],
    )

    result = solve_daily_ps1(test_problem, Scenario.A, _options())
    assert result.status in (PS1SolverStatus.OPTIMAL, PS1SolverStatus.FEASIBLE)

    # Contract C001 must have used at most 2 distinct service dates in week 20
    c1_dates = {
        a.service_date for a in result.calendar_assignments if a.week == week and a.contract_number == "C001"
    }
    assert len(c1_dates) <= 2


def test_nightly_workfront_limit_enforced_on_real_dates() -> None:
    """Contract with number_of_workfronts=2 cannot run 3 activities on the same date."""
    problem = load_problem_from_directory(DATA_DIR)
    acts = [a for a in problem.activities if a.contract_number == "C001"][:4]
    week = 21
    single_date = problem.parameters.week_start_date(week) + date.resolution

    # Force all 4 activities to only be eligible on a single date
    calendar = OperatingCalendarInput(
        instance_revision_id="rev-wf-test",
        contract_rules=[
            ContractCalendarRule(
                contract_number="C001",
                eligible_dates=[single_date],
            )
        ],
    )

    test_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[
            problem.contract("C001").model_copy(
                update={"number_of_workfronts": 2, "number_of_maximum_access_per_week": 3}
            )
        ],
        activities=[
            a.model_copy(
                update={
                    "total_accesses": 1,
                    "planned_start_date": problem.parameters.week_start_date(week),
                    "predecessor_activity_id": None,
                }
            )
            for a in acts
        ],
    )

    # 4 activities need 1 access each on single date, but workfront limit is 2 -> INFEASIBLE
    result = solve_daily_ps1(test_problem, Scenario.A, _options(), calendar=calendar)
    assert result.status == PS1SolverStatus.INFEASIBLE


def test_predecessor_strict_week_ordering() -> None:
    """Successor first week must strictly exceed predecessor last week."""
    problem = load_problem_from_directory(DATA_DIR)
    # A004 has predecessor A003
    a003 = problem.activity("A003")
    a004 = problem.activity("A004")

    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract(a003.contract_number)],
        activities=[
            a003.model_copy(update={"total_accesses": 1}),
            a004.model_copy(update={"total_accesses": 1, "predecessor_activity_id": "A003"}),
        ],
    )

    result = solve_daily_ps1(small_problem, Scenario.A, _options())
    assert result.status in (PS1SolverStatus.OPTIMAL, PS1SolverStatus.FEASIBLE)

    a003_week = next(r.week for r in result.access_rows if r.activity_id == "A003")
    a004_week = next(r.week for r in result.access_rows if r.activity_id == "A004")
    assert a004_week > a003_week

    # Also verify dates: a004 date is strictly after a003 date
    a003_date = next(a.service_date for a in result.calendar_assignments if a.activity_id == "A003")
    a004_date = next(a.service_date for a in result.calendar_assignments if a.activity_id == "A004")
    assert a004_date > a003_date


def test_calendar_blackout_restrictions() -> None:
    """Line and location blackouts are respected directly by the daily solver."""
    problem = load_problem_from_directory(DATA_DIR)
    act = problem.activity("A001")
    week = 21
    target_date = problem.parameters.week_start_date(week)

    # Black out all dates in week 21 EXCEPT target_date, but black out line BET on target_date
    other_dates = [
        problem.parameters.week_start_date(week) + date.resolution * i
        for i in range(1, 7)
    ]
    calendar = OperatingCalendarInput(
        instance_revision_id="rev-blackout",
        line_nights=[
            LineNightRule(
                service_date=target_date,
                line_code="BET",
                maintenance_available=False,
            )
        ],
        contract_rules=[
            ContractCalendarRule(
                contract_number="C001",
                eligible_dates=[target_date],  # Only candidate date, but line is blacked out!
            )
        ],
    )

    small_problem = ProblemInstance(
        lines=problem.lines,
        stations=problem.stations,
        sectors=problem.sectors,
        locations=problem.locations,
        buffer_rules=problem.buffer_rules,
        parameters=problem.parameters,
        contracts=[problem.contract("C001")],
        activities=[
            act.model_copy(
                update={
                    "total_accesses": 1,
                    "planned_start_date": problem.parameters.week_start_date(week),
                    "predecessor_activity_id": None,
                }
            )
        ],
    )

    result = solve_daily_ps1(small_problem, Scenario.A, _options(), calendar=calendar)
    assert result.status == PS1SolverStatus.INFEASIBLE


def test_scenario_a_full_public_solution() -> None:
    """Test Scenario A on the full public dataset: no ECLO, no excess, full workload."""
    problem = load_problem_from_directory(DATA_DIR)
    result = solve_ps1(problem, Scenario.A, _options(time_limit=20.0))

    assert result.has_incumbent
    assert result.validation.local_accounting_passed
    assert result.calendar_validation is not None
    assert result.calendar_validation.passed
    assert result.score is not None
    assert result.score.eclo_accesses == 0
    assert result.score.excess_slots == 0
    assert len(result.calendar_assignments) == 192

    # Dynamic assertion: all activities in problem are scheduled
    scheduled_acts = {r.activity_id for r in result.access_rows}
    assert scheduled_acts == {a.activity_id for a in problem.activities}


def test_scenario_b_full_public_solution() -> None:
    """Test Scenario B on the full public dataset: no lateness, ECLO allowed."""
    problem = load_problem_from_directory(DATA_DIR)
    result = solve_ps1(problem, Scenario.B, _options(time_limit=20.0))

    assert result.has_incumbent
    assert result.validation.local_accounting_passed
    assert result.calendar_validation is not None
    assert result.calendar_validation.passed
    assert result.score is not None
    assert result.score.weighted_activity_lateness == 0.0

    # Overrun is strictly 0 for all contracts
    for res_row in result.contract_results:
        assert res_row.overrun_days == 0


def test_scenario_c_full_public_solution() -> None:
    """Test Scenario C on the full public dataset: balanced, <=1 excess, line ECLO windows."""
    problem = load_problem_from_directory(DATA_DIR)
    result = solve_ps1(problem, Scenario.C, _options(time_limit=20.0))

    assert result.has_incumbent
    assert result.validation.local_accounting_passed
    assert result.calendar_validation is not None
    assert result.calendar_validation.passed
    assert result.score is not None
    assert result.score.excess_slots <= len(problem.locations) * problem.parameters.horizon_weeks
