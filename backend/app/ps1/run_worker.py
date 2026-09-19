"""Execution boundary for persisted official PS1 solver runs."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.database import Database
from backend.app.db.repositories.instances import load_revision
from backend.app.db.repositories.runs import finish_run, store_results, update_progress
from backend.app.ps1.models import PS1SolveOptions
from backend.app.ps1.solver import solve_ps1


def execute_official_run(database: Database, run_id: str) -> None:
    """Solve one exact queued run and persist only a complete validated incumbent."""

    with database.connection(write=True) as connection:
        row = connection.execute(
            "SELECT revision_id,scenario,requested_time_limit,status FROM solver_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if row is None or row["status"] != "QUEUED":
            return
        connection.execute(
            "UPDATE solver_runs SET status='RUNNING',phase='FEASIBILITY',started_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
        problem = load_revision(connection, row["revision_id"])

    try:
        result = solve_ps1(
            problem,
            row["scenario"],
            PS1SolveOptions(time_limit_seconds=float(row["requested_time_limit"])),
        )
        with database.connection(write=True) as connection:
            if result.has_incumbent and result.validation.local_accounting_passed:
                store_results(
                    connection,
                    run_id,
                    result.access_rows,
                    result.occupancy_rows,
                    result.contract_results,
                )
                update_progress(
                    connection,
                    run_id,
                    phase="DONE",
                    score=result.score.objective_score if result.score else None,
                    workload_complete=True,
                )
                connection.execute(
                    "UPDATE solver_runs SET solver_version=?,validator_version=? WHERE id=?",
                    ("ps1-cp-sat-v1", result.validation.provenance, run_id),
                )
                finish_run(connection, run_id, status="SUCCEEDED")
            else:
                finish_run(connection, run_id, status=result.status.value)
    except Exception as exc:  # preserve the prior valid run on all failures
        with database.connection(write=True) as connection:
            finish_run(connection, run_id, status="FAILED", error_message=str(exc))
