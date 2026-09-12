"""Domain data classes and validation layer for the CP-SAT scheduling engine.

Pure domain representation: never imports solver, database, or API service modules.
"""
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Literal, Mapping, Self
from zoneinfo import ZoneInfo
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SGT = ZoneInfo("Asia/Singapore")


def normalize_and_validate_datetime(v: Any) -> datetime:
    if isinstance(v, str):
        s = v.strip()
        try:
            v = datetime.fromisoformat(s)
        except Exception as e:
            raise ValueError(f"Invalid ISO datetime string: '{s}'") from e
    if not isinstance(v, datetime):
        raise ValueError(f"Expected datetime, got {type(v).__name__}")
    if v.utcoffset() is None:
        raise ValueError("Datetime must be timezone-aware (e.g. +08:00)")
    if v.second != 0 or v.microsecond != 0:
        raise ValueError("Datetime must have whole-minute precision (seconds and microseconds must be 0)")
    return v.astimezone(SGT)


def normalize_and_validate_opt_datetime(v: Any) -> datetime | None:
    if v is None:
        return None
    return normalize_and_validate_datetime(v)


AwareMinuteDatetime = Annotated[datetime, BeforeValidator(normalize_and_validate_datetime)]
OptAwareMinuteDatetime = Annotated[datetime | None, BeforeValidator(normalize_and_validate_opt_datetime)]


