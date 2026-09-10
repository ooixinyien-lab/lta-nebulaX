"""Stateless Conflict Checker evaluating schedule and job issues."""

from typing import Optional
from models import Job, Schedule


def create_issue(
    code: str,
    job_ids: list[str],
    message: str,
    resource: Optional[str] = None,
    severity: str = "error",
) -> dict:
    """Creates a standardized issue dictionary for API and UI reporting."""
    return {
        "code": code,
        "request_ids": sorted(set(job_ids)),
        "message": message,
        "resource": resource,
        "severity": severity,
    }


def conflict_checker(schedule: Schedule, job: Job) -> list[dict]:
    """Evaluates a job against the active schedule and returns structured issue reports."""
    issues: list[dict] = []

    # -------------------------------------------------------------
    # 1. Direct Bound Checks (Constraint 1 & Constraint 8)
    # -------------------------------------------------------------
    bound_errors = job.validate_bounds(schedule.window_length_minutes)
    for err in bound_errors:
        issues.append(
            create_issue(
                code=err["code"],
                job_ids=[job.id],
                message=err["message"],
                resource=err["field"],
            )
        )

    if job.start < job.earliest_start or job.end > job.latest_finish:
        issues.append(
            create_issue(
                code="TIMING_WINDOW_VIOLATION",
                job_ids=[job.id],
                message=(
                    f"Requested window [{job.start:04d}-{job.end:04d}] exceeds "
                    f"permitted bounds [{job.earliest_start:04d}-{job.latest_finish:04d}]."
                ),
            )
        )

    # -------------------------------------------------------------
    # 2. Same-Day Overlap Queries & Resource Capacity Sweeps
    # -------------------------------------------------------------
    same_day_overlaps = schedule.time_overlap(job)
    buffer_jobs = schedule.buffer_overlap(job)

    # Constraint 4: Pooled Equipment Capacity Checks
    for eq_type in set(job.equipment_requirement):
        req_qty = job.equipment_requirement.count(eq_type)
        used_qty = schedule.equipment_in_use_at(job.date, job.start, job.end, eq_type)
        max_qty = schedule.equipment_available.get(eq_type, 0)

        if used_qty + req_qty > max_qty:
            clashing_jobs = [j for j in same_day_overlaps if eq_type in j.equipment_requirement]
            clashing_ids = [j.id for j in clashing_jobs] + [job.id]
            issues.append(
                create_issue(
                    code="EQUIPMENT_CONFLICT",
                    job_ids=clashing_ids,
                    message=(
                        f"Equipment '{eq_type}' demand ({used_qty + req_qty}) exceeds pool capacity ({max_qty}) "
                        f"on {job.date} [{job.start:04d}-{job.end:04d}] due to jobs: {clashing_ids}."
                    ),
                    resource=eq_type,
                )
            )

    # Constraint 4: Pooled Manpower Team Capacity Checks
    if job.manpower_requirement:
        m_type = job.manpower_requirement
        req_teams = job.manpower_count
        used_teams = schedule.manpower_in_use_at(job.date, job.start, job.end, m_type)
        max_teams = schedule.manpower_available.get(m_type, 0)

        if used_teams + req_teams > max_teams:
            clashing_jobs = [j for j in same_day_overlaps if j.manpower_requirement == m_type]
            clashing_ids = [j.id for j in clashing_jobs] + [job.id]
            issues.append(
                create_issue(
                    code="MANPOWER_CONFLICT",
                    job_ids=clashing_ids,
                    message=(
                        f"Manpower '{m_type}' team demand ({used_teams + req_teams}) exceeds pool capacity ({max_teams}) "
                        f"on {job.date} [{job.start:04d}-{job.end:04d}] due to jobs: {clashing_ids}."
                    ),
                    resource=m_type,
                )
            )

    # -------------------------------------------------------------
    # 3. Same-Day Pairwise Checks (Constraints 2 & 3)
    # -------------------------------------------------------------
    for j in same_day_overlaps:
        pair_ids = [job.id, j.id]

        # Constraint 2: Spatial Track & Safety Footprint Overlap
        common_sectors = set(job.protected_sectors) & set(j.protected_sectors)
        if common_sectors:
            label = ", ".join(sorted(common_sectors))
            issues.append(
                create_issue(
                    code="SAFETY_FOOTPRINT_OVERLAP",
                    job_ids=pair_ids,
                    message=f"Exclusive safety footprint conflict on sector(s): {label} with Job '{j.id}' on {job.date}.",
                    resource=label,
                )
            )

        # Constraint 3: Power Compatibility Check
        if not job.check_power(j):
            issues.append(
                create_issue(
                    code="POWER_CONFLICT",
                    job_ids=pair_ids,
                    message=(
                        f"Traction power requirement conflict ({job.power_requirement} vs {j.power_requirement}) "
                        f"with active Job '{j.id}' on {job.date}."
                    ),
                    resource="POWER_ZONE",
                )
            )

    # -------------------------------------------------------------
    # 4. Global Dependency Check Across All Scheduled Days (Constraint 6)
    # -------------------------------------------------------------
    for prereq_id in job.prerequisite_jobs:
        prereq_job = next((j for j in schedule.jobs if j.id == prereq_id), None)
        if prereq_job and not job.check_dependency(prereq_job):
            issues.append(
                create_issue(
                    code="DEPENDENCY_VIOLATION",
                    job_ids=[job.id, prereq_job.id],
                    message=(
                        f"Sequence conflict: Job '{job.id}' ({job.date} {job.start:04d}) is scheduled "
                        f"before prerequisite Job '{prereq_job.id}' completes ({prereq_job.date} {prereq_job.end:04d})."
                    ),
                    resource=prereq_job.id,
                )
            )

    # Constraint 5: Travel Buffer Warnings
    if buffer_jobs:
        buf_ids = [j.id for j in buffer_jobs]
        issues.append(
            create_issue(
                code="BUFFER_WARNING",
                job_ids=[job.id] + buf_ids,
                message=f"Tight travel/transit buffer ({schedule.buffer} mins) on {job.date} with jobs: {buf_ids}.",
                severity="warning",
            )
        )

    return issues