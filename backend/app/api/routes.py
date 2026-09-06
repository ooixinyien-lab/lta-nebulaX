"""API owner: backend teammate. Inputs/outputs documented in docs/API_CONTRACT.md."""
import json
import sqlite3
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from ..auth.dependencies import current_user, officer_only
from ..config import DEMO_USERS
from ..schemas import User, RequestCreate, CommitInput, ResourceChange
from ..services.checker import check_plan
from ..services.common import preferred_plan
from ..services.scheduler import solve

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {"ok": True, "application": "RailPlan starter"}

@router.get("/config")
def public_config(request: Request):
    s = request.app.state.settings
    return {"auth_mode": s.auth_mode, "solver_engine": s.solver_engine,
            "demo_users": list(DEMO_USERS.values()) if s.auth_mode == "demo" else [],
            "supabase_url": s.supabase_url if s.auth_mode == "supabase" else "",
            "supabase_publishable_key": s.supabase_publishable_key if s.auth_mode == "supabase" else "",
            "synthetic": True}

@router.get("/me", response_model=User)
def me(user: User = Depends(current_user)):
    return user

@router.get("/planning-snapshot")
def get_snapshot(request: Request, user: User = Depends(current_user)):
    snapshot = request.app.state.db.snapshot()
    all_requests = {r["id"]: r for r in snapshot["requests"]}
    snapshot["occupancy"] = [{"start": a["start"], "end": a["end"],
        "protected_sectors": all_requests[a["request_id"]]["protected_sectors"],
        "label": a["request_id"] if user.role == "officer" or all_requests[a["request_id"]]["owner_id"] == user.id else "Reserved"}
        for a in snapshot["committed_allocations"]]
    if user.role != "officer":
        snapshot["requests"] = [r for r in snapshot["requests"] if r["owner_id"] == user.id]
        own = {r["id"] for r in snapshot["requests"]}
        snapshot["committed_allocations"] = [a for a in snapshot["committed_allocations"] if a["request_id"] in own]
    return snapshot

@router.post("/requests", status_code=201)
def create_request(payload: RequestCreate, request: Request, user: User = Depends(current_user)):
    if user.role != "requester":
        raise HTTPException(403, "Use a requester account to submit maintenance work")
    db = request.app.state.db
    with db.connection(write=True) as c:
        s = db.snapshot(c)
        if len([r for r in s["requests"] if r["status"] != "cancelled"]) >= 40:
            raise HTTPException(409, "Starter is capped at 40 active requests")
        raw = payload.model_dump(mode="json")
        sectors = {x["id"]: x for x in s["sectors"]}
        if not set(raw["protected_sectors"]) <= sectors.keys():
            raise HTTPException(422, "Unknown protection sector")
        equipment = {q["id"] for q in s["equipment"]}
        if not set(raw["required_equipment_ids"]) <= equipment:
            raise HTTPException(422, "Unknown equipment")
        eligible = [e["id"] for e in s["engineers"] if raw["required_skill"] in e["skills"]]
        if not eligible:
            raise HTTPException(422, "Unknown skill or no qualified engineer in the catalog")
        if raw["preferred_engineer"] is not None and raw["preferred_engineer"] not in eligible:
            raise HTTPException(422, "Preferred engineer is not eligible for this skill")
        own_ids = {r["id"] for r in s["requests"] if r["owner_id"] == user.id and r["status"] != "cancelled"}
        if not set(raw["depends_on"]) <= own_ids:
            raise HTTPException(422, "New requests may reference your own active requests as prerequisites")
        if not set(raw["allowed_dates"]) <= {w["date"] for w in s["engineering_windows"]}:
            raise HTTPException(422, "Date is outside the seeded planning calendar")
        if payload.preferred_start.date().isoformat() not in raw["allowed_dates"]:
            raise HTTPException(422, "Preferred start must be on an allowed date")
        if payload.preferred_start.minute % s["planning_rules"]["start_grid_minutes"]:
            raise HTTPException(422, "Preferred start must be on the five-minute grid")
        raw.update(id="R-" + uuid4().hex[:6].upper(), owner_id=user.id, status="submitted",
                   eligible_engineers=eligible, power_zone=sectors[raw["work_sector"]]["power_zone"],
                   mandatory_in_this_demo=True, priority="normal", split_allowed=False)
        c.execute("INSERT INTO requests VALUES (?,?,?)", (raw["id"], user.id, json.dumps(raw)))
        db.bump(c)
        db.audit(c, user.id, "request_submitted", raw["id"])
    return raw

