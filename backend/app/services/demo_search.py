"""Explicit dependency-free teaching solver. NOT CP-SAT and NOT for large inputs.
Enumerates small candidate combinations with branch-and-bound. Kept to let the
website run without OR-Tools and as a cross-check for the optimisation teammate.
"""
from time import monotonic
from .candidates import candidates, allocation_cost
from .checker import check_plan


def solve(snapshot: dict, time_limit: float = 8) -> dict:
    started = monotonic()
    fixed = [a.copy() for a in snapshot["committed_allocations"]]
    ids = {a["request_id"] for a in fixed}
    remaining = [r for r in snapshot["requests"] if r["status"] == "submitted" and r["id"] not in ids]
    base = {"engine": "demo_search", "allocations": []}
    if len(remaining) > 6:
        return {**base, "status": "LIMIT", "message": "Demo search is capped at six pending jobs. Select CP-SAT for larger tests.", "elapsed_seconds": 0}
    if check_plan(snapshot, fixed):
        return {**base, "status": "INFEASIBLE", "message": "Existing locked bookings violate the current rules/resources.", "elapsed_seconds": 0}
    ordered = []
    while remaining:
        ready = [r for r in remaining if set(r["depends_on"]) <= ids]
        if not ready:
            return {**base, "status": "INFEASIBLE", "message": "Dependencies are cyclic or refer to unavailable jobs.", "elapsed_seconds": 0}
        r = ready[0]
        ordered.append(r)
        remaining.remove(r)
        ids.add(r["id"])
    n = sum(r["status"] in ("scheduled", "submitted") for r in snapshot["requests"])
    options = []
    for r in ordered:
        choices = candidates(snapshot, r)
        choices.sort(key=lambda a: (allocation_cost(r, a, n), a["start"], a["engineer_id"]))
        if not choices:
            return {**base, "status": "INFEASIBLE", "message": f"{r['id']} has no feasible individual candidate.", "elapsed_seconds": monotonic()-started}
        options.append(choices)
    best, best_cost, timed_out = None, float("inf"), False
    def visit(i, plan, cost):
        nonlocal best, best_cost, timed_out
        if monotonic() - started > time_limit:
            timed_out = True
            return
        if cost >= best_cost:
            return
        if i == len(ordered):
            if not check_plan(snapshot, plan, require_all=True):
                best, best_cost = [a.copy() for a in plan], cost
            return
        for a in options[i]:
            next_cost = cost + allocation_cost(ordered[i], a, n)
            if next_cost >= best_cost:
                break  # Candidate costs are sorted.
            trial = plan + [a]
            if not check_plan(snapshot, trial):
                visit(i+1, trial, next_cost)
            if timed_out:
                break
    visit(0, fixed, 0)
    if best is not None:
        for a in best:
            a["locked"] = True
        return {**base, "status": "FEASIBLE" if timed_out else "OPTIMAL", "allocations": best,
                "objective": best_cost, "elapsed_seconds": round(monotonic()-started, 4),
                "message": "Tiny-demo enumerative result, not CP-SAT. Approval is still required."}
    return {**base, "status": "UNKNOWN" if timed_out else "INFEASIBLE", "elapsed_seconds": round(monotonic()-started, 4),
            "message": "Search timed out without a plan." if timed_out else "No plan satisfies the encoded constraints."}
