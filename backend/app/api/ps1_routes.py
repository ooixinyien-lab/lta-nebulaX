"""PS1 database-backed upload and run lifecycle endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pydantic import Field
from backend.app.domain_models import PS1Base
from backend.app.db.records import decode, get

from backend.app.auth.dependencies import current_user
from backend.app.db.models import Instance, InstanceRevision, RunAccess, RunContractResult, RunOccupancy, SolverRun
from backend.app.db.repositories.audit import record_event
from backend.app.db.repositories.instances import fingerprint_files, find_fingerprint
from backend.app.db.seed import OFFICIAL_FILES, validate_bundle, import_bundle
from backend.app.db.repositories.runs import create_run
from backend.app.db.reset import clear_planning_data
from backend.app.ps1.run_worker import execute_official_run
from backend.app.io import DataLayerError
from backend.app.schemas import User

router = APIRouter(prefix="/api/ps1", tags=["ps1"])

EXPECTED_FILES = set(OFFICIAL_FILES)


class SolveRequest(PS1Base):
    instance_id: str
    instance_revision_id: str | None = None
    scenario: str = Field(pattern="^[ABC]$")
    time_limit_seconds: float = Field(default=60.0, ge=0.1, le=3600)
    baseline_run_id: str | None = None


def _db(request: Request):
    return request.app.state.db


@router.post("/instances/upload", status_code=201)
async def upload_instance(request: Request, files: list[UploadFile] = File(...), user: User = Depends(current_user)):
    supplied = {f.filename for f in files if f.filename}
    if supplied != EXPECTED_FILES or len(files) != len(EXPECTED_FILES):
        missing = sorted(EXPECTED_FILES - supplied)
        extra = sorted(supplied - EXPECTED_FILES)
        raise HTTPException(422, {"message": "Exactly the eight official CSV files are required", "missing": missing, "extra": extra})
    contents: dict[str, bytes] = {}
    for upload in files:
        contents[upload.filename] = await upload.read()
    try:
        problem = validate_bundle(contents)
    except (UnicodeDecodeError, DataLayerError, ValueError) as exc:
        raise HTTPException(422, f"CSV validation failed: {exc}") from exc

    fingerprint = fingerprint_files(contents)
    with _db(request).connection(write=True) as session:
        existing = find_fingerprint(session, fingerprint)
        if existing is not None:
            raise HTTPException(409, {"message": "Identical eight-file CSV bundle already exists",
                "instance_id": existing.instance_id, "revision_id": existing.id, "fingerprint": fingerprint})
        instance, revision = import_bundle(session, contents, problem, actor=user.id, name=files[0].filename or "PS1 instance")
        return {"instance_id": instance.id, "revision_id": revision.id, "fingerprint": fingerprint, "validation_status": revision.validation_status, "duplicate": False, "entity_counts": {"lines": len(problem.lines), "stations": len(problem.stations), "sectors": len(problem.sectors), "locations": len(problem.locations), "contracts": len(problem.contracts), "activities": len(problem.activities), "horizon_weeks": problem.parameters.horizon_weeks}}


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        instance = get(session, Instance, instance_id)
        if instance is None:
            raise HTTPException(404, "Instance not found")
        revisions = [decode(InstanceRevision, row) for row in session.execute("SELECT * FROM instance_revisions WHERE instance_id=? ORDER BY revision_number DESC", (instance_id,))]
        return {"id": instance.id, "name": instance.name, "fingerprint": instance.fingerprint, "created_by": instance.created_by, "revisions": [{"id": x.id, "revision_number": x.revision_number, "validation_status": x.validation_status, "created_at": x.created_at.isoformat()} for x in revisions]}


@router.post("/solve", status_code=202)
def queue_solve(payload: SolveRequest, request: Request, user: User = Depends(current_user)):
    with _db(request).connection(write=True) as session:
        if payload.instance_revision_id:
            revision = decode(InstanceRevision, session.execute(
                "SELECT * FROM instance_revisions WHERE id=? AND instance_id=?",
                (payload.instance_revision_id, payload.instance_id),
            ).fetchone())
        else:
            revision = decode(InstanceRevision, session.execute("SELECT * FROM instance_revisions WHERE instance_id=? ORDER BY revision_number DESC LIMIT 1", (payload.instance_id,)).fetchone())
        if revision is None:
            raise HTTPException(404, "Instance has no revision")
        run = create_run(session, revision_id=revision.id, scenario=payload.scenario, created_by=user.id, time_limit=payload.time_limit_seconds, baseline_run_id=payload.baseline_run_id)
        record_event(session, actor=user.id, action="solver_run_queued", entity_type="solver_run", entity_id=run.id, detail={"scenario": payload.scenario})
        response = {"run_id": run.id, "instance_id": payload.instance_id, "revision_id": revision.id, "scenario": run.scenario, "status": run.status, "created_at": run.created_at.isoformat()}
    return response


@router.post("/runs/{run_id}/execute", status_code=202)
def execute_run(run_id: str, request: Request, background_tasks: BackgroundTasks, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        run = get(session, SolverRun, run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        if run.status != "QUEUED":
            raise HTTPException(409, "Only a queued run can be executed")
    background_tasks.add_task(execute_official_run, _db(request), run_id)
    return {"run_id": run_id, "status": "QUEUED"}


@router.get("/runs/{run_id}/progress")
def run_progress(run_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        run = get(session, SolverRun, run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return {"run_id": run.id, "status": run.status, "phase": run.phase, "elapsed_seconds": ((run.finished_at or datetime.now(timezone.utc)).replace(tzinfo=timezone.utc) - run.started_at.replace(tzinfo=timezone.utc)).total_seconds() if run.started_at else 0, "solver_status": run.status, "workload_complete": run.workload_complete, "incumbent_score": run.incumbent_score}


@router.get("/runs/{run_id}/results")
def run_results(run_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        run = get(session, SolverRun, run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        accesses = [decode(RunAccess, row) for row in session.execute("SELECT * FROM run_accesses WHERE run_id=? ORDER BY activity_id,access_seq", (run_id,))]
        occupancy = [decode(RunOccupancy, row) for row in session.execute("SELECT * FROM run_occupancies WHERE run_id=? ORDER BY week,location_id,activity_id", (run_id,))]
        contracts = [decode(RunContractResult, row) for row in session.execute("SELECT * FROM run_contract_results WHERE run_id=? ORDER BY contract_number", (run_id,))]
        revision = get(session, InstanceRevision, run.revision_id)
        return {"run_id": run.id, "instance_id": revision.instance_id if revision else None, "revision_id": run.revision_id, "scenario": run.scenario, "status": run.status, "workload_complete": run.workload_complete, "accesses": [{"activity_id": x.activity_id, "access_seq": x.access_seq, "week": x.week, "eclo": x.eclo, "access_night": x.access_night} for x in accesses], "occupancy": [{"activity_id": x.activity_id, "week": x.week, "location_id": x.location_id, "co_share_group": x.co_share_group} for x in occupancy], "contract_results": [{"scenario": x.scenario, "contract_number": x.contract_number, "simulated_completion_date": x.simulated_completion_date.isoformat(), "overrun_days": x.overrun_days} for x in contracts]}


def _chat_service(request: Request):
    from backend.app.ps1.chat_service import ChatService
    if not hasattr(request.app.state, "chat_service"):
        request.app.state.chat_service = ChatService(request.app.state.settings)
    return request.app.state.chat_service


@router.get("/runs/{run_id}/explanations/{activity_id}")
def get_activity_explanation(
    run_id: str,
    activity_id: str,
    request: Request,
    baseline_run_id: str | None = None,
    user: User = Depends(current_user),
):
    service = _chat_service(request)
    with _db(request).connection(write=True) as session:
        return service.get_or_build_explanation(
            session=session,
            run_id=run_id,
            activity_id=activity_id,
            user=user,
            baseline_run_id=baseline_run_id,
        )


@router.post("/chat")
def post_chat(
    request: Request,
    payload: dict,
    user: User = Depends(current_user),
):
    from backend.app.ps1.chat_models import ChatRequest
    chat_req = ChatRequest.model_validate(payload)
    service = _chat_service(request)
    with _db(request).connection(write=True) as session:
        return service.handle_chat_turn(
            session=session,
            payload=chat_req,
            user=user,
        )


@router.get("/planning-context")
def planning_context(request: Request, user: User = Depends(current_user)):
    """Return selectable identities; never select a schedule on the client's behalf."""
    with _db(request).connection() as session:
        instances = [dict(row) for row in session.execute(
            "SELECT i.id instance_id,r.id revision_id,r.revision_number,r.created_at "
            "FROM instances i JOIN instance_revisions r ON r.instance_id=i.id "
            "WHERE r.validation_status='VALID' ORDER BY r.created_at DESC"
        )]
        official_runs = [dict(row) for row in session.execute(
            "SELECT id run_id,revision_id,scenario,status,created_at FROM solver_runs "
            "WHERE status='SUCCEEDED' ORDER BY created_at DESC"
        )]
        baselines = [dict(row) for row in session.execute(
            "SELECT baseline_key baseline_id,revision baseline_revision,official_revision_id,created_at "
            "FROM schedule_insertion_baselines ORDER BY created_at DESC"
        )]
        operational_runs = [dict(row) for row in session.execute(
            "SELECT id run_id,baseline_key baseline_id,baseline_revision,scenario,status,created_at "
            "FROM schedule_insertion_runs ORDER BY created_at DESC"
        )]
    return {"instances": instances, "official_runs": official_runs, "operational_baselines": baselines, "operational_runs": operational_runs}


@router.delete("/planning-data")
def reset_planning_data(request: Request, user: User = Depends(current_user)):
    with _db(request).connection(write=True) as session:
        deleted = clear_planning_data(session)
    request.app.state.network_map_service = None
    return {"status": "cleared", "deleted": deleted}
