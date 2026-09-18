"""Independent operational validation.

The validator rebuilds footprints, workload, calendar and resource accounting
from typed output rows.  It does not trust CP-SAT variables or the solver's
reported objective.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from backend.app.domain_models import AccessType, ProblemInstance
from backend.app.schedule_insertion.config import ScheduleInsertionConfig
from backend.app.schedule_insertion.geometry import (
    job_line_code,
    maintenance_closure_locations,
    project_core_locations,
)
from backend.app.schedule_insertion.models import (
    BaselineBundle,
    MaintenanceVisit,
    OperationalValidation,
    ProjectAccess,
    ProjectJob,
    ScheduleScenario,
    ValidationFinding,
)
from backend.app.topology import NetworkTopology


def _finding(
    findings: list[ValidationFinding],
    rule: str,
    detail: str,
    *,
    severity: str = "error",
    job_id: str | None = None,
    visit_id: str | None = None,
    service_date: date | None = None,
    location_id: str | None = None,
) -> None:
    findings.append(
        ValidationFinding(
            rule=rule,
            detail=detail,
            severity=severity,  # type: ignore[arg-type]
            job_id=job_id,
            visit_id=visit_id,
            service_date=service_date,
            location_id=location_id,
        )
    )


def _maintenance_checks(
    problem: ProblemInstance,
    bundle: BaselineBundle,
    findings: list[ValidationFinding],
    config: ScheduleInsertionConfig,
) -> None:
    jobs = {job.job_id: job for job in bundle.maintenance_jobs}
    visits_by_job: dict[str, list[MaintenanceVisit]] = defaultdict(list)
    visits_by_date: dict[date, list[MaintenanceVisit]] = defaultdict(list)
    visit_ids: set[str] = set()
    for visit in bundle.maintenance_visits:
        if visit.visit_id in visit_ids:
            _finding(findings, "maintenance_identity", f"Duplicate maintenance visit ID {visit.visit_id}", visit_id=visit.visit_id)
        visit_ids.add(visit.visit_id)
        if visit.job_id not in jobs:
            _finding(findings, "maintenance_reference", f"Visit references unknown job {visit.job_id}", visit_id=visit.visit_id)
        if visit.sector_id not in {sector.sector_id for sector in problem.sectors}:
            _finding(findings, "maintenance_reference", f"Visit references unknown sector {visit.sector_id}", visit_id=visit.visit_id)
        visits_by_job[visit.job_id].append(visit)
        visits_by_date[visit.service_date].append(visit)

    for job in bundle.maintenance_jobs:
        visits = visits_by_job.get(job.job_id, [])
        if len(visits) != job.required_visits:
            _finding(findings, "maintenance_workload", f"{job.job_id} has {len(visits)} visits; required {job.required_visits}", job_id=job.job_id)
        if len({visit.service_date for visit in visits}) != len(visits):
            _finding(findings, "maintenance_distinct_dates", f"{job.job_id} has multiple visits on one date", job_id=job.job_id)

    for service_date, visits in visits_by_date.items():
        if len(visits) > config.maintenance_daily_capacity:
            _finding(findings, "maintenance_daily_capacity", f"{len(visits)} visits exceed daily maintenance capacity {config.maintenance_daily_capacity}", service_date=service_date)
        occupied: dict[str, str] = {}
        for visit in visits:
            for location_id in maintenance_closure_locations(problem, visit.sector_id):
                previous = occupied.get(location_id)
                if previous is not None and previous != visit.visit_id:
                    _finding(findings, "maintenance_footprint_overlap", f"Visits {previous} and {visit.visit_id} overlap at {location_id}", visit_id=visit.visit_id, service_date=service_date, location_id=location_id)
                occupied[location_id] = visit.visit_id

    horizon_start = bundle.horizon_start
    horizon_end = horizon_start + timedelta(days=bundle.horizon_weeks * 7 - 1)
    for sector in problem.sectors:
        dates = sorted(v.service_date for v in bundle.maintenance_visits if v.sector_id == sector.sector_id)
        if not dates:
            _finding(findings, "maintenance_coverage", f"No maintenance visits for sector {sector.sector_id}", job_id=sector.sector_id)
            continue
        interval = config.coverage_interval_days
        # Check every possible rolling-window start in the planning horizon.
        for day_offset in range((horizon_end - horizon_start).days + 1):
            window_start = horizon_start + timedelta(days=day_offset)
            window_end = window_start + timedelta(days=interval)
            count = sum(window_start <= visit_date < window_end for visit_date in dates)
            if count < 3:
                _finding(findings, "maintenance_coverage", f"Sector {sector.sector_id} has {count} visits in rolling window starting {window_start.isoformat()}", service_date=window_start)
                break


def _legal_group(roles: list[AccessType]) -> bool:
    pm = roles.count(AccessType.PM)
    pc = roles.count(AccessType.PC)
    c = roles.count(AccessType.C)
    return (
        (pm == 1 and pc == 0 and c == 0)
        or (pm == 0 and pc == 1 and c <= 3)
        or (pm == 0 and pc == 0 and 1 <= c <= 4)
    )


def validate_operational_schedule(
    problem: ProblemInstance,
    bundle: BaselineBundle,
    project_jobs: list[ProjectJob],
    project_accesses: list[ProjectAccess],
    scenario: ScheduleScenario | str,
    *,
    config: ScheduleInsertionConfig | None = None,
    frozen_access_ids: set[str] | None = None,
) -> OperationalValidation:
    """Validate a complete operational candidate and return all findings."""

    config = config or ScheduleInsertionConfig(horizon_weeks=bundle.horizon_weeks)
    scenario = ScheduleScenario(scenario)
    findings: list[ValidationFinding] = []
    _maintenance_checks(problem, bundle, findings, config)

    job_by_id = {job.job_id: job for job in project_jobs}
    topology = NetworkTopology.from_problem(problem)
    core_by_job: dict[str, set[str]] = {}
    for job in project_jobs:
        try:
            core_by_job[job.job_id] = set(project_core_locations(job, problem, topology))
        except (KeyError, ValueError) as exc:
            _finding(findings, "project_footprint", str(exc), job_id=job.job_id)

    calendar_by_date = {day.service_date: day for day in bundle.calendar}
    maintenance_by_date: dict[date, set[str]] = defaultdict(set)
    for visit in bundle.maintenance_visits:
        maintenance_by_date[visit.service_date].update(maintenance_closure_locations(problem, visit.sector_id))

    accesses_by_job: dict[str, list[ProjectAccess]] = defaultdict(list)
    access_ids: set[str] = set()
    location_groups: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    role_members: dict[tuple[str, int, str], list[AccessType]] = defaultdict(list)
    project_count_by_date: dict[date, int] = defaultdict(int)
    line_eclo_weeks: dict[str, set[int]] = defaultdict(set)
    start = bundle.horizon_start
    end = start + timedelta(days=bundle.horizon_weeks * 7 - 1)

    for access in project_accesses:
        if access.access_id in access_ids:
            _finding(findings, "project_identity", f"Duplicate access ID {access.access_id}", job_id=access.job_id)
        access_ids.add(access.access_id)
        job = job_by_id.get(access.job_id)
        if job is None:
            _finding(findings, "project_reference", f"Access references unknown job {access.job_id}", job_id=access.job_id)
            continue
        accesses_by_job[access.job_id].append(access)
        day = calendar_by_date.get(access.service_date)
        if day is None or not day.eligible or not day.physical_available:
            _finding(findings, "calendar_eligibility", f"Service date {access.service_date} is not physically eligible", job_id=job.job_id, service_date=access.service_date)
        if not start <= access.service_date <= end:
            _finding(findings, "calendar_horizon", f"Service date {access.service_date} is outside the planning horizon", job_id=job.job_id, service_date=access.service_date)
        expected_week = ((access.service_date - start).days // 7) + 1
        if expected_week != access.week:
            _finding(findings, "week_date_mapping", f"Week {access.week} does not contain service date {access.service_date}", job_id=job.job_id, service_date=access.service_date)
        if access.global_night_id is not None and day is not None and access.global_night_id != day.global_night_id:
            _finding(findings, "global_night_identity", f"Global night ID does not match calendar revision for {access.service_date}", job_id=job.job_id, service_date=access.service_date)
        if access.eclo and (day is None or not day.eclo_eligible):
            _finding(findings, "eclo_calendar", f"ECLO is not eligible on {access.service_date}", job_id=job.job_id, service_date=access.service_date)
        if access.service_date < job.effective_release_date:
            _finding(findings, "release", f"Access is before release date {job.effective_release_date}", job_id=job.job_id, service_date=access.service_date)
        if scenario == ScheduleScenario.B and access.service_date > job.effective_deadline:
            _finding(findings, "deadline", f"Access is after hard deadline {job.effective_deadline}", job_id=job.job_id, service_date=access.service_date)
        if access.access_night > job.number_of_maximum_access_per_week:
            _finding(findings, "local_night", f"Local night {access.access_night} exceeds weekly cap", job_id=job.job_id)
        project_count_by_date[access.service_date] += 1
        line_eclo_weeks[job_line_code(job)].add(access.week) if access.eclo else None
        if access.eclo and scenario == ScheduleScenario.A:
            _finding(findings, "eclo_policy", "Scenario A forbids ECLO", job_id=job.job_id)

        closure = maintenance_by_date.get(access.service_date, set())
        for location_id in core_by_job.get(job.job_id, set()) & closure:
            _finding(findings, "maintenance_project_conflict", f"Project core {location_id} shares a night with a maintenance closure", job_id=job.job_id, service_date=access.service_date, location_id=location_id)
        for location_id in core_by_job.get(job.job_id, set()):
            group = access.group_by_location.get(location_id)
            if not group:
                _finding(findings, "occupancy", f"No possession group for core location {location_id}", job_id=job.job_id, service_date=access.service_date, location_id=location_id)
                continue
            key = (location_id, access.week, group)
            location_groups[(location_id, access.week, group)].add(job.job_id)
            role_members[key].append(job.access_type)

    for service_date, count in project_count_by_date.items():
        day = calendar_by_date.get(service_date)
        if day and count > day.gross_capacity:
            _finding(findings, "calendar_capacity", f"{count} project accesses exceed gross date capacity {day.gross_capacity}", service_date=service_date)

    for job in project_jobs:
        rows = accesses_by_job.get(job.job_id, [])
        if not rows:
            _finding(findings, "project_workload", "Project has no accesses", job_id=job.job_id)
            continue
        if len({row.week for row in rows}) != len(rows):
            _finding(findings, "weekly_frequency", "Project has more than one access in a week", job_id=job.job_id)
        delivered = sum(2 + int(row.eclo) for row in rows)
        if delivered < 2 * job.total_accesses:
            _finding(findings, "project_workload", f"Delivered doubled workload {delivered} is below {2 * job.total_accesses}", job_id=job.job_id)
        if job.predecessor_job_id:
            predecessor_rows = accesses_by_job.get(job.predecessor_job_id, [])
            if predecessor_rows and min(row.week for row in rows) <= max(row.week for row in predecessor_rows):
                _finding(findings, "precedence", f"Project starts before predecessor {job.predecessor_job_id} finishes", job_id=job.job_id)

    for (location_id, week, group), members in location_groups.items():
        roles = role_members[(location_id, week, group)]
        if not _legal_group(roles):
            _finding(findings, "possession_mix", f"Illegal group {group}: {[role.value for role in roles]}", location_id=location_id)

    groups_by_location_week: dict[tuple[str, int], set[str]] = defaultdict(set)
    for location_id, week, group in location_groups:
        groups_by_location_week[(location_id, week)].add(group)
    for (location_id, week), groups in groups_by_location_week.items():
        supply = problem.location(location_id).supply_capacity
        if scenario == ScheduleScenario.A and len(groups) > supply:
            _finding(findings, "nominal_supply", f"{len(groups)} groups exceed nominal supply {supply}", location_id=location_id,)
        if scenario == ScheduleScenario.C and len(groups) > supply + 1:
            _finding(findings, "scenario_c_supply", f"{len(groups)} groups exceed Scenario C allowance {supply + 1}", location_id=location_id)

    if scenario == ScheduleScenario.C:
        for line_code, weeks in line_eclo_weeks.items():
            if weeks and max(weeks) - min(weeks) > 1:
                _finding(findings, "scenario_c_eclo_window", f"ECLO weeks {sorted(weeks)} do not fit a two-week line window")

    if frozen_access_ids is not None:
        baseline_by_id = {access.access_id: access for access in bundle.project_accesses}
        for access_id in frozen_access_ids:
            original = baseline_by_id.get(access_id)
            current = next((access for access in project_accesses if access.access_id == access_id), None)
            if original is None or current is None:
                _finding(findings, "frozen_commitment", f"Frozen access {access_id} is missing")
            elif (
                current.job_id,
                current.week,
                current.service_date,
                current.eclo,
                current.access_night,
            ) != (
                original.job_id,
                original.week,
                original.service_date,
                original.eclo,
                original.access_night,
            ):
                _finding(findings, "frozen_commitment", f"Frozen access {access_id} changed")

    return OperationalValidation(
        passed=not any(f.severity == "error" for f in findings),
        status="passed" if not any(f.severity == "error" for f in findings) else "failed",
        findings=findings,
    )


def validate_maintenance_fixture(
    problem: ProblemInstance,
    bundle: BaselineBundle,
    *,
    config: ScheduleInsertionConfig | None = None,
) -> OperationalValidation:
    """Public convenience check for the generated maintenance-only baseline."""

    return validate_operational_schedule(problem, bundle, [], [], ScheduleScenario.A, config=config)