class DomainModel(BaseModel):
    """Base domain model forbidding extra fields, enabling assignment validation and name population."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True,
    )

    @field_validator("*", mode="after")
    @classmethod
    def _validate_domain_fields(cls, v: Any, info) -> Any:
        if isinstance(v, datetime):
            return normalize_and_validate_datetime(v)
        if isinstance(v, str):
            if not v.strip():
                raise ValueError(f"Field '{info.field_name}' must not be blank")
        elif isinstance(v, list):
            for idx, item in enumerate(v):
                if isinstance(item, str) and not item.strip():
                    raise ValueError(f"List item at index {idx} in '{info.field_name}' must not be blank")
        elif isinstance(v, dict):
            for k in v.keys():
                if isinstance(k, str) and not k.strip():
                    raise ValueError(f"Dict key in '{info.field_name}' must not be blank")
        return v


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class PowerRequirement(str, Enum):
    ON = "ON"
    OFF = "OFF"
    NONE = "NONE"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            upper = value.strip().upper()
            if upper == "ANY":
                return cls.NONE
            for member in cls:
                if member.value == upper:
                    return member
        return None


class TimingMode(str, Enum):
    EXACT = "EXACT"
    RANGE = "RANGE"
    ANY_TIME = "ANY_TIME"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            upper = value.strip().upper()
            for member in cls:
                if member.value == upper:
                    return member
        return None


class RequestStatus(str, Enum):
    submitted = "submitted"
    approved = "approved"
    scheduled = "scheduled"
    cancelled = "cancelled"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            lower = value.strip().lower()
            for member in cls:
                if member.value == lower:
                    return member
        return None


class PhaseType(str, Enum):
    setup = "setup"
    work = "work"
    test = "test"
    handback = "handback"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            lower = value.strip().lower()
            for member in cls:
                if member.value == lower:
                    return member
        return None


class VehicleType(str, Enum):
    LOCOMOTIVE = "LOCOMOTIVE"
    TAMPING_MACHINE = "TAMPING_MACHINE"
    INSPECTION_TRAIN = "INSPECTION_TRAIN"
    FLAT_WAGON = "FLAT_WAGON"
    ROAD_RAILER = "ROAD_RAILER"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            upper = value.strip().upper()
            for member in cls:
                if member.value == upper:
                    return member
        return None


class ConflictCode(str, Enum):
    DURATION = "DURATION"
    START_GRID = "START_GRID"
    REQUEST_WINDOW = "REQUEST_WINDOW"
    ENGINEERING_WINDOW = "ENGINEERING_WINDOW"
    BLACKOUT = "BLACKOUT"
    SPACE = "SPACE"
    POWER = "POWER"
    WORK_COMPATIBILITY = "WORK_COMPATIBILITY"
    ENGINEER = "ENGINEER"
    QUALIFICATION = "QUALIFICATION"
    EQUIPMENT = "EQUIPMENT"
    EQUIPMENT_ASSIGNMENT = "EQUIPMENT_ASSIGNMENT"
    EQUIPMENT_UNAVAILABLE = "EQUIPMENT_UNAVAILABLE"
    RESOURCE_WINDOW = "RESOURCE_WINDOW"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    TRANSFER_TIME = "TRANSFER_TIME"
    DEPENDENCY = "DEPENDENCY"
    LOCKED_BOOKING = "LOCKED_BOOKING"
    MANDATORY_DROPPED = "MANDATORY_DROPPED"
    MANPOWER = "MANPOWER"
    DUPLICATE = "DUPLICATE"
    UNKNOWN_REQUEST = "UNKNOWN_REQUEST"
    MISSING_WORK = "MISSING_WORK"
    CANCELLED = "CANCELLED"
    VEHICLE_TRANSIT = "VEHICLE_TRANSIT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# -----------------------------------------------------------------------------
# Snapshot Metadata & Topology
# -----------------------------------------------------------------------------

class SnapshotMetadata(DomainModel):
    schema_version: str
    planning_version: int = Field(gt=0)
    timezone: str
    planning_date: str | None = None
    synthetic: bool
    description: str
    disclaimer: str
    scope: str
    simplifications: list[str]

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, v: str) -> str:
        s = v.strip()
        try:
            ZoneInfo(s)
        except Exception as e:
            raise ValueError(f"Invalid timezone name '{s}'") from e
        return s

    @field_validator("planning_date")
    @classmethod
    def validate_planning_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        try:
            d = date.fromisoformat(s)
            if d.isoformat() != s:
                raise ValueError(f"Date must be in YYYY-MM-DD format, got '{s}'")
        except Exception as e:
            raise ValueError(f"Invalid ISO calendar date '{s}'") from e
        return s


class Station(DomainModel):
    id: str
    name: str
    schematic_x: int | float


class PowerZone(DomainModel):
    id: str
    sector_ids: list[str]

    @field_validator("sector_ids")
    @classmethod
    def validate_sector_ids(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate sector IDs in power zone")
        return v


# -----------------------------------------------------------------------------
# Time Windows, Handback, Closures
# -----------------------------------------------------------------------------

class TimeWindow(DomainModel):
    start: AwareMinuteDatetime
    end: AwareMinuteDatetime

    @model_validator(mode="after")
    def validate_positive_duration(self) -> Self:
        if self.start >= self.end:
            raise ValueError(f"TimeWindow start ({self.start}) must be strictly before end ({self.end})")
        return self

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


class Sector(DomainModel):
    id: str
    from_station: str
    to_station: str
    direction: str
    power_zone: str
    exclusive_protection: bool = True
    fixed_unavailable_intervals: list[TimeWindow] = Field(default_factory=list)


class EngineeringWindow(DomainModel):
    date: str
    sector_ids: list[str]
    start: AwareMinuteDatetime
    end: AwareMinuteDatetime
    handback_buffer_minutes: int = 20

    @field_validator("date")
    @classmethod
    def validate_date_str(cls, v: str) -> str:
        s = v.strip()
        try:
            d = date.fromisoformat(s)
            if d.isoformat() != s:
                raise ValueError(f"Date must be formatted as YYYY-MM-DD, got '{s}'")
        except Exception as e:
            raise ValueError(f"Invalid ISO calendar date '{s}'") from e
        return s

    @field_validator("sector_ids")
    @classmethod
    def validate_sector_ids(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate sector IDs in engineering window")
        return v

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.start >= self.end:
            raise ValueError(f"Engineering window start ({self.start}) must be before end ({self.end})")
        if self.handback_buffer_minutes < 0:
            raise ValueError("handback_buffer_minutes must be non-negative")
        if (self.end - self.start).total_seconds() <= self.handback_buffer_minutes * 60:
            raise ValueError(
                f"Handback buffer ({self.handback_buffer_minutes}m) must leave a positive usable window"
            )
        start_date = self.start.astimezone(SGT).date().isoformat()
        if self.date != start_date:
            raise ValueError(f"Window start date '{start_date}' does not match declared date '{self.date}'")
        return self

    @property
    def usable_end(self) -> datetime:
        return self.end - timedelta(minutes=self.handback_buffer_minutes)


class Blackout(DomainModel):
    id: str
    sector_ids: list[str]
    start: AwareMinuteDatetime
    end: AwareMinuteDatetime
    reason: str

    @field_validator("sector_ids")
    @classmethod
    def validate_sector_ids(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Blackout must specify at least one sector")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate sector IDs in blackout")
        return v

    @model_validator(mode="after")
    def validate_blackout(self) -> Self:
        if self.start >= self.end:
            raise ValueError(f"Blackout start ({self.start}) must be strictly before end ({self.end})")
        return self

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


# -----------------------------------------------------------------------------
# Phases & Maintenance Requests
# -----------------------------------------------------------------------------

class Phase(DomainModel):
    name: PhaseType
    duration_minutes: int = Field(ge=0)


class MaintenanceRequest(DomainModel):
    id: str
    title: str
    status: RequestStatus
    owner_id: str
    work_type: str | None = None

    work_sector: str
    protected_sectors: list[str]
    power_zone: str | None = None
    power_requirement: PowerRequirement

    phases: list[Phase]
    legacy_duration: int | None = Field(
        default=None,
        alias="duration_minutes",
        exclude=True,
    )

    timing_mode: TimingMode = TimingMode.RANGE
    preferred_start: OptAwareMinuteDatetime = None
    earliest_start: AwareMinuteDatetime
    deadline: AwareMinuteDatetime
    allowed_dates: list[str]

    deferrable: bool = True
    mandatory: bool = Field(
        default=False,
        validation_alias=AliasChoices("mandatory", "mandatory_in_this_demo"),
    )
    approved: bool = False
    frozen: bool = False
    existing_start: OptAwareMinuteDatetime = None
    urgency_score: int = Field(default=3, ge=1, le=5)
    priority: str | None = None

    required_skill: str
    required_engineer_roles: dict[str, int] = Field(default_factory=dict)
    eligible_engineers: list[str] = Field(default_factory=list)
    preferred_engineer: str | None = None

    required_equipment_ids: list[str] = Field(default_factory=list)
    technicians_required: int = Field(default=0, ge=0)
    pooled_resources: dict[str, int] = Field(default_factory=dict)

    depends_on: list[str] = Field(default_factory=list)
    handover_buffer_minutes: int = Field(default=0, ge=0)
    handover_buffers: dict[str, int] = Field(default_factory=dict)
    split_allowed: bool = False

    @field_validator("allowed_dates")
    @classmethod
    def validate_allowed_dates(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("allowed_dates must contain at least one date")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate dates in allowed_dates")
        for item in v:
            s = item.strip()
            try:
                d = date.fromisoformat(s)
                if d.isoformat() != s:
                    raise ValueError(f"Date must be formatted as YYYY-MM-DD, got '{s}'")
            except Exception as e:
                raise ValueError(f"Invalid ISO calendar date '{s}' in allowed_dates") from e
        return v

    @field_validator("protected_sectors")
    @classmethod
    def validate_protected_sectors(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("protected_sectors must contain at least one sector")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate sectors in protected_sectors")
        return v

    @field_validator("required_equipment_ids")
    @classmethod
    def validate_required_equipment(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate equipment IDs in required_equipment_ids")
        return v

    @field_validator("depends_on")
    @classmethod
    def validate_depends_on(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate dependency IDs in depends_on")
        return v

    @field_validator("eligible_engineers")
    @classmethod
    def validate_eligible_engineers(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate engineer IDs in eligible_engineers")
        return v

    @field_validator("required_engineer_roles")
    @classmethod
    def validate_engineer_roles(cls, v: dict[str, int]) -> dict[str, int]:
        for role, count in v.items():
            if not role.strip():
                raise ValueError("Role name must not be blank")
            if count < 0:
                raise ValueError(f"Role count for '{role}' must be non-negative")
        return v

    @field_validator("pooled_resources")
    @classmethod
    def validate_pooled_resources(cls, v: dict[str, int]) -> dict[str, int]:
        for res, qty in v.items():
            if not res.strip():
                raise ValueError("Resource name must not be blank")
            if qty < 0:
                raise ValueError(f"Resource quantity for '{res}' must be non-negative")
        return v

    @field_validator("handover_buffers")
    @classmethod
    def validate_handover_buffers(cls, v: dict[str, int]) -> dict[str, int]:
        for k, buffer in v.items():
            if not k.strip():
                raise ValueError("Handover buffer key must not be blank")
            if buffer < 0:
                raise ValueError(f"Handover buffer for '{k}' must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_request_package(self) -> Self:
        # 1. Phase validation
        phase_names = [p.name.value if isinstance(p.name, PhaseType) else p.name for p in self.phases]
        if phase_names != ["setup", "work", "test", "handback"]:
            raise ValueError("Phases must be setup, work, test, handback in that exact order")
        if len(self.phases) != 4:
            raise ValueError("Request must contain exactly four phases")
        if self.phases[1].duration_minutes <= 0:
            raise ValueError("Work phase duration must be positive")
        tot_dur = sum(p.duration_minutes for p in self.phases)
        if tot_dur <= 0:
            raise ValueError("Total package duration must be positive")

        if self.legacy_duration is not None and self.legacy_duration != tot_dur:
            raise ValueError(
                f"Supplied legacy duration_minutes ({self.legacy_duration}) "
                f"does not match sum of phases ({tot_dur})"
            )

        # 2. Footprint contains work sector
        if self.work_sector not in self.protected_sectors:
            raise ValueError(f"Work sector '{self.work_sector}' must be included in protected_sectors")

        # 3. Timing mode semantics
        if self.earliest_start >= self.deadline:
            raise ValueError("earliest_start must be strictly before deadline")

        if self.timing_mode == TimingMode.EXACT:
            if self.preferred_start is None:
                raise ValueError("EXACT timing mode requires preferred_start to be specified")
            if self.earliest_start != self.preferred_start:
                raise ValueError("EXACT timing mode requires earliest_start to equal preferred_start")
            expected_deadline = self.preferred_start + timedelta(minutes=tot_dur)
            if self.deadline != expected_deadline:
                raise ValueError(
                    f"EXACT timing mode requires deadline ({self.deadline}) "
                    f"to equal preferred_start + duration ({expected_deadline})"
                )
            if self.preferred_start.astimezone(SGT).date().isoformat() not in self.allowed_dates:
                raise ValueError("preferred_start date must be included in allowed_dates")

        elif self.timing_mode == TimingMode.RANGE:
            if self.preferred_start is not None:
                if self.preferred_start < self.earliest_start:
                    raise ValueError("preferred_start cannot be before earliest_start in RANGE timing mode")
                if self.preferred_start + timedelta(minutes=tot_dur) > self.deadline:
                    raise ValueError("preferred_start + duration exceeds deadline in RANGE timing mode")
                if self.preferred_start.astimezone(SGT).date().isoformat() not in self.allowed_dates:
                    raise ValueError("preferred_start date must be included in allowed_dates")

        elif self.timing_mode == TimingMode.ANY_TIME:
            if self.preferred_start is not None:
                raise ValueError("ANY_TIME timing mode permits no preferred_start objective")

        # 4. Invariants on dependencies
        if self.id in self.depends_on:
            raise ValueError(f"Request '{self.id}' cannot depend on itself")
        if not set(self.handover_buffers.keys()).issubset(set(self.depends_on)):
            raise ValueError("handover_buffers keys must be a subset of depends_on")

        # 5. Freeze / approval invariant
        if self.frozen and not self.approved:
            raise ValueError("Request cannot be frozen=True unless approved=True")

        # 6. Legacy default derivations
        if not self.required_engineer_roles and self.required_skill:
            self.required_engineer_roles = {self.required_skill: 1}
        if not self.pooled_resources and self.technicians_required > 0:
            self.pooled_resources = {"TECH": self.technicians_required}

        return self

    @property
    def duration_minutes(self) -> int:
        return sum(p.duration_minutes for p in self.phases)

    def get_handover_buffer(self, predecessor_id: str) -> int:
        return self.handover_buffers.get(predecessor_id, self.handover_buffer_minutes)


# -----------------------------------------------------------------------------
# Resources: Engineers, Equipment, Resource Pools
# -----------------------------------------------------------------------------

class Engineer(DomainModel):
    id: str
    name: str
    skills: list[str]
    initial_sector: str
    availability: list[TimeWindow]
    unavailable: list[TimeWindow] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Engineer must have at least one skill")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate skills for engineer")
        return v


class Equipment(DomainModel):
    id: str
    type: str
    initial_sector: str
    capacity: int = 1
    availability: list[TimeWindow]
    unavailable: list[TimeWindow] = Field(default_factory=list)
    serviceable: bool = True


class ResourcePool(DomainModel):
    id: str
    name: str
    capacity: int = Field(ge=0)


# -----------------------------------------------------------------------------
# Travel Times and Work Compatibility
# -----------------------------------------------------------------------------

class TravelTimeEntry(DomainModel):
    from_sector: str
    to_sector: str
    travel_minutes: int = Field(ge=0)


class TravelTimeMatrix(DomainModel):
    entries: list[TravelTimeEntry] = Field(default_factory=list)

    @field_validator("entries")
    @classmethod
    def validate_entries(cls, v: list[TravelTimeEntry]) -> list[TravelTimeEntry]:
        seen = set()
        for entry in v:
            pair = (entry.from_sector, entry.to_sector)
            if pair in seen:
                raise ValueError(f"Duplicate travel time entry for pair {pair}")
            seen.add(pair)
        return v

    def get(self, from_sector: str, to_sector: str) -> int | None:
        for entry in self.entries:
            if entry.from_sector == from_sector and entry.to_sector == to_sector:
                return entry.travel_minutes
        return None


class CompatibilityRule(DomainModel):
    work_type_a: str
    work_type_b: str
    compatible: bool
    transition_minutes: int = Field(default=0, ge=0)


# -----------------------------------------------------------------------------
# Vehicles & Transit
# -----------------------------------------------------------------------------

class TransitLeg(DomainModel):
    sector_id: str
    travel_minutes: int = Field(gt=0)


class TransitRoute(DomainModel):
    origin_depot: str
    destination_sector: str
    legs: list[TransitLeg] = Field(default_factory=list)

    @property
    def total_transit_minutes(self) -> int:
        return sum(leg.travel_minutes for leg in self.legs)


class TransitSchedule(DomainModel):
    vehicle_id: str
    sector_id: str
    start: AwareMinuteDatetime
    end: AwareMinuteDatetime

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        if self.start >= self.end:
            raise ValueError(f"TransitSchedule start ({self.start}) must be before end ({self.end})")
        return self


class Vehicle(DomainModel):
    id: str
    name: str
    type: VehicleType
    home_depot: str
    availability: list[TimeWindow] = Field(default_factory=list)
    routes: list[TransitRoute] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Allocations
# -----------------------------------------------------------------------------

class Allocation(DomainModel):
    request_id: str
    start: AwareMinuteDatetime
    end: AwareMinuteDatetime
    engineer_id: str | None = None
    engineer_assignments: dict[str, list[str]] = Field(default_factory=dict)
    equipment_ids: list[str] = Field(default_factory=list)
    vehicle_ids: list[str] = Field(default_factory=list)
    locked: bool = False
    moved: bool = False

    @field_validator("equipment_ids")
    @classmethod
    def validate_equipment_ids(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate equipment IDs in allocation")
        return v

    @field_validator("vehicle_ids")
    @classmethod
    def validate_vehicle_ids(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate vehicle IDs in allocation")
        return v

    @model_validator(mode="after")
    def validate_allocation(self) -> Self:
        if self.start >= self.end:
            raise ValueError(f"Allocation start ({self.start}) must be before end ({self.end})")
        return self


# -----------------------------------------------------------------------------
# Planning Rules
# -----------------------------------------------------------------------------

class PlanningRules(DomainModel):
    source: str | None = None
    start_grid_minutes: int = 5
    different_site_transfer_minutes: int = 15
    opposed_power_transition_minutes: int = 10
    morning_buffer_minutes: int = 20
    freeze_horizon_days: int = 3
    power_values: list[PowerRequirement]
    power_compatibility: dict[PowerRequirement, dict[PowerRequirement, bool]]
    work_compatibility_rules: list[CompatibilityRule] = Field(default_factory=list)
    unknown_rule_policy: str = "REVIEW_REQUIRED"

    @model_validator(mode="before")
    @classmethod
    def pre_validate_power_rules(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        def _to_upper(x: Any) -> str:
            if hasattr(x, "value"):
                return str(x.value).strip().upper()
            return str(x).strip().upper()

        # Check power_values for both ANY and NONE
        raw_vals = data.get("power_values")
        if isinstance(raw_vals, list):
            str_vals = [_to_upper(v) for v in raw_vals]
            if "ANY" in str_vals and "NONE" in str_vals:
                raise ValueError(
                    "Ambiguous conflicting definitions: both 'ANY' and 'NONE' supplied in power_values"
                )

        # Check power_compatibility keys
        raw_compat = data.get("power_compatibility")
        if isinstance(raw_compat, dict):
            outer_keys = [_to_upper(k) for k in raw_compat.keys()]
            if "ANY" in outer_keys and "NONE" in outer_keys:
                raise ValueError(
                    "Ambiguous conflicting definitions: both 'ANY' and 'NONE' supplied in power_compatibility keys"
                )
            for k, inner in raw_compat.items():
                if isinstance(inner, dict):
                    inner_keys = [_to_upper(ik) for ik in inner.keys()]
                    if "ANY" in inner_keys and "NONE" in inner_keys:
                        raise ValueError(
                            f"Ambiguous conflicting definitions: both 'ANY' and 'NONE' supplied in inner keys for '{k}'"
                        )
        return data


# -----------------------------------------------------------------------------
# Conflict Reporting
# -----------------------------------------------------------------------------

class Conflict(DomainModel):
    code: ConflictCode
    request_ids: list[str]
    message: str
    resource: str | None = None
    severity: Literal["error", "warning"] = "error"

    @field_validator("request_ids")
    @classmethod
    def validate_request_ids(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Conflict must have at least one request ID")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate request IDs in conflict")
        return v


# -----------------------------------------------------------------------------
# Job Catalogue & Snapshot
# -----------------------------------------------------------------------------

class JobTypeEntry(DomainModel):
    work_type: str
    default_duration_minutes: int = Field(gt=0)
    required_engineer_roles: dict[str, int] = Field(default_factory=dict)
    pooled_resources: dict[str, int] = Field(default_factory=dict)
    power_requirement: PowerRequirement = PowerRequirement.NONE
    default_protection_rule: str | None = None

    @field_validator("required_engineer_roles", "pooled_resources")
    @classmethod
    def validate_quantities(cls, v: dict[str, int]) -> dict[str, int]:
        for k, qty in v.items():
            if qty < 0:
                raise ValueError(f"Quantity for '{k}' must be non-negative")
        return v


class PlanningSnapshot(DomainModel):
    metadata: SnapshotMetadata
    stations: list[Station]
    power_zones: list[PowerZone] = Field(default_factory=list)
    sectors: list[Sector]
    engineering_windows: list[EngineeringWindow]
    blackouts: list[Blackout] = Field(default_factory=list)
    planning_rules: PlanningRules
    engineers: list[Engineer]
    equipment: list[Equipment]
    resource_pools: list[ResourcePool]
    requests: list[MaintenanceRequest]
    committed_allocations: list[Allocation]
    travel_time_matrix: TravelTimeMatrix = Field(default_factory=TravelTimeMatrix)
    vehicles: list[Vehicle] = Field(default_factory=list)
    transit_schedules: list[TransitSchedule] = Field(default_factory=list)
    job_catalogue: list[JobTypeEntry] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        return cls.model_validate_json(payload)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @model_validator(mode="after")
    def validate_cross_entity_integrity(self) -> Self:
        # 1. Stations uniqueness
        station_ids = {s.id for s in self.stations}
        if len(station_ids) != len(self.stations):
            raise ValueError("Duplicate station ID detected in stations collection")

        # 2. Sectors uniqueness and endpoint references
        sector_ids = {s.id for s in self.sectors}
        if len(sector_ids) != len(self.sectors):
            raise ValueError("Duplicate sector ID detected in sectors collection")

        sector_map = {s.id: s for s in self.sectors}
        for s in self.sectors:
            if s.from_station not in station_ids:
                raise ValueError(f"Sector '{s.id}' from_station '{s.from_station}' does not reference a known station")
            if s.to_station not in station_ids:
                raise ValueError(f"Sector '{s.id}' to_station '{s.to_station}' does not reference a known station")

        # 3. Explicit PowerZones validation
        if self.power_zones:
            pz_ids = {pz.id for pz in self.power_zones}
            if len(pz_ids) != len(self.power_zones):
                raise ValueError("Duplicate power zone ID detected in power_zones collection")

            seen_pz_sectors = set()
            for pz in self.power_zones:
                for sid in pz.sector_ids:
                    if sid not in sector_ids:
                        raise ValueError(f"PowerZone '{pz.id}' references unknown sector '{sid}'")
                    if sid in seen_pz_sectors:
                        raise ValueError(f"Sector '{sid}' appears in multiple power zones")
                    seen_pz_sectors.add(sid)
                    if sector_map[sid].power_zone != pz.id:
                        raise ValueError(
                            f"Sector '{sid}' power_zone '{sector_map[sid].power_zone}' "
                            f"does not match PowerZone record '{pz.id}'"
                        )
            for s in self.sectors:
                if s.power_zone not in pz_ids:
                    raise ValueError(f"Sector '{s.id}' references unknown power zone '{s.power_zone}'")

        # 4. Engineering windows: sector coverage and handback buffer agreement
        for w in self.engineering_windows:
            for sid in w.sector_ids:
                if sid not in sector_ids:
                    raise ValueError(f"Engineering window references unknown sector '{sid}'")
            if w.handback_buffer_minutes != self.planning_rules.morning_buffer_minutes:
                raise ValueError(
                    f"Engineering window handback buffer ({w.handback_buffer_minutes}m) "
                    f"must agree with planning rules morning buffer ({self.planning_rules.morning_buffer_minutes}m)"
                )

        if self.metadata.planning_date is not None:
            if not any(w.date == self.metadata.planning_date for w in self.engineering_windows):
                raise ValueError(
                    f"Declared planning_date '{self.metadata.planning_date}' has no corresponding engineering window"
                )

        # 5. Blackout sectors
        blackout_ids = {b.id for b in self.blackouts}
        if len(blackout_ids) != len(self.blackouts):
            raise ValueError("Duplicate blackout ID detected in blackouts collection")

        for b in self.blackouts:
            for sid in b.sector_ids:
                if sid not in sector_ids:
                    raise ValueError(f"Blackout '{b.id}' references unknown sector '{sid}'")

        # 6. Resource collections uniqueness
        engineer_ids = {e.id for e in self.engineers}
        if len(engineer_ids) != len(self.engineers):
            raise ValueError("Duplicate engineer ID detected in engineers collection")
        for e in self.engineers:
            if e.initial_sector not in sector_ids:
                raise ValueError(f"Engineer '{e.id}' initial_sector '{e.initial_sector}' not found in sectors")

        equipment_ids = {eq.id for eq in self.equipment}
        if len(equipment_ids) != len(self.equipment):
            raise ValueError("Duplicate equipment ID detected in equipment collection")
        for eq in self.equipment:
            if eq.initial_sector not in sector_ids:
                raise ValueError(f"Equipment '{eq.id}' initial_sector '{eq.initial_sector}' not found in sectors")

        pool_ids = {p.id for p in self.resource_pools}
        if len(pool_ids) != len(self.resource_pools):
            raise ValueError("Duplicate resource pool ID detected in resource_pools collection")

        vehicle_ids = {v.id for v in self.vehicles}
        if len(vehicle_ids) != len(self.vehicles):
            raise ValueError("Duplicate vehicle ID detected in vehicles collection")

        # 7. Transit schedules and vehicles
        for ts in self.transit_schedules:
            if ts.vehicle_id not in vehicle_ids:
                raise ValueError(f"Transit schedule references unknown vehicle '{ts.vehicle_id}'")
            if ts.sector_id not in sector_ids:
                raise ValueError(f"Transit schedule references unknown sector '{ts.sector_id}'")

        for v in self.vehicles:
            for route in v.routes:
                if route.destination_sector not in sector_ids:
                    raise ValueError(f"Vehicle route references unknown destination sector '{route.destination_sector}'")
                for leg in route.legs:
                    if leg.sector_id not in sector_ids:
                        raise ValueError(f"Vehicle route leg references unknown sector '{leg.sector_id}'")

        # 8. Travel time matrix sectors
        for entry in self.travel_time_matrix.entries:
            if entry.from_sector not in sector_ids:
                raise ValueError(f"Travel matrix references unknown from_sector '{entry.from_sector}'")
            if entry.to_sector not in sector_ids:
                raise ValueError(f"Travel matrix references unknown to_sector '{entry.to_sector}'")

        # 9. Requests validation and cross-entity references
        request_map = {}
        for r in self.requests:
            if r.id in request_map:
                raise ValueError(f"Duplicate request ID '{r.id}' detected in requests collection")
            request_map[r.id] = r

            if r.work_sector not in sector_ids:
                raise ValueError(f"Request '{r.id}' work_sector '{r.work_sector}' not found in sectors")
            for ps in r.protected_sectors:
                if ps not in sector_ids:
                    raise ValueError(f"Request '{r.id}' protected sector '{ps}' not found in sectors")

            # Sector power zone consistency
            sec = sector_map[r.work_sector]
            if r.power_zone is not None and r.power_zone != sec.power_zone:
                raise ValueError(
                    f"Request '{r.id}' power_zone '{r.power_zone}' does not match sector power_zone '{sec.power_zone}'"
                )
            elif r.power_zone is None:
                r.power_zone = sec.power_zone

            for eid in r.eligible_engineers:
                if eid not in engineer_ids:
                    raise ValueError(f"Request '{r.id}' references unknown eligible engineer '{eid}'")
            if r.preferred_engineer is not None and r.preferred_engineer not in engineer_ids:
                raise ValueError(f"Request '{r.id}' references unknown preferred engineer '{r.preferred_engineer}'")

            for qid in r.required_equipment_ids:
                if qid not in equipment_ids:
                    raise ValueError(f"Request '{r.id}' references unknown equipment '{qid}'")

            for dep_id in r.depends_on:
                if not any(other.id == dep_id for other in self.requests):
                    raise ValueError(f"Request '{r.id}' references unknown dependency '{dep_id}'")

            # Engineering window coverage check for allowed dates
            for ad in r.allowed_dates:
                matching = [w for w in self.engineering_windows if w.date == ad]
                if not matching:
                    raise ValueError(f"Request '{r.id}' allowed_date '{ad}' has no corresponding engineering window")
                covered_sectors = {sid for w in matching for sid in w.sector_ids}
                if not set(r.protected_sectors).issubset(covered_sectors):
                    raise ValueError(
                        f"Request '{r.id}' protected sectors not fully covered by engineering windows on date '{ad}'"
                    )

        # 10. Dependency cycle detection
        visited = {}  # 1 = in progress, 2 = done

        def dfs(node: str, path: list[str]) -> None:
            visited[node] = 1
            req = request_map[node]
            for parent in req.depends_on:
                if visited.get(parent) == 1:
                    cycle_str = " -> ".join(path + [parent])
                    raise ValueError(f"Dependency cycle detected among requests: {cycle_str}")
                if visited.get(parent) is None:
                    dfs(parent, path + [parent])
            visited[node] = 2

        for r in self.requests:
            if r.id not in visited:
                dfs(r.id, [r.id])

        # 11. Allocations integrity & request derivations
        committed_map = {}
        for a in self.committed_allocations:
            if a.request_id in committed_map:
                raise ValueError(f"Duplicate allocation for request '{a.request_id}' in committed_allocations")
            committed_map[a.request_id] = a

            if a.request_id not in request_map:
                raise ValueError(f"Committed allocation references unknown request '{a.request_id}'")
            req = request_map[a.request_id]

            if req.status == RequestStatus.cancelled:
                raise ValueError(f"Cancelled request '{req.id}' cannot have a committed allocation")

            if (a.end - a.start).total_seconds() != req.duration_minutes * 60:
                raise ValueError(
                    f"Allocation duration for request '{req.id}' ({(a.end - a.start).total_seconds() / 60}m) "
                    f"does not match request phase duration ({req.duration_minutes}m)"
                )

            if a.engineer_id is not None and a.engineer_id not in engineer_ids:
                raise ValueError(f"Allocation engineer '{a.engineer_id}' does not exist")
            for qid in a.equipment_ids:
                if qid not in equipment_ids:
                    raise ValueError(f"Allocation equipment '{qid}' does not exist")
            for vid in a.vehicle_ids:
                if vid not in vehicle_ids:
                    raise ValueError(f"Allocation vehicle '{vid}' does not exist")

            if req.existing_start is not None and req.existing_start != a.start:
                raise ValueError(
                    f"Request '{req.id}' existing_start ({req.existing_start}) "
                    f"does not match committed allocation start ({a.start})"
                )

        # 12. Scheduled requests must have committed allocations and derive approval / existing_start
        for r in self.requests:
            if r.status == RequestStatus.scheduled:
                if r.id not in committed_map:
                    raise ValueError(f"Scheduled request '{r.id}' must have a matching committed allocation")
                alloc = committed_map[r.id]
                if not r.approved:
                    r.approved = True
                if r.existing_start is None:
                    r.existing_start = alloc.start
                # Note: Allocation.locked does NOT infer request.frozen=True

        return self
