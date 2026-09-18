"""Operational schedule-insertion API.

These endpoints intentionally do not expose the official PS1 export routes.
They return versioned operational records, exact service dates and explicit
validation provenance instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth.dependencies import current_user
from backend.app.db.repositories.instances import load_revision
from backend.app.db.records import get
from backend.app.db.models import InstanceRevision
from backend.app.domain_models import PS1Base
from backend.app.schedule_insertion.config import ScheduleInsertionConfig
from backend.app.schedule_insertion.models import (
    BaselineBundle,
    ProjectAddition,
    ReplanRequest,
)
from backend.app.schedule_insertion.persistence import (
    list_baseline_revisions,
    load_baseline,
    load_run,
    save_baseline,
    save_run,
)
from backend.app.schedule_insertion.solver import solve_schedule_insertion
from backend.app.schedule_insertion.validation import validate_maintenance_fixture
from backend.app.schemas import User


router = APIRouter(prefix="/api/ps1/schedule-insertion", tags=["ps1-schedule-insertion"])


class BaselineImportRequest(PS1Base):
    baseline: BaselineBundle
    official_revision_id: str | None = None


class AdditionsRequest(PS1Base):
    baseline_revision: int
    additions: list[ProjectAddition]


class SolveRequest(PS1Base):
    official_revision_id: str | None = None
    request: ReplanRequest


class PromoteRunRequest(PS1Base):
    expected_baseline_revision: int


def _db(request: Request):
    return request.app.state.db


def _official_problem(request: Request, revision_id: str | None):
    with _db(request).connection() as session:
        selected = revision_id
        if selected is None:
            row = session.execute("SELECT id FROM instance_revisions ORDER BY created_at DESC LIMIT 1").fetchone()
            selected = row[0] if row else None
        if selected is None or get(session, InstanceRevision, selected) is None:
            raise HTTPException(404, "Official instance revision not found")
        return load_revision(session, selected), selected


@router.post("/baselines", status_code=201)
def import_baseline(payload: BaselineImportRequest, request: Request, user: User = Depends(current_user)):
    problem, official_revision_id = _official_problem(request, payload.official_revision_id or payload.baseline.official_revision_id)
    config = ScheduleInsertionConfig(horizon_weeks=payload.baseline.horizon_weeks)
    validation = validate_maintenance_fixture(problem, payload.baseline, config=config)
    if not validation.passed:
        raise HTTPException(422, {"message": "Baseline failed operational maintenance validation", "findings": [finding.model_dump(mode="json") for finding in validation.findings]})
    with _db(request).connection(write=True) as session:
        stored = save_baseline(session, payload.baseline, actor=user.id, official_revision_id=official_revision_id)
    return {"baseline": stored.model_dump(mode="json"), "validation": validation.model_dump(mode="json"), "official_revision_id": official_revision_id}


@router.get("/baselines/{baseline_id}")
def get_baseline(baseline_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        baseline = load_baseline(session, baseline_id)
        if baseline is None:
            raise HTTPException(404, "Operational baseline not found")
        return {"baseline": baseline.model_dump(mode="json"), "revisions": list_baseline_revisions(session, baseline_id)}


@router.post("/baselines/{baseline_id}/additions", status_code=201)
def add_jobs(baseline_id: str, payload: AdditionsRequest, request: Request, user: User = Depends(current_user)):
    with _db(request).connection(write=True) as session:
        baseline = load_baseline(session, baseline_id, payload.baseline_revision)
        if baseline is None:
            raise HTTPException(409, "Baseline revision is stale or missing")
        existing = {job.job_id for job in baseline.project_jobs}
        additions = [addition.job for addition in payload.additions if addition.job.job_id not in existing]
        updated = baseline.model_copy(update={"project_jobs": baseline.project_jobs + additions})
        stored = save_baseline(session, updated, actor=user.id, official_revision_id=baseline.official_revision_id)
    return {"baseline": stored.model_dump(mode="json"), "added_job_ids": [job.job_id for job in additions]}


@router.post("/runs", status_code=201)
def solve(payload: SolveRequest, request: Request, user: User = Depends(current_user)):
    problem, official_revision_id = _official_problem(request, payload.official_revision_id)
    with _db(request).connection() as session:
        baseline = load_baseline(session, payload.request.baseline_id, payload.request.baseline_revision)
    if baseline is None:
        raise HTTPException(409, "Baseline revision is stale or missing")
    result = solve_schedule_insertion(problem, baseline, payload.request, config=ScheduleInsertionConfig(horizon_weeks=baseline.horizon_weeks))
    with _db(request).connection(write=True) as session:
        run_id = save_run(session, result, actor=user.id, official_revision_id=official_revision_id)
    return {"run_id": run_id, "result": result.model_dump(mode="json")}


@router.post("/baselines/{baseline_id}/from-run/{run_id}", status_code=201)
def promote_run(
    baseline_id: str,
    run_id: str,
    payload: PromoteRunRequest,
    request: Request,
    user: User = Depends(current_user),
):
    """Accept a validated operational run as the next immutable baseline."""

    with _db(request).connection(write=True) as session:
        baseline = load_baseline(session, baseline_id, payload.expected_baseline_revision)
        result = load_run(session, run_id)
        if baseline is None or result is None or result.baseline_id != baseline_id or result.baseline_revision != baseline.revision:
            raise HTTPException(409, "Baseline or run revision is stale")
        candidate = result.lower_disruption_candidate or result.reference_candidate
        if result.status != "SUCCEEDED" or candidate is None or not candidate.validation.passed:
            raise HTTPException(409, "Only a complete validated run can become a baseline")
        updated = baseline.model_copy(update={"project_accesses": candidate.projects})
        stored = save_baseline(session, updated, actor=user.id, official_revision_id=baseline.official_revision_id)
    return {"baseline": stored.model_dump(mode="json"), "source_run_id": run_id}


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        result = load_run(session, run_id)
    if result is None:
        raise HTTPException(404, "Schedule-insertion run not found")
    return result.model_dump(mode="json")


@router.get("/runs/{run_id}/diff")
def get_diff(run_id: str, request: Request, user: User = Depends(current_user)):
    with _db(request).connection() as session:
        result = load_run(session, run_id)
    if result is None:
        raise HTTPException(404, "Schedule-insertion run not found")
    candidate = result.lower_disruption_candidate or result.reference_candidate
    return {
        "run_id": run_id,
        "baseline_id": result.baseline_id,
        "baseline_revision": result.baseline_revision,
        "scenario": result.scenario.value,
        "scenario_cost": candidate.cost.model_dump(mode="json") if candidate else None,
        "disruption": candidate.disruption.model_dump(mode="json") if candidate else None,
        "published_candidate": result.published_candidate,
    }
