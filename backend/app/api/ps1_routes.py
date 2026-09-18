"""PS1 database-backed upload and run lifecycle endpoints."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.app.auth.dependencies import current_user
from backend.app.config import Settings
from backend.app.db.models import Instance, InstanceRevision, RunAccess, RunContractResult, RunOccupancy, SolverRun
from backend.app.db.repositories.audit import record_event
from backend.app.db.repositories.instances import create_instance_revision, fingerprint_files
from backend.app.db.repositories.runs import create_run
from backend.app.io import DataLayerError, load_problem_from_streams
from backend.app.schemas import User

router = APIRouter(prefix="/api/ps1", tags=["ps1"])

EXPECTED_FILES = {
    "01_LINES.csv", "02_STATIONS.csv", "03_SECTORS.csv", "04_LOCATION_SUPPLY.csv",
    "05_BUFFER_LOCATION.csv", "06_PARAMETERS.csv", "07_PROJECT_DETAILS.csv", "08_ACTIVITY_DETAILS.csv",
}


class SolveRequest(BaseModel):
    instance_id: str
    scenario: str = Field(pattern="^[ABC]$")
    time_limit_seconds: float = Field(default=60.0, ge=0.1, le=3600)
    baseline_run_id: str | None = None


def _db(request: Request):
    return request.app.state.ps1_db


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
        streams = {name: contents[name].decode("utf-8-sig") for name in EXPECTED_FILES}
        problem = load_problem_from_streams(streams)
    except (UnicodeDecodeError, DataLayerError, ValueError) as exc:
        raise HTTPException(422, f"CSV validation failed: {exc}") from exc

    settings: Settings = request.app.state.settings
    fingerprint = fingerprint_files(contents)
    storage_dir = Path(settings.upload_storage_path) / fingerprint
    storage_dir.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for name, content in contents.items():
        path = storage_dir / name
        path.write_bytes(content)
        metadata[name] = {"filename": name, "storage_key": str(path), "sha256": fingerprint_files({name: content}), "size_bytes": len(content)}

    with _db(request).session() as session:
        instance, revision = create_instance_revision(
            session, problem, name=files[0].filename or "PS1 instance", created_by=user.id,
            input_fingerprint=fingerprint, files=metadata,
        )
        record_event(session, actor=user.id, action="instance_uploaded", entity_type="instance_revision", entity_id=revision.id, detail={"file_count": len(files)})
        return {"instance_id": instance.id, "revision_id": revision.id, "fingerprint": fingerprint, "validation_status": revision.validation_status, "entity_counts": {"lines": len(problem.lines), "stations": len(problem.stations), "sectors": len(problem.sectors), "locations": len(problem.locations), "contracts": len(problem.contracts), "activities": len(problem.activities), "horizon_weeks": problem.parameters.horizon_weeks}}


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).session() as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            raise HTTPException(404, "Instance not found")
        revisions = session.scalars(select(InstanceRevision).where(InstanceRevision.instance_id == instance_id).order_by(InstanceRevision.revision_number.desc())).all()
        return {"id": instance.id, "name": instance.name, "fingerprint": instance.fingerprint, "created_by": instance.created_by, "revisions": [{"id": x.id, "revision_number": x.revision_number, "validation_status": x.validation_status, "created_at": x.created_at.isoformat()} for x in revisions]}


@router.post("/solve", status_code=202)
def queue_solve(payload: SolveRequest, request: Request, user: User = Depends(current_user)):
    with _db(request).session() as session:
        revision = session.scalar(select(InstanceRevision).where(InstanceRevision.instance_id == payload.instance_id).order_by(InstanceRevision.revision_number.desc()))
        if revision is None:
            raise HTTPException(404, "Instance has no revision")
        run = create_run(session, revision_id=revision.id, scenario=payload.scenario, created_by=user.id, time_limit=payload.time_limit_seconds, baseline_run_id=payload.baseline_run_id)
        record_event(session, actor=user.id, action="solver_run_queued", entity_type="solver_run", entity_id=run.id, detail={"scenario": payload.scenario})
        return {"run_id": run.id, "instance_id": payload.instance_id, "revision_id": revision.id, "scenario": run.scenario, "status": run.status, "created_at": run.created_at.isoformat()}


@router.get("/runs/{run_id}/progress")
def run_progress(run_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).session() as session:
        run = session.get(SolverRun, run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return {"run_id": run.id, "status": run.status, "phase": run.phase, "elapsed_seconds": ((run.finished_at or run.started_at) - run.started_at).total_seconds() if run.started_at and (run.finished_at or run.started_at) else 0, "solver_status": run.status, "workload_complete": run.workload_complete, "incumbent_score": run.incumbent_score}


@router.get("/runs/{run_id}/results")
def run_results(run_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).session() as session:
        run = session.get(SolverRun, run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        accesses = session.scalars(select(RunAccess).where(RunAccess.run_id == run_id).order_by(RunAccess.activity_id, RunAccess.access_seq)).all()
        occupancy = session.scalars(select(RunOccupancy).where(RunOccupancy.run_id == run_id).order_by(RunOccupancy.week, RunOccupancy.location_id, RunOccupancy.activity_id)).all()
        contracts = session.scalars(select(RunContractResult).where(RunContractResult.run_id == run_id).order_by(RunContractResult.contract_number)).all()
        return {"run_id": run.id, "revision_id": run.revision_id, "scenario": run.scenario, "status": run.status, "workload_complete": run.workload_complete, "accesses": [{"activity_id": x.activity_id, "access_seq": x.access_seq, "week": x.week, "eclo": x.eclo, "access_night": x.access_night} for x in accesses], "occupancy": [{"activity_id": x.activity_id, "week": x.week, "location_id": x.location_id, "co_share_group": x.co_share_group} for x in occupancy], "contract_results": [{"scenario": x.scenario, "contract_number": x.contract_number, "simulated_completion_date": x.simulated_completion_date.isoformat(), "overrun_days": x.overrun_days} for x in contracts]}
