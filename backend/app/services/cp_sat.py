"""CP-SAT extension point. Owner: optimisation teammate.
No HTTP, database or UI imports. Unit-test solve(snapshot, time_limit) directly.
This is a real model, not a lookup of the reference schedule.
"""
from time import monotonic
from itertools import combinations
from .common import dt, duration, make_allocation, zones
from .candidates import candidates


def solve(snapshot: dict, time_limit: float = 8) -> dict:
    started = monotonic()
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return {"status": "UNAVAILABLE", "engine": "cp_sat", "allocations": [],
                "message": "Install requirements-cpsat.txt to enable OR-Tools, or explicitly select SOLVER_ENGINE=demo_search for the tiny local demo.", "elapsed_seconds": 0}
    requests = [r for r in snapshot["requests"] if r["status"] in ("scheduled", "submitted")]
    if len(requests) > 40:
        return {"status": "LIMIT", "engine": "cp_sat", "allocations": [], "message": "Starter limit is 40 active jobs. Benchmark a larger model before increasing it.", "elapsed_seconds": 0}
    base = dt(min(w["start"] for w in snapshot["engineering_windows"]))
    minute = lambda s: int((dt(s) - base).total_seconds() // 60)
    horizon = minute(max(w["end"] for w in snapshot["engineering_windows"])) + 1440
    engineer_ids = [e["id"] for e in snapshot["engineers"]]
    fixed = {a["request_id"]: a for a in snapshot["committed_allocations"]}
    model = cp_model.CpModel()
    tasks = {}
    cost_terms = []
    for r in requests:
        options = [fixed[r["id"]]] if r["id"] in fixed else candidates(snapshot, r)
        if not options:
            return {"status": "INFEASIBLE", "engine": "cp_sat", "allocations": [],
                    "message": f"{r['id']} has no candidate satisfying its window and individual resource requirements.", "elapsed_seconds": monotonic()-started}
        starts = sorted({minute(a["start"]) for a in options})
        start = model.new_int_var_from_domain(cp_model.Domain.from_values(starts), f"start_{r['id']}")
        end = model.new_int_var(0, horizon, f"end_{r['id']}")
        eng = model.new_int_var(0, len(engineer_ids)-1, f"engineer_{r['id']}")
        model.add_allowed_assignments([start, eng], [(minute(a["start"]), engineer_ids.index(a["engineer_id"])) for a in options])
        interval = model.new_interval_var(start, duration(r), end, f"job_{r['id']}")
        tasks[r["id"]] = {"start": start, "end": end, "eng": eng, "interval": interval}
        if r["id"] not in fixed:
            delta = model.new_int_var(0, horizon + 10000, f"deviation_{r['id']}")
            model.add_abs_equality(delta, start - minute(r["preferred_start"]))
            cost_terms.append((len(requests)+1) * delta)
            if r.get("preferred_engineer") in engineer_ids:
                changed = model.new_bool_var(f"reassigned_{r['id']}")
                idx = engineer_ids.index(r["preferred_engineer"])
                model.add(eng != idx).only_enforce_if(changed)
                model.add(eng == idx).only_enforce_if(changed.Not())
                cost_terms.append(changed)
    rules = snapshot["planning_rules"]
    for ra, rb in combinations(requests, 2):
        a, b = tasks[ra["id"]], tasks[rb["id"]]
        order = model.new_bool_var(f"order_{ra['id']}_{rb['id']}")
        def separate(gap, condition=None):
            left = [order] + ([] if condition is None else [condition])
            right = [order.Not()] + ([] if condition is None else [condition])
            model.add(a["end"] + gap <= b["start"]).only_enforce_if(left)
            model.add(b["end"] + gap <= a["start"]).only_enforce_if(right)
        if set(ra["protected_sectors"]) & set(rb["protected_sectors"]):
            model.add_no_overlap([a["interval"], b["interval"]])
            separate(0)
        compatible = rules["power_compatibility"].get(ra["power_requirement"], {}).get(rb["power_requirement"])
        if zones(snapshot, ra) & zones(snapshot, rb):
            if compatible is None:
                return {"status": "REVIEW_REQUIRED", "engine": "cp_sat", "allocations": [], "message": "Missing power compatibility rule.", "elapsed_seconds": monotonic()-started}
            if not compatible:
                separate(rules["opposed_power_transition_minutes"])
        gap = rules["different_site_transfer_minutes"] if ra["work_sector"] != rb["work_sector"] else 0
        same_engineer = model.new_bool_var(f"same_engineer_{ra['id']}_{rb['id']}")
        model.add(a["eng"] == b["eng"]).only_enforce_if(same_engineer)
        model.add(a["eng"] != b["eng"]).only_enforce_if(same_engineer.Not())
        separate(gap, same_engineer)
        if set(ra["required_equipment_ids"]) & set(rb["required_equipment_ids"]):
            separate(gap)
    for r in requests:
        for predecessor in r["depends_on"]:
            if predecessor not in tasks:
                return {"status": "INFEASIBLE", "engine": "cp_sat", "allocations": [], "message": f"{r['id']} has an unavailable predecessor {predecessor}.", "elapsed_seconds": monotonic()-started}
            model.add(tasks[predecessor]["end"] <= tasks[r["id"]]["start"])
    capacity = next(p["capacity"] for p in snapshot["resource_pools"] if p["id"] == "TECH")
    model.add_cumulative([tasks[r["id"]]["interval"] for r in requests], [r["technicians_required"] for r in requests], capacity)
    model.minimize(sum(cost_terms))
    validation_error = model.validate()
    if validation_error:
        return {"status": "MODEL_INVALID", "engine": "cp_sat", "allocations": [], "message": validation_error, "elapsed_seconds": monotonic()-started}
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 17
    status = solver.solve(model)
    result = {"status": solver.status_name(status), "engine": "cp_sat", "allocations": [], "elapsed_seconds": round(monotonic()-started, 4)}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        from datetime import timedelta
        for r in requests:
            if r["id"] in fixed:
                result["allocations"].append(fixed[r["id"]].copy())
            else:
                t = tasks[r["id"]]
                result["allocations"].append(make_allocation(r, base+timedelta(minutes=solver.value(t["start"])), engineer_ids[solver.value(t["eng"])], locked=True))
        result["objective"] = solver.objective_value
        result["message"] = "All active jobs allocated under the demo constraints. Officer approval is still required."
    else:
        result["message"] = "No feasible plan exists under this model." if status == cp_model.INFEASIBLE else "No plan returned within this solve; this is not proof of impossibility."
    return result
