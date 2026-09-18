"""CSV parsing and domain model ingestion layer for NEBULA X (PS1)."""

import csv
from typing import Optional
from pydantic import BaseModel


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
    description: str
    award_date: str
    activity_type: str
    nature_of_works: str
    contract_priority: int
    contractual_completion_date: str
    planned_completion_date: str
    workfronts: int
    access_type: str
    weekly_maximum: int


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
            seq=int(r.get("seq", 0)),
            is_interchange=int(r.get("is_interchange", 0)),
        )
        for r in rows
    ]


def parse_sectors_csv(content: str) -> list[SectorInput]:
    rows = _read_csv_rows(content)
    return [
        SectorInput(
            sector_id=r.get("sector_id", "").strip(),
            line_code=r.get("line_code", "").strip(),
            # Safely handle header variants: 'from_station' vs 'from_station_id' vs 'start_station'
            from_station=(r.get("from_station") or r.get("from_station_id") or r.get("start_station") or "").strip(),
            to_station=(r.get("to_station") or r.get("to_station_id") or r.get("end_station") or "").strip(),
            seq=int(r.get("seq", 0)),
            is_shared=int(r.get("is_shared", 0)),
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
            supply_capacity=int(r.get("supply_capacity", 0)),
        )
        for r in rows
    ]


def parse_buffer_location_csv(content: str) -> list[BufferLocationInput]:
    rows = _read_csv_rows(content)
    return [
        BufferLocationInput(
            nature_of_works=r.get("nature_of_works", "").strip(),
            up_to_buffer_sectors=int(r.get("up_to_buffer_sectors", 0)),
            opposite_bound_required=int(r.get("opposite_bound_required", 0)),
        )
        for r in rows
    ]


def parse_project_details_csv(content: str) -> list[ProjectDetailsInput]:
    rows = _read_csv_rows(content)
    return [
        ProjectDetailsInput(
            contract_number=r.get("contract_number", "").strip(),
            description=r.get("description", "").strip(),
            award_date=r.get("award_date", "").strip(),
            activity_type=r.get("activity_type", "").strip(),
            nature_of_works=r.get("nature_of_works", "").strip(),
            contract_priority=int(r.get("contract_priority", 0)),
            contractual_completion_date=r.get("contractual_completion_date", "").strip(),
            planned_completion_date=r.get("planned_completion_date", "").strip(),
            workfronts=int(r.get("workfronts", 0)),
            access_type=r.get("access_type", "").strip(),
            weekly_maximum=int(r.get("weekly_maximum", 0)),
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
                total_accesses=int(r.get("total_accesses", 0)),
                planned_start_week=int(r.get("planned_start_week", 0)),
                predecessor_activity_id=pred_val if pred_val and pred_val.lower() != "none" else None,
                activity_priority=int(r.get("activity_priority", 0)),
            )
        )
    return activities


def _read_csv_rows(content: str) -> list[dict]:
    """Helper to parse raw CSV content, automatically stripping spaces from header keys."""
    reader = csv.DictReader(content.splitlines())
    rows = []
    for row in reader:
        # Clean both keys and values of any stray whitespace
        cleaned_row = {
            (k.strip() if k else ""): (v.strip() if v else "")
            for k, v in row.items()
        }
        rows.append(cleaned_row)
    return rows