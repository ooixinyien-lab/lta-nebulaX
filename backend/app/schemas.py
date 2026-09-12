"""Shared contract. Agree changes here before changing the frontend or solver."""
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SGT = ZoneInfo("Asia/Singapore")

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class User(StrictModel):
    id: str
    name: str
    role: Literal["requester", "officer"]

class Phase(StrictModel):
    name: Literal["setup", "work", "test", "handback"]
    duration_minutes: int = Field(ge=0, le=1440)

class RequestCreate(StrictModel):
    title: str = Field(min_length=3, max_length=100)
    work_type: str | None = None
    work_sector: str
    protected_sectors: list[str] = Field(min_length=1, max_length=6)
    power_requirement: Literal["ON", "OFF", "NONE", "ANY"]
    required_skill: str
    preferred_engineer: str | None = None
    required_equipment_ids: list[str] = Field(default_factory=list, max_length=3)
    technicians_required: int = Field(ge=0, le=20)
    phases: list[Phase] = Field(min_length=4, max_length=4)
    preferred_start: datetime
    earliest_start: datetime
    deadline: datetime
    allowed_dates: list[str] = Field(min_length=1, max_length=7)
    depends_on: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("Title must contain at least three non-blank characters")
        return v.strip()

    @field_validator("preferred_start", "earliest_start", "deadline")
    @classmethod
    def aware_datetime(cls, v):
        if v.utcoffset() is None:
            raise ValueError("Include a timezone, for example +08:00")
        if v.second or v.microsecond:
            raise ValueError("Use whole minutes")
        return v.astimezone(SGT)

    @model_validator(mode="after")
    def validate_package(self):
        if [p.name for p in self.phases] != ["setup", "work", "test", "handback"]:
            raise ValueError("Use setup, work, test, handback in that order")
        if self.phases[1].duration_minutes <= 0 or sum(p.duration_minutes for p in self.phases) > 1440:
            raise ValueError("Work must take positive time; package cannot exceed 24 hours")
        if not self.earliest_start <= self.preferred_start < self.deadline:
            raise ValueError("Preferred start must fall between earliest start and deadline")
        if (self.deadline - self.earliest_start).total_seconds() > 8 * 86400:
            raise ValueError("Starter horizon is at most eight days")
        for name in ["protected_sectors", "required_equipment_ids", "allowed_dates", "depends_on"]:
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate values in {name}")
        if self.work_sector not in self.protected_sectors:
            raise ValueError("Protection footprint must contain the work sector")
        return self

class CommitInput(StrictModel):
    expected_version: int = Field(ge=1)


class AllocationDraft(StrictModel):
    request_id: str
    start: datetime
    engineer_id: str
    locked: bool = False

    @field_validator("start")
    @classmethod
    def valid_start(cls, v):
        if v.utcoffset() is None:
            raise ValueError("Include a timezone, for example +08:00")
        if v.second or v.microsecond:
            raise ValueError("Use whole minutes")
        return v.astimezone(SGT)


class ManualPlanInput(StrictModel):
    allocations: list[AllocationDraft] = Field(min_length=1, max_length=40)


class SolveInput(StrictModel):
    locked_allocations: list[AllocationDraft] = Field(default_factory=list, max_length=40)


class ApprovalInput(StrictModel):
    request_ids: list[str] = Field(min_length=1, max_length=40)
    approved: bool


class AllocationLockInput(StrictModel):
    request_ids: list[str] = Field(min_length=1, max_length=40)
    locked: bool

class ResourceChange(StrictModel):
    kind: Literal["engineers", "equipment"]
    id: str
    unavailable_from: datetime | None = None
    unavailable_to: datetime | None = None
    serviceable: bool | None = None

    @model_validator(mode="after")
    def validate_change(self):
        if self.kind == "engineers" and self.serviceable is not None:
            raise ValueError("Serviceability applies to equipment, not people")
        if (self.unavailable_from is None) != (self.unavailable_to is None):
            raise ValueError("Provide both unavailable_from and unavailable_to")
        if self.unavailable_from is not None:
            if self.unavailable_from.utcoffset() is None or self.unavailable_to.utcoffset() is None:
                raise ValueError("Include timezones")
            if self.unavailable_from >= self.unavailable_to:
                raise ValueError("Unavailable interval must have positive duration")
        if self.unavailable_from is None and self.serviceable is None:
            raise ValueError("Provide a change")
        return self
