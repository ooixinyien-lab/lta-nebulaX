"""Railway network topology and activity footprint calculation engine.

Models line geometry, stations, sectors, interchange hubs, and computes
activity core working footprints (strictly satisfying the 2k+1 invariant),
safety buffer expansions, opposite-bound mirroring, and cross-line interchange effects.
"""
from __future__ import annotations

from typing import Any
from pydantic import Field

from backend.app.domain_models import (
    Activity,
    Bound,
    BufferRule,
    Contract,
    LocationSupply,
    NatureOfWorks,
    ProblemInstance,
    PS1Base,
    Sector,
    Station,
)


class LineTopology:
    """Ordered geometric representation of a single railway line."""

    def __init__(
        self,
        line_code: str,
        stations: list[Station],
        sectors: list[Sector],
    ) -> None:
        self.line_code = line_code
        self.stations = sorted(stations, key=lambda s: s.seq)
        self.sectors = sorted(sectors, key=lambda s: s.seq)

        self._station_by_id: dict[str, Station] = {s.station_id: s for s in self.stations}
        self._station_idx: dict[str, int] = {s.station_id: i for i, s in enumerate(self.stations)}
        self._sector_by_id: dict[str, Sector] = {s.sector_id: s for s in self.sectors}
        self._sector_idx: dict[str, int] = {s.sector_id: i for i, s in enumerate(self.sectors)}
        self._sectors_by_from_to: dict[tuple[str, str], Sector] = {
            (s.from_station_id, s.to_station_id): s for s in self.sectors
        }

    def get_station(self, station_id: str) -> Station:
        """Retrieve station by ID."""
        if station_id not in self._station_by_id:
            raise KeyError(f"Station {station_id} not found on line {self.line_code}")
        return self._station_by_id[station_id]

    def get_sector(self, sector_id: str) -> Sector:
        """Retrieve sector by ID."""
        if sector_id not in self._sector_by_id:
            raise KeyError(f"Sector {sector_id} not found on line {self.line_code}")
        return self._sector_by_id[sector_id]

    def get_sectors_between(self, start_sector_id: str, end_sector_id: str) -> list[Sector]:
        """Returns the contiguous ordered slice of sectors from start to end (inclusive)."""
        if start_sector_id not in self._sector_idx:
            raise KeyError(f"Start sector {start_sector_id} not found on line {self.line_code}")
        if end_sector_id not in self._sector_idx:
            raise KeyError(f"End sector {end_sector_id} not found on line {self.line_code}")

        start_idx = self._sector_idx[start_sector_id]
        end_idx = self._sector_idx[end_sector_id]

        if start_idx > end_idx:
            raise ValueError(
                f"Start sector {start_sector_id} (seq {self.sectors[start_idx].seq}) "
                f"comes after end sector {end_sector_id} (seq {self.sectors[end_idx].seq})"
            )

        return list(self.sectors[start_idx : end_idx + 1])

    def get_stations_for_sectors(self, sectors: list[Sector]) -> list[Station]:
        """Returns ordered stations spanning the given contiguous sectors.

        For k contiguous sectors, exactly k+1 ordered stations are returned.
        """
        if not sectors:
            return []

        station_ids: list[str] = [sectors[0].from_station_id]
        for sec in sectors:
            station_ids.append(sec.to_station_id)

        return [self.get_station(sid) for sid in station_ids]

    def get_upstream_sectors(self, sector_id: str, count: int) -> list[Sector]:
        """Returns up to `count` sectors upstream of the given sector, clamped at line start."""
        if count <= 0 or sector_id not in self._sector_idx:
            return []
        idx = self._sector_idx[sector_id]
        start_idx = max(0, idx - count)
        return list(self.sectors[start_idx:idx])

    def get_downstream_sectors(self, sector_id: str, count: int) -> list[Sector]:
        """Returns up to `count` sectors downstream of the given sector, clamped at line end."""
        if count <= 0 or sector_id not in self._sector_idx:
            return []
        idx = self._sector_idx[sector_id]
        end_idx = min(len(self.sectors) - 1, idx + count)
        return list(self.sectors[idx + 1 : end_idx + 1])


