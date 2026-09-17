"""PS1 Ingestion, relational integrity validation, and export serialization.

Provides:
- Dual ingestion pipelines (directory and memory streams)
- Comprehensive relational integrity validation (PK, FK, semantic invariants, DFS cycle detection, horizon bounds)
- Strict CSV export serializers for official PS1 output formats
"""
from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path
from typing import IO, Any

from backend.app.domain_models import (
    AccessScheduleRow,
    Activity,
    BufferRule,
    Contract,
    Line,
    LocationSupply,
    OccupancyScheduleRow,
    PlanningParameters,
    ProblemInstance,
    ScenarioResultRow,
    Sector,
    Station,
)


# ============================================================================
# Exceptions
# ============================================================================


class DataLayerError(Exception):
    """Base exception for PS1 data layer errors."""

    pass


class RelationalIntegrityError(DataLayerError):
    """Raised when primary key, foreign key, or cross-table relational integrity is violated."""

    pass


class PredecessorCycleError(DataLayerError):
    """Raised when circular dependencies are detected in the activity DAG."""

    pass


class HorizonBoundError(DataLayerError):
    """Raised when planning horizon rules or date boundaries are violated."""

    pass


# ============================================================================
# Relational Integrity Validation
# ============================================================================


def validate_problem_instance(problem: ProblemInstance) -> None:
    """Validates relational integrity, foreign keys, semantic rules, cycles, and horizon bounds."""
    # 1. Primary Key Uniqueness
    _check_unique_pk(problem.lines, lambda l: l.line_code, "Line", "line_code")
    _check_unique_pk(
        problem.stations, lambda s: (s.line_code, s.station_id), "Station", "(line_code, station_id)"
    )
    _check_unique_pk(problem.sectors, lambda s: s.sector_id, "Sector", "sector_id")
    _check_unique_pk(problem.locations, lambda l: l.location_id, "LocationSupply", "location_id")
    _check_unique_pk(
        problem.buffer_rules, lambda b: b.nature_of_works, "BufferRule", "nature_of_works"
    )
    _check_unique_pk(problem.contracts, lambda c: c.contract_number, "Contract", "contract_number")
    _check_unique_pk(problem.activities, lambda a: a.activity_id, "Activity", "activity_id")

    lines_by_code = problem._lines_by_code
    stations_by_key = problem._stations_by_key
    sectors_by_id = problem._sectors_by_id
    locations_by_id = problem._locations_by_id
    contracts_by_number = problem._contracts_by_number
    activities_by_id = problem._activities_by_id
    buffer_by_nature = problem._buffer_by_nature

    # 2. Foreign Key Integrity
    # Station -> Line
    for stn in problem.stations:
        if stn.line_code not in lines_by_code:
            raise RelationalIntegrityError(
                f"Station '{stn.station_id}' references non-existent line '{stn.line_code}'"
            )

    # Sector -> Line & Stations
    for sec in problem.sectors:
        if sec.line_code not in lines_by_code:
            raise RelationalIntegrityError(
                f"Sector '{sec.sector_id}' references non-existent line '{sec.line_code}'"
            )
        from_key = (sec.line_code, sec.from_station_id)
        if from_key not in stations_by_key:
            raise RelationalIntegrityError(
                f"Sector '{sec.sector_id}' references non-existent from_station '{sec.from_station_id}' on line '{sec.line_code}'"
            )
        to_key = (sec.line_code, sec.to_station_id)
        if to_key not in stations_by_key:
            raise RelationalIntegrityError(
                f"Sector '{sec.sector_id}' references non-existent to_station '{sec.to_station_id}' on line '{sec.line_code}'"
            )

    # LocationSupply -> Line
    for loc in problem.locations:
        if loc.line_code not in lines_by_code:
            raise RelationalIntegrityError(
                f"Location '{loc.location_id}' references non-existent line '{loc.line_code}'"
            )

    # Contract -> BufferRule
    for c in problem.contracts:
        if c.nature_of_activity not in buffer_by_nature:
            raise RelationalIntegrityError(
                f"Contract '{c.contract_number}' references undefined nature_of_activity '{c.nature_of_activity}'"
            )

    # Activity -> Contract & LocationSupply
    for act in problem.activities:
        if act.contract_number not in contracts_by_number:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' references non-existent contract '{act.contract_number}'"
            )
        if act.start_location_id not in locations_by_id:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' references non-existent start_location_id '{act.start_location_id}'"
            )
        if act.end_location_id not in locations_by_id:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' references non-existent end_location_id '{act.end_location_id}'"
            )

        # Predecessor existence & intra-contract check
        if act.predecessor_activity_id is not None:
            if act.predecessor_activity_id not in activities_by_id:
                raise RelationalIntegrityError(
                    f"Activity '{act.activity_id}' references non-existent predecessor '{act.predecessor_activity_id}'"
                )
            pred = activities_by_id[act.predecessor_activity_id]
            if pred.contract_number != act.contract_number:
                raise RelationalIntegrityError(
                    f"Predecessor '{pred.activity_id}' belongs to contract '{pred.contract_number}', "
                    f"violating intra-contract dependency for activity '{act.activity_id}' in contract '{act.contract_number}'"
                )

    # 3. Cross-Table Semantic Invariants
    for act in problem.activities:
        contract = contracts_by_number[act.contract_number]
        # Activity type match
        if act.activity_type != contract.activity_type:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' activity_type '{act.activity_type}' does not match "
                f"contract '{contract.contract_number}' activity_type '{contract.activity_type}'"
            )

        start_loc = locations_by_id[act.start_location_id]
        end_loc = locations_by_id[act.end_location_id]

        # Line and Bound consistency
        if start_loc.line_code != end_loc.line_code:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' start location line '{start_loc.line_code}' "
                f"does not match end location line '{end_loc.line_code}'"
            )
        if start_loc.bound != end_loc.bound:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' start location bound '{start_loc.bound}' "
                f"does not match end location bound '{end_loc.bound}'"
            )

        # Spatial directionality check: start sector seq <= end sector seq
        start_sec_id = act.start_location_id.rsplit(":", 1)[0]
        end_sec_id = act.end_location_id.rsplit(":", 1)[0]

        if start_sec_id not in sectors_by_id:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' start sector '{start_sec_id}' not found in sectors"
            )
        if end_sec_id not in sectors_by_id:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' end sector '{end_sec_id}' not found in sectors"
            )

        start_sec = sectors_by_id[start_sec_id]
        end_sec = sectors_by_id[end_sec_id]
        if start_sec.seq > end_sec.seq:
            raise RelationalIntegrityError(
                f"Activity '{act.activity_id}' has reversed spatial direction: start sector "
                f"'{start_sec.sector_id}' (seq {start_sec.seq}) > end sector '{end_sec.sector_id}' (seq {end_sec.seq})"
            )

    # 4. Predecessor Cycle Detection (DFS)
    _detect_predecessor_cycles(problem.activities)

    # 5. Horizon Bounds
    params = problem.parameters
    if params.horizon_weeks <= 0:
        raise HorizonBoundError(f"horizon_weeks must be positive, got {params.horizon_weeks}")

    # horizon_start must be a Monday (ISO weekday 1)
    if params.horizon_start.isoweekday() != 1:
        raise HorizonBoundError(
            f"horizon_start must be a Monday (ISO weekday 1), got {params.horizon_start} "
            f"(ISO weekday {params.horizon_start.isoweekday()})"
        )

    h_start = params.horizon_start
    h_end = params.horizon_end

    for act in problem.activities:
        if not (h_start <= act.planned_start_date <= h_end):
            raise HorizonBoundError(
                f"Activity '{act.activity_id}' planned_start_date {act.planned_start_date} "
                f"is outside planning horizon [{h_start}, {h_end}]"
            )

    for c in problem.contracts:
        if c.contract_award_date > c.contract_completion_date:
            raise HorizonBoundError(
                f"Contract '{c.contract_number}' award date {c.contract_award_date} "
                f"is after completion date {c.contract_completion_date}"
            )
        if c.planned_completion_date > c.contract_completion_date:
            raise HorizonBoundError(
                f"Contract '{c.contract_number}' planned completion {c.planned_completion_date} "
                f"is after contract completion {c.contract_completion_date}"
            )


