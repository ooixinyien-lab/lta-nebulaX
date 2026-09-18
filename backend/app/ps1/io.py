"""CSV parsing and domain model ingestion layer for NEBULA X (PS1)."""

import csv
from typing import Dict, List, Optional
from pydantic import BaseModel


class DataLayerError(Exception):
    """Custom exception raised when CSV parsing fails."""
    pass


# --- Ingestion Data Classes ---

class LineInput(BaseModel):
    line_code: str
    line_name: str


class StationInput(BaseModel):
    line_code: str
    station_id: str
    seq: int
    is_interchange: int


class SectorInput(BaseModel):
    sector_id: str
    line_code: str
    from_station: str
    to_station: str
    seq: int
    is_shared: int


class LocationSupplyInput(BaseModel):
    location_id: str
    location_kind: str
    line_code: str
    bound: str
    supply_capacity: int


class BufferLocationInput(BaseModel):
    nature_of_works: str
    up_to_buffer_sectors: int
    opposite_bound_required: int


class ProjectDetailsInput(BaseModel):
    contract_number: str
    contract_description: str
    contract_award_date: str
    activity_type: str
    nature_of_works: str
    contract_priority: int
    contractual_completion_date: str
    planned_completion_date: str
    number_of_workfronts: int
    access_type: str
    number_of_maximum_access_per_week: int


class ActivityDetailsInput(BaseModel):
    activity_id: str
    contract_number: str
    activity_type: str
    start_location: str
    end_location: str
    total_accesses: int
    planned_start_week: int
    predecessor_activity_id: Optional[str] = None
    activity_priority: int


class ProblemInstance(BaseModel):
    """Aggregated container for all 8 official PS1 domain inputs."""
    lines: List[LineInput]
    stations: List[StationInput]
    sectors: List[SectorInput]
    supplies: List[LocationSupplyInput]
    buffers: List[BufferLocationInput]
    projects: List[ProjectDetailsInput]
    activities: List[ActivityDetailsInput]


# --- Defensive Type Helpers ---

def _to_int(val: str, default: int = 0) -> int:
    """Safely coerces a string cell to int, falling back to default on empty or invalid inputs."""
    if not val:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


# --- Ingestion Parsers ---

def parse_lines_csv(content: str) -> list[LineInput]:
    rows = _read_csv_rows(content)
    return [
        LineInput(
            line_code=r.get("line_code", "").strip(),
            line_name=r.get("line_name", "").strip(),
        )
        for r in rows
    ]


def parse_stations_csv(content: str) -> list[StationInput]:
    rows = _read_csv_rows(content)
    return [
        StationInput(
            line_code=r.get("line_code", "").strip(),
            station_id=r.get("station_id", "").strip(),
            seq=_to_int(r.get("seq")),
            is_interchange=_to_int(r.get("is_interchange")),
        )
        for r in rows
    ]


def parse_sectors_csv(content: str) -> list[SectorInput]:
    rows = _read_csv_rows(content)
    return [
        SectorInput(
            sector_id=r.get("sector_id", "").strip(),
            line_code=r.get("line_code", "").strip(),
            from_station=(r.get("from_station") or r.get("from_station_id") or r.get("start_station") or "").strip(),
            to_station=(r.get("to_station") or r.get("to_station_id") or r.get("end_station") or "").strip(),
            seq=_to_int(r.get("seq")),
            is_shared=_to_int(r.get("is_shared")),
        )
        for r in rows
    ]


def parse_location_supply_csv(content: str) -> list[LocationSupplyInput]:
    rows = _read_csv_rows(content)
    return [
        LocationSupplyInput(
            location_id=r.get("location_id", "").strip(),
            location_kind=r.get("location_kind", "").strip(),
            line_code=r.get("line_code", "").strip(),
            bound=r.get("bound", "").strip(),
            supply_capacity=_to_int(r.get("supply_capacity")),
        )
        for r in rows
    ]


