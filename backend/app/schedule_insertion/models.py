"""Typed operational models for schedule insertion.

The models in this module never extend the official CSV schemas.  They carry
the extra identity, calendar, maintenance and replan facts needed by the
operational workflow.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from backend.app.domain_models import AccessType, ActivityType, NatureOfWorks, PS1Base


class ScheduleScenario(str, Enum):
    A = "A"
    B = "B"
    C = "C"

    @classmethod
    def _missing_(cls, value: object) -> "ScheduleScenario | None":
        if isinstance(value, str):
            value = value.strip().upper()
            for member in cls:
                if member.value == value:
                    return member
        return None


class WorkSource(str, Enum):
    OFFICIAL = "official"
    ADDITION = "addition"
    EMERGENCY = "emergency"
    RECURRING = "recurring"


class MaintenanceVisitStatus(str, Enum):
    HISTORICAL = "historical"
    SCHEDULED = "scheduled"
    COMMITTED = "committed"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"


class OperationalCalendarDay(PS1Base):
    """One explicit, timezone-aware service date in the synthetic calendar."""

    service_date: date
    global_night_id: str
    timezone: str = "Asia/Singapore"
    eligible: bool = True
    physical_available: bool = True
    eclo_eligible: bool = True
    gross_capacity: int = Field(default=24, ge=0)
    nominal_weekly_limit: int = Field(default=3, ge=0)
    calendar_revision: str = "synthetic-calendar-v1"


class MaintenanceJob(PS1Base):
    """A single sector occurrence; its visits close both directions."""

    job_id: str
    occurrence_id: str
    job_type: Literal["maintenance"] = "maintenance"
    line_code: str
    sector_id: str
    required_visits: int = Field(default=3, ge=1)
    cycle_days: int = Field(default=245, ge=1)
    coverage_interval_days: int = Field(default=364, ge=1)
    occurrence_anchor: date
    source: Literal["generated", "imported"] = "generated"


class MaintenanceVisit(PS1Base):
    """Persistent maintenance placement.  IDs survive later replans."""

    visit_id: str
    job_id: str
    occurrence_id: str
    line_code: str
    sector_id: str
    service_date: date
    visit_seq: int = Field(ge=1)
    status: MaintenanceVisitStatus = MaintenanceVisitStatus.SCHEDULED
    locked: bool = False
    actual: bool = False

    @model_validator(mode="before")
    @classmethod
    def consistent_actual_state(cls, data: object) -> object:
        values = dict(data) if isinstance(data, dict) else data
        if not isinstance(values, dict):
            return data
        status = values.get("status")
        status_value = status.value if isinstance(status, MaintenanceVisitStatus) else status
        if status_value in (MaintenanceVisitStatus.HISTORICAL.value, MaintenanceVisitStatus.COMPLETED.value):
            values["actual"] = True
            values["locked"] = True
        if status_value == MaintenanceVisitStatus.IN_PROGRESS.value:
            values["locked"] = True
        return values


class ProjectJob(PS1Base):
    """Official or operational project work represented in the shared model."""

    job_id: str
    contract_number: str
    activity_type: ActivityType
    nature_of_activity: NatureOfWorks
    access_type: AccessType
    start_location_id: str
    end_location_id: str
    total_accesses: int = Field(ge=1)
    planned_start_date: date
    planned_completion_date: date
    contract_priority: int = Field(default=3, ge=1, le=3)
    activity_priority: int = Field(default=3, ge=1, le=3)
    number_of_workfronts: int = Field(default=1, ge=1)
    number_of_maximum_access_per_week: int = Field(default=3, ge=1)
    predecessor_job_id: str | None = None
    source: WorkSource = WorkSource.OFFICIAL
    hard_completion_date: date | None = None
    release_date: date | None = None

    @property
    def effective_release_date(self) -> date:
        return self.release_date or self.planned_start_date

    @property
    def effective_deadline(self) -> date:
        return self.hard_completion_date or self.planned_completion_date


class ProjectAccess(PS1Base):
    """Operational project access with a persistent internal access identity."""

    access_id: str
    job_id: str
    access_seq: int = Field(ge=1)
    week: int = Field(ge=1)
    service_date: date
    global_night_id: str | None = None
    eclo: bool = False
    access_night: int = Field(default=1, ge=1)
    group_by_location: dict[str, str] = Field(default_factory=dict)
    locked: bool = False


class EffectiveChange(PS1Base):
    """Versioned change applied at a replan's effective timestamp."""

    change_id: str
    effective_at: datetime
    kind: Literal["calendar_outage", "supply_outage", "deadline", "priority", "lock"]
    job_id: str | None = None
    location_ids: list[str] = Field(default_factory=list)
    service_dates: list[date] = Field(default_factory=list)
    new_deadline: date | None = None
    locked: bool | None = None
    detail: str | None = None

    @field_validator("effective_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must include a timezone")
        return value.astimezone(timezone.utc)


