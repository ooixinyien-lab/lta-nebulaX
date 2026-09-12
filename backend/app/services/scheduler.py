"""Stable API-to-solver seam; replace/extend the solver without changing routes."""
from . import cp_sat, demo_search
from .checker import check_plan

def solve(snapshot, engine="cp_sat", time_limit=8, locked_allocations=None):
    locked_allocations = locked_allocations or []
    fixed = [a for a in snapshot["committed_allocations"] if a.get("locked")]
    baseline_errors = check_plan(snapshot, fixed)
    if baseline_errors:
        return {"status": "REVIEW_REQUIRED", "engine": engine, "allocations": [],
                "message": "Existing locked bookings are invalid under the current data. Review them before adding work.",
                "issues": baseline_errors, "elapsed_seconds": 0}
    result = (cp_sat if engine == "cp_sat" else demo_search).solve(snapshot, time_limit, locked_allocations)
    if result.get("allocations"):
        errors = check_plan(snapshot, result["allocations"], require_all=True)
        if errors:
            return {"status": "VALIDATION_FAILED", "engine": engine, "allocations": [],
                    "message": "Independent checker rejected the candidate. Nothing can be published.", "issues": errors, "elapsed_seconds": result["elapsed_seconds"]}
    return result
