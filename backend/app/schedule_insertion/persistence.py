"""Dedicated immutable records for the operational workflow."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlite3 import Connection

from backend.app.schedule_insertion.models import BaselineBundle, ScheduleInsertionResult


def _payload(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def save_baseline(connection: Connection, baseline: BaselineBundle, *, actor: str, official_revision_id: str | None = None) -> BaselineBundle:
    """Insert a new immutable revision; never overwrite an existing revision."""

    baseline_key = baseline.baseline_id
    row = connection.execute(
        "SELECT COALESCE(MAX(revision), 0) FROM schedule_insertion_baselines WHERE baseline_key=?",
        (baseline_key,),
    ).fetchone()
    revision = int(row[0]) + 1
    stored = baseline.model_copy(update={"revision": revision, "official_revision_id": official_revision_id or baseline.official_revision_id})
    payload = _payload(stored.model_dump(mode="json"))
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    record_id = f"sib-{uuid4().hex}"
    now = datetime.now(timezone.utc).isoformat()
    connection.execute(
        "INSERT INTO schedule_insertion_baselines (id, baseline_key, revision, official_revision_id, fingerprint, config_version, payload, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (record_id, baseline_key, revision, stored.official_revision_id, fingerprint, stored.config_version, payload, actor, now),
    )
    return stored


def load_baseline(connection: Connection, baseline_key: str, revision: int | None = None) -> BaselineBundle | None:
    if revision is None:
        row = connection.execute(
            "SELECT payload FROM schedule_insertion_baselines WHERE baseline_key=? ORDER BY revision DESC LIMIT 1",
            (baseline_key,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT payload FROM schedule_insertion_baselines WHERE baseline_key=? AND revision=?",
            (baseline_key, revision),
        ).fetchone()
    return BaselineBundle.model_validate(json.loads(row[0])) if row else None


def list_baseline_revisions(connection: Connection, baseline_key: str) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in connection.execute(
            "SELECT baseline_key, revision, official_revision_id, fingerprint, config_version, created_by, created_at FROM schedule_insertion_baselines WHERE baseline_key=? ORDER BY revision DESC",
            (baseline_key,),
        )
    ]


def save_run(connection: Connection, result: ScheduleInsertionResult, *, actor: str, official_revision_id: str | None = None) -> str:
    run_id = f"sir-{uuid4().hex}"
    payload = _payload(result.model_dump(mode="json"))
    candidate = result.lower_disruption_candidate or result.reference_candidate
    cost = candidate.cost.objective_points if candidate else None
    now = datetime.now(timezone.utc).isoformat()
    connection.execute(
        "INSERT INTO schedule_insertion_runs (id, baseline_key, baseline_revision, official_revision_id, scenario, status, solver_version, validator_version, scenario_cost, payload, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, result.baseline_id, result.baseline_revision, official_revision_id, result.scenario.value, result.status, result.solver_version, result.validator_version, cost, payload, actor, now),
    )
    return run_id


def load_run(connection: Connection, run_id: str) -> ScheduleInsertionResult | None:
    row = connection.execute("SELECT payload FROM schedule_insertion_runs WHERE id=?", (run_id,)).fetchone()
    return ScheduleInsertionResult.model_validate(json.loads(row[0])) if row else None