class NetworkTopology:
    """Network-level topology managing all railway lines and interchange hubs."""

    def __init__(
        self,
        lines: dict[str, LineTopology],
        interchange_station_ids: set[str],
    ) -> None:
        self.lines = lines
        self.interchange_station_ids = interchange_station_ids

    def get_line(self, line_code: str) -> LineTopology:
        """Retrieve line topology by line code."""
        if line_code not in self.lines:
            raise KeyError(f"Line {line_code} not found in network topology")
        return self.lines[line_code]

    def is_interchange_station(self, station_id: str) -> bool:
        """Check if station is an interchange station."""
        return station_id in self.interchange_station_ids

    @classmethod
    def from_problem(cls, problem: ProblemInstance) -> NetworkTopology:
        """Construct NetworkTopology from ProblemInstance collections."""
        stations_by_line: dict[str, list[Station]] = {}
        for stn in problem.stations:
            stations_by_line.setdefault(stn.line_code, []).append(stn)

        sectors_by_line: dict[str, list[Sector]] = {}
        for sec in problem.sectors:
            sectors_by_line.setdefault(sec.line_code, []).append(sec)

        lines: dict[str, LineTopology] = {}
        for line in problem.lines:
            lines[line.line_code] = LineTopology(
                line_code=line.line_code,
                stations=stations_by_line.get(line.line_code, []),
                sectors=sectors_by_line.get(line.line_code, []),
            )

        interchanges = {s.station_id for s in problem.stations if s.is_interchange}
        return cls(lines=lines, interchange_station_ids=interchanges)


# ============================================================================
# Footprint Schemas
# ============================================================================


class ActivityFootprint(PS1Base):
    """Core working footprint for an activity.

    Enforces the structural invariant:
    k traversed sectors => k tunnels + (k+1) platforms = 2k+1 core locations.
    """

    activity_id: str
    line_code: str
    bound: Bound
    sectors: list[Sector]
    stations: list[Station]
    tunnel_locations: list[str]
    platform_locations: list[str]
    core_locations: list[str]


class ProtectionFootprint(PS1Base):
    """Full safety protection footprint enclosing an activity.

    Encompasses core locations, buffer expansion, opposite-bound mirroring,
    and cross-line interchange effects.
    """

    activity_id: str
    core: ActivityFootprint
    buffer_sectors: list[Sector]
    buffer_tunnel_locations: list[str]
    buffer_platform_locations: list[str]
    buffer_locations: list[str]
    mirrored_tunnel_locations: list[str]
    mirrored_platform_locations: list[str]
    mirrored_locations: list[str]
    cross_line_tunnel_locations: list[str]
    cross_line_platform_locations: list[str]
    cross_line_locations: list[str]
    all_protected_locations: list[str]


# ============================================================================
# Footprint Computation Functions
# ============================================================================


def compute_core_footprint(
    activity: Activity,
    topology: NetworkTopology,
    locations_by_id: dict[str, LocationSupply] | None = None,
) -> ActivityFootprint:
    """Computes the core working footprint for an activity.

    Guarantees the structural invariant: k sectors -> 2k+1 locations.
    """
    start_sec_id, start_bound_str = activity.start_location_id.rsplit(":", 1)
    end_sec_id, end_bound_str = activity.end_location_id.rsplit(":", 1)

    start_bound = Bound(start_bound_str)
    end_bound = Bound(end_bound_str)

    if start_bound != end_bound:
        raise ValueError(
            f"Activity {activity.activity_id} has mismatched bounds: "
            f"{start_bound} vs {end_bound}"
        )

    # Determine line code from sector ID, e.g. SEC:ALP:S01_S02
    start_sec_parts = start_sec_id.split(":")
    line_code = start_sec_parts[1]
    line_topo = topology.get_line(line_code)

    sectors = line_topo.get_sectors_between(start_sec_id, end_sec_id)
    k = len(sectors)
    stations = line_topo.get_stations_for_sectors(sectors)

    # Generate tunnel locations: SEC:{line}:{from}_{to}:{bound}
    tunnel_locations: list[str] = [f"{sec.sector_id}:{start_bound.value}" for sec in sectors]

    # Generate platform locations: PLAT:{line}:{station}:{bound}
    platform_locations: list[str] = [
        f"PLAT:{line_code}:{stn.station_id}:{start_bound.value}" for stn in stations
    ]

    core_locations = tunnel_locations + platform_locations

    # Strict structural invariant verification
    expected_locations_count = 2 * k + 1
    if len(core_locations) != expected_locations_count:
        raise ValueError(
            f"Core footprint invariant violated for activity {activity.activity_id}: "
            f"traversed {k} sectors but produced {len(core_locations)} locations "
            f"(expected {expected_locations_count})"
        )

    if len(set(core_locations)) != expected_locations_count:
        raise ValueError(
            f"Duplicate locations detected in core footprint for {activity.activity_id}"
        )

    if locations_by_id is not None:
        for loc_id in core_locations:
            if loc_id not in locations_by_id:
                raise KeyError(
                    f"Generated core location {loc_id} does not exist in LocationSupply table"
                )

    return ActivityFootprint(
        activity_id=activity.activity_id,
        line_code=line_code,
        bound=start_bound,
        sectors=sectors,
        stations=stations,
        tunnel_locations=tunnel_locations,
        platform_locations=platform_locations,
        core_locations=core_locations,
    )


