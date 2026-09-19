"""One CP-SAT engine for operational insertion under A/B/C policies."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from math import ceil
from time import monotonic
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from backend.app.domain_models import ProblemInstance
from backend.app.schedule_insertion.config import ScheduleInsertionConfig
from backend.app.schedule_insertion.geometry import (
    job_line_code,
    maintenance_closure_locations,
    project_core_locations,
)
from backend.app.schedule_insertion.models import (
    BaselineBundle,
    CandidateSchedule,
    EffectiveChange,
    MaintenanceVisit,
    OperationalCalendarDay,
    ProjectAccess,
    ProjectAddition,
    ProjectJob,
    ReplanRequest,
    ScenarioCost,
    ScheduleInsertionResult,
    ScheduleScenario,
    SolveOptions,
)
from backend.app.schedule_insertion.scoring import compute_disruption, compute_scenario_cost, disruption_key
from backend.app.schedule_insertion.validation import validate_operational_schedule


@dataclass(frozen=True)
class _Slot:
    slot_id: str
    job_id: str
    access_id: str
    baseline: ProjectAccess | None = None


@dataclass
class _Artifacts:
    model: cp_model.CpModel
    scenario: ScheduleScenario
    jobs: dict[str, ProjectJob]
    slots: list[_Slot]
    fixed: list[ProjectAccess]
    core_by_job: dict[str, tuple[str, ...]]
    calendar_by_week: dict[int, list[OperationalCalendarDay]]
    x: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    active: dict[str, cp_model.IntVar] = field(default_factory=dict)
    eclo: dict[str, cp_model.IntVar] = field(default_factory=dict)
    date_choice: dict[tuple[str, int, date], cp_model.IntVar] = field(default_factory=dict)
    night: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    group: dict[tuple[str, int, str, str], cp_model.IntVar] = field(default_factory=dict)
    group_used: dict[tuple[str, int, str], cp_model.IntVar] = field(default_factory=dict)
    excess: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    last_week: dict[str, cp_model.IntVar] = field(default_factory=dict)
    changed: dict[str, cp_model.IntVar] = field(default_factory=dict)
    job_changed: dict[str, cp_model.IntVar] = field(default_factory=dict)
    displacement_terms: list[cp_model.LinearExpr] = field(default_factory=list)
    eclo_change_terms: list[cp_model.LinearExpr] = field(default_factory=list)
    scenario_expr: cp_model.LinearExpr | int = 0
    reference_objective: int | None = None
    fixed_eclo: int = 0
    fixed_date_count: dict[date, int] = field(default_factory=lambda: defaultdict(int))
    fixed_week_count: dict[tuple[str, int], int] = field(default_factory=lambda: defaultdict(int))
    fixed_night_count: dict[tuple[str, int, int], int] = field(default_factory=lambda: defaultdict(int))


def _official_jobs(problem: ProblemInstance) -> list[ProjectJob]:
    return [
        ProjectJob(
            job_id=activity.activity_id,
            contract_number=activity.contract_number,
            activity_type=activity.activity_type,
            nature_of_activity=problem.contract(activity.contract_number).nature_of_activity,
            access_type=problem.contract(activity.contract_number).access_type,
            start_location_id=activity.start_location_id,
            end_location_id=activity.end_location_id,
            total_accesses=activity.total_accesses,
            planned_start_date=activity.planned_start_date,
            planned_completion_date=problem.contract(activity.contract_number).planned_completion_date,
            contract_priority=int(problem.contract(activity.contract_number).contract_priority),
            activity_priority=int(activity.activity_priority),
            number_of_workfronts=problem.contract(activity.contract_number).number_of_workfronts,
            number_of_maximum_access_per_week=problem.contract(activity.contract_number).number_of_maximum_access_per_week,
            predecessor_job_id=activity.predecessor_activity_id,
            source="official",
        )
        for activity in problem.activities
    ]


def _apply_changes(
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    request: ReplanRequest,
) -> tuple[list[ProjectJob], list[OperationalCalendarDay], set[str], dict[tuple[str, int], int]]:
    by_job = {job.job_id: job for job in jobs}
    calendar = {day.service_date: day for day in baseline.calendar}
    forced_locks: set[str] = set()
    supply_delta: dict[tuple[str, int], int] = defaultdict(int)
    for change in request.changes:
        if change.effective_at > request.as_of:
            continue
        if change.kind == "deadline" and change.job_id in by_job and change.new_deadline:
            by_job[change.job_id] = by_job[change.job_id].model_copy(update={"hard_completion_date": change.new_deadline})
        elif change.kind == "lock":
            if change.locked and change.job_id:
                forced_locks.update(
                    access.access_id
                    for access in baseline.project_accesses
                    if access.job_id == change.job_id
                )
        elif change.kind == "calendar_outage":
            for service_date in change.service_dates:
                if service_date in calendar:
                    calendar[service_date] = calendar[service_date].model_copy(update={"physical_available": False})
        elif change.kind == "supply_outage":
            for location_id in change.location_ids:
                for week in range(1, baseline.horizon_weeks + 1):
                    supply_delta[(location_id, week)] -= 1
    return list(by_job.values()), list(calendar.values()), forced_locks, supply_delta


def _fixed_and_slots(
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    request: ReplanRequest,
    forced_locks: set[str],
) -> tuple[list[ProjectAccess], list[_Slot]]:
    baseline_by_job: dict[str, list[ProjectAccess]] = defaultdict(list)
    for access in baseline.project_accesses:
        baseline_by_job[access.job_id].append(access)
    fixed: list[ProjectAccess] = []
    slots: list[_Slot] = []
    as_of_date = request.as_of.astimezone(ZoneInfo(baseline.timezone)).date()
    for job in jobs:
        job_rows = baseline_by_job.get(job.job_id, [])
        fixed_rows = [
            row for row in job_rows
            if row.locked or row.access_id in forced_locks or row.service_date <= as_of_date
        ]
        fixed.extend(fixed_rows)
        fixed_work = sum(2 + int(row.eclo) for row in fixed_rows)
        remaining = max(0, 2 * job.total_accesses - fixed_work)
        movable_rows = [row for row in job_rows if row not in fixed_rows]
        slot_count = max(len(movable_rows), ceil(remaining / 2))
        for index in range(slot_count):
            baseline_row = movable_rows[index] if index < len(movable_rows) else None
            access_id = baseline_row.access_id if baseline_row else f"{job.job_id}:ACCESS:{index + 1:03d}"
            slots.append(_Slot(slot_id=f"{job.job_id}:SLOT:{index + 1:03d}", job_id=job.job_id, access_id=access_id, baseline=baseline_row))
    return fixed, slots


def _week_for(bundle: BaselineBundle, service_date: date) -> int:
    return ((service_date - bundle.horizon_start).days // 7) + 1


def _build_model(
    problem: ProblemInstance,
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    fixed: list[ProjectAccess],
    slots: list[_Slot],
    scenario: ScheduleScenario,
    calendar: list[OperationalCalendarDay],
    supply_delta: dict[tuple[str, int], int],
    *,
    scenario_bound: int | None = None,
    disruption_objective: bool = False,
    optimize: bool = True,
) -> _Artifacts:
    model = cp_model.CpModel()
    topology = None
    core_by_job: dict[str, tuple[str, ...]] = {}
    for job in jobs:
        try:
            core_by_job[job.job_id] = project_core_locations(job, problem, topology)
        except (KeyError, ValueError):
            core_by_job[job.job_id] = ()
    calendar_by_week: dict[int, list[OperationalCalendarDay]] = defaultdict(list)
    horizon_end = baseline.horizon_start + timedelta(days=baseline.horizon_weeks * 7 - 1)
    for day in calendar:
        week = _week_for(baseline, day.service_date)
        if 1 <= week <= baseline.horizon_weeks and baseline.horizon_start <= day.service_date <= horizon_end:
            calendar_by_week[week].append(day)
    for days in calendar_by_week.values():
        days.sort(key=lambda item: item.service_date)

    artifacts = _Artifacts(
        model=model,
        scenario=scenario,
        jobs={job.job_id: job for job in jobs},
        slots=slots,
        fixed=fixed,
        core_by_job=core_by_job,
        calendar_by_week=calendar_by_week,
    )
    fixed_by_location_week_group: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for access in fixed:
        job = next((item for item in jobs if item.job_id == access.job_id), None)
        if job is not None and access.access_night > job.number_of_maximum_access_per_week:
            model.add(0 == 1)
        if scenario == ScheduleScenario.A and access.eclo:
            model.add(0 == 1)
        artifacts.fixed_eclo += int(access.eclo)
        artifacts.fixed_date_count[access.service_date] += 1
        artifacts.fixed_week_count[(access.job_id, access.week)] += 1
        artifacts.fixed_night_count[(access.job_id, access.week, access.access_night)] += 1
        for location_id, group in access.group_by_location.items():
            fixed_by_location_week_group[(location_id, access.week, group)].add(access.job_id)

    # The maintenance closure is an explicit operational protection policy.
    blocked_by_date: dict[date, set[str]] = defaultdict(set)
    for visit in baseline.maintenance_visits:
        blocked_by_date[visit.service_date].update(maintenance_closure_locations(problem, visit.sector_id))

    job_slots: dict[str, list[_Slot]] = defaultdict(list)
    for slot in slots:
        job_slots[slot.job_id].append(slot)

    # Candidate group labels are scoped to one location and week.  NEW labels
    # are symmetry placeholders; they are never used for disruption accounting.
    dynamic_group_roles: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for slot in slots:
        for location_id in core_by_job.get(slot.job_id, ()):
            role = artifacts.jobs[slot.job_id].access_type.value
            dynamic_group_roles[location_id][role] += 1
    groups_by_location_week: dict[tuple[str, int], list[str]] = {}
    for location in problem.locations:
        for week in range(1, baseline.horizon_weeks + 1):
            fixed_names = sorted({group for (loc, wk, group) in fixed_by_location_week_group if loc == location.location_id and wk == week})
            supply = location.supply_capacity + supply_delta.get((location.location_id, week), 0)
            roles = dynamic_group_roles[location.location_id]
            if scenario == ScheduleScenario.A:
                count = max(len(fixed_names), supply)
            elif scenario == ScheduleScenario.C:
                count = max(len(fixed_names), supply + 1)
            else:
                # PM is alone, PC can host at most three C, and C-only
                # groups host up to four.  This is a safe legal-mix upper
                # bound and avoids one symmetry variable per candidate slot.
                count = len(fixed_names) + roles.get("PM", 0) + roles.get("PC", 0) + ceil(roles.get("C", 0) / 4)
            count = max(0, count)
            groups_by_location_week[(location.location_id, week)] = fixed_names + [f"NEW:{index}" for index in range(count - len(fixed_names))]

    # Access placement, exact calendar date choice and local-night allocation.
    for slot in slots:
        job = artifacts.jobs[slot.job_id]
        active = model.new_bool_var(f"active[{slot.slot_id}]")
        eclo = model.new_bool_var(f"eclo[{slot.slot_id}]")
        artifacts.active[slot.slot_id] = active
        artifacts.eclo[slot.slot_id] = eclo
        model.add(eclo <= active)
        if scenario == ScheduleScenario.A:
            model.add(eclo == 0)
        x_vars: list[cp_model.IntVar] = []
        for week in range(1, baseline.horizon_weeks + 1):
            x = model.new_bool_var(f"x[{slot.slot_id},{week}]")
            artifacts.x[(slot.slot_id, week)] = x
            x_vars.append(x)
            model.add(x <= active)
            valid_days: list[OperationalCalendarDay] = []
            if job.effective_release_date <= baseline.horizon_start + timedelta(days=week * 7 - 1):
                valid_days = [
                    day for day in calendar_by_week.get(week, [])
                    if day.eligible and day.physical_available and day.service_date >= job.effective_release_date
                ]
            if scenario == ScheduleScenario.B:
                valid_days = [day for day in valid_days if day.service_date <= job.effective_deadline]
            date_vars: list[cp_model.IntVar] = []
            for day in valid_days:
                variable = model.new_bool_var(f"date[{slot.slot_id},{day.service_date.isoformat()}]")
                artifacts.date_choice[(slot.slot_id, week, day.service_date)] = variable
                date_vars.append(variable)
                if day.service_date in blocked_by_date and set(core_by_job.get(job.job_id, ())) & blocked_by_date[day.service_date]:
                    model.add(variable == 0)
                if not day.eclo_eligible:
                    model.add(variable + eclo <= 1)
            if date_vars:
                model.add(sum(date_vars) == x)
            else:
                model.add(x == 0)
            for location_id in core_by_job.get(job.job_id, ()):
                group_names = groups_by_location_week[(location_id, week)]
                assignments: list[cp_model.IntVar] = []
                for group_name in group_names:
                    variable = model.new_bool_var(f"group[{slot.slot_id},{week},{location_id},{group_name}]")
                    artifacts.group[(slot.slot_id, week, location_id, group_name)] = variable
                    assignments.append(variable)
                model.add(sum(assignments) == x)
        model.add(sum(x_vars) == active)
        nights = []
        for night in range(1, job.number_of_maximum_access_per_week + 1):
            variable = model.new_bool_var(f"night[{slot.slot_id},{night}]")
            artifacts.night[(slot.slot_id, night)] = variable
            nights.append(variable)
        model.add(sum(nights) == active)

        if slot.baseline is not None:
            baseline_row = slot.baseline
            changed = model.new_bool_var(f"changed[{slot.slot_id}]")
            artifacts.changed[slot.slot_id] = changed
            original_week = baseline_row.week
            if (slot.slot_id, original_week) in artifacts.x:
                model.add(changed >= 1 - artifacts.x[(slot.slot_id, original_week)])
            original_date_var = artifacts.date_choice.get((slot.slot_id, original_week, baseline_row.service_date))
            if original_date_var is not None:
                model.add(changed >= 1 - original_date_var)
            else:
                model.add(changed == 1)
            if baseline_row.eclo:
                model.add(changed >= 1 - eclo)
            else:
                model.add(changed >= eclo)
            artifacts.displacement_terms.extend(
                abs((day_date - baseline_row.service_date).days) * variable
                for (sid, _week, day_date), variable in artifacts.date_choice.items()
                if sid == slot.slot_id
            )
            artifacts.eclo_change_terms.append(eclo if not baseline_row.eclo else 1 - eclo)

    # Each activity receives at most one access per official week.
    for job in jobs:
        for week in range(1, baseline.horizon_weeks + 1):
            fixed_count = artifacts.fixed_week_count.get((job.job_id, week), 0)
            model.add(sum(artifacts.x[(slot.slot_id, week)] for slot in job_slots[job.job_id]) + fixed_count <= 1)
        fixed_work = sum(2 + int(row.eclo) for row in fixed if row.job_id == job.job_id)
        remaining_work = max(0, 2 * job.total_accesses - fixed_work)
        model.add(
            2 * sum(artifacts.active[slot.slot_id] for slot in job_slots[job.job_id])
            + sum(artifacts.eclo[slot.slot_id] for slot in job_slots[job.job_id])
            >= remaining_work
        )

    # Exact weekly local-night assignment and workfront limits.
    for slot in slots:
        job = artifacts.jobs[slot.job_id]
        for week in range(1, baseline.horizon_weeks + 1):
            for night in range(1, job.number_of_maximum_access_per_week + 1):
                variable = model.new_bool_var(f"week_night[{slot.slot_id},{week},{night}]")
                # Keep it equivalent to x and the slot's local-night choice.
                model.add(variable <= artifacts.x[(slot.slot_id, week)])
                model.add(variable <= artifacts.night[(slot.slot_id, night)])
                model.add(variable >= artifacts.x[(slot.slot_id, week)] + artifacts.night[(slot.slot_id, night)] - 1)
                artifacts.group[(slot.slot_id, week, "__night__", str(night))] = variable
            model.add(sum(artifacts.group[(slot.slot_id, week, "__night__", str(night))] for night in range(1, job.number_of_maximum_access_per_week + 1)) == artifacts.x[(slot.slot_id, week)])
    for job in jobs:
        for week in range(1, baseline.horizon_weeks + 1):
            for night in range(1, job.number_of_maximum_access_per_week + 1):
                model.add(
                    sum(artifacts.group[(slot.slot_id, week, "__night__", str(night))] for slot in job_slots[job.job_id])
                    + artifacts.fixed_night_count.get((job.job_id, week, night), 0)
                    <= job.number_of_workfronts
                )

    # Possession legal-mix and capacity constraints.
    for location in problem.locations:
        location_id = location.location_id
        for week in range(1, baseline.horizon_weeks + 1):
            for group_name in groups_by_location_week[(location_id, week)]:
                members = fixed_by_location_week_group.get((location_id, week, group_name), set())
                used = model.new_bool_var(f"used[{location_id},{week},{group_name}]")
                artifacts.group_used[(location_id, week, group_name)] = used
                dynamic = [
                    artifacts.group[(slot.slot_id, week, location_id, group_name)]
                    for slot in slots
                    if (slot.slot_id, week, location_id, group_name) in artifacts.group
                ]
                if members:
                    model.add(used == 1)
                elif dynamic:
                    model.add(sum(dynamic) >= used)
                    model.add(sum(dynamic) <= len(dynamic) * used)
                else:
                    model.add(used == 0)
                fixed_roles = [artifacts.jobs[job_id].access_type for job_id in members if job_id in artifacts.jobs]
                pm = sum(1 for role in fixed_roles if role.value == "PM")
                pc = sum(1 for role in fixed_roles if role.value == "PC")
                c = sum(1 for role in fixed_roles if role.value == "C")
                pm_expr = pm + sum(artifacts.group[(slot.slot_id, week, location_id, group_name)] for slot in slots if (slot.slot_id, week, location_id, group_name) in artifacts.group and artifacts.jobs[slot.job_id].access_type.value == "PM")
                pc_expr = pc + sum(artifacts.group[(slot.slot_id, week, location_id, group_name)] for slot in slots if (slot.slot_id, week, location_id, group_name) in artifacts.group and artifacts.jobs[slot.job_id].access_type.value == "PC")
                c_expr = c + sum(artifacts.group[(slot.slot_id, week, location_id, group_name)] for slot in slots if (slot.slot_id, week, location_id, group_name) in artifacts.group and artifacts.jobs[slot.job_id].access_type.value == "C")
                model.add(pm_expr + pc_expr <= used)
                model.add(pc_expr + c_expr <= 4 * used)
                model.add(c_expr + 4 * pm_expr <= 4 * used)
            supply = max(0, location.supply_capacity + supply_delta.get((location_id, week), 0))
            used_vars = [artifacts.group_used[(location_id, week, group)] for group in groups_by_location_week[(location_id, week)]]
            excess = model.new_int_var(0, len(used_vars), f"excess[{location_id},{week}]")
            artifacts.excess[(location_id, week)] = excess
            model.add_max_equality(excess, [0, sum(used_vars) - supply])
            if scenario == ScheduleScenario.A:
                model.add(excess == 0)
            elif scenario == ScheduleScenario.C:
                model.add(excess <= 1)

    # Last-week/lateness and hard precedence/deadline rules.
    for job in jobs:
        fixed_last = max((row.week for row in fixed if row.job_id == job.job_id), default=0)
        last = model.new_int_var(0, baseline.horizon_weeks, f"last_week[{job.job_id}]")
        artifacts.last_week[job.job_id] = last
        values: list[cp_model.LinearExpr | int] = [fixed_last]
        values.extend(week * artifacts.x[(slot.slot_id, week)] for slot in job_slots[job.job_id] for week in range(1, baseline.horizon_weeks + 1))
        model.add_max_equality(last, values)
        if scenario == ScheduleScenario.B:
            deadline = job.effective_deadline
            for slot in job_slots[job.job_id]:
                for week in range(1, baseline.horizon_weeks + 1):
                    if baseline.horizon_start + timedelta(days=week * 7 - 1) > deadline:
                        model.add(artifacts.x[(slot.slot_id, week)] == 0)
            if any(row.service_date > deadline for row in fixed if row.job_id == job.job_id):
                model.add(0 == 1)
        if job.predecessor_job_id and job.predecessor_job_id in artifacts.last_week:
            pred_last = artifacts.last_week[job.predecessor_job_id]
            for slot in job_slots[job.job_id]:
                for week in range(1, baseline.horizon_weeks + 1):
                    successor_selected = artifacts.x[(slot.slot_id, week)]
                    model.add(
                        pred_last + successor_selected
                        <= week + baseline.horizon_weeks * (1 - successor_selected)
                    )
            fixed_successor_first = min((row.week for row in fixed if row.job_id == job.job_id), default=None)
            if fixed_successor_first is not None:
                model.add(pred_last < fixed_successor_first)

    # Scenario C chooses an independent two-week ECLO span per affected line.
    if scenario == ScheduleScenario.C:
        lines = sorted({job_line_code(job) for job in jobs})
        window_vars: dict[tuple[str, int], cp_model.IntVar] = {}
        for line in lines:
            for start in range(1, baseline.horizon_weeks + 1):
                window_vars[(line, start)] = model.new_bool_var(f"eclo_window[{line},{start}]")
            model.add(sum(window_vars[(line, start)] for start in range(1, baseline.horizon_weeks + 1)) == 1)
        for access in fixed:
            if access.eclo and access.job_id in artifacts.jobs:
                line = job_line_code(artifacts.jobs[access.job_id])
                allowed = sum(
                    window_vars[(line, start)]
                    for start in range(1, baseline.horizon_weeks + 1)
                    if access.week in (start, start + 1)
                )
                model.add(allowed == 1)
        for slot in slots:
            line = job_line_code(artifacts.jobs[slot.job_id])
            for week in range(1, baseline.horizon_weeks + 1):
                allowed = sum(window_vars[(line, start)] for start in range(1, baseline.horizon_weeks + 1) if week in (start, start + 1))
                model.add(artifacts.eclo[slot.slot_id] + artifacts.x[(slot.slot_id, week)] <= 1 + allowed)

    # Date capacity and fixed access protection.
    for week, days in calendar_by_week.items():
        for day in days:
            date_vars = [variable for (slot_id, _week, service_date), variable in artifacts.date_choice.items() if service_date == day.service_date]
            model.add(sum(date_vars) + artifacts.fixed_date_count.get(day.service_date, 0) <= day.gross_capacity)

    p_terms: list[cp_model.LinearExpr] = []
    for job in jobs:
        deadline_offset = (job.planned_completion_date - baseline.horizon_start).days
        lateness = model.new_int_var(0, max(0, baseline.horizon_weeks * 7), f"lateness[{job.job_id}]")
        model.add_max_equality(lateness, [0, 7 * artifacts.last_week[job.job_id] - 1 - deadline_offset])
        coefficient = {1: 100, 2: 10, 3: 1}[job.contract_priority] * (10 + (3 if job.activity_priority == 1 else 2 if job.activity_priority == 2 else 0))
        p_terms.append(coefficient * lateness)
    p_expr: cp_model.LinearExpr | int = sum(p_terms) if p_terms else 0
    eclo_expr = artifacts.fixed_eclo + sum(artifacts.eclo.values())
    excess_expr = sum(artifacts.excess.values())
    if scenario == ScheduleScenario.A:
        scenario_expr: cp_model.LinearExpr | int = p_expr
    elif scenario == ScheduleScenario.B:
        scenario_expr = 70 * excess_expr + 50 * eclo_expr
    else:
        scenario_expr = p_expr + 70 * excess_expr + 50 * eclo_expr
    artifacts.scenario_expr = scenario_expr
    if scenario_bound is not None:
        model.add(scenario_expr <= scenario_bound)

    if disruption_objective:
        # The scaling keeps the stated lexicographic order exact while leaving
        # scenario cost as the final tie-breaker.
        max_scenario = max(1, len(jobs) * 100 * baseline.horizon_weeks * 7 + len(slots) * 50 + len(artifacts.excess) * 70)
        max_eclo = max(1, len(slots) + 1)
        max_displacement = max(1, len(slots) * baseline.horizon_weeks * 7)
        w_eclo = max_scenario + 1
        w_displacement = (max_eclo + 1) * w_eclo
        w_visits = (max_displacement + 1) * w_displacement
        w_jobs = (len(slots) + 1) * w_visits
        for job_id in {slot.job_id for slot in slots}:
            changed_vars = [artifacts.changed[slot.slot_id] for slot in slots if slot.job_id == job_id and slot.slot_id in artifacts.changed]
            job_changed = model.new_bool_var(f"job_changed[{job_id}]")
            artifacts.job_changed[job_id] = job_changed
            for changed in changed_vars:
                model.add(job_changed >= changed)
            if changed_vars:
                model.add(job_changed <= sum(changed_vars))
        secondary = (
            w_jobs * sum(artifacts.job_changed.values())
            + w_visits * sum(artifacts.changed.values())
            + w_displacement * sum(artifacts.displacement_terms)
            + w_eclo * sum(artifacts.eclo_change_terms)
            + scenario_expr
        )
        model.minimize(secondary)
    elif optimize:
        model.minimize(scenario_expr)
    return artifacts


def _solver(options: SolveOptions, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.01, seconds)
    solver.parameters.num_search_workers = options.num_search_workers
    solver.parameters.random_seed = options.random_seed
    solver.parameters.cp_model_presolve = True
    return solver


def _candidate_from_solution(
    problem: ProblemInstance,
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    fixed: list[ProjectAccess],
    artifacts: _Artifacts,
    solver: cp_model.CpSolver,
    request: ReplanRequest,
    status: str,
    runtime: float,
) -> CandidateSchedule:
    global_night_by_date = {
        day.service_date: day.global_night_id
        for days in artifacts.calendar_by_week.values()
        for day in days
    }
    rows = [
        row.model_copy(update={"global_night_id": global_night_by_date.get(row.service_date)})
        if row.global_night_id is None else row
        for row in fixed
    ]
    for slot in artifacts.slots:
        if solver.value(artifacts.active[slot.slot_id]) == 0:
            continue
        selected_week = next((week for week in range(1, baseline.horizon_weeks + 1) if solver.value(artifacts.x[(slot.slot_id, week)])), None)
        if selected_week is None:
            continue
        selected_date = next((service_date for (slot_id, _week, service_date), variable in artifacts.date_choice.items() if slot_id == slot.slot_id and _week == selected_week and solver.value(variable)), None)
        if selected_date is None:
            continue
        selected_night = next((night for night in range(1, artifacts.jobs[slot.job_id].number_of_maximum_access_per_week + 1) if solver.value(artifacts.group[(slot.slot_id, selected_week, "__night__", str(night))])), 1)
        groups: dict[str, str] = {}
        for location_id in artifacts.core_by_job.get(slot.job_id, ()):
            group_names = [key[3] for key in artifacts.group if key[0] == slot.slot_id and key[1] == selected_week and key[2] == location_id]
            selected_group = next((group for group in group_names if solver.value(artifacts.group[(slot.slot_id, selected_week, location_id, group)])), None)
            if selected_group:
                groups[location_id] = selected_group
        rows.append(ProjectAccess(
            access_id=slot.access_id,
            job_id=slot.job_id,
            access_seq=1,
            week=selected_week,
            service_date=selected_date,
            global_night_id=global_night_by_date.get(selected_date),
            eclo=bool(solver.value(artifacts.eclo[slot.slot_id])),
            access_night=selected_night,
            group_by_location=groups,
            locked=False,
        ))
    rows.sort(key=lambda row: (row.job_id, row.service_date, row.access_id))
    sequenced: list[ProjectAccess] = []
    for job_id in sorted({row.job_id for row in rows}):
        job_rows = [row for row in rows if row.job_id == job_id]
        for sequence, row in enumerate(job_rows, start=1):
            sequenced.append(row.model_copy(update={"access_seq": sequence}))
    cost = compute_scenario_cost(problem, baseline, jobs, sequenced, request.scenario)
    cost = cost.model_copy(update={"best_known": status in ("OPTIMAL", "FEASIBLE"), "proof_status": "proven" if status == "OPTIMAL" else "best_known" if status == "FEASIBLE" else "unknown"})
    disruption = compute_disruption(baseline, sequenced)
    frozen_ids = {row.access_id for row in fixed}
    validation = validate_operational_schedule(problem, baseline, jobs, sequenced, request.scenario, frozen_access_ids=frozen_ids)
    return CandidateSchedule(
        status=status, projects=sequenced, maintenance_visits=list(baseline.maintenance_visits), cost=cost,
        disruption=disruption, validation=validation, runtime_seconds=runtime,
        objective_bound=(solver.best_objective_bound / 10 if status in ("OPTIMAL", "FEASIBLE") else None),
        relative_gap=None,
    )


def _solve_candidate(
    problem: ProblemInstance,
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    fixed: list[ProjectAccess],
    slots: list[_Slot],
    request: ReplanRequest,
    calendar: list[OperationalCalendarDay],
    supply_delta: dict[tuple[str, int], int],
    seconds: float,
    *,
    scenario_bound: int | None = None,
    disruption_objective: bool = False,
) -> tuple[CandidateSchedule | None, int | None, str]:
    artifacts = _build_model(
        problem,
        baseline,
        jobs,
        fixed,
        slots,
        request.scenario,
        calendar,
        supply_delta,
        scenario_bound=scenario_bound,
        disruption_objective=disruption_objective,
        optimize=request.options.optimize or disruption_objective,
    )
    solver = _solver(request.options, seconds)
    started = monotonic()
    raw_status = solver.solve(artifacts.model)
    runtime = monotonic() - started
    status_map = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE", cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN", cp_model.MODEL_INVALID: "UNKNOWN"}
    status = status_map.get(raw_status, "UNKNOWN")
    if raw_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None, status
    candidate = _candidate_from_solution(problem, baseline, jobs, fixed, artifacts, solver, request, status, runtime)
    return candidate, int(round(solver.objective_value)), status


def _calendarized_official_seed(
    problem: ProblemInstance,
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    request: ReplanRequest,
    seconds: float,
) -> CandidateSchedule | None:
    """Calendarize a canonical weekly incumbent for a clean initial baseline.

    This bounded bridge is deliberately narrow: it is used only before any
    operational project accesses or additions exist.  It lets the operational
    layer obtain a complete incumbent for the public 54-activity starting
    instance; every later replan, emergency and disruption comparison uses
    the new engine's model above.
    """

    if baseline.project_accesses or baseline.project_jobs or request.additions:
        return None
    try:
        from backend.app.ps1.models import PS1SolveOptions, Scenario as OfficialScenario
        from backend.app.ps1.solver import solve_ps1
    except ImportError:
        return None
    official = solve_ps1(
        problem,
        OfficialScenario(request.scenario.value),
        PS1SolveOptions(
            time_limit_seconds=max(0.1, seconds),
            feasibility_time_limit_seconds=max(0.1, min(seconds * 0.25, seconds)),
            num_search_workers=request.options.num_search_workers,
            random_seed=request.options.random_seed,
            optimize=True,
        ),
    )
    if not official.has_incumbent:
        return None
    job_by_id = {job.job_id: job for job in jobs}
    occupancy_by_key = {
        (row.activity_id, row.week, row.location_id): row.co_share_group
        for row in official.occupancy_rows
    }
    calendar_by_week: dict[int, list[OperationalCalendarDay]] = defaultdict(list)
    for day in baseline.calendar:
        week = _week_for(baseline, day.service_date)
        if 1 <= week <= baseline.horizon_weeks and day.eligible and day.physical_available:
            calendar_by_week[week].append(day)
    for days in calendar_by_week.values():
        days.sort(key=lambda day: day.service_date)
    blocked_by_date: dict[date, set[str]] = defaultdict(set)
    for visit in baseline.maintenance_visits:
        blocked_by_date[visit.service_date].update(maintenance_closure_locations(problem, visit.sector_id))
    used_by_date: dict[date, int] = defaultdict(int)
    accesses: list[ProjectAccess] = []
    for row in sorted(official.access_rows, key=lambda item: (item.week, item.activity_id, item.access_seq)):
        job = job_by_id.get(row.activity_id)
        if job is None:
            return None
        core = set(project_core_locations(job, problem))
        selected_day = next(
            (
                day for day in calendar_by_week.get(row.week, [])
                if (not row.eclo or day.eclo_eligible)
                and not core & blocked_by_date.get(day.service_date, set())
                and used_by_date[day.service_date] < day.gross_capacity
            ),
            None,
        )
        if selected_day is None:
            return None
        used_by_date[selected_day.service_date] += 1
        groups = {
            location_id: occupancy_by_key[(row.activity_id, row.week, location_id)]
            for location_id in core
            if (row.activity_id, row.week, location_id) in occupancy_by_key
        }
        accesses.append(
            ProjectAccess(
                access_id=f"{row.activity_id}:ACCESS:{row.access_seq:03d}",
                job_id=row.activity_id,
                access_seq=row.access_seq,
                week=row.week,
                service_date=selected_day.service_date,
                global_night_id=selected_day.global_night_id,
                eclo=row.eclo,
                access_night=row.access_night,
                group_by_location=groups,
            )
        )
    validation = validate_operational_schedule(problem, baseline, jobs, accesses, request.scenario)
    if not validation.passed:
        return None
    status = official.status.value
    official_metrics = official.solve_metrics
    cost = compute_scenario_cost(problem, baseline, jobs, accesses, request.scenario).model_copy(
        update={
            "best_known": True,
            "proof_status": "proven" if status == "OPTIMAL" else "best_known",
        }
    )
    return CandidateSchedule(
        status=status if status in ("OPTIMAL", "FEASIBLE") else "FEASIBLE",
        projects=accesses,
        maintenance_visits=list(baseline.maintenance_visits),
        cost=cost,
        disruption=compute_disruption(baseline, accesses),
        validation=validation,
        runtime_seconds=official_metrics.wall_time_seconds,
        objective_bound=official_metrics.objective_bound_score,
        relative_gap=official_metrics.relative_gap,
    )


def _validated_baseline_seed(
    problem: ProblemInstance,
    baseline: BaselineBundle,
    jobs: list[ProjectJob],
    request: ReplanRequest,
) -> CandidateSchedule | None:
    """Retain a complete validated baseline when a bounded replan finds no incumbent."""

    if not baseline.project_accesses or request.additions or request.changes:
        return None
    validation = validate_operational_schedule(
        problem,
        baseline,
        jobs,
        baseline.project_accesses,
        request.scenario,
    )
    if not validation.passed:
        return None
    cost = compute_scenario_cost(
        problem,
        baseline,
        jobs,
        baseline.project_accesses,
        request.scenario,
    ).model_copy(update={"best_known": False, "proof_status": "unknown"})
    return CandidateSchedule(
        status="FEASIBLE",
        projects=list(baseline.project_accesses),
        maintenance_visits=list(baseline.maintenance_visits),
        cost=cost,
        disruption=compute_disruption(baseline, baseline.project_accesses),
        validation=validation,
        runtime_seconds=0.0,
    )


def solve_schedule_insertion(
    problem: ProblemInstance,
    baseline: BaselineBundle,
    request: ReplanRequest,
    *,
    config: ScheduleInsertionConfig | None = None,
) -> ScheduleInsertionResult:
    """Solve reference scenario cost, then low-disruption within allowance."""

    config = config or ScheduleInsertionConfig(horizon_weeks=baseline.horizon_weeks)
    if request.baseline_id != baseline.baseline_id or request.baseline_revision != baseline.revision:
        return ScheduleInsertionResult(
            baseline_id=baseline.baseline_id,
            baseline_revision=baseline.revision,
            scenario=request.scenario,
            status="FAILED",
            configuration=config.model_dump(mode="json"),
            conflict_evidence=[],
        )
    jobs = _official_jobs(problem)
    known_job_ids = {job.job_id for job in jobs}
    jobs.extend(job for job in baseline.project_jobs if job.job_id not in known_job_ids)
    additions = [addition.job.model_copy(update={"source": addition.requested_source}) for addition in request.additions]
    existing_ids = {job.job_id for job in jobs}
    jobs.extend(job for job in additions if job.job_id not in existing_ids)
    jobs, calendar, forced_locks, supply_delta = _apply_changes(baseline, jobs, request)
    fixed, slots = _fixed_and_slots(baseline, jobs, request, forced_locks)
    retained_baseline = _validated_baseline_seed(problem, baseline, jobs, request)
    total_budget = request.options.time_limit_seconds
    reference_seconds = max(0.05, total_budget * 0.60)
    if len(jobs) > 20 and not baseline.project_accesses and not baseline.project_jobs and not request.additions:
        seed = _calendarized_official_seed(problem, baseline, jobs, request, total_budget * 0.80)
        if seed is not None:
            return ScheduleInsertionResult(
                baseline_id=baseline.baseline_id,
                baseline_revision=baseline.revision,
                scenario=request.scenario,
                status="SUCCEEDED",
                reference_candidate=seed,
                published_candidate="reference",
                configuration={**config.model_dump(mode="json"), "engine_mode": "calendarized_weekly_incumbent"},
            )
    reference, reference_objective, reference_status = _solve_candidate(problem, baseline, jobs, fixed, slots, request, calendar, supply_delta, reference_seconds)
    if reference is None:
        if retained_baseline is not None and reference_status == "UNKNOWN":
            return ScheduleInsertionResult(
                baseline_id=baseline.baseline_id,
                baseline_revision=baseline.revision,
                scenario=request.scenario,
                status="SUCCEEDED",
                reference_candidate=retained_baseline,
                published_candidate="reference",
                configuration={
                    **config.model_dump(mode="json"),
                    "engine_mode": "retained_validated_baseline",
                    "solver_outcome": reference_status,
                },
            )
        return ScheduleInsertionResult(
            baseline_id=baseline.baseline_id,
            baseline_revision=baseline.revision,
            scenario=request.scenario,
            status="INFEASIBLE" if reference_status == "INFEASIBLE" else "UNKNOWN",
            configuration=config.model_dump(mode="json"),
            conflict_evidence=[],
        )
    lower: CandidateSchedule | None = None
    remaining = max(0.05, total_budget - reference_seconds)
    allowance = 0 if request.options.strict_scenario_cost else min(request.options.scenario_cost_allowance, config.scenario_cost_allowance)
    if request.options.optimize and remaining > 0.05:
        bound = int(round(reference.cost.objective_scaled + allowance * 10))
        lower, _, _ = _solve_candidate(problem, baseline, jobs, fixed, slots, request, calendar, supply_delta, remaining, scenario_bound=bound, disruption_objective=True)
        if lower is not None and (not lower.validation.passed or disruption_key(lower.disruption, lower.cost) >= disruption_key(reference.disruption, reference.cost)):
            # Keep the candidate available for audit, but only publish it when
            # it actually improves the documented lexicographic tie-breakers.
            pass
    published = "reference"
    if lower is not None and lower.validation.passed and disruption_key(lower.disruption, lower.cost) < disruption_key(reference.disruption, reference.cost):
        published = "lower_disruption"
    if not reference.validation.passed:
        return ScheduleInsertionResult(
            baseline_id=baseline.baseline_id,
            baseline_revision=baseline.revision,
            scenario=request.scenario,
            status="FAILED",
            reference_candidate=reference,
            lower_disruption_candidate=lower,
            published_candidate="none",
            configuration=config.model_dump(mode="json"),
            conflict_evidence=reference.validation.findings,
        )
    return ScheduleInsertionResult(
        baseline_id=baseline.baseline_id,
        baseline_revision=baseline.revision,
        scenario=request.scenario,
        status="SUCCEEDED",
        reference_candidate=reference,
        lower_disruption_candidate=lower,
        published_candidate=published,
        configuration=config.model_dump(mode="json"),
    )
