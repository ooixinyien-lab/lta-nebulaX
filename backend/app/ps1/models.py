"""Typed configuration and result models for the official PS1 solver."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import Field

from backend.app.domain_models import (
    AccessScheduleRow,
    ActivityType,
    OccupancyScheduleRow,
    PS1Base,
    ScenarioResultRow,
)


class Scenario(str, Enum):
    """Official PS1 simulation scenarios."""

    A = "A"
    B = "B"
    C = "C"

    @classmethod
    def _missing_(cls, value: object) -> Scenario | None:
        if isinstance(value, str):
            normalized = value.strip().upper()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class PS1SolverStatus(str, Enum):
    """Externally stable solver status names."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"


class OfficialCheckerStatus(str, Enum):
    """Whether validation by the organiser's checker has occurred."""

    UNAVAILABLE = "unavailable"
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"


class SafetyValidationStatus(str, Enum):
    """Confidence in the unresolved protection compatibility semantics."""

    UNVERIFIED = "unverified"
    PASSED = "passed"
    FAILED = "failed"


class ValidationIssue(PS1Base):
    """A locally detected artifact or accounting violation."""

    rule: str
    detail: str
    activity_id: str | None = None
    week: int | None = None
    location_id: str | None = None


class ValidationSummary(PS1Base):
    """Independent local validation and its explicit provenance."""

    local_accounting_passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    provisional_policies: list[str] = Field(default_factory=list)
    local_validator_name: str = "backend.app.ps1.validation.validate_schedule"
    local_validator_version: str = "ps1-accounting-v1"
    formulation_reference: str = (
        "PS1_OFFICIAL_ADOPTION_PLAN.md; docs/PS1_SOLVER_FORMULATION_REVIEW.md"
    )
    safety_status: SafetyValidationStatus = SafetyValidationStatus.UNVERIFIED
    official_checker_status: OfficialCheckerStatus = OfficialCheckerStatus.UNAVAILABLE


class ScoreBreakdown(PS1Base):
    """Exact official score components, including integer-scaled values."""

    weighted_activity_lateness_scaled: int
    weighted_activity_lateness: float
    excess_slots: int
    eclo_accesses: int
    excess_penalty_scaled: int
    eclo_penalty_scaled: int
    objective_scaled: int
    objective_score: float


class ECLOAccessDetail(PS1Base):
    """One scheduled ECLO access at official weekly precision."""

    activity_id: str
    access_seq: int
    contract_number: str
    activity_type: ActivityType
    week: int
    week_start_date: date
    week_end_date: date
    access_night: int
    affected_line_codes: list[str]


class ECLOWeekSummary(PS1Base):
    """ECLO access count in one planning week."""

    week: int
    week_start_date: date
    week_end_date: date
    access_count: int


class ECLOLineSummary(PS1Base):
    """Actual ECLO use affecting one line."""

    line_code: str
    usage_weeks: list[int]
    affected_access_count: int


class ECLOWindow(PS1Base):
    """Scenario C's selected line-specific ECLO window."""

    line_code: str
    start_week: int
    end_week: int
    start_date: date
    end_date: date


class ECLOSummary(PS1Base):
    """ECLO counts and weekly timing derived from access rows."""

    eclo_accesses_total: int
    eclo_penalty: int
    accesses: list[ECLOAccessDetail]
    by_week: list[ECLOWeekSummary]
    by_line: list[ECLOLineSummary]
    selected_windows: list[ECLOWindow] | None = None


class SolveMetrics(PS1Base):
    """Timing and optimization information for a solver invocation."""

    wall_time_seconds: float
    feasibility_time_seconds: float
    improvement_time_seconds: float
    feasibility_status: PS1SolverStatus
    improvement_status: PS1SolverStatus | None = None
    objective_bound_scaled: float | None = None
    objective_bound_score: float | None = None
    relative_gap: float | None = None


class PS1SolveOptions(PS1Base):
    """Bounded CP-SAT search options."""

    time_limit_seconds: float = Field(default=60.0, gt=0)
    feasibility_time_limit_seconds: float = Field(default=10.0, gt=0)
    num_search_workers: int = Field(default=8, ge=1)
    random_seed: int = 0
    optimize: bool = True
    log_search_progress: bool = False


class PS1SolveResult(PS1Base):
    """Complete typed solver result used by the application and exporters."""

    scenario: Scenario
    status: PS1SolverStatus
    has_incumbent: bool
    access_rows: list[AccessScheduleRow] = Field(default_factory=list)
    occupancy_rows: list[OccupancyScheduleRow] = Field(default_factory=list)
    contract_results: list[ScenarioResultRow] = Field(default_factory=list)
    score: ScoreBreakdown | None = None
    eclo_summary: ECLOSummary | None = None
    validation: ValidationSummary
    solve_metrics: SolveMetrics


def coerce_scenario(value: Scenario | str) -> Scenario:
    """Convert a public scenario argument to a typed Scenario."""

    return value if isinstance(value, Scenario) else Scenario(value)