class BaselineBundle(PS1Base):
    """Immutable operational input revision and its saved placements."""

    baseline_id: str = "baseline-fixture-v1"
    revision: int = Field(default=1, ge=1)
    official_revision_id: str | None = None
    official_fingerprint: str | None = None
    horizon_start: date
    horizon_weeks: int = Field(default=52, ge=1)
    timezone: str = "Asia/Singapore"
    config_version: str = "schedule-insertion-v1"
    maintenance_jobs: list[MaintenanceJob] = Field(default_factory=list)
    maintenance_visits: list[MaintenanceVisit] = Field(default_factory=list)
    calendar: list[OperationalCalendarDay] = Field(default_factory=list)
    project_jobs: list[ProjectJob] = Field(default_factory=list)
    project_accesses: list[ProjectAccess] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectAddition(PS1Base):
    """A typed project/emergency insertion submitted for a replan."""

    job: ProjectJob
    requested_source: Literal["addition", "emergency"] = "addition"

    @model_validator(mode="after")
    def apply_source(self) -> "ProjectAddition":
        self.job.source = WorkSource(self.requested_source)
        if self.requested_source == "emergency" and self.job.hard_completion_date is None:
            raise ValueError("emergency additions must specify hard_completion_date")
        return self


class SolveOptions(PS1Base):
    time_limit_seconds: float = Field(default=60.0, gt=0, le=3600)
    num_search_workers: int = Field(default=8, ge=1, le=64)
    random_seed: int = 0
    scenario_cost_allowance: int = Field(default=10, ge=0)
    strict_scenario_cost: bool = False
    optimize: bool = True


class ReplanRequest(PS1Base):
    baseline_id: str
    baseline_revision: int = Field(ge=1)
    scenario: ScheduleScenario
    as_of: datetime
    additions: list[ProjectAddition] = Field(default_factory=list)
    changes: list[EffectiveChange] = Field(default_factory=list)
    options: SolveOptions = Field(default_factory=SolveOptions)

    @field_validator("as_of")
    @classmethod
    def as_of_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value.astimezone(timezone.utc)


class ScenarioCost(PS1Base):
    lateness_points: float = 0.0
    excess_slot_points: float = 0.0
    eclo_points: float = 0.0
    objective_points: float = 0.0
    objective_scaled: int = 0
    best_known: bool = False
    proof_status: Literal["proven", "best_known", "unknown"] = "unknown"


class DisruptionMetrics(PS1Base):
    changed_existing_jobs: int = 0
    changed_existing_visits: int = 0
    total_absolute_service_date_displacement: int = 0
    eclo_changes: int = 0
    sharing_changes: int = 0
    label_only_changes: int = 0


class ValidationFinding(PS1Base):
    rule: str
    detail: str
    severity: Literal["error", "warning"] = "error"
    job_id: str | None = None
    visit_id: str | None = None
    service_date: date | None = None
    location_id: str | None = None


class OperationalValidation(PS1Base):
    passed: bool
    status: Literal["passed", "failed", "validator_unavailable"]
    validator_version: str = "schedule-insertion-validator-v1"
    findings: list[ValidationFinding] = Field(default_factory=list)
    maintenance_coverage_checked: bool = True
    calendar_checked: bool = True
    official_checker_status: Literal["not_applicable", "unavailable"] = "unavailable"


class CandidateSchedule(PS1Base):
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"]
    projects: list[ProjectAccess] = Field(default_factory=list)
    maintenance_visits: list[MaintenanceVisit] = Field(default_factory=list)
    cost: ScenarioCost
    disruption: DisruptionMetrics = Field(default_factory=DisruptionMetrics)
    validation: OperationalValidation
    runtime_seconds: float = 0.0
    objective_bound: float | None = None
    relative_gap: float | None = None


class ScheduleInsertionResult(PS1Base):
    baseline_id: str
    baseline_revision: int
    scenario: ScheduleScenario
    status: Literal["SUCCEEDED", "INFEASIBLE", "UNKNOWN", "FAILED"]
    reference_candidate: CandidateSchedule | None = None
    lower_disruption_candidate: CandidateSchedule | None = None
    published_candidate: Literal["reference", "lower_disruption", "none"] = "none"
    solver_version: str = "schedule-insertion-cp-sat-v1"
    validator_version: str = "schedule-insertion-validator-v1"
    configuration: dict[str, Any] = Field(default_factory=dict)
    conflict_evidence: list[ValidationFinding] = Field(default_factory=list)


def coerce_scenario(value: ScheduleScenario | str) -> ScheduleScenario:
    return value if isinstance(value, ScheduleScenario) else ScheduleScenario(value)