def _check_unique_pk(items: list[Any], key_fn: Any, entity_name: str, pk_name: str) -> None:
    seen: set[Any] = set()
    for item in items:
        k = key_fn(item)
        if k in seen:
            raise RelationalIntegrityError(f"Duplicate {entity_name} primary key {pk_name}='{k}'")
        seen.add(k)


def _detect_predecessor_cycles(activities: list[Activity]) -> None:
    """Detects circular dependencies in activities using DFS (white/gray/black)."""
    # Graph edges: predecessor -> successor (or act -> pred)
    # We trace dependencies: act depends on pred
    graph: dict[str, list[str]] = {a.activity_id: [] for a in activities}
    for a in activities:
        if a.predecessor_activity_id:
            graph[a.activity_id].append(a.predecessor_activity_id)

    # 0 = WHITE (unvisited), 1 = GRAY (visiting), 2 = BLACK (visited)
    state: dict[str, int] = {aid: 0 for aid in graph}
    path: list[str] = []

    def dfs(node: str) -> None:
        state[node] = 1
        path.append(node)
        for neighbor in graph.get(node, []):
            if state.get(neighbor) == 1:
                # Cycle detected
                cycle_start_idx = path.index(neighbor)
                cycle = path[cycle_start_idx:] + [neighbor]
                cycle_str = " -> ".join(cycle)
                raise PredecessorCycleError(
                    f"Circular dependency detected in activity predecessor graph: {cycle_str}"
                )
            elif state.get(neighbor) == 0:
                dfs(neighbor)
        path.pop()
        state[node] = 2

    for aid in graph:
        if state[aid] == 0:
            dfs(aid)


