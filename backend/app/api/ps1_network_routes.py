"""API endpoints for the interactive SVG railway network map."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Query, Request

from backend.app.railway_map import NetworkMapService

router = APIRouter(prefix="/api/ps1/network", tags=["ps1-network-map"])


def _get_service(request: Request) -> NetworkMapService:
    if not hasattr(request.app.state, "network_map_service"):
        request.app.state.network_map_service = NetworkMapService(
            db_session_factory=request.app.state.ps1_db,
            settings=request.app.state.settings,
        )
    return request.app.state.network_map_service


@router.get("/context")
def get_map_context(request: Request) -> dict[str, Any]:
    """Returns bootstrap and scenario availability metadata."""
    service = _get_service(request)
    return service.get_context()


@router.get("/topology")
def get_map_topology(request: Request) -> dict[str, Any]:
    """Returns network lines, stations, sectors, and locations."""
    service = _get_service(request)
    return service.get_topology()


@router.get("/activities")
def get_map_activities(request: Request) -> list[dict[str, Any]]:
    """Returns activities with precomputed core and safety protection footprints."""
    service = _get_service(request)
    return service.get_activities()


@router.get("/occupancy")
def get_map_occupancy(
    request: Request,
    scenario: str = Query(default="A", pattern="^[A-Z0-9_-]+$"),
    week: int = Query(default=1, ge=1, le=52),
    activity_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Returns weekly physical occupancy and protection footprints for a scenario."""
    service = _get_service(request)
    return service.get_weekly_occupancy(
        scenario=scenario,
        week=week,
        activity_id=activity_id,
    )


@router.get("/full-schedule")
def get_full_schedule(
    request: Request,
    scenario: str = Query(default="A", pattern="^[ABC]$"),
) -> dict[str, Any]:
    """Returns the complete PS1 schedule including all activities, locations, contracts, accesses, and occupancies."""
    service = _get_service(request)
    problem, cache = service._get_problem_and_cache()
    source = service.schedule_source

    accesses = source.get_accesses(scenario=scenario)
    occupancies = source.get_occupancies(scenario=scenario)
    contract_results = source.get_results(scenario=scenario)

    activities_payload = []
    for act in problem.activities:
        contract = problem.contract(act.contract_number)
        core = cache.get_core_footprint(act.activity_id)
        prot = cache.get_protection_footprint(act.activity_id)
        activities_payload.append({
            "activity_id": act.activity_id,
            "contract_number": act.contract_number,
            "activity_type": act.activity_type.value,
            "start_location_id": act.start_location_id,
            "end_location_id": act.end_location_id,
            "total_accesses": act.total_accesses,
            "planned_start_date": act.planned_start_date.isoformat(),
            "planned_start_week": problem.planned_start_week(act),
            "predecessor_activity_id": act.predecessor_activity_id,
            "activity_priority": int(act.activity_priority),
            "nature_of_activity": contract.nature_of_activity.value,
            "access_type": contract.access_type.value,
            "line_code": core.line_code,
            "bound": core.bound.value,
            "core_locations": list(core.core_locations),
            "buffer_locations": list(prot.buffer_locations),
            "mirrored_locations": list(prot.mirrored_locations),
        })

    contracts_payload = []
    for c in problem.contracts:
        contracts_payload.append({
            "contract_number": c.contract_number,
            "contract_description": c.contract_description,
            "access_type": c.access_type.value,
            "number_of_workfronts": c.number_of_workfronts,
            "number_of_maximum_access_per_week": c.number_of_maximum_access_per_week,
            "planned_completion_date": c.planned_completion_date.isoformat(),
            "contract_priority": int(c.contract_priority),
        })

    locations_payload = []
    for loc in problem.locations:
        locations_payload.append({
            "location_id": loc.location_id,
            "location_kind": loc.location_kind.value,
            "line_code": loc.line_code,
            "bound": loc.bound.value,
            "supply_capacity": loc.supply_capacity,
        })

    sectors_payload = []
    for sec in problem.sectors:
        sectors_payload.append({
            "sector_id": sec.sector_id,
            "line_code": sec.line_code,
            "from_station": sec.from_station_id,
            "to_station": sec.to_station_id,
            "seq": sec.seq,
            "is_shared": sec.is_shared,
        })

    return {
        "scenario": scenario,
        "horizon_weeks": problem.parameters.horizon_weeks,
        "activities": activities_payload,
        "contracts": contracts_payload,
        "locations": locations_payload,
        "sectors": sectors_payload,
        "accesses": [
            {
                "activity_id": r.activity_id,
                "access_seq": r.access_seq,
                "week": r.week,
                "eclo": 1 if r.eclo else 0,
                "access_night": r.access_night,
            }
            for r in accesses
        ],
        "occupancies": [
            {
                "activity_id": r.activity_id,
                "week": r.week,
                "location_id": r.location_id,
                "co_share_group": r.co_share_group,
            }
            for r in occupancies
        ],
        "contract_results": [
            {
                "contract_number": r.contract_number,
                "simulated_completion_date": r.simulated_completion_date.isoformat(),
                "overrun_days": r.overrun_days,
            }
            for r in contract_results
        ],
    }


@router.post("/validate-schedule")
async def validate_schedule_endpoint(request: Request) -> dict[str, Any]:
    """Validates modified accesses and occupancies against all official PS1 and AGENTS.md rules."""
    from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow
    from backend.app.ps1.validation import validate_schedule

    service = _get_service(request)
    problem, cache = service._get_problem_and_cache()
    payload = await request.json()

    scenario = payload.get("scenario", "A")
    raw_accesses = payload.get("accesses", [])
    raw_occupancies = payload.get("occupancies", [])

    access_rows = [
        AccessScheduleRow(
            activity_id=r["activity_id"],
            access_seq=int(r.get("access_seq", 1)),
            week=int(r["week"]),
            eclo=bool(r.get("eclo", False)),
            access_night=int(r["access_night"]),
        )
        for r in raw_accesses
    ]
    occupancy_rows = [
        OccupancyScheduleRow(
            activity_id=r["activity_id"],
            week=int(r["week"]),
            location_id=r["location_id"],
            co_share_group=str(r.get("co_share_group", "SOLO")),
        )
        for r in raw_occupancies
    ]

    summary = validate_schedule(
        problem=problem,
        scenario=scenario,
        access_rows=access_rows,
        occupancy_rows=occupancy_rows,
        footprints=cache,
    )

    return {
        "valid": summary.local_accounting_passed,
        "issue_count": len(summary.issues),
        "issues": [
            {
                "rule": issue.rule,
                "detail": issue.detail,
                "activity_id": issue.activity_id,
                "week": issue.week,
                "location_id": issue.location_id,
            }
            for issue in summary.issues
        ],
    }


@router.post("/reschedule")
def reschedule_with_solver(
    request: Request,
    scenario: str = Query(default="A", pattern="^[ABC]$"),
) -> dict[str, Any]:
    """Resets schedule to the pristine CP-SAT solver baseline for the given scenario."""
    service = _get_service(request)
    # Refresh schedule source to clear any mutated cached state
    from backend.app.network_schedule.sample_output_source import SampleOutputScheduleSource
    service.schedule_source = SampleOutputScheduleSource()
    return get_full_schedule(request=request, scenario=scenario)