def compute_protection_footprint(
    activity: Activity,
    core: ActivityFootprint,
    topology: NetworkTopology,
    buffer_rules: dict[NatureOfWorks, BufferRule] | list[BufferRule],
    contract: Contract,
    locations_by_id: dict[str, LocationSupply] | None = None,
) -> ProtectionFootprint:
    """Computes full safety protection footprint for an activity.

    Handles buffer expansion upstream and downstream along the line,
    opposite-bound mirroring for Live works, and interchange cross-line effects.
    """
    if isinstance(buffer_rules, list):
        rule_map = {r.nature_of_works: r for r in buffer_rules}
    else:
        rule_map = buffer_rules

    rule = rule_map.get(contract.nature_of_activity)
    if rule is None:
        raise KeyError(
            f"No buffer rule defined for nature of activity '{contract.nature_of_activity}'"
        )

    line_topo = topology.get_line(core.line_code)
    n_buffer = rule.up_to_buffer_sectors

    # 1. Buffer expansion
    buffer_sectors: list[Sector] = []
    if n_buffer > 0 and core.sectors:
        upstream = line_topo.get_upstream_sectors(core.sectors[0].sector_id, n_buffer)
        downstream = line_topo.get_downstream_sectors(core.sectors[-1].sector_id, n_buffer)
        buffer_sectors = upstream + downstream

    buffer_tunnel_locations: list[str] = [
        f"{sec.sector_id}:{core.bound.value}" for sec in buffer_sectors
    ]

    core_stn_ids = {s.station_id for s in core.stations}
    buffer_platform_locations: list[str] = []
    if buffer_sectors:
        buffer_stations = [
            stn
            for stn in line_topo.get_stations_for_sectors(buffer_sectors)
            if stn.station_id not in core_stn_ids
        ]
        buffer_platform_locations = [
            f"PLAT:{core.line_code}:{stn.station_id}:{core.bound.value}"
            for stn in buffer_stations
        ]

    buffer_locations = buffer_tunnel_locations + buffer_platform_locations

    # 2. Opposite-bound mirroring
    mirrored_tunnel_locations: list[str] = []
    mirrored_platform_locations: list[str] = []
    if rule.opposite_bound_required:
        opp_bound = core.bound.opposite
        mirrored_tunnel_locations = [
            f"{sec.sector_id}:{opp_bound.value}" for sec in core.sectors
        ]
        mirrored_platform_locations = [
            f"PLAT:{core.line_code}:{stn.station_id}:{opp_bound.value}"
            for stn in core.stations
        ]

    mirrored_locations = mirrored_tunnel_locations + mirrored_platform_locations

    # 3. Interchange cross-line effects
    cross_line_tunnel_locations: list[str] = []
    cross_line_platform_locations: list[str] = []
    if contract.nature_of_activity == NatureOfWorks.LIVE:
        interchange_stns = [s for s in core.stations if topology.is_interchange_station(s.station_id)]
        if interchange_stns:
            # Determine intersecting line(s)
            other_line_codes = [lc for lc in topology.lines if lc != core.line_code]
            for other_line in other_line_codes:
                # Mirror platforms on the other line at the interchange
                for stn in interchange_stns:
                    for b in (Bound.EB, Bound.WB):
                        plat_id = f"PLAT:{other_line}:{stn.station_id}:{b.value}"
                        if locations_by_id is None or plat_id in locations_by_id:
                            cross_line_platform_locations.append(plat_id)

                # Check if core spans the interchange sector (e.g. H01_H02)
                interchange_sector_found = any(
                    "H01_H02" in sec.sector_id for sec in core.sectors
                )
                if interchange_sector_found:
                    for b in (Bound.EB, Bound.WB):
                        sec_id = f"SEC:{other_line}:H01_H02:{b.value}"
                        if locations_by_id is None or sec_id in locations_by_id:
                            cross_line_tunnel_locations.append(sec_id)

    cross_line_locations = cross_line_tunnel_locations + cross_line_platform_locations

    # Filter against known locations if provided
    if locations_by_id is not None:
        buffer_locations = [loc for loc in buffer_locations if loc in locations_by_id]
        mirrored_locations = [loc for loc in mirrored_locations if loc in locations_by_id]
        cross_line_locations = [loc for loc in cross_line_locations if loc in locations_by_id]

    # Combine all locations while preserving order and uniqueness
    all_protected: list[str] = []
    seen: set[str] = set()
    for loc_id in (
        core.core_locations
        + buffer_locations
        + mirrored_locations
        + cross_line_locations
    ):
        if loc_id not in seen:
            seen.add(loc_id)
            all_protected.append(loc_id)

    return ProtectionFootprint(
        activity_id=activity.activity_id,
        core=core,
        buffer_sectors=buffer_sectors,
        buffer_tunnel_locations=buffer_tunnel_locations,
        buffer_platform_locations=buffer_platform_locations,
        buffer_locations=buffer_locations,
        mirrored_tunnel_locations=mirrored_tunnel_locations,
        mirrored_platform_locations=mirrored_platform_locations,
        mirrored_locations=mirrored_locations,
        cross_line_tunnel_locations=cross_line_tunnel_locations,
        cross_line_platform_locations=cross_line_platform_locations,
        cross_line_locations=cross_line_locations,
        all_protected_locations=all_protected,
    )