# ============================================================================
# Ingestion Pipelines
# ============================================================================


def _normalize_stream_key(key: str) -> str:
    """Normalizes input filename / key to canonical table identifier."""
    stem = Path(key).stem.lower().strip()
    if "01" in stem or "line" in stem:
        return "lines"
    if "02" in stem or "station" in stem:
        return "stations"
    if "03" in stem or "sector" in stem:
        return "sectors"
    if "05" in stem or "buffer" in stem:
        return "buffer_rules"
    if "04" in stem or "supply" in stem or "location" in stem:
        return "locations"
    if "06" in stem or "param" in stem:
        return "parameters"
    if "07" in stem or "contract" in stem or "project" in stem:
        return "contracts"
    if "08" in stem or "activit" in stem:
        return "activities"
    return stem


def _read_csv_rows(content: IO[str] | str) -> list[dict[str, str]]:
    """Parses text or stream into list of trimmed string dicts."""
    if isinstance(content, str):
        stream = io.StringIO(content)
    else:
        stream = content
    reader = csv.DictReader(stream)
    rows: list[dict[str, str]] = []
    for r in reader:
        rows.append({k.strip(): (v.strip() if v is not None else "") for k, v in r.items() if k})
    return rows


def load_problem_from_streams(
    streams: dict[str, IO[str] | str],
    validate: bool = True,
) -> ProblemInstance:
    """Loads a ProblemInstance from in-memory CSV text strings or file-like streams."""
    norm_streams: dict[str, IO[str] | str] = {}
    for k, v in streams.items():
        norm_streams[_normalize_stream_key(k)] = v

    required_keys = {
        "lines",
        "stations",
        "sectors",
        "locations",
        "buffer_rules",
        "parameters",
        "contracts",
        "activities",
    }
    missing = required_keys - set(norm_streams.keys())
    if missing:
        raise DataLayerError(f"Missing required input tables: {missing}")

    # 1. Lines
    lines = [Line.model_validate(r) for r in _read_csv_rows(norm_streams["lines"])]

    # 2. Stations
    stations = [Station.model_validate(r) for r in _read_csv_rows(norm_streams["stations"])]

    # 3. Sectors
    sectors = [Sector.model_validate(r) for r in _read_csv_rows(norm_streams["sectors"])]

    # 4. LocationSupply
    locations = [LocationSupply.model_validate(r) for r in _read_csv_rows(norm_streams["locations"])]

    # 5. BufferRule
    buffer_rules = [BufferRule.model_validate(r) for r in _read_csv_rows(norm_streams["buffer_rules"])]

    # 6. PlanningParameters (key,value table)
    param_rows = _read_csv_rows(norm_streams["parameters"])
    param_dict: dict[str, str] = {}
    for r in param_rows:
        k = r.get("key") or r.get("Key")
        v = r.get("value") or r.get("Value")
        if k and v:
            param_dict[k.strip()] = v.strip()

    if "horizon_start" not in param_dict or "horizon_weeks" not in param_dict:
        raise DataLayerError(
            f"Parameters CSV missing horizon_start or horizon_weeks, found: {list(param_dict.keys())}"
        )

    parameters = PlanningParameters(
        horizon_start=date.fromisoformat(param_dict["horizon_start"]),
        horizon_weeks=int(param_dict["horizon_weeks"]),
    )

    # 7. Contracts
    contracts = [Contract.model_validate(r) for r in _read_csv_rows(norm_streams["contracts"])]

    # 8. Activities
    activities = [Activity.model_validate(r) for r in _read_csv_rows(norm_streams["activities"])]

    problem = ProblemInstance(
        lines=lines,
        stations=stations,
        sectors=sectors,
        locations=locations,
        buffer_rules=buffer_rules,
        parameters=parameters,
        contracts=contracts,
        activities=activities,
    )

    if validate:
        validate_problem_instance(problem)

    return problem


