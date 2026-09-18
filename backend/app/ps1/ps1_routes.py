"""FastAPI endpoints for CSV ingestion, network topology, and CP-SAT solver execution for NEBULA X (PS1)."""
import sys
from pathlib import Path

# Add the 'backend' root directory to Python's module search path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Dict, List, Optional
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from .io import (
    parse_activity_details_csv,
    parse_buffer_location_csv,
    parse_lines_csv,
    parse_location_supply_csv,
    parse_project_details_csv,
    parse_ps1_csv_bundle,
    parse_sectors_csv,
    parse_stations_csv,
)
from .solver import solve_ps1_scenario

router = APIRouter(prefix="/api/ps1", tags=["PS1 Data Ingestion, Topology & Solver Pipeline"])

REQUIRED_FILES = [
    "01_LINES.csv",
    "02_STATIONS.csv",
    "03_SECTORS.csv",
    "04_LOCATION_SUPPLY.csv",
    "05_BUFFER_LOCATION.csv",
    "06_PARAMETERS.csv",
    "07_PROJECT_DETAILS.csv",
    "08_ACTIVITY_DETAILS.csv",
]


# --- Response Schemas ---

class UploadSummaryResponse(BaseModel):
    status: str
    message: str
    counts: Dict[str, int]
    sample_projects: list[dict]
    sample_activities: list[dict]


class StationTopologyOut(BaseModel):
    station_id: str
    line_code: str
    seq: int
    is_interchange: int


class SectorTopologyOut(BaseModel):
    sector_id: str
    line_code: str
    from_station: str
    to_station: str
    seq: int


class LineTopologyOut(BaseModel):
    line_code: str
    line_name: str
    stations: List[StationTopologyOut]
    sectors: List[SectorTopologyOut]


class NetworkTopologyResponse(BaseModel):
    status: str
    lines: List[LineTopologyOut]
    interchange_station_ids: List[str]


class ScheduleDisplayResponse(BaseModel):
    status: str
    scenario: str
    counts: Dict[str, int]
    sample_sectors: List[dict]
    sample_activities: List[dict]
    results: List[dict]


# --- Ingestion & Topology Endpoints ---

@router.post("/upload", response_model=UploadSummaryResponse)
async def upload_csv_bundle(files: list[UploadFile] = File(...)):
    """Ingests the 8 official CSV files and parses them into validated Pydantic domain models."""
    file_map = {f.filename: f for f in files}
    missing_files = [req for req in REQUIRED_FILES if req not in file_map]

    if missing_files:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required CSV file(s): {', '.join(missing_files)}",
        )

    try:
        lines = parse_lines_csv((await file_map["01_LINES.csv"].read()).decode("utf-8-sig"))
        stations = parse_stations_csv((await file_map["02_STATIONS.csv"].read()).decode("utf-8-sig"))
        sectors = parse_sectors_csv((await file_map["03_SECTORS.csv"].read()).decode("utf-8-sig"))
        supplies = parse_location_supply_csv((await file_map["04_LOCATION_SUPPLY.csv"].read()).decode("utf-8-sig"))
        buffers = parse_buffer_location_csv((await file_map["05_BUFFER_LOCATION.csv"].read()).decode("utf-8-sig"))
        projects = parse_project_details_csv((await file_map["07_PROJECT_DETAILS.csv"].read()).decode("utf-8-sig"))
        activities = parse_activity_details_csv((await file_map["08_ACTIVITY_DETAILS.csv"].read()).decode("utf-8-sig"))

    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse CSV inputs into data classes: {str(e)}",
        )

    return UploadSummaryResponse(
        status="SUCCESS",
        message="All 8 CSV files successfully parsed into domain data classes.",
        counts={
            "lines": len(lines),
            "stations": len(stations),
            "sectors": len(sectors),
            "location_supplies": len(supplies),
            "buffer_rules": len(buffers),
            "projects": len(projects),
            "activities": len(activities),
        },
        sample_projects=[p.model_dump() for p in projects[:3]],
        sample_activities=[a.model_dump() for a in activities[:3]],
    )


