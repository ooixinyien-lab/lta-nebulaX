"""Domain models for PS1 data adaptation layer.

Defines all official PS1 Pydantic v2 domain schemas for input CSVs,
output CSVs, domain enums, and the ProblemInstance container.
Zero imports or references to legacy models.
"""
from __future__ import annotations

from datetime import date, timedelta
from enum import Enum, IntEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator


class PS1Base(BaseModel):
    """Base for all PS1 domain models adhering strictly to Pydantic v2."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )


# ============================================================================
# Domain Enums (7 enums)
# ============================================================================


class ActivityType(str, Enum):
    """Activity type dimension: Renewal vs Construction."""

    RENEWAL = "Renewal"
    CONSTRUCTION = "Construction"

    @classmethod
    def _missing_(cls, value: object) -> ActivityType | None:
        if isinstance(value, str):
            val_lower = value.strip().lower()
            for member in cls:
                if member.value.lower() == val_lower:
                    return member
        return None


class NatureOfWorks(str, Enum):
    """Nature of works classification for safety buffers and traction power."""

    LIVE = "Live"
    NON_LIVE_CONSIST = "Non-live (Consist)"
    NON_LIVE_OTHERS = "Non-live (Others)"

    @classmethod
    def _missing_(cls, value: object) -> NatureOfWorks | None:
        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower in ("live",):
                return cls.LIVE
            if val_lower in (
                "non-live (consist)",
                "consist",
                "non-live consist",
                "non_live_consist",
            ):
                return cls.NON_LIVE_CONSIST
            if val_lower in (
                "non-live (others)",
                "others",
                "other",
                "non-live others",
                "non_live_others",
            ):
                return cls.NON_LIVE_OTHERS
            for member in cls:
                if member.value.lower() == val_lower:
                    return member
        return None


class AccessType(str, Enum):
    """Access hierarchy: PM (Possession Master), PC (Possession Co-sharer), C (Co-sharer)."""

    PM = "PM"
    PC = "PC"
    C = "C"

    @classmethod
    def _missing_(cls, value: object) -> AccessType | None:
        if isinstance(value, str):
            val_upper = value.strip().upper()
            for member in cls:
                if member.value.upper() == val_upper:
                    return member
        return None


class ContractPriority(IntEnum):
    """Contract priority tiers 1 (highest), 2, 3 (lowest)."""

    P1 = 1
    P2 = 2
    P3 = 3

    @classmethod
    def _missing_(cls, value: object) -> ContractPriority | None:
        if isinstance(value, str):
            try:
                return cls(int(value.strip()))
            except (ValueError, TypeError):
                pass
        return None


class ActivityPriority(IntEnum):
    """Activity priority tiers 1 (highest), 2, 3 (lowest)."""

    P1 = 1
    P2 = 2
    P3 = 3

    @classmethod
    def _missing_(cls, value: object) -> ActivityPriority | None:
        if isinstance(value, str):
            try:
                return cls(int(value.strip()))
            except (ValueError, TypeError):
                pass
        return None


class Bound(str, Enum):
    """Track bound: Eastbound (EB) vs Westbound (WB), or BOTH.

    NB and SB are recognized via aliases to EB and WB respectively.
    """

    EB = "EB"
    WB = "WB"
    BOTH = "BOTH"
    NB = "EB"  # Alias
    SB = "WB"  # Alias

    @property
    def opposite(self) -> Bound:
        """Returns the opposite track bound."""
        if self == Bound.EB:
            return Bound.WB
        if self == Bound.WB:
            return Bound.EB
        return Bound.BOTH

    @classmethod
    def _missing_(cls, value: object) -> Bound | None:
        if isinstance(value, str):
            norm = value.strip().upper()
            if norm in ("EB", "EAST", "EASTBOUND"):
                return cls.EB
            if norm in ("WB", "WEST", "WESTBOUND"):
                return cls.WB
            if norm in ("BOTH", "ALL", "BIDIRECTIONAL", "DUAL"):
                return cls.BOTH
            if norm in ("NB", "NORTH", "NORTHBOUND"):
                return cls.EB
            if norm in ("SB", "SOUTH", "SOUTHBOUND"):
                return cls.WB
        return None


class LocationKind(str, Enum):
    """Kind of network physical location: tunnel sector vs platform sector."""

    TUNNEL_SECTOR = "tunnel sector"
    PLATFORM_SECTOR = "platform sector"

    @classmethod
    def _missing_(cls, value: object) -> LocationKind | None:
        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower in ("tunnel sector", "tunnel", "tunnel_sector"):
                return cls.TUNNEL_SECTOR
            if val_lower in ("platform sector", "platform", "platform_sector"):
                return cls.PLATFORM_SECTOR
        return None


# ============================================================================
# 8 Official Input Models
# ============================================================================


class Line(PS1Base):
    """01_LINES.csv: Railway line."""

    line_code: str
    line_name: str


class Station(PS1Base):
    """02_STATIONS.csv: Railway station.

    Composite primary key is (line_code, station_id).
    """

    station_id: str
    line_code: str
    seq: int
    is_interchange: bool

    @field_validator("is_interchange", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip() in ("1", "true", "True")
        return bool(v)


class Sector(PS1Base):
    """03_SECTORS.csv: Track sector connecting two adjacent stations."""

    sector_id: str
    line_code: str
    from_station_id: str
    to_station_id: str
    seq: int
    is_shared: bool

    @field_validator("is_shared", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip() in ("1", "true", "True")
        return bool(v)


class LocationSupply(PS1Base):
    """04_LOCATION_SUPPLY.csv: Weekly possession capacity for a specific location."""

    location_id: str
    location_kind: LocationKind
    line_code: str
    bound: Bound
    supply_capacity: int


class BufferRule(PS1Base):
    """05_BUFFER_LOCATION.csv: Safety buffer expansion and mirroring rules."""

    nature_of_works: NatureOfWorks
    up_to_buffer_sectors: int
    opposite_bound_required: bool

    @field_validator("opposite_bound_required", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip() in ("1", "true", "True")
        return bool(v)


class PlanningParameters(PS1Base):
    """06_PARAMETERS.csv: Global planning horizon."""

    horizon_start: date
    horizon_weeks: int

    @property
    def horizon_end(self) -> date:
        """Sunday completion date of the final week in the planning horizon."""
        return self.horizon_start + timedelta(days=7 * self.horizon_weeks - 1)

    def week_end_date(self, week: int) -> date:
        """Sunday date on which week `week` (1-indexed) completes."""
        return self.horizon_start + timedelta(days=7 * week - 1)

    def week_start_date(self, week: int) -> date:
        """Monday date on which week `week` (1-indexed) begins."""
        return self.horizon_start + timedelta(days=7 * (week - 1))

    def date_to_week(self, d: date) -> int:
        """Converts any calendar date to a 1-indexed planning week."""
        return ((d - self.horizon_start).days // 7) + 1


class Contract(PS1Base):
    """07_PROJECT_DETAILS.csv: Contract details and resource boundaries."""

    contract_number: str
    contract_description: str
    contract_award_date: date
    activity_type: ActivityType
    nature_of_activity: NatureOfWorks
    contract_priority: ContractPriority
    contract_completion_date: date
    planned_completion_date: date
    number_of_workfronts: int
    access_type: AccessType
    number_of_maximum_access_per_week: int

    @property
    def score_weight(self) -> int:
        """Contract priority weight for overrun scoring: P1=100, P2=10, P3=1."""
        return {1: 100, 2: 10, 3: 1}[int(self.contract_priority)]


class Activity(PS1Base):
    """08_ACTIVITY_DETAILS.csv: Mandatory activity and workload demands."""

    activity_id: str
    contract_number: str
    activity_type: ActivityType
    start_location_id: str
    end_location_id: str
    total_accesses: int
    planned_start_date: date
    predecessor_activity_id: str | None = None
    activity_priority: ActivityPriority

    @field_validator("predecessor_activity_id", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: Any) -> str | None:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @property
    def doubled_workload(self) -> int:
        """Doubled workload units for exact integer ECLO accounting (standard=2, ECLO=3)."""
        return self.total_accesses * 2

    @property
    def score_nudge(self) -> float:
        """Activity priority score nudge: P1=0.3, P2=0.2, P3=0.0."""
        return {1: 0.3, 2: 0.2, 3: 0.0}[int(self.activity_priority)]


# ============================================================================
# 3 Official Output Models
# ============================================================================


class AccessScheduleRow(PS1Base):
    """SCHEDULE_ACCESS.csv output row."""

    activity_id: str
    access_seq: int
    week: int
    eclo: bool
    access_night: int

    @field_validator("eclo", mode="before")
    @classmethod
    def _parse_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip() in ("1", "true", "True")
        return bool(v)


class OccupancyScheduleRow(PS1Base):
    """SCHEDULE_OCCUPANCY.csv output row."""

    activity_id: str
    week: int
    location_id: str
    co_share_group: str


class ScenarioResultRow(PS1Base):
    """RESULTS.csv output row."""

    scenario: str
    contract_number: str
    simulated_completion_date: date
    overrun_days: int


# ============================================================================
# Unified Container: ProblemInstance
# ============================================================================


class ProblemInstance(PS1Base):
    """Unified container aggregating all 8 PS1 input collections.

    Maintains fast internal lookup indices via PrivateAttr.
    """

    lines: list[Line]
    stations: list[Station]
    sectors: list[Sector]
    locations: list[LocationSupply]
    buffer_rules: list[BufferRule]
    parameters: PlanningParameters
    contracts: list[Contract]
    activities: list[Activity]

    _lines_by_code: dict[str, Line] = PrivateAttr(default_factory=dict)
    _stations_by_key: dict[tuple[str, str], Station] = PrivateAttr(default_factory=dict)
    _sectors_by_id: dict[str, Sector] = PrivateAttr(default_factory=dict)
    _sectors_by_line: dict[str, list[Sector]] = PrivateAttr(default_factory=dict)
    _locations_by_id: dict[str, LocationSupply] = PrivateAttr(default_factory=dict)
    _contracts_by_number: dict[str, Contract] = PrivateAttr(default_factory=dict)
    _activities_by_id: dict[str, Activity] = PrivateAttr(default_factory=dict)
    _activities_by_contract: dict[str, list[Activity]] = PrivateAttr(default_factory=dict)
    _buffer_by_nature: dict[NatureOfWorks, BufferRule] = PrivateAttr(default_factory=dict)
    _predecessor_graph: dict[str, list[str]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._lines_by_code = {l.line_code: l for l in self.lines}
        self._stations_by_key = {(s.line_code, s.station_id): s for s in self.stations}
        self._sectors_by_id = {s.sector_id: s for s in self.sectors}

        sectors_by_line: dict[str, list[Sector]] = {}
        for s in self.sectors:
            sectors_by_line.setdefault(s.line_code, []).append(s)
        for l_code in sectors_by_line:
            sectors_by_line[l_code].sort(key=lambda s: s.seq)
        self._sectors_by_line = sectors_by_line

        self._locations_by_id = {loc.location_id: loc for loc in self.locations}
        self._contracts_by_number = {c.contract_number: c for c in self.contracts}
        self._activities_by_id = {a.activity_id: a for a in self.activities}

        acts_by_contract: dict[str, list[Activity]] = {}
        for a in self.activities:
            acts_by_contract.setdefault(a.contract_number, []).append(a)
        self._activities_by_contract = acts_by_contract

        self._buffer_by_nature = {b.nature_of_works: b for b in self.buffer_rules}

        pred_graph: dict[str, list[str]] = {a.activity_id: [] for a in self.activities}
        for a in self.activities:
            if a.predecessor_activity_id:
                pred_graph.setdefault(a.predecessor_activity_id, []).append(a.activity_id)
        self._predecessor_graph = pred_graph

    def line(self, code: str) -> Line:
        """Retrieve Line by line_code."""
        if code not in self._lines_by_code:
            raise KeyError(f"Unknown line code: '{code}'")
        return self._lines_by_code[code]

    def station(self, line: str, id: str) -> Station:
        """Retrieve Station by composite key (line_code, station_id)."""
        key = (line, id)
        if key not in self._stations_by_key:
            raise KeyError(f"Unknown station: line='{line}', id='{id}'")
        return self._stations_by_key[key]

    def sector(self, id: str) -> Sector:
        """Retrieve Sector by sector_id."""
        if id not in self._sectors_by_id:
            raise KeyError(f"Unknown sector id: '{id}'")
        return self._sectors_by_id[id]

    def location(self, id: str) -> LocationSupply:
        """Retrieve LocationSupply by location_id."""
        if id not in self._locations_by_id:
            raise KeyError(f"Unknown location id: '{id}'")
        return self._locations_by_id[id]

    def contract(self, num: str) -> Contract:
        """Retrieve Contract by contract_number."""
        if num not in self._contracts_by_number:
            raise KeyError(f"Unknown contract number: '{num}'")
        return self._contracts_by_number[num]

    def activity(self, id: str) -> Activity:
        """Retrieve Activity by activity_id."""
        if id not in self._activities_by_id:
            raise KeyError(f"Unknown activity id: '{id}'")
        return self._activities_by_id[id]

    def buffer_rule_for(self, nature: NatureOfWorks) -> BufferRule:
        """Retrieve BufferRule by nature_of_works."""
        if nature not in self._buffer_by_nature:
            raise KeyError(f"No buffer rule for nature of works: '{nature}'")
        return self._buffer_by_nature[nature]

    def line_sectors_ordered(self, line: str) -> list[Sector]:
        """Return ordered sectors for a line."""
        return list(self._sectors_by_line.get(line, []))

    def planned_start_week(self, activity: Activity | str) -> int:
        """Get the 1-indexed planning week corresponding to an activity's planned_start_date."""
        if isinstance(activity, str):
            act = self.activity(activity)
        else:
            act = activity
        return self.parameters.date_to_week(act.planned_start_date)
