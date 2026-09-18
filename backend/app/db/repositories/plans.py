"""Mutable draft plans with optimistic versioning."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlite3 import Connection
from backend.app.db.records import get, insert, insert_many

from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow
from backend.app.db.models import Plan, PlanAccess, PlanChangeEvent, PlanOccupancy


def create_plan(session: Connection, *, revision_id: str, scenario: str, created_by: str, base_run_id: str | None = None) -> Plan:
    plan = Plan(id=f"plan-{uuid4().hex}", revision_id=revision_id, scenario=scenario, base_run_id=base_run_id, created_by=created_by)
    insert(session, plan)
    return plan


def replace_draft_rows(session: Connection, plan_id: str, *, expected_version: int, actor: str, access: list[AccessScheduleRow], occupancy: list[OccupancyScheduleRow], reason: str | None = None) -> Plan:
    plan = get(session, Plan, plan_id)
    if plan is None:
        raise KeyError(plan_id)
    if plan.status != "DRAFT":
        raise ValueError("Only draft plans can be edited")
    if plan.version != expected_version:
        raise RuntimeError("stale plan version")
    session.execute("DELETE FROM plan_accesses WHERE plan_id=?", (plan_id,))
    session.execute("DELETE FROM plan_occupancies WHERE plan_id=?", (plan_id,))
    insert_many(session, [PlanAccess(plan_id=plan_id, activity_id=x.activity_id, access_seq=x.access_seq, week=x.week, eclo=x.eclo, access_night=x.access_night) for x in access])
    insert_many(session, [PlanOccupancy(plan_id=plan_id, activity_id=x.activity_id, week=x.week, location_id=x.location_id, co_share_group=x.co_share_group) for x in occupancy])
    session.execute("UPDATE plans SET version=version+1 WHERE id=?", (plan_id,))
    plan.version += 1
    insert(session, PlanChangeEvent(plan_id=plan_id, version=plan.version, actor=actor, action="replace_rows", detail={"reason": reason} if reason else None))
    return plan


def publish_plan(session: Connection, plan_id: str, *, expected_version: int, actor: str) -> Plan:
    plan = get(session, Plan, plan_id)
    if plan is None:
        raise KeyError(plan_id)
    if plan.version != expected_version:
        raise RuntimeError("stale plan version")
    if plan.status != "DRAFT":
        raise ValueError("Plan is already published or archived")
    session.execute("UPDATE plans SET status='PUBLISHED',published_by=?,published_at=?,version=version+1 WHERE id=?", (actor, datetime.now(timezone.utc).isoformat(), plan_id))
    plan.status = "PUBLISHED"
    plan.published_by = actor
    plan.published_at = datetime.now(timezone.utc)
    plan.version += 1
    insert(session, PlanChangeEvent(plan_id=plan_id, version=plan.version, actor=actor, action="publish"))
    return plan
