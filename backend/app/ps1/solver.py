"""Stable public facade for the official PS1 solver."""

from __future__ import annotations

from pathlib import Path

from backend.app.domain_models import ProblemInstance
from backend.app.io import export_bundle
from backend.app.ps1.artifacts import verify_export_round_trip
from backend.app.ps1.calendar_models import OperatingCalendarInput
from backend.app.ps1.daily_solver import (
    _configure_solver,
    solve_daily_ps1,
)
from backend.app.ps1.models import (
    PS1SolveOptions,
    PS1SolveResult,
    Scenario,
)
from backend.app.ps1.weekly_solver import (
    solve_legacy_weekly_ps1,
    solve_weekly_ps1,
)


class SolverExportError(ValueError):
    """Raised when a result is not safe to export as a complete bundle."""


def solve_ps1(
    problem: ProblemInstance,
    scenario: Scenario | str,
    options: PS1SolveOptions | None = None,
    calendar: OperatingCalendarInput | None = None,
) -> PS1SolveResult:
    """Solve one PS1 scenario directly in the real calendar date space."""

    return solve_daily_ps1(
        problem=problem,
        scenario=scenario,
        options=options,
        calendar=calendar,
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
    calendar: OperatingCalendarInput | None = None,
) -> dict[Scenario, PS1SolveResult]:
    """Run the same daily solver independently for A, B, and C."""

    results: dict[Scenario, PS1SolveResult] = {}
    for scenario in Scenario:
        result = solve_ps1(problem, scenario, options=options, calendar=calendar)
        results[scenario] = result
        if output_root is not None and result.has_incumbent:
            export_solve_result(result, Path(output_root) / scenario.value)
    return results
