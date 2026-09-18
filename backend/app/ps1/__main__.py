"""Command-line entry point for the official PS1 solver."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.io import load_problem_from_directory
from backend.app.ps1.models import PS1SolveOptions, Scenario
from backend.app.ps1.solver import export_solve_result, solve_all_scenarios, solve_ps1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve official PS1 weekly schedules")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--scenario", choices=["A", "B", "C", "all"], default="all")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--feasibility-time-limit", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-optimize", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    problem = load_problem_from_directory(args.data_dir)
    options = PS1SolveOptions(
        time_limit_seconds=args.time_limit,
        feasibility_time_limit_seconds=args.feasibility_time_limit,
        num_search_workers=args.workers,
        random_seed=args.seed,
        optimize=not args.no_optimize,
    )

    if args.scenario == "all":
        results = solve_all_scenarios(problem, options, args.output_dir)
        payload = {scenario.value: result.model_dump(mode="json") for scenario, result in results.items()}
    else:
        scenario = Scenario(args.scenario)
        result = solve_ps1(problem, scenario, options)
        if result.has_incumbent:
            export_solve_result(result, args.output_dir / scenario.value)
        payload = result.model_dump(mode="json")

    print(json.dumps(payload, indent=2))
    return 0 if all(
        result.has_incumbent
        for result in (results.values() if args.scenario == "all" else [result])
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
