"""Repositories for asynchronous solver runs and immutable outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlite3 import Connection
from backend.app.db.records import decode, get, insert, insert_many

from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow, ScenarioResultRow
from backend.app.db.models import RunAccess, RunArtifact, RunContractResult, RunOccupancy, RunValidationReport, SolverRun


def create_run(session: Connection, *, revision_id: str, scenario: str, created_by: str, time_limit: float, baseline_run_id: str | None = None) -> SolverRun:
    run = SolverRun(id=f"run-{uuid4().hex}", revision_id=revision_id, scenario=scenario, baseline_run_id=baseline_run_id, requested_time_limit=time_limit, created_by=created_by)
    insert(session, run)
    return run


def claim_next_run(session: Connection) -> SolverRun | None:
    """Claim within the caller's BEGIN IMMEDIATE transaction."""
    row = session.execute("SELECT * FROM solver_runs WHERE status='QUEUED' ORDER BY created_at,id LIMIT 1").fetchone()
    if row is None:
        return None
    session.execute("UPDATE solver_runs SET status='RUNNING',phase='FEASIBILITY',started_at=? WHERE id=? AND status='QUEUED'",
                    (datetime.now(timezone.utc).isoformat(), row['id']))
    return get(session, SolverRun, row['id'])


def update_progress(session: Connection, run_id: str, *, phase: str | None = None, score: float | None = None, workload_complete: bool | None = None) -> SolverRun:
    if get(session, SolverRun, run_id) is None:
        raise KeyError(run_id)
    session.execute("UPDATE solver_runs SET phase=COALESCE(?,phase),incumbent_score=COALESCE(?,incumbent_score),workload_complete=COALESCE(?,workload_complete) WHERE id=?",
                    (phase, score, workload_complete, run_id))
    return get(session, SolverRun, run_id)


def store_results(session: Connection, run_id: str, access: list[AccessScheduleRow], occupancy: list[OccupancyScheduleRow], results: list[ScenarioResultRow]) -> None:
    insert_many(session, [RunAccess(run_id=run_id, activity_id=x.activity_id, access_seq=x.access_seq, week=x.week, eclo=x.eclo, access_night=x.access_night) for x in access])
    insert_many(session, [RunOccupancy(run_id=run_id, activity_id=x.activity_id, week=x.week, location_id=x.location_id, co_share_group=x.co_share_group) for x in occupancy])
    insert_many(session, [RunContractResult(run_id=run_id, scenario=x.scenario, contract_number=x.contract_number, simulated_completion_date=x.simulated_completion_date, overrun_days=x.overrun_days) for x in results])


def finish_run(session: Connection, run_id: str, *, status: str, error_message: str | None = None) -> SolverRun:
    if get(session, SolverRun, run_id) is None:
        raise KeyError(run_id)
    session.execute("UPDATE solver_runs SET status=?,finished_at=?,error_message=? WHERE id=?",
                    (status, datetime.now(timezone.utc).isoformat(), error_message, run_id))
    return get(session, SolverRun, run_id)
