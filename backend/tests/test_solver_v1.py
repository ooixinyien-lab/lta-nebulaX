"""Regression tests for the educational Solver V1 progression."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOLVER_PATH = ROOT / "data" / "solver_v1.py"
DATA_PATH = ROOT / "data" / "comprehensive_synthetic_data.json"


def load_solver_v1():
    """Load solver_v1.py directly because data/ is not a Python package."""
    specification = importlib.util.spec_from_file_location(
        "educational_solver_v1",
        SOLVER_PATH,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not create an import specification for Solver V1")

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_ground_truth_data() -> dict:
    """Return the confirmed comprehensive synthetic dataset as a dictionary."""
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_v1_normalizes_the_comprehensive_dataset() -> None:
    """V1 should share V0's corrected planning-night and nullable-time input."""
    solver_v1 = load_solver_v1()
    origin, horizon, jobs, _ = solver_v1.normalize(load_ground_truth_data())
    jobs_by_id = {job["id"]: job for job in jobs}

    assert solver_v1.DATA_PATH == DATA_PATH
    assert origin.isoformat() == "2026-09-14T01:15:00+08:00"
    assert horizon == 190
    assert len(jobs) == 12
    assert jobs_by_id["R10"]["preferred_start"] is None
    assert jobs_by_id["R12"]["preferred_start"] is None


def test_v1_adds_dependency_and_power_rules_to_v0() -> None:
    """R03 must follow R01/R04 with the configured buffers and power guard."""
    solver_v1 = load_solver_v1()
    _, _, jobs, planning_rules = solver_v1.normalize(load_ground_truth_data())
    jobs_by_id = {job["id"]: job for job in jobs}

    solver, status, variables = solver_v1.build_and_solve(
        jobs,
        planning_rules,
    )

    assert status == solver_v1.cp_model.OPTIMAL

    r01_end = solver.value(variables["R01"]["end"])
    r03_start = solver.value(variables["R03"]["start"])
    assert r03_start >= (
        r01_end + jobs_by_id["R03"]["handover_buffer_minutes"]
    )

    # R04 uses OFF and R03 uses ON in Z01, so they require a 10-minute guard.
    r04_end = solver.value(variables["R04"]["end"])
    transition = planning_rules["opposed_power_transition_minutes"]
    assert r03_start >= r04_end + transition
