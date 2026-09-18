"""Repositories for asynchronous solver runs and immutable outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow, ScenarioResultRow
from backend.app.db.models import RunAccess, RunArtifact, RunContractResult, RunOccupancy, RunValidationReport, SolverRun


def create_run(session: Session, *, revision_id: str, scenario: str, created_by: str, time_limit: float, baseline_run_id: str | None = None) -> SolverRun:
    run = SolverRun(id=f"run-{uuid4().hex}", revision_id=revision_id, scenario=scenario, baseline_run_id=baseline_run_id, requested_time_limit=time_limit, created_by=created_by)
    session.add(run)
    session.flush()
    return run


def claim_next_run(session: Session) -> SolverRun | None:
    """Atomically claim one queued run; PostgreSQL workers may call this concurrently."""
    query = select(SolverRun).where(SolverRun.status == "QUEUED").order_by(SolverRun.created_at).with_for_update(skip_locked=True).limit(1)
    run = session.scalar(query)
    if run:
        run.status = "RUNNING"
        run.phase = "FEASIBILITY"
        run.started_at = datetime.now(timezone.utc)
    return run


def update_progress(session: Session, run_id: str, *, phase: str | None = None, score: float | None = None, workload_complete: bool | None = None) -> SolverRun:
    run = session.get(SolverRun, run_id)
    if run is None:
        raise KeyError(run_id)
    if phase is not None:
        run.phase = phase
    if score is not None:
        run.incumbent_score = score
    if workload_complete is not None:
        run.workload_complete = workload_complete
    return run


def store_results(session: Session, run_id: str, access: list[AccessScheduleRow], occupancy: list[OccupancyScheduleRow], results: list[ScenarioResultRow]) -> None:
    session.add_all([RunAccess(run_id=run_id, activity_id=x.activity_id, access_seq=x.access_seq, week=x.week, eclo=x.eclo, access_night=x.access_night) for x in access])
    session.add_all([RunOccupancy(run_id=run_id, activity_id=x.activity_id, week=x.week, location_id=x.location_id, co_share_group=x.co_share_group) for x in occupancy])
    session.add_all([RunContractResult(run_id=run_id, scenario=x.scenario, contract_number=x.contract_number, simulated_completion_date=x.simulated_completion_date, overrun_days=x.overrun_days) for x in results])


def finish_run(session: Session, run_id: str, *, status: str, error_message: str | None = None) -> SolverRun:
    run = session.get(SolverRun, run_id)
    if run is None:
        raise KeyError(run_id)
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.error_message = error_message
    return run