def parse_buffer_location_csv(content: str) -> list[BufferLocationInput]:
    rows = _read_csv_rows(content)
    return [
        BufferLocationInput(
            nature_of_works=r.get("nature_of_works", "").strip(),
            up_to_buffer_sectors=_to_int(r.get("up_to_buffer_sectors")),
            opposite_bound_required=_to_int(r.get("opposite_bound_required")),
        )
        for r in rows
    ]


def parse_project_details_csv(content: str) -> list[ProjectDetailsInput]:
    rows = _read_csv_rows(content)
    return [
        ProjectDetailsInput(
            contract_number=r.get("contract_number", "").strip(),
            contract_description=(r.get("contract_description") or r.get("description") or "").strip(),
            contract_award_date=(r.get("contract_award_date") or r.get("award_date") or "").strip(),
            activity_type=r.get("activity_type", "").strip(),
            nature_of_works=r.get("nature_of_works", "").strip(),
            contract_priority=_to_int(r.get("contract_priority")),
            contractual_completion_date=(r.get("contractual_completion_date") or r.get("contract_completion_date") or "").strip(),
            planned_completion_date=r.get("planned_completion_date", "").strip(),
            number_of_workfronts=_to_int(r.get("number_of_workfronts") or r.get("workfronts")),
            access_type=r.get("access_type", "").strip(),
            number_of_maximum_access_per_week=_to_int(r.get("number_of_maximum_access_per_week") or r.get("weekly_maximum")),
        )
        for r in rows
    ]


def parse_activity_details_csv(content: str) -> list[ActivityDetailsInput]:
    rows = _read_csv_rows(content)
    activities = []
    for r in rows:
        pred_val = (r.get("predecessor_activity_id") or r.get("predecessor_id") or "").strip()
        activities.append(
            ActivityDetailsInput(
                activity_id=r.get("activity_id", "").strip(),
                contract_number=r.get("contract_number", "").strip(),
                activity_type=r.get("activity_type", "").strip(),
                start_location=r.get("start_location", "").strip(),
                end_location=r.get("end_location", "").strip(),
                total_accesses=_to_int(r.get("total_accesses")),
                planned_start_week=_to_int(r.get("planned_start_week")),
                predecessor_activity_id=pred_val if pred_val and pred_val.lower() != "none" else None,
                activity_priority=_to_int(r.get("activity_priority")),
            )
        )
    return activities


def load_problem_from_streams(streams: Dict[str, str]) -> ProblemInstance:
    """Parses text content from the 8 official CSV streams into a complete ProblemInstance."""
    try:
        return ProblemInstance(
            lines=parse_lines_csv(streams.get("01_LINES.csv", "")),
            stations=parse_stations_csv(streams.get("02_STATIONS.csv", "")),
            sectors=parse_sectors_csv(streams.get("03_SECTORS.csv", "")),
            supplies=parse_location_supply_csv(streams.get("04_LOCATION_SUPPLY.csv", "")),
            buffers=parse_buffer_location_csv(streams.get("05_BUFFER_LOCATION.csv", "")),
            projects=parse_project_details_csv(streams.get("07_PROJECT_DETAILS.csv", "")),
            activities=parse_activity_details_csv(streams.get("08_ACTIVITY_DETAILS.csv", "")),
        )
    except Exception as exc:
        raise DataLayerError(f"Failed to parse CSV streams into ProblemInstance: {exc}") from exc


def parse_ps1_csv_bundle(file_bytes_map: Dict[str, bytes]) -> ProblemInstance:
    """Accepts bytes dict (filename -> raw_bytes), decodes utf-8-sig, and returns ProblemInstance."""
    streams = {
        filename: content.decode("utf-8-sig")
        for filename, content in file_bytes_map.items()
    }
    return load_problem_from_streams(streams)


def _read_csv_rows(content: str) -> list[dict]:
    """Helper to parse raw CSV content, automatically stripping spaces and BOM from header keys."""
    if not content or not content.strip():
        return []
    reader = csv.DictReader(content.splitlines())
    rows = []
    for row in reader:
        cleaned_row = {
            (k.strip().lstrip("\ufeff") if k else ""): (v.strip() if v else "")
            for k, v in row.items()
        }
        rows.append(cleaned_row)
    return rows