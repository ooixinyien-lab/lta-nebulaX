"""Independent rule checker. Owner: backend / rules teammate.
Pure input -> structured issues. Never imports a solver and never writes the DB.
All constraints here are synthetic assumptions, not an operator safety rulebook.
"""
from itertools import combinations
from .common import dt, duration, overlap, zones


def issue(code, ids, message, resource=None):
    return {"code": code, "request_ids": sorted(set(ids)), "message": message,
            "resource": resource, "severity": "error"}


def unary_issues(snapshot: dict, request: dict, allocation: dict) -> list[dict]:
    r, a = request, allocation
    ids = [r["id"]]
    problems = []
    start, end = dt(a["start"]), dt(a["end"])
    if (end - start).total_seconds() != duration(r) * 60:
        problems.append(issue("DURATION", ids, "The complete setup/work/test/handback duration must be reserved."))
    if start.second or start.microsecond or start.minute % snapshot["planning_rules"]["start_grid_minutes"]:
        problems.append(issue("START_GRID", ids, "Start must lie on the configured minute grid."))
    if (start < dt(r["earliest_start"]) or end > dt(r["deadline"])
            or start.date().isoformat() not in r["allowed_dates"]):
        problems.append(issue("REQUEST_WINDOW", ids, "Allocation is outside the request's allowed dates or deadline."))
    for sid in r["protected_sectors"]:
        if not any(sid in w["sector_ids"] and dt(w["start"]) <= start and end <= dt(w["end"])
                   for w in snapshot["engineering_windows"]):
            problems.append(issue("ENGINEERING_WINDOW", ids, f"The full package is outside {sid}'s engineering window.", sid))
    for b in snapshot["blackouts"]:
        if set(r["protected_sectors"]) & set(b["sector_ids"]) and overlap(start, end, dt(b["start"]), dt(b["end"])):
            problems.append(issue("BLACKOUT", ids, f"Protection footprint overlaps restriction {b['id']}: {b['reason']}", b["id"]))
    eng = next((e for e in snapshot["engineers"] if e["id"] == a["engineer_id"]), None)
    if eng is None or eng["id"] not in r["eligible_engineers"] or r["required_skill"] not in eng["skills"]:
        problems.append(issue("QUALIFICATION", ids, "Assigned engineer does not have the required eligibility and skill.", a["engineer_id"]))
    if sorted(a["equipment_ids"]) != sorted(r["required_equipment_ids"]):
        problems.append(issue("EQUIPMENT_ASSIGNMENT", ids, "Allocation must include exactly the required equipment."))
    resources = ([eng] if eng else [])
    for qid in a["equipment_ids"]:
        q = next((q for q in snapshot["equipment"] if q["id"] == qid), None)
        if q is None or not q.get("serviceable", False):
            problems.append(issue("EQUIPMENT_UNAVAILABLE", ids, f"Equipment {qid} is unknown or out of service.", qid))
        if q:
            resources.append(q)
    for resource in resources:
        if not any(dt(w["start"]) <= start and end <= dt(w["end"]) for w in resource["availability"]):
            problems.append(issue("RESOURCE_WINDOW", ids, f"{resource['id']} is not available for the entire work package.", resource["id"]))
        if any(overlap(start, end, dt(w["start"]), dt(w["end"])) for w in resource.get("unavailable", [])):
            problems.append(issue("RESOURCE_UNAVAILABLE", ids, f"{resource['id']} has an absence/unavailable period.", resource["id"]))
    return problems