def load_problem_from_directory(
    path: Path | str,
    validate: bool = True,
) -> ProblemInstance:
    """Loads and validates ProblemInstance from directory containing the 8 official PS1 CSVs."""
    dir_path = Path(path)
    if not dir_path.is_dir():
        raise DataLayerError(f"Directory does not exist: {path}")

    streams: dict[str, str] = {}
    for file in dir_path.glob("*.csv"):
        streams[file.name] = file.read_text(encoding="utf-8")

    return load_problem_from_streams(streams, validate=validate)


# ============================================================================
# Export Serialization
# ============================================================================


def export_access_schedule(rows: list[AccessScheduleRow]) -> str:
    """Exports AccessScheduleRow objects to exact SCHEDULE_ACCESS.csv string."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["activity_id", "access_seq", "week", "eclo", "access_night"])
    for r in rows:
        writer.writerow([r.activity_id, r.access_seq, r.week, 1 if r.eclo else 0, r.access_night])
    return buf.getvalue()


def export_occupancy_schedule(rows: list[OccupancyScheduleRow]) -> str:
    """Exports OccupancyScheduleRow objects to exact SCHEDULE_OCCUPANCY.csv string."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["activity_id", "week", "location_id", "co_share_group"])
    for r in rows:
        writer.writerow([r.activity_id, r.week, r.location_id, r.co_share_group])
    return buf.getvalue()


def export_results(rows: list[ScenarioResultRow]) -> str:
    """Exports ScenarioResultRow objects to exact RESULTS.csv string."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["scenario", "contract_number", "simulated_completion_date", "overrun_days"])
    for r in rows:
        writer.writerow([
            r.scenario,
            r.contract_number,
            r.simulated_completion_date.isoformat(),
            r.overrun_days,
        ])
    return buf.getvalue()


def export_bundle(
    access: list[AccessScheduleRow],
    occupancy: list[OccupancyScheduleRow],
    results: list[ScenarioResultRow],
    output_dir: Path | str,
) -> dict[str, Path]:
    """Writes all 3 official output CSVs to output_dir and returns mapping of output paths."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    access_path = out_dir / "SCHEDULE_ACCESS.csv"
    occupancy_path = out_dir / "SCHEDULE_OCCUPANCY.csv"
    results_path = out_dir / "RESULTS.csv"

    access_path.write_text(export_access_schedule(access), encoding="utf-8")
    occupancy_path.write_text(export_occupancy_schedule(occupancy), encoding="utf-8")
    results_path.write_text(export_results(results), encoding="utf-8")

    return {
        "access": access_path,
        "occupancy": occupancy_path,
        "results": results_path,
    }
