"""Typed SQLite records; official domain entities remain in domain_models."""
from datetime import date, datetime, timezone
from pydantic import Field
from typing import Any, ClassVar
from backend.app.domain_models import PS1Base

class ActivityRow(PS1Base):
    table: ClassVar[str] = "instance_activities"
    activity_id: str
    contract_number: str
    activity_type: str
    start_location_id: str
    end_location_id: str
    total_accesses: int
    planned_start_date: date
    predecessor_activity_id: str | None = None
    activity_priority: int
    revision_id: str

class AuditEvent(PS1Base):
    table: ClassVar[str] = "audit_events"
    id: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str
    action: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any] | None = None

class BufferRuleRow(PS1Base):
    table: ClassVar[str] = "instance_buffer_rules"
    nature_of_works: str
    up_to_buffer_sectors: int
    opposite_bound_required: bool
    revision_id: str

class ContractRow(PS1Base):
    table: ClassVar[str] = "instance_contracts"
    contract_number: str
    contract_description: str
    contract_award_date: date
    activity_type: str
    nature_of_activity: str
    contract_priority: int
    contract_completion_date: date
    planned_completion_date: date
    number_of_workfronts: int
    access_type: str
    number_of_maximum_access_per_week: int
    revision_id: str

class Instance(PS1Base):
    table: ClassVar[str] = "instances"
    id: str
    name: str
    fingerprint: str
    created_by: str
    status: str = 'ACTIVE'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class InstanceFile(PS1Base):
    table: ClassVar[str] = "instance_files"
    revision_id: str
    file_type: str
    original_filename: str
    storage_key: str
    sha256: str
    size_bytes: int

class InstanceRevision(PS1Base):
    table: ClassVar[str] = "instance_revisions"
    id: str
    instance_id: str
    revision_number: int
    input_fingerprint: str
    parser_version: str
    validation_status: str
    validation_errors: list[Any] | None = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LineRow(PS1Base):
    table: ClassVar[str] = "instance_lines"
    line_code: str
    line_name: str
    revision_id: str

class LocationRow(PS1Base):
    table: ClassVar[str] = "instance_locations"
    location_id: str
    location_kind: str
    line_code: str
    bound: str
    supply_capacity: int
    revision_id: str

class ParameterRow(PS1Base):
    table: ClassVar[str] = "instance_parameters"
    key: str
    value: str
    revision_id: str

class Plan(PS1Base):
    table: ClassVar[str] = "plans"
    id: str
    revision_id: str
    scenario: str
    base_run_id: str | None = None
    status: str = 'DRAFT'
    version: int = 1
    created_by: str
    published_by: str | None = None
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanAccess(PS1Base):
    table: ClassVar[str] = "plan_accesses"
    plan_id: str
    activity_id: str
    access_seq: int
    week: int
    eclo: bool
    access_night: int

class PlanChangeEvent(PS1Base):
    table: ClassVar[str] = "plan_change_events"
    id: int = 0
    plan_id: str
    version: int
    actor: str
    action: str
    detail: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanOccupancy(PS1Base):
    table: ClassVar[str] = "plan_occupancies"
    plan_id: str
    activity_id: str
    week: int
    location_id: str
    co_share_group: str

class RunAccess(PS1Base):
    table: ClassVar[str] = "run_accesses"
    run_id: str
    activity_id: str
    access_seq: int
    week: int
    eclo: bool
    access_night: int

class RunArtifact(PS1Base):
    table: ClassVar[str] = "run_artifacts"
    run_id: str
    artifact_type: str
    storage_key: str
    sha256: str
    content_type: str

class RunContractResult(PS1Base):
    table: ClassVar[str] = "run_contract_results"
    run_id: str
    scenario: str
    contract_number: str
    simulated_completion_date: date
    overrun_days: int

class RunOccupancy(PS1Base):
    table: ClassVar[str] = "run_occupancies"
    run_id: str
    activity_id: str
    week: int
    location_id: str
    co_share_group: str

class RunValidationReport(PS1Base):
    table: ClassVar[str] = "run_validation_reports"
    run_id: str
    provenance: str
    local_checks_passed: bool
    rule_results: dict[str, Any]
    score_components: dict[str, Any] | None = None

class SectorRow(PS1Base):
    table: ClassVar[str] = "instance_sectors"
    sector_id: str
    line_code: str
    from_station_id: str
    to_station_id: str
    seq: int
    is_shared: bool
    revision_id: str

class SolverRun(PS1Base):
    table: ClassVar[str] = "solver_runs"
    id: str
    revision_id: str
    scenario: str
    baseline_run_id: str | None = None
    status: str = 'QUEUED'
    phase: str | None = None
    requested_time_limit: float
    solver_version: str | None = None
    validator_version: str | None = None
    workload_complete: bool = False
    incumbent_score: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StationRow(PS1Base):
    table: ClassVar[str] = "instance_stations"
    line_code: str
    station_id: str
    seq: int
    is_interchange: bool
    revision_id: str


class ScheduleBundleRecord(PS1Base):
    table: ClassVar[str] = "schedule_bundles"
    id: str
    revision_id: str
    scenario: str
    fingerprint: str
    validation: dict[str, Any]
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CalendarRevisionRecord(PS1Base):
    table: ClassVar[str] = "calendar_revisions"
    id: str
    revision_id: str
    fingerprint: str
    timezone: str
    assumed_calendar: bool
    assumptions: list[str]
    definition: dict[str, Any]
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CalendarAttemptRecord(PS1Base):
    table: ClassVar[str] = "calendarisation_attempts"
    id: str
    bundle_id: str
    calendar_revision_id: str
    status: str = "QUEUED"
    solver_status: str | None = None
    solver_version: str = "calendar-cpsat-v1"
    validator_version: str = "calendar-validator-v1"
    complete: bool = False
    preference_value: int | None = None
    requested_time_limit: float
    commitments: list[dict[str, Any]] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    error_message: str | None = None
    worker_token: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CalendarAssignmentRecord(PS1Base):
    table: ClassVar[str] = "calendar_assignments"
    attempt_id: str
    activity_id: str
    access_seq: int
    access_id: str
    week: int
    access_night: int
    eclo: bool
    service_date: date
    global_night_id: str
    contract_number: str
    contract_description: str
    line_codes: list[str]
    location_ids: list[str]
