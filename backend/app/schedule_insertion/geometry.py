"""Small operational geometry helpers built on the authoritative topology."""

from __future__ import annotations

from backend.app.domain_models import Activity, ActivityPriority, ProblemInstance
from backend.app.schedule_insertion.models import ProjectJob
from backend.app.topology import NetworkTopology, compute_core_footprint


def maintenance_closure_locations(problem: ProblemInstance, sector_id: str) -> set[str]:
    """Return both-bound sector and endpoint-platform closure locations."""

    sector = problem.sector(sector_id)
    locations: set[str] = set()
    for bound in ("EB", "WB"):
        locations.add(f"{sector.sector_id}:{bound}")
        locations.add(f"PLAT:{sector.line_code}:{sector.from_station_id}:{bound}")
        locations.add(f"PLAT:{sector.line_code}:{sector.to_station_id}:{bound}")
    return locations


def job_as_activity(job: ProjectJob) -> Activity:
    """Adapt an operational project descriptor to shared topology geometry."""

    return Activity(
        activity_id=job.job_id,
        contract_number=job.contract_number,
        activity_type=job.activity_type,
        start_location_id=job.start_location_id,
        end_location_id=job.end_location_id,
        total_accesses=job.total_accesses,
        planned_start_date=job.planned_start_date,
        predecessor_activity_id=job.predecessor_job_id,
        activity_priority=ActivityPriority(job.activity_priority),
    )


def project_core_locations(
    job: ProjectJob,
    problem: ProblemInstance,
    topology: NetworkTopology | None = None,
) -> tuple[str, ...]:
    topology = topology or NetworkTopology.from_problem(problem)
    if job.job_id in problem._activities_by_id:
        activity = problem.activity(job.job_id)
    else:
        activity = job_as_activity(job)
    return tuple(compute_core_footprint(activity, topology).core_locations)


def job_line_code(job: ProjectJob) -> str:
    return job.start_location_id.split(":", 2)[1]
