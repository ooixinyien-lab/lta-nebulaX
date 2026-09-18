"""Operational scenario-cost and reproducible disruption accounting."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from backend.app.domain_models import AccessType, ProblemInstance
from backend.app.schedule_insertion.models import (
    BaselineBundle,
    CandidateSchedule,
    DisruptionMetrics,
    ProjectAccess,
    ProjectJob,
    ScenarioCost,
    ScheduleScenario,
)


def compute_scenario_cost(
    problem: ProblemInstance,
    bundle: BaselineBundle,
    jobs: list[ProjectJob],
    accesses: list[ProjectAccess],
    scenario: ScheduleScenario | str,
) -> ScenarioCost:
    scenario = ScheduleScenario(scenario)
    jobs_by_id = {job.job_id: job for job in jobs}
    horizon_start = bundle.horizon_start
    weighted_lateness_scaled = 0
    for job in jobs:
        rows = [row for row in accesses if row.job_id == job.job_id]
        if not rows:
            continue
        last_week = max(row.week for row in rows)
        finish = horizon_start + timedelta(days=last_week * 7 - 1)
        late_days = max(0, (finish - job.planned_completion_date).days)
        weighted_lateness_scaled += {1: 100, 2: 10, 3: 1}[job.contract_priority] * (10 + (3 if job.activity_priority == 1 else 2 if job.activity_priority == 2 else 0)) * late_days

    groups: dict[tuple[str, int], set[str]] = defaultdict(set)
    for access in accesses:
        job = jobs_by_id.get(access.job_id)
        if job is None:
            continue
        for location_id, group in access.group_by_location.items():
            groups[(location_id, access.week)].add(group)
    excess = 0
    for (location_id, _week), group_ids in groups.items():
        try:
            supply = problem.location(location_id).supply_capacity
        except KeyError:
            supply = 0
        excess += max(0, len(group_ids) - supply)
    eclo = sum(int(row.eclo) for row in accesses)

    if scenario == ScheduleScenario.A:
        objective_scaled = weighted_lateness_scaled
    elif scenario == ScheduleScenario.B:
        objective_scaled = 70 * excess + 50 * eclo
    else:
        objective_scaled = weighted_lateness_scaled + 70 * excess + 50 * eclo
    return ScenarioCost(
        lateness_points=weighted_lateness_scaled / 10,
        excess_slot_points=7 * excess,
        eclo_points=5 * eclo,
        objective_points=objective_scaled / 10,
        objective_scaled=objective_scaled,
    )


def _sharing_signatures(accesses: list[ProjectAccess]) -> dict[tuple[str, str, int], frozenset[str]]:
    members: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for access in accesses:
        for location_id, group in access.group_by_location.items():
            members[(location_id, access.week, group)].add(access.job_id)
    result: dict[tuple[str, str, int], frozenset[str]] = {}
    for (location_id, week, _group), job_ids in members.items():
        for job_id in job_ids:
            result[(job_id, location_id, week)] = frozenset(job_ids)
    return result


def compute_disruption(
    baseline: BaselineBundle,
    current: list[ProjectAccess],
) -> DisruptionMetrics:
    """Compare persistent access identities; ignore group-label symmetry."""

    original = {access.access_id: access for access in baseline.project_accesses}
    updated = {access.access_id: access for access in current}
    changed_ids: set[str] = set()
    date_displacement = 0
    eclo_changes = 0
    for access_id, before in original.items():
        after = updated.get(access_id)
        if after is None:
            changed_ids.add(access_id)
            continue
        changed = before.week != after.week or before.service_date != after.service_date or before.eclo != after.eclo
        if changed:
            changed_ids.add(access_id)
        date_displacement += abs((after.service_date - before.service_date).days)
        eclo_changes += int(before.eclo != after.eclo)

    original_sharing = _sharing_signatures(baseline.project_accesses)
    updated_sharing = _sharing_signatures(current)
    sharing_changes = sum(
        1
        for key, before in original_sharing.items()
        if updated_sharing.get(key, frozenset()) != before
    )
    # A changed access is a visit-level change; additions do not count because
    # they have no baseline movement penalty.
    changed_jobs = {original[access_id].job_id for access_id in changed_ids if access_id in original}
    return DisruptionMetrics(
        changed_existing_jobs=len(changed_jobs),
        changed_existing_visits=len(changed_ids),
        total_absolute_service_date_displacement=date_displacement,
        eclo_changes=eclo_changes,
        sharing_changes=sharing_changes,
        label_only_changes=0,
    )


def disruption_key(metrics: DisruptionMetrics, scenario_cost: ScenarioCost) -> tuple[int, int, int, int, int]:
    """The documented lexicographic order, with scenario cost last."""

    return (
        metrics.changed_existing_jobs,
        metrics.changed_existing_visits,
        metrics.total_absolute_service_date_displacement,
        metrics.eclo_changes + metrics.sharing_changes,
        scenario_cost.objective_scaled,
    )
