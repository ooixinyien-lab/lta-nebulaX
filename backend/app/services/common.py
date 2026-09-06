"""Small pure helpers shared by checker/solver (not constraint implementations)."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")

def dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timezone missing")
    return parsed.astimezone(SGT)

def duration(request: dict) -> int:
    return sum(p["duration_minutes"] for p in request["phases"])

def overlap(a, b, c, d) -> bool:
    return a < d and c < b

def make_allocation(request, start, engineer, locked=False):
    start = dt(start) if isinstance(start, str) else start
    return {"request_id": request["id"], "start": start.isoformat(),
            "end": (start + timedelta(minutes=duration(request))).isoformat(),
            "engineer_id": engineer, "equipment_ids": request["required_equipment_ids"].copy(),
            "locked": locked}

def zones(snapshot, request):
    ids = set(request["protected_sectors"])
    return {s["power_zone"] for s in snapshot["sectors"] if s["id"] in ids}

def preferred_plan(snapshot):
    allocations = [a.copy() for a in snapshot["committed_allocations"]]
    booked = {a["request_id"] for a in allocations}
    for r in snapshot["requests"]:
        if r["status"] == "submitted" and r["id"] not in booked:
            engineer = r.get("preferred_engineer") or next(iter(r["eligible_engineers"]), "UNASSIGNED")
            allocations.append(make_allocation(r, r["preferred_start"], engineer))
    return allocations