def check_plan(snapshot: dict, allocations: list[dict], require_all=False) -> list[dict]:
    """Return errors; [] means feasible ONLY under this fixture's model."""
    requests = {r["id"]: r for r in snapshot["requests"]}
    selected = {a["request_id"]: a for a in allocations}
    problems = []
    if len(selected) != len(allocations):
        problems.append(issue("DUPLICATE", list(selected), "A job occurs more than once in this plan."))
    unknown = set(selected) - set(requests)
    if unknown:
        return [issue("UNKNOWN_REQUEST", list(unknown), "Plan references unknown requests.")]
    if require_all:
        missing = {r["id"] for r in requests.values() if r["status"] in ("submitted", "scheduled")} - set(selected)
        if missing:
            problems.append(issue("MISSING_WORK", list(missing), "This starter schedules all active requests; work cannot be silently dropped."))
    for old in snapshot["committed_allocations"]:
        new = selected.get(old["request_id"])
        keys = ["start", "end", "engineer_id", "equipment_ids"]
        if old.get("locked") and (new is None or any(new[k] != old[k] for k in keys)):
            problems.append(issue("LOCKED_BOOKING", [old["request_id"]], "An existing locked booking was changed or removed."))
    for a in allocations:
        r = requests[a["request_id"]]
        if r["status"] == "cancelled":
            problems.append(issue("CANCELLED", [r["id"]], "Cancelled work cannot be allocated."))
        problems.extend(unary_issues(snapshot, r, a))
        for parent in r["depends_on"]:
            if parent not in selected or dt(selected[parent]["end"]) > dt(a["start"]):
                problems.append(issue("DEPENDENCY", [r["id"], parent], f"{r['id']} must start after {parent} has finished."))
    rules = snapshot["planning_rules"]
    from datetime import timedelta
    for a, b in combinations(allocations, 2):
        ra, rb = requests[a["request_id"]], requests[b["request_id"]]
        ids = [ra["id"], rb["id"]]
        sa, ea, sb, eb = dt(a["start"]), dt(a["end"]), dt(b["start"]), dt(b["end"])
        common_sectors = set(ra["protected_sectors"]) & set(rb["protected_sectors"])
        if common_sectors and overlap(sa, ea, sb, eb):
            label = ", ".join(sorted(common_sectors))
            problems.append(issue("SPACE", ids, f"Exclusive protection footprints overlap in {label}.", label))
        common_zones = zones(snapshot, ra) & zones(snapshot, rb)
        compatible = rules["power_compatibility"].get(ra["power_requirement"], {}).get(rb["power_requirement"])
        if common_zones and compatible is None:
            problems.append(issue("REVIEW_REQUIRED", ids, "Power compatibility rule missing. Do not assume permission."))
        elif common_zones and not compatible:
            guard = timedelta(minutes=rules["opposed_power_transition_minutes"])
            if not (ea + guard <= sb or eb + guard <= sa):
                label = ", ".join(sorted(common_zones))
                problems.append(issue("POWER", ids, f"Opposed power requirements in {label}; allow the configured {rules['opposed_power_transition_minutes']}-minute guard.", label))
        gap = rules["different_site_transfer_minutes"] if ra["work_sector"] != rb["work_sector"] else 0
        separated = ea + timedelta(minutes=gap) <= sb or eb + timedelta(minutes=gap) <= sa
        if a["engineer_id"] == b["engineer_id"] and not separated:
            problems.append(issue("ENGINEER", ids, f"{a['engineer_id']} is double-booked or lacks the {gap}-minute transfer allowance.", a["engineer_id"]))
        for q in set(a["equipment_ids"]) & set(b["equipment_ids"]):
            if not separated:
                problems.append(issue("EQUIPMENT", ids, f"{q} is double-booked or lacks the {gap}-minute transfer allowance.", q))
    capacity = next(p["capacity"] for p in snapshot["resource_pools"] if p["id"] == "TECH")
    ticks = sorted({dt(a[k]) for a in allocations for k in ["start", "end"]})
    for start, end in zip(ticks, ticks[1:]):
        active = [a for a in allocations if overlap(start, end, dt(a["start"]), dt(a["end"]))]
        demand = sum(requests[a["request_id"]]["technicians_required"] for a in active)
        if demand > capacity:
            ids = [a["request_id"] for a in active]
            problems.append(issue("MANPOWER", ids, f"{start.strftime('%d %b %H:%M')}-{end.strftime('%H:%M')}: technician demand {demand} exceeds capacity {capacity}.", "TECH"))
    return problems