@router.post("/topology", response_model=NetworkTopologyResponse)
async def extract_network_topology(files: list[UploadFile] = File(...)):
    """Extracts line, station, sector, and interchange topology for UI network mapping."""
    file_map = {f.filename: f for f in files}
    missing_files = [req for req in ["01_LINES.csv", "02_STATIONS.csv", "03_SECTORS.csv"] if req not in file_map]

    if missing_files:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required topology CSV file(s): {', '.join(missing_files)}",
        )

    try:
        lines = parse_lines_csv((await file_map["01_LINES.csv"].read()).decode("utf-8-sig"))
        stations = parse_stations_csv((await file_map["02_STATIONS.csv"].read()).decode("utf-8-sig"))
        sectors = parse_sectors_csv((await file_map["03_SECTORS.csv"].read()).decode("utf-8-sig"))

        stations_by_line: Dict[str, List[StationTopologyOut]] = {}
        for stn in stations:
            stations_by_line.setdefault(stn.line_code, []).append(
                StationTopologyOut(
                    station_id=stn.station_id,
                    line_code=stn.line_code,
                    seq=stn.seq,
                    is_interchange=stn.is_interchange,
                )
            )

        sectors_by_line: Dict[str, List[SectorTopologyOut]] = {}
        for sec in sectors:
            sectors_by_line.setdefault(sec.line_code, []).append(
                SectorTopologyOut(
                    sector_id=sec.sector_id,
                    line_code=sec.line_code,
                    from_station=sec.from_station,
                    to_station=sec.to_station,
                    seq=sec.seq,
                )
            )

        lines_payload = []
        for line in lines:
            line_stns = sorted(stations_by_line.get(line.line_code, []), key=lambda s: s.seq)
            line_secs = sorted(sectors_by_line.get(line.line_code, []), key=lambda s: s.seq)
            lines_payload.append(
                LineTopologyOut(
                    line_code=line.line_code,
                    line_name=line.line_name,
                    stations=line_stns,
                    sectors=line_secs,
                )
            )

        interchange_ids = list({stn.station_id for stn in stations if stn.is_interchange == 1})

        return NetworkTopologyResponse(
            status="SUCCESS",
            lines=lines_payload,
            interchange_station_ids=interchange_ids,
        )

    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract network topology: {str(e)}",
        )


# --- Solver Execution Endpoints for React Dispatch Board ---

@router.post("/run-solver", response_model=ScheduleDisplayResponse)
async def run_solver_pipeline(
    scenario: str = Query("A", regex="^[ABC]$"),
    files: List[UploadFile] = File(...),
):
    """
    Ingests 8 uploaded CSV files, executes CP-SAT solver for Scenario A/B/C,
    and returns schedule output formatted for ScheduleDashboard.jsx.
    """
    if len(files) < 8:
        raise HTTPException(
            status_code=400,
            detail=f"Expected 8 official CSV files, but received {len(files)}.",
        )

    file_bytes_map = {}
    for file in files:
        content = await file.read()
        file_bytes_map[file.filename] = content

    try:
        # Pass raw file bytes directly to io.py bundle parser
        problem_instance = parse_ps1_csv_bundle(file_bytes_map)
        solver_result = solve_ps1_scenario(problem_instance, scenario=scenario)

        if not solver_result or solver_result.status not in ["OPTIMAL", "FEASIBLE"]:
            raise HTTPException(
                status_code=422,
                detail=f"Solver failed to find a feasible solution for Scenario {scenario}.",
            )

        access_df = pd.DataFrame([row.model_dump() for row in solver_result.schedule_access])
        occupancy_df = pd.DataFrame([row.model_dump() for row in solver_result.schedule_occupancy])
        results_df = pd.DataFrame([row.model_dump() for row in solver_result.results])

        merged = pd.merge(occupancy_df, access_df, on=["activity_id", "week"], how="left")

        sample_sectors = [
            {"sector_id": loc_id, "line_code": str(loc_id).split(":")[1] if ":" in str(loc_id) else "BET"}
            for loc_id in sorted(merged["location_id"].dropna().unique())
        ]

        sample_activities = []
        grouped = merged.groupby(["activity_id", "week", "location_id"]).first().reset_index()

        for _, row in grouped.iterrows():
            sample_activities.append({
                "activity_id": str(row["activity_id"]),
                "contract_number": str(row.get("contract_number", "C001")),
                "start_location": str(row["location_id"]),
                "planned_start_week": int(row["week"]),
                "access_night": int(row["access_night"]) if pd.notnull(row.get("access_night")) else 1,
                "access_seq": int(row["access_seq"]) if pd.notnull(row.get("access_seq")) else 1,
                "eclo": int(row["eclo"]) if pd.notnull(row.get("eclo")) else 0,
                "co_share_group": str(row["co_share_group"]) if pd.notnull(row.get("co_share_group")) else "",
                "access_type": "PC",
            })

        return ScheduleDisplayResponse(
            status="SUCCESS",
            scenario=scenario,
            counts={
                "locations": len(sample_sectors),
                "activities": len(sample_activities),
            },
            sample_sectors=sample_sectors,
            sample_activities=sample_activities,
            results=results_df.to_dict(orient="records"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Solver Execution Error: {str(e)}",
        )


@router.get("/schedule-display", response_model=ScheduleDisplayResponse)
async def get_schedule_display(scenario: str = Query("A", regex="^[ABC]$")):
    """Returns baseline schedule display feed for ScheduleDashboard.jsx."""
    return ScheduleDisplayResponse(
        status="SUCCESS",
        scenario=scenario,
        counts={"locations": 0, "activities": 0},
        sample_sectors=[],
        sample_activities=[],
        results=[],
    )