class FootprintCache:
    """Pre-computes and provides fast lookup for activity footprints."""

    def __init__(
        self,
        problem: ProblemInstance,
        topology: NetworkTopology | None = None,
    ) -> None:
        self.problem = problem
        self.topology = topology or NetworkTopology.from_problem(problem)
        self._core_footprints: dict[str, ActivityFootprint] = {}
        self._protection_footprints: dict[str, ProtectionFootprint] = {}
        self._precompute()

    def _precompute(self) -> None:
        for act in self.problem.activities:
            core = compute_core_footprint(
                act, self.topology, self.problem._locations_by_id
            )
            self._core_footprints[act.activity_id] = core
            contract = self.problem.contract(act.contract_number)
            prot = compute_protection_footprint(
                act,
                core,
                self.topology,
                self.problem._buffer_by_nature,
                contract,
                self.problem._locations_by_id,
            )
            self._protection_footprints[act.activity_id] = prot

    def get_core_footprint(self, activity_id: str) -> ActivityFootprint:
        """Retrieve precomputed core footprint for an activity."""
        if activity_id not in self._core_footprints:
            raise KeyError(f"Activity {activity_id} not found in footprint cache")
        return self._core_footprints[activity_id]

    def get_protection_footprint(self, activity_id: str) -> ProtectionFootprint:
        """Retrieve precomputed protection footprint for an activity."""
        if activity_id not in self._protection_footprints:
            raise KeyError(f"Activity {activity_id} not found in footprint cache")
        return self._protection_footprints[activity_id]

    @property
    def core_footprints(self) -> dict[str, ActivityFootprint]:
        """All precomputed core footprints keyed by activity ID."""
        return dict(self._core_footprints)

    @property
    def protection_footprints(self) -> dict[str, ProtectionFootprint]:
        """All precomputed protection footprints keyed by activity ID."""
        return dict(self._protection_footprints)
