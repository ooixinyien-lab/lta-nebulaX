"""Repository for immutable explanation fact packs."""
from __future__ import annotations

import sqlite3
from backend.app.db.records import decode, get, insert
from backend.app.db.models import ExplanationFactPackRow


def save_fact_pack(session: sqlite3.Connection, row: ExplanationFactPackRow) -> ExplanationFactPackRow:
    """Save an immutable explanation fact pack."""
    existing = get(session, ExplanationFactPackRow, row.id)
    if existing is not None:
        return existing
    insert(session, row)
    return row


def get_fact_pack(session: sqlite3.Connection, fact_pack_id: str) -> ExplanationFactPackRow | None:
    return get(session, ExplanationFactPackRow, fact_pack_id)


def find_fact_pack(
    session: sqlite3.Connection,
    run_id: str,
    activity_id: str,
    baseline_run_id: str | None = None,
) -> ExplanationFactPackRow | None:
    query = (
        "SELECT * FROM explanation_fact_packs WHERE run_id=? AND activity_id=? "
        "AND (baseline_run_id=? OR (baseline_run_id IS NULL AND ? IS NULL)) "
        "ORDER BY created_at DESC LIMIT 1"
    )
    row = session.execute(query, (run_id, activity_id, baseline_run_id, baseline_run_id)).fetchone()
    return decode(ExplanationFactPackRow, row)
