"""API endpoints for the interactive SVG railway network map."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Query, Request

from backend.app.railway_map import NetworkMapService

router = APIRouter(prefix="/api/ps1/network", tags=["ps1-network-map"])


def _get_service(request: Request) -> NetworkMapService:
    if not hasattr(request.app.state, "network_map_service"):
        request.app.state.network_map_service = NetworkMapService(
            database=request.app.state.db,
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
