from typing import Any
from sqlite3 import Connection
from backend.app.db.models import AuditEvent
from backend.app.db.records import decode, insert


def record_event(connection: Connection, *, actor: str, action: str, entity_type: str, entity_id: str, detail: dict[str, Any] | None = None) -> AuditEvent:
    return insert(connection, AuditEvent(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail))


def recent_events(connection: Connection, limit: int = 100) -> list[AuditEvent]:
    return [decode(AuditEvent, row) for row in connection.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT ?', (limit,))]