@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: str, request: Request, user: User = Depends(current_user)):
    db = request.app.state.db
    with db.connection(write=True) as c:
        row = c.execute("SELECT payload FROM requests WHERE id=?", (request_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Request not found")
        r = json.loads(row["payload"])
        if r["owner_id"] != user.id:
            raise HTTPException(404, "Request not found")
        if r["status"] != "submitted":
            raise HTTPException(409, "Only an unbooked submitted request can be withdrawn")
        s = db.snapshot(c)
        if any(request_id in x["depends_on"] and x["status"] != "cancelled" for x in s["requests"]):
            raise HTTPException(409, "Another active request depends on this one")
        r["status"] = "cancelled"
        c.execute("UPDATE requests SET payload=? WHERE id=?", (json.dumps(r), request_id))
        db.bump(c)
        db.audit(c, user.id, "request_withdrawn", request_id)
    return {"ok": True}

@router.post("/conflicts/check")
def conflicts(request: Request, user: User = Depends(officer_only)):
    snapshot = request.app.state.db.snapshot()
    return {"planning_version": snapshot["metadata"]["planning_version"],
            "issues": check_plan(snapshot, preferred_plan(snapshot), require_all=True)}

@router.post("/schedule/proposals")
def propose(request: Request, user: User = Depends(officer_only)):
    db, settings = request.app.state.db, request.app.state.settings
    snapshot = db.snapshot()
    if not any(r["status"] == "submitted" for r in snapshot["requests"]):
        raise HTTPException(409, "No pending requests to schedule")
    result = solve(snapshot, settings.solver_engine, settings.solver_time_limit_seconds)
    proposal = {**result, "id": "P-" + uuid4().hex[:10], "planning_version": snapshot["metadata"]["planning_version"],
                "status_workflow": "draft", "created_by": user.id}
    if result.get("allocations"):
        originals = {a["request_id"]: a for a in snapshot["committed_allocations"]}
        reqs = {r["id"]: r for r in snapshot["requests"]}
        proposal["changes"] = [{"request_id": a["request_id"], "title": reqs[a["request_id"]]["title"],
            "preferred_start": reqs[a["request_id"]]["preferred_start"], "start": a["start"], "end": a["end"], "engineer_id": a["engineer_id"],
            "explanation": "New allocation within the encoded constraints; complete plan independently rechecked."}
            for a in result["allocations"] if a["request_id"] not in originals]
        with db.connection(write=True) as c:
            if db.snapshot(c)["metadata"]["planning_version"] != proposal["planning_version"]:
                raise HTTPException(409, "Inputs changed while solving. Generate a new proposal.")
            c.execute("INSERT INTO proposals VALUES (?,?)", (proposal["id"], json.dumps(proposal)))
            db.audit(c, user.id, "proposal_generated", proposal["id"])
    return proposal

@router.get("/proposals")
def list_proposals(request: Request, user: User = Depends(officer_only)):
    with request.app.state.db.connection() as c:
        return [json.loads(r["payload"]) for r in c.execute("SELECT payload FROM proposals ORDER BY rowid DESC LIMIT 10")]

@router.post("/proposals/{proposal_id}/commit")
def commit(proposal_id: str, payload: CommitInput, request: Request, user: User = Depends(officer_only)):
    """The officer's click is the approval in this starter. No automatic railway authority."""
    db = request.app.state.db
    with db.connection(write=True) as c:
        row = c.execute("SELECT payload FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Proposal not found")
        p = json.loads(row["payload"])
        if p["status_workflow"] != "draft":
            raise HTTPException(409, "Proposal is already committed")
        s = db.snapshot(c)
        if p["planning_version"] != payload.expected_version or p["planning_version"] != s["metadata"]["planning_version"]:
            raise HTTPException(409, "This proposal is stale. Generate and approve a fresh plan.")
        errors = check_plan(s, p["allocations"], require_all=True)
        if errors:
            raise HTTPException(409, {"message": "Revalidation failed; nothing was changed", "issues": errors})
        for a in p["allocations"]:
            c.execute("INSERT OR REPLACE INTO allocations VALUES (?,?)", (a["request_id"], json.dumps(a)))
            original = next(r for r in s["requests"] if r["id"] == a["request_id"])
            original["status"] = "scheduled"
            c.execute("UPDATE requests SET payload=? WHERE id=?", (json.dumps(original), original["id"]))
        p["status_workflow"] = "committed"
        p["approved_by"] = user.id
        c.execute("UPDATE proposals SET payload=? WHERE id=?", (json.dumps(p), proposal_id))
        db.bump(c)
        db.audit(c, user.id, "proposal_approved_and_committed", proposal_id)
        version = db.snapshot(c)["metadata"]["planning_version"]
    return {"ok": True, "planning_version": version}

@router.patch("/resources")
def change_resource(payload: ResourceChange, request: Request, user: User = Depends(officer_only)):
    db = request.app.state.db
    with db.connection(write=True) as c:
        s = db.snapshot(c)
        resource = next((x for x in s[payload.kind] if x["id"] == payload.id), None)
        if resource is None:
            raise HTTPException(404, "Resource not found")
        if payload.unavailable_from:
            resource.setdefault("unavailable", []).append({"start": payload.unavailable_from.isoformat(), "end": payload.unavailable_to.isoformat()})
        if payload.serviceable is not None:
            resource["serviceable"] = payload.serviceable
        db.save_catalog(c, s)
        db.bump(c)
        db.audit(c, user.id, "resource_changed", f"{payload.kind}:{payload.id}")
    return {"ok": True}

@router.get("/audit")
def audit(request: Request, user: User = Depends(officer_only)):
    with request.app.state.db.connection() as c:
        return [dict(x) for x in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 30")]

@router.post("/demo/reset")
def reset(request: Request, user: User = Depends(officer_only)):
    s = request.app.state.settings
    if s.auth_mode != "demo" or s.app_env == "production":
        raise HTTPException(404, "Demo reset disabled")
    with request.app.state.db.connection(write=True) as c:
        request.app.state.db.seed(c)
    return {"ok": True}
