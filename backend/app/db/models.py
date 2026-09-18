"""Relational SQLAlchemy models for immutable PS1 inputs and solver outputs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Instance(Base, TimestampMixin):
    __tablename__ = "instances"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    revisions: Mapped[list["InstanceRevision"]] = relationship(back_populates="instance")


class InstanceRevision(Base, TimestampMixin):
    __tablename__ = "instance_revisions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("instances.id"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_errors: Mapped[list[Any] | None] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    instance: Mapped[Instance] = relationship(back_populates="revisions")
    __table_args__ = (UniqueConstraint("instance_id", "revision_number"),)


class InstanceFile(Base):
    __tablename__ = "instance_files"
    revision_id: Mapped[str] = mapped_column(ForeignKey("instance_revisions.id"), primary_key=True)
    file_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class RevisionRow(Base):
    __abstract__ = True
    revision_id: Mapped[str] = mapped_column(ForeignKey("instance_revisions.id"), primary_key=True)


class LineRow(RevisionRow):
    __tablename__ = "instance_lines"
    line_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    line_name: Mapped[str] = mapped_column(String(255), nullable=False)


class StationRow(RevisionRow):
    __tablename__ = "instance_stations"
    line_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    station_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    is_interchange: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SectorRow(RevisionRow):
    __tablename__ = "instance_sectors"
    sector_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    line_code: Mapped[str] = mapped_column(String(32), nullable=False)
    from_station_id: Mapped[str] = mapped_column(String(64), nullable=False)
    to_station_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LocationRow(RevisionRow):
    __tablename__ = "instance_locations"
    location_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    location_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    line_code: Mapped[str] = mapped_column(String(32), nullable=False)
    bound: Mapped[str] = mapped_column(String(16), nullable=False)
    supply_capacity: Mapped[int] = mapped_column(Integer, nullable=False)


class BufferRuleRow(RevisionRow):
    __tablename__ = "instance_buffer_rules"
    nature_of_works: Mapped[str] = mapped_column(String(64), primary_key=True)
    up_to_buffer_sectors: Mapped[int] = mapped_column(Integer, nullable=False)
    opposite_bound_required: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ParameterRow(RevisionRow):
    __tablename__ = "instance_parameters"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class ContractRow(RevisionRow):
    __tablename__ = "instance_contracts"
    contract_number: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_description: Mapped[str] = mapped_column(Text, nullable=False)
    contract_award_date: Mapped[date] = mapped_column(Date, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    nature_of_activity: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    number_of_workfronts: Mapped[int] = mapped_column(Integer, nullable=False)
    access_type: Mapped[str] = mapped_column(String(16), nullable=False)
    number_of_maximum_access_per_week: Mapped[int] = mapped_column(Integer, nullable=False)


class ActivityRow(RevisionRow):
    __tablename__ = "instance_activities"
    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_number: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    start_location_id: Mapped[str] = mapped_column(String(128), nullable=False)
    end_location_id: Mapped[str] = mapped_column(String(128), nullable=False)
    total_accesses: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    predecessor_activity_id: Mapped[str | None] = mapped_column(String(64))
    activity_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (Index("ix_activity_revision_contract", "revision_id", "contract_number"),)


class SolverRun(Base, TimestampMixin):
    __tablename__ = "solver_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("instance_revisions.id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(1), nullable=False)
    baseline_run_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    phase: Mapped[str | None] = mapped_column(String(32))
    requested_time_limit: Mapped[float] = mapped_column(nullable=False)
    solver_version: Mapped[str | None] = mapped_column(String(128))
    validator_version: Mapped[str | None] = mapped_column(String(128))
    workload_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    incumbent_score: Mapped[float | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (Index("ix_solver_runs_revision", "revision_id", "scenario"),)


class RunAccess(Base):
    __tablename__ = "run_accesses"
    run_id: Mapped[str] = mapped_column(ForeignKey("solver_runs.id"), primary_key=True)
    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    access_seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    eclo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    access_night: Mapped[int] = mapped_column(Integer, nullable=False)


class RunOccupancy(Base):
    __tablename__ = "run_occupancies"
    run_id: Mapped[str] = mapped_column(ForeignKey("solver_runs.id"), primary_key=True)
    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    week: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    co_share_group: Mapped[str] = mapped_column(String(128), nullable=False)
    __table_args__ = (Index("ix_run_occupancy_location", "run_id", "week", "location_id"),)


class RunContractResult(Base):
    __tablename__ = "run_contract_results"
    run_id: Mapped[str] = mapped_column(ForeignKey("solver_runs.id"), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(1), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(64), primary_key=True)
    simulated_completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    overrun_days: Mapped[int] = mapped_column(Integer, nullable=False)


class RunValidationReport(Base):
    __tablename__ = "run_validation_reports"
    run_id: Mapped[str] = mapped_column(ForeignKey("solver_runs.id"), primary_key=True)
    provenance: Mapped[str] = mapped_column(String(128), nullable=False)
    local_checks_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rule_results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    score_components: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RunArtifact(Base):
    __tablename__ = "run_artifacts"
    run_id: Mapped[str] = mapped_column(ForeignKey("solver_runs.id"), primary_key=True)
    artifact_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("instance_revisions.id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(1), nullable=False)
    base_run_id: Mapped[str | None] = mapped_column(ForeignKey("solver_runs.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_plans_revision", "revision_id", "scenario", "status"),)


class PlanAccess(Base):
    __tablename__ = "plan_accesses"
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), primary_key=True)
    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    access_seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    eclo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    access_night: Mapped[int] = mapped_column(Integer, nullable=False)


class PlanOccupancy(Base):
    __tablename__ = "plan_occupancies"
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), primary_key=True)
    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    week: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    co_share_group: Mapped[str] = mapped_column(String(128), nullable=False)


class PlanChangeEvent(Base):
    __tablename__ = "plan_change_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
