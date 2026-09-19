"""Explicit schedule-identity projections shared by the React schedule and map."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.auth.dependencies import current_user
from backend.app.db.repositories.instances import load_revision
from backend.app.schedule_insertion.geometry import maintenance_closure_locations
from backend.app.schedule_insertion.persistence import load_baseline, load_run
from backend.app.schedule_insertion.validation import validate_operational_schedule
from backend.app.schedule_insertion.models import ScheduleScenario
from backend.app.schedule_insertion.solver import _official_jobs
from backend.app.schemas import User


router = APIRouter(prefix="/api/ps1/schedules", tags=["ps1-schedule-projection"])


def _official_projection(connection, *, scenario: str, revision_id: str, run_id: str) -> tuple[dict, object]:
    run = connection.execute(
        "SELECT id,revision_id,scenario,status FROM solver_runs WHERE id=?", (run_id,)
    ).fetchone()
    if run is None or run["revision_id"] != revision_id or run["scenario"] != scenario:
        raise HTTPException(409, "Official run does not match the requested schedule identity")
    if run["status"] != "SUCCEEDED":
        raise HTTPException(409, "Official run is not complete")
    problem = load_revision(connection, revision_id)
    accesses = [dict(row) for row in connection.execute(
        "SELECT activity_id,access_seq,week,eclo,access_night FROM run_accesses WHERE run_id=? ORDER BY week,activity_id,access_seq",
        (run_id,),
    )]
    occupancies = [dict(row) for row in connection.execute(
        "SELECT activity_id,week,location_id,co_share_group FROM run_occupancies WHERE run_id=? ORDER BY week,location_id,activity_id",
        (run_id,),
    )]
    results = [dict(row) for row in connection.execute(
        "SELECT scenario,contract_number,simulated_completion_date,overrun_days FROM run_contract_results WHERE run_id=? ORDER BY contract_number",
        (run_id,),
    )]
    revision = connection.execute("SELECT instance_id,revision_number FROM instance_revisions WHERE id=?", (revision_id,)).fetchone()
    identity = {
        "mode": "requirements", "scenario": scenario,
        "instanceId": revision["instance_id"], "instanceRevision": revision["revision_number"],
        "instanceRevisionId": revision_id, "runId": run_id,
    }
    return _base_projection(problem, identity, accesses, occupancies, results, [], [], []), problem


def _operational_projection(connection, *, scenario: str, baseline_id: str, baseline_revision: int, run_id: str | None) -> tuple[dict, object]:
    baseline = load_baseline(connection, baseline_id, baseline_revision)
    if baseline is None:
        raise HTTPException(404, "Operational baseline revision not found")
    if not baseline.official_revision_id:
        raise HTTPException(409, "Operational baseline is not linked to an official revision")
    problem = load_revision(connection, baseline.official_revision_id)
    candidate = None
    result = None
    if run_id:
        result = load_run(connection, run_id)
        if result is None or result.baseline_id != baseline_id or result.baseline_revision != baseline_revision or result.scenario.value != scenario:
            raise HTTPException(409, "Operational candidate does not match the requested schedule identity")
        candidate = result.lower_disruption_candidate or result.reference_candidate
        if candidate is None:
            raise HTTPException(409, "Operational run has no candidate schedule")
    project_accesses = candidate.projects if candidate else baseline.project_accesses
    jobs = {job.job_id: job for job in _official_jobs(problem)}
    operational_jobs = {job.job_id: job for job in baseline.project_jobs}
    jobs.update(operational_jobs)
    official_activities = {activity.activity_id: activity for activity in problem.activities}
    official_contracts = {contract.contract_number: contract for contract in problem.contracts}
    accesses = []
    occupancies = []
    for access in project_accesses:
        accesses.append({
            "activity_id": access.job_id, "job_id": access.job_id, "access_id": access.access_id,
            "access_seq": access.access_seq, "week": access.week, "eclo": int(access.eclo),
            "access_night": access.access_night, "service_date": access.service_date.isoformat(),
            "global_night_id": access.global_night_id, "locked": access.locked,
            "source": jobs[access.job_id].source.value if access.job_id in jobs else "official",
        })
        group_map = access.group_by_location
        if not group_map and access.job_id in official_activities:
            # Accepted operational runs always retain their explicit group map; this is a defensive empty state.
            group_map = {}
        for location_id, group in group_map.items():
            occupancies.append({"activity_id": access.job_id, "week": access.week, "location_id": location_id, "co_share_group": group})

    extra_activities = []
    extra_contracts = []
    for job in operational_jobs.values():
        extra_activities.append({
            "activity_id": job.job_id, "contract_number": job.contract_number,
            "activity_type": job.activity_type.value, "start_location_id": job.start_location_id,
            "end_location_id": job.end_location_id, "total_accesses": job.total_accesses,
            "planned_start_date": job.planned_start_date.isoformat(),
            "predecessor_activity_id": job.predecessor_job_id, "activity_priority": job.activity_priority,
            "access_type": job.access_type.value, "source": job.source.value,
        })
        if job.contract_number not in official_contracts:
            extra_contracts.append({
                "contract_number": job.contract_number, "contract_description": f"Operational job {job.job_id}",
                "activity_type": job.activity_type.value, "nature_of_activity": job.nature_of_activity.value,
                "contract_priority": job.contract_priority, "planned_completion_date": job.planned_completion_date.isoformat(),
                "access_type": job.access_type.value, "number_of_workfronts": job.number_of_workfronts,
                "number_of_maximum_access_per_week": job.number_of_maximum_access_per_week,
            })
    maintenance = []
    for visit in (candidate.maintenance_visits if candidate else baseline.maintenance_visits):
        week = ((visit.service_date - baseline.horizon_start).days // 7) + 1
        if 1 <= week <= baseline.horizon_weeks:
            maintenance.append({
                **visit.model_dump(mode="json"), "week": week,
                "location_ids": sorted(maintenance_closure_locations(problem, visit.sector_id)),
            })
    validation = candidate.validation if candidate else validate_operational_schedule(
        problem, baseline, list(jobs.values()), project_accesses, ScheduleScenario(scenario)
    )
    conflicts = [finding.model_dump(mode="json") for finding in validation.findings]
    identity = {
        "mode": "operations", "scenario": scenario, "baselineId": baseline_id,
        "baselineRevision": baseline_revision, "runId": run_id,
        "instanceRevisionId": baseline.official_revision_id,
    }
    diff = None
    if candidate:
        diff = {"scenarioCost": candidate.cost.model_dump(mode="json"), "disruption": candidate.disruption.model_dump(mode="json")}
    return _base_projection(problem, identity, accesses, occupancies, [], maintenance, conflicts, extra_activities, extra_contracts, diff), problem


def _base_projection(problem, identity, accesses, occupancies, results, maintenance, conflicts, extra_activities, extra_contracts=None, diff=None):
    activities = [activity.model_dump(mode="json") for activity in problem.activities] + extra_activities
    contract_by_id = {contract.contract_number: contract for contract in problem.contracts}
    for activity in activities:
        contract = contract_by_id.get(activity["contract_number"])
        if contract:
            activity["access_type"] = contract.access_type.value
            activity["source"] = activity.get("source", "official")
    return {
        "identity": identity,
        "horizon": {"start_date": problem.parameters.horizon_start.isoformat(), "weeks": problem.parameters.horizon_weeks},
        "activities": activities,
        "contracts": [contract.model_dump(mode="json") for contract in problem.contracts] + (extra_contracts or []),
        "locations": [location.model_dump(mode="json") for location in problem.locations],
        "sectors": [sector.model_dump(mode="json") for sector in problem.sectors],
        "accesses": accesses, "occupancies": occupancies, "contract_results": results,
        "maintenance": maintenance, "conflicts": conflicts, "diff": diff,
    }


def _map_week(projection: dict, week: int) -> dict:
    accesses = [row for row in projection["accesses"] if row["week"] == week]
    occupancies = [row for row in projection["occupancies"] if row["week"] == week]
    maintenance = [row for row in projection["maintenance"] if row["week"] == week]
    locations = {row["location_id"]: row for row in projection["locations"]}
    grouped = defaultdict(lambda: defaultdict(set))
    for row in occupancies:
        grouped[row["location_id"]][row["co_share_group"]].add(row["activity_id"])
    location_occupancy = {}
    for location_id, groups in grouped.items():
        supply = int(locations.get(location_id, {}).get("supply_capacity", 0))
        location_occupancy[location_id] = {
            "locationId": location_id, "supplyCapacity": supply,
            "activeActivities": sorted({item for members in groups.values() for item in members}),
            "coShareGroups": [{"group": group, "activities": sorted(members), "isCompliant": True} for group, members in groups.items()],
            "occupiedGroupCount": len(groups), "peakOccupiedGroupCount": len(groups),
            "capacityExceeded": len(groups) > supply,
        }
    for visit in maintenance:
        for location_id in visit["location_ids"]:
            entry = location_occupancy.setdefault(location_id, {
                "locationId": location_id, "supplyCapacity": int(locations.get(location_id, {}).get("supply_capacity", 0)),
                "activeActivities": [], "coShareGroups": [], "occupiedGroupCount": 0,
                "peakOccupiedGroupCount": 0, "capacityExceeded": False,
            })
            entry.setdefault("maintenanceVisits", []).append(visit["visit_id"])
    return {
        "identity": projection["identity"], "scenario": projection["identity"]["scenario"], "week": week,
        "available": True, "activeActivities": sorted({row["activity_id"] for row in accesses}),
        "locationOccupancy": location_occupancy,
        "protection": {"bufferLocations": {}, "mirroredLocations": {}, "crossLineLocations": {}, "explanations": []},
        "maintenance": maintenance, "conflicts": projection["conflicts"], "results": projection["contract_results"],
    }


@router.get("/project")
def project_schedule(
    request: Request,
    mode: Literal["requirements", "operations"],
    scenario: str = Query(pattern="^[ABC]$"),
    instance_revision_id: str | None = None,
    run_id: str | None = None,
    baseline_id: str | None = None,
    baseline_revision: int | None = None,
    week: int | None = Query(default=None, ge=1, le=52),
    user: User = Depends(current_user),
):
    with request.app.state.db.connection() as connection:
        if mode == "requirements":
            if not instance_revision_id or not run_id:
                raise HTTPException(422, "Requirements projection needs instance_revision_id and run_id")
            projection, _ = _official_projection(connection, scenario=scenario, revision_id=instance_revision_id, run_id=run_id)
        else:
            if not baseline_id or baseline_revision is None:
                raise HTTPException(422, "Operations projection needs baseline_id and baseline_revision")
            projection, _ = _operational_projection(connection, scenario=scenario, baseline_id=baseline_id, baseline_revision=baseline_revision, run_id=run_id)
    return _map_week(projection, week) if week is not None else projection
