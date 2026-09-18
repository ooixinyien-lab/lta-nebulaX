"""Typed operational calendar inputs and date-assignment outputs.

These models deliberately live outside the official PS1 CSV schemas.  A dated
assignment always points back to one immutable SCHEDULE_ACCESS row.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    PS1Base,
    ScenarioResultRow,
)


SINGAPORE_TIMEZONE = "Asia/Singapore"
CALENDAR_POLICY_VERSION = "calendar-v1"
DEMO_PROTECTION_POLICY = "conservative_demo_v1"


class CalendarJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CalendarSolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    PRECHECK_FAILED = "PRECHECK_FAILED"


class LocationNightRule(PS1Base):
    service_date: date
    location_id: str
    maintenance_available: bool = True
    possession_capacity: int = Field(default=1, ge=0)


class LineNightRule(PS1Base):
    service_date: date
    line_code: str
    maintenance_available: bool = True
    eclo_eligible: bool = True


class ContractCalendarRule(PS1Base):
    contract_number: str
    eligible_dates: list[date] | None = None
    local_slot_eligible_dates: dict[int, list[date]] = Field(default_factory=dict)
    actual_night_limit_per_week: int | None = Field(default=None, ge=1)
    nightly_workfront_limit: int | None = Field(default=None, ge=1)

    @field_validator("local_slot_eligible_dates")
    @classmethod
    def _positive_slot_numbers(
        cls, value: dict[int, list[date]]
    ) -> dict[int, list[date]]:
        if any(slot < 1 for slot in value):
            raise ValueError("Local slot numbers must be positive")
        return value


class OperatingCalendarInput(PS1Base):
    instance_revision_id: str
    timezone: Literal["Asia/Singapore"] = SINGAPORE_TIMEZONE
    assumed_calendar: bool = False
    assumptions: list[str] = Field(default_factory=list)
    source: str = "user"
    policy_version: str = CALENDAR_POLICY_VERSION
    protection_policy: Literal["conservative_demo_v1"] = DEMO_PROTECTION_POLICY
    default_maintenance_available: bool = True
    default_location_possession_capacity: int = Field(default=1, ge=0)
    default_eclo_eligible: bool = True
    location_nights: list[LocationNightRule] = Field(default_factory=list)
    line_nights: list[LineNightRule] = Field(default_factory=list)
    contract_rules: list[ContractCalendarRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_rules(self) -> OperatingCalendarInput:
        location_keys = [
            (rule.location_id, rule.service_date) for rule in self.location_nights
        ]
        if len(location_keys) != len(set(location_keys)):
            raise ValueError("Duplicate location/date calendar rule")
        line_keys = [(rule.line_code, rule.service_date) for rule in self.line_nights]
        if len(line_keys) != len(set(line_keys)):
            raise ValueError("Duplicate line/date calendar rule")
        contracts = [rule.contract_number for rule in self.contract_rules]
        if len(contracts) != len(set(contracts)):
            raise ValueError("Duplicate contract calendar rule")
        if self.assumed_calendar and not self.assumptions:
            raise ValueError("An assumed calendar must describe its assumptions")
        return self


class DateCommitment(PS1Base):
    activity_id: str
    access_seq: int = Field(ge=1)
    service_date: date
    reason: Literal["pinned", "completed", "occurred", "in_progress", "locked"] = (
        "pinned"
    )


class CalendariseOptions(PS1Base):
    time_limit_seconds: float = Field(default=30.0, gt=0, le=3600)
    num_search_workers: int = Field(default=8, ge=1, le=64)
    random_seed: int = 0


class CalendarConflict(PS1Base):
    rule_code: str
    severity: Literal["hard", "warning"] = "hard"
    message: str
    activity_ids: list[str] = Field(default_factory=list)
    access_ids: list[str] = Field(default_factory=list)
    service_dates: list[date] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    required_capacity: int | None = None
    available_capacity: int | None = None


class CalendarAssignment(PS1Base):
    access_id: str
    activity_id: str
    access_seq: int
    week: int
    access_night: int
    eclo: bool
    service_date: date
    global_night_id: str
    contract_number: str
    contract_description: str
    line_codes: list[str]
    location_ids: list[str]


class CalendarValidationSummary(PS1Base):
    passed: bool
    weekly_validation_passed: bool
    calendar_validation_passed: bool
    source_results_match: bool
    issues: list[CalendarConflict] = Field(default_factory=list)
    validator_version: str = "calendar-validator-v1"
    protection_policy: str = DEMO_PROTECTION_POLICY
    safety_validation_status: Literal["UNVERIFIED"] = "UNVERIFIED"
    official_checker_status: Literal["UNAVAILABLE"] = "UNAVAILABLE"


class FixedScheduleBundle(PS1Base):
    bundle_id: str
    instance_revision_id: str
    scenario: str
    fingerprint: str
    access_rows: list[AccessScheduleRow]
    occupancy_rows: list[OccupancyScheduleRow]
    result_rows: list[ScenarioResultRow]


class CalendarisationResult(PS1Base):
    solver_status: CalendarSolverStatus
    complete: bool
    assignments: list[CalendarAssignment] = Field(default_factory=list)
    conflicts: list[CalendarConflict] = Field(default_factory=list)
    validation: CalendarValidationSummary | None = None
    wall_time_seconds: float
    preference_value: int | None = None
    assumed_calendar: bool
    assumptions: list[str] = Field(default_factory=list)


class CalendarPreviewSource(PS1Base):
    bundle_id: str
    instance_revision_id: str
    scenario: str
    access_count: int
    created_at: datetime


class CalendarPreviewInstance(PS1Base):
    revision_id: str
    name: str
    horizon_start: date
    horizon_end: date
    horizon_weeks: int


class CalendarPreviewCalendar(PS1Base):
    calendar_revision_id: str
    instance_revision_id: str
    assumed_calendar: bool
    assumptions: list[str]


class CalendarPreviewContext(PS1Base):
    bundle: CalendarPreviewSource | None = None
    instance: CalendarPreviewInstance | None = None
    calendar: CalendarPreviewCalendar | None = None
    latest_attempt_id: str | None = None
    last_complete_attempt_id: str | None = None


def demo_calendar(instance_revision_id: str) -> OperatingCalendarInput:
    """Create the explicit, opt-in demo policy; no official CSV supplies it."""

    return OperatingCalendarInput(
        instance_revision_id=instance_revision_id,
        assumed_calendar=True,
        source="generated_demo",
        assumptions=[
            "All seven service dates in each planning week are eligible.",
            "Each location has one possession group available per service date.",
            "There are no maintenance blackouts or extra contract date restrictions.",
            "ECLO is calendar-eligible on every date; the source scenario remains fixed.",
            "Each contract uses at most its supplied weekly night count as distinct actual dates.",
            "Each contract uses at most its supplied workfront count on an actual date.",
            "Protection compatibility uses conservative_demo_v1 and is not official checker certification.",
        ],
    )
