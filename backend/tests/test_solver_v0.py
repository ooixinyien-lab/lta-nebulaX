"""Regression tests for the educational Solver V0 baseline."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOLVER_PATH = ROOT / "data" / "solver_v0.py"
DATA_PATH = ROOT / "data" / "comprehensive_synthetic_data.json"


def load_solver_v0():
    """Load solver_v0.py directly because data/ is not a Python package."""
    specification = importlib.util.spec_from_file_location(
        "educational_solver_v0",
        SOLVER_PATH,
    )

    if specification is None or specification.loader is None:
        raise RuntimeError("Could not create an import specification for Solver V0")

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_ground_truth_data() -> dict:
    """Return the confirmed comprehensive synthetic dataset as a dictionary."""
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_v0_normalizes_the_primary_ground_truth_night() -> None:
    """V0 should understand the comprehensive fixture's baseline time fields."""
    solver_v0 = load_solver_v0()
    data = load_ground_truth_data()

    origin, horizon, jobs = solver_v0.normalize(data)
    jobs_by_id = {job["id"]: job for job in jobs}

    assert solver_v0.DATA_PATH == DATA_PATH
    assert origin.isoformat() == "2026-09-14T01:15:00+08:00"
    assert horizon == 190
    assert len(jobs) == 12

    # R01 is frozen at 01:30, which is 15 minutes after the 01:15 origin.
    assert jobs_by_id["R01"]["locked"] is True
    assert jobs_by_id["R01"]["locked_start"] == 15

    # R04 is an exact 02:00 start with a 70-minute reserved duration.
    assert jobs_by_id["R04"]["earliest_start"] == 45
    assert jobs_by_id["R04"]["latest_finish"] == 115
    assert jobs_by_id["R04"]["duration"] == 70

    # R08's request deadline extends beyond handback, so V0 clips it to 04:25.
    assert jobs_by_id["R08"]["latest_finish"] == 190

    # ANY_TIME and preference-free RANGE requests have no preferred timestamp.
    assert jobs_by_id["R10"]["preferred_start"] is None
    assert jobs_by_id["R12"]["preferred_start"] is None


def test_v0_can_select_the_secondary_planning_night() -> None:
    """Only requests permitted on the selected night should enter that model."""
    solver_v0 = load_solver_v0()
    data = load_ground_truth_data()

    origin, horizon, jobs = solver_v0.normalize(data, "2026-09-15")

    assert origin.isoformat() == "2026-09-15T01:15:00+08:00"
    assert horizon == 190
    assert [job["id"] for job in jobs] == ["R12"]


def test_v0_solves_within_its_documented_baseline_scope() -> None:
    """Every V0 result should satisfy its own time and frozen-start rules."""
    solver_v0 = load_solver_v0()
    data = load_ground_truth_data()
    _, _, jobs = solver_v0.normalize(data)

    solver, status, variables = solver_v0.build_and_solve(jobs)

    assert status == solver_v0.cp_model.OPTIMAL

    for job in jobs:
        start = solver.value(variables[job["id"]]["start"])
        end = solver.value(variables[job["id"]]["end"])

        assert start >= job["earliest_start"]
        assert end <= job["latest_finish"]
        assert end == start + job["duration"]

    assert solver.value(variables["R01"]["start"]) == 15
