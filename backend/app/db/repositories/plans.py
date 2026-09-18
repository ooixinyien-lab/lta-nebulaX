"""Mutable draft plans with optimistic versioning."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow
from backend.app.db.models import Plan, PlanAccess, PlanChangeEvent, PlanOccupancy


def create_plan(session: Session, *, revision_id: str, scenario: str, created_by: str, base_run_id: str | None = None) -> Plan:
    plan = Plan(id=f"plan-{uuid4().hex}", revision_id=revision_id, scenario=scenario, base_run_id=base_run_id, created_by=created_by)
    session.add(plan)
    session.flush()
    return plan


def replace_draft_rows(session: Session, plan_id: str, *, expected_version: int, actor: str, access: list[AccessScheduleRow], occupancy: list[OccupancyScheduleRow], reason: str | None = None) -> Plan:
    plan = session.scalar(select(Plan).where(Plan.id == plan_id).with_for_update())
    if plan is None:
        raise KeyError(plan_id)
    if plan.status != "DRAFT":
        raise ValueError("Only draft plans can be edited")
    if plan.version != expected_version:
        raise RuntimeError("stale plan version")
    session.query(PlanAccess).filter_by(plan_id=plan_id).delete()
    session.query(PlanOccupancy).filter_by(plan_id=plan_id).delete()
    session.add_all([PlanAccess(plan_id=plan_id, activity_id=x.activity_id, access_seq=x.access_seq, week=x.week, eclo=x.eclo, access_night=x.access_night) for x in access])
    session.add_all([PlanOccupancy(plan_id=plan_id, activity_id=x.activity_id, week=x.week, location_id=x.location_id, co_share_group=x.co_share_group) for x in occupancy])
    plan.version += 1
    session.add(PlanChangeEvent(plan_id=plan_id, version=plan.version, actor=actor, action="replace_rows", detail={"reason": reason} if reason else None))
    return plan


def publish_plan(session: Session, plan_id: str, *, expected_version: int, actor: str) -> Plan:
    plan = session.scalar(select(Plan).where(Plan.id == plan_id).with_for_update())
    if plan is None:
        raise KeyError(plan_id)
    if plan.version != expected_version:
        raise RuntimeError("stale plan version")
    if plan.status != "DRAFT":
        raise ValueError("Plan is already published or archived")
    plan.status = "PUBLISHED"
    plan.published_by = actor
    plan.published_at = datetime.now(timezone.utc)
    plan.version += 1
    session.add(PlanChangeEvent(plan_id=plan_id, version=plan.version, actor=actor, action="publish"))
    return plan
