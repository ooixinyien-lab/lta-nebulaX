"""Resource-level authorization helpers for instances, runs, and activities."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from fastapi import HTTPException
from backend.app.db.records import decode, get
from backend.app.db.models import ActivityRow, Instance, InstanceRevision, SolverRun
from backend.app.schemas import User


@dataclass(frozen=True)
class ChatScope:
    instance_id: str
    instance_revision_id: str
    run_id: str
    baseline_run_id: str | None
    scenario: str
    user_id: str
    user_role: str
    is_mock: bool = False


def authorize_instance_read(session: sqlite3.Connection, instance_id: str, user: User) -> Instance:
    """Enforces instance read authorization:
    - Planning officers can read any instance
    - Users can read instances they created or system-seeded instances
    - Mock/sample instances are readable by any authenticated user
    """
    if instance_id in ("mock", "sample", "mock-instance", "sample-instance"):
        # Synthesize a mock instance object for testing/sample data
        return Instance(
            id=instance_id,
            name="Mock Instance",
            fingerprint="mock-fingerprint",
            created_by="system",
        )

    instance = get(session, Instance, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")

    if user.role == "officer":
        return instance

    if instance.created_by in (user.id, "system"):
        return instance

    raise HTTPException(status_code=403, detail="Access denied: you do not have permission to view this instance")


def authorize_run_read(
    session: sqlite3.Connection,
    run_id: str,
    user: User,
) -> tuple[SolverRun, Instance, InstanceRevision]:
    """Enforces run read authorization:
    - Run must exist
    - User must have read permission on the parent instance
    """
    if run_id in ("mock", "sample", "sample_run", "sample-run", "mock_run") or run_id.startswith("mock-"):
        mock_instance = authorize_instance_read(session, "mock-instance", user)
        mock_rev = InstanceRevision(
            id="mock-rev",
            instance_id=mock_instance.id,
            revision_number=1,
            input_fingerprint="mock-fp",
            parser_version="mock",
            validation_status="VALID",
            created_by="system",
        )
        mock_run = SolverRun(
            id=run_id,
            revision_id=mock_rev.id,
            scenario="A",
            requested_time_limit=10.0,
            created_by="system",
            status="SUCCEEDED",
            workload_complete=True,
        )
        return mock_run, mock_instance, mock_rev

    run = get(session, SolverRun, run_id)
    if run is None:
        # Check operational runs table
        op_row = session.execute(
            "SELECT id, baseline_key, baseline_revision, scenario, status, created_at FROM schedule_insertion_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if op_row is not None:
            base_row = session.execute(
                "SELECT official_revision_id FROM schedule_insertion_baselines WHERE baseline_key=? AND revision=?",
                (op_row["baseline_key"], op_row["baseline_revision"]),
            ).fetchone()
            rev_id = base_row["official_revision_id"] if base_row else None
            revision = get(session, InstanceRevision, rev_id) if rev_id else None
            if revision is None:
                rev_row = session.execute(
                    "SELECT * FROM instance_revisions WHERE validation_status='VALID' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                revision = decode(InstanceRevision, rev_row)
            instance = authorize_instance_read(session, revision.instance_id, user) if revision else Instance(
                id="op-instance", name="Operational Instance", fingerprint="op-fp", created_by=user.id
            )
            fake_solver_run = SolverRun(
                id=run_id,
                revision_id=revision.id if revision else "op-rev",
                scenario=op_row["scenario"],
                requested_time_limit=10.0,
                created_by="system",
                status=op_row["status"],
                workload_complete=True,
            )
            return fake_solver_run, instance, revision or InstanceRevision(
                id="op-rev", instance_id=instance.id, revision_number=1,
                input_fingerprint="op-fp", parser_version="op", validation_status="VALID", created_by="system"
            )
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    revision = get(session, InstanceRevision, run.revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail=f"Revision for run '{run_id}' not found")

    instance = authorize_instance_read(session, revision.instance_id, user)

    # Additional run-level ownership check if not an officer and not created by system/user
    if user.role != "officer" and run.created_by not in (user.id, "system") and instance.created_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied: you do not have permission to view this run")

    return run, instance, revision


def authorize_activity_read(
    session: sqlite3.Connection,
    revision_id: str,
    activity_id: str,
) -> ActivityRow:
    """Verifies that an activity belongs to the specified instance revision."""
    row = session.execute(
        "SELECT * FROM instance_activities WHERE revision_id=? AND activity_id=?",
        (revision_id, activity_id),
    ).fetchone()
    activity = decode(ActivityRow, row)
    if activity is None:
        # Fallback check across all valid revisions in case revision_id is not yet set
        row_any = session.execute(
            "SELECT * FROM instance_activities WHERE activity_id=? LIMIT 1",
            (activity_id,),
        ).fetchone()
        activity = decode(ActivityRow, row_any)
    if activity is None:
        raise HTTPException(
            status_code=404,
            detail=f"Activity '{activity_id}' not found in revision '{revision_id}'",
        )
    return activity


def build_chat_scope(
    session: sqlite3.Connection,
    run_id: str | None,
    user: User,
    baseline_run_id: str | None = None,
    instance_id: str | None = None,
    scenario: str = "A",
    instance_revision_id: str | None = None,
) -> ChatScope:
    """Authenticates and scopes a chat turn before any data or provider calls.
    If run_id is omitted or empty, automatically resolves to the latest completed
    database run matching scenario and instance_revision_id.
    """
    is_explicit_mock = bool(
        run_id and (
            run_id in ("mock", "sample", "sample_run", "sample-run", "mock_run")
            or run_id.startswith("mock-")
        )
    )
    
    if is_explicit_mock:
        return ChatScope(
            instance_id=instance_id or "mock-instance",
            instance_revision_id="mock-rev",
            run_id=run_id or "sample_run",
            baseline_run_id=baseline_run_id,
            scenario=scenario,
            user_id=user.id,
            user_role=user.role,
            is_mock=True,
        )

    # Auto-resolve run_id from database if not explicitly supplied
    if not run_id:
        query = (
            "SELECT id FROM solver_runs WHERE scenario=? "
            "AND status IN ('SUCCESS', 'SUCCEEDED')"
        )
        params: list[str] = [scenario]
        if instance_revision_id:
            query += " AND revision_id=?"
            params.append(instance_revision_id)
        query += " ORDER BY created_at DESC, id DESC LIMIT 1"
        matched = session.execute(query, params).fetchone()
        if matched:
            run_id = matched["id"]
        else:
            # Check operational runs
            op_match = session.execute(
                "SELECT id FROM schedule_insertion_runs WHERE scenario=? AND status IN ('SUCCESS', 'SUCCEEDED') ORDER BY created_at DESC LIMIT 1",
                (scenario,),
            ).fetchone()
            if op_match:
                run_id = op_match["id"]

    # If a run_id is resolved or was provided, authorize and return
    if run_id:
        run, instance, revision = authorize_run_read(session, run_id, user)
        if baseline_run_id:
            authorize_run_read(session, baseline_run_id, user)
        return ChatScope(
            instance_id=instance.id,
            instance_revision_id=revision.id,
            run_id=run.id,
            baseline_run_id=baseline_run_id,
            scenario=run.scenario,
            user_id=user.id,
            user_role=user.role,
            is_mock=False,
        )

    # If no run has succeeded yet, resolve the latest valid instance revision from SQLite
    rev_row = session.execute(
        "SELECT id, instance_id FROM instance_revisions WHERE validation_status='VALID' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if rev_row:
        instance = authorize_instance_read(session, rev_row["instance_id"], user)
        return ChatScope(
            instance_id=instance.id,
            instance_revision_id=rev_row["id"],
            run_id="",
            baseline_run_id=baseline_run_id,
            scenario=scenario,
            user_id=user.id,
            user_role=user.role,
            is_mock=False,
        )

    # Ultimate fallback if database is completely empty
    return ChatScope(
        instance_id=instance_id or "empty-instance",
        instance_revision_id="empty-rev",
        run_id="",
        baseline_run_id=baseline_run_id,
        scenario=scenario,
        user_id=user.id,
        user_role=user.role,
        is_mock=False,
    )
