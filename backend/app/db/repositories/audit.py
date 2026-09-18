from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.models import AuditEvent


def record_event(session: Session, *, actor: str, action: str, entity_type: str, entity_id: str, detail: dict[str, Any] | None = None) -> AuditEvent:
    event = AuditEvent(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail)
    session.add(event)
    session.flush()
    return event


def recent_events(session: Session, limit: int = 100) -> list[AuditEvent]:
    return list(session.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)))
