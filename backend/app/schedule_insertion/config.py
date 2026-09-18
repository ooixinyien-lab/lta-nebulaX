"""Operational solver defaults; official PS1 options remain independent."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from backend.app.domain_models import PS1Base


class ScheduleInsertionConfig(PS1Base):
    horizon_weeks: int = Field(default=52, ge=1)
    maintenance_daily_capacity: int = Field(default=3, ge=1)
    coverage_interval_days: int = Field(default=364, ge=1)
    maintenance_cycle_days: int = Field(default=245, ge=1)
    scenario_cost_allowance: int = Field(default=10, ge=0)
    timezone: str = "Asia/Singapore"
    solver_version: str = "schedule-insertion-cp-sat-v1"
    validator_version: str = "schedule-insertion-validator-v1"
    fixture_version: str = "schedule-insertion-fixture-v1"
    # This is an operational default only.  It does not alter official supply.
    default_project_gross_capacity: int = Field(default=24, ge=1)
    default_nominal_weekly_limit: int = Field(default=3, ge=1)

    def horizon_end(self, horizon_start: date) -> date:
        return horizon_start.fromordinal(
            horizon_start.toordinal() + self.horizon_weeks * 7 - 1
        )
