"""Repository for chat sessions, conversation turns, and retention pruning."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
from backend.app.db.records import decode, get, insert
from backend.app.db.models import ChatSessionRow, ChatTurnRow


def create_chat_session(
    session: sqlite3.Connection,
    *,
    session_id: str,
    instance_id: str,
    run_id: str,
    baseline_run_id: str | None = None,
    created_by: str,
) -> ChatSessionRow:
    now = datetime.now(timezone.utc)
    row = ChatSessionRow(
        id=session_id,
        instance_id=instance_id,
        run_id=run_id,
        baseline_run_id=baseline_run_id,
        created_by=created_by,
        created_at=now,
        last_activity_at=now,
    )
    insert(session, row)
    return row


def get_chat_session(session: sqlite3.Connection, session_id: str) -> ChatSessionRow | None:
    return get(session, ChatSessionRow, session_id)


def touch_chat_session(session: sqlite3.Connection, session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    session.execute("UPDATE chat_sessions SET last_activity_at=? WHERE id=?", (now, session_id))


def record_chat_turn(session: sqlite3.Connection, turn: ChatTurnRow) -> ChatTurnRow:
    insert(session, turn)
    touch_chat_session(session, turn.session_id)
    return turn


def list_session_turns(
    session: sqlite3.Connection,
    session_id: str,
    limit: int = 20,
) -> list[ChatTurnRow]:
    cursor = session.execute(
        "SELECT * FROM chat_turns WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
        (session_id, limit),
    )
    return [decode(ChatTurnRow, r) for r in cursor.fetchall() if r]


def prune_chat_logs(session: sqlite3.Connection, retention_days: int) -> int:
    """Prunes chat turns and sessions older than retention_days."""
    if retention_days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    # Delete turns from expired sessions or older than cutoff
    turns_cur = session.execute("DELETE FROM chat_turns WHERE created_at < ?", (cutoff,))
    deleted_turns = turns_cur.rowcount
    session.execute("DELETE FROM chat_sessions WHERE last_activity_at < ?", (cutoff,))
    return deleted_turns
