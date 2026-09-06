"""Finite 5-minute candidates for the small starter; not an industrial model.
Unary rules screen domains. Pairwise/global rules remain in the solver and checker.
"""
from datetime import timedelta
from .common import dt, make_allocation
from .checker import unary_issues

def candidates(snapshot, request):
    unique = {}
    step = snapshot["planning_rules"]["start_grid_minutes"]
    for window in snapshot["engineering_windows"]:
        if window["date"] not in request["allowed_dates"]:
            continue
        start, last = dt(window["start"]), dt(window["end"])
        while start < last:
            for eng in request["eligible_engineers"]:
                a = make_allocation(request, start, eng)
                if not unary_issues(snapshot, request, a):
                    unique[(a["start"], eng)] = a
            start += timedelta(minutes=step)
    return list(unique.values())

def allocation_cost(request, a, n_jobs):
    # Time preference dominates ALL possible engineer preference penalties.
    minutes = int(abs((dt(a["start"]) - dt(request["preferred_start"])).total_seconds()) // 60)
    changed = int(bool(request.get("preferred_engineer")) and a["engineer_id"] != request["preferred_engineer"])
    return (n_jobs + 1) * minutes + changed
