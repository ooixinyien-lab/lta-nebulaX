"""Independent PS1 score, completion, and ECLO summary reconstruction."""

from __future__ import annotations

from collections import defaultdict

from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    ProblemInstance,
    ScenarioResultRow,
)
from backend.app.ps1.models import (
    ECLOAccessDetail,
    ECLOLineSummary,
    ECLOSummary,
    ECLOWeekSummary,
    ECLOWindow,
    Scenario,
    ScoreBreakdown,
    coerce_scenario,
)
from backend.app.topology import FootprintCache


class ScheduleEvaluationError(ValueError):
    """Raised when score reconstruction cannot be performed safely."""


_ACTIVITY_NUDGE_TENTHS = {1: 3, 2: 2, 3: 0}


def activity_lateness_days(
    problem: ProblemInstance,
    activity_id: str,
    last_week: int,
) -> int:
    """Return exact calendar-day lateness against the planned deadline."""

    activity = problem.activity(activity_id)
    contract = problem.contract(activity.contract_number)
    finish = problem.parameters.week_end_date(last_week)
    return max(0, (finish - contract.planned_completion_date).days)


def affected_line_codes(
    problem: ProblemInstance,
    footprints: FootprintCache,
    activity_id: str,
) -> list[str]:
    """Return every line whose protection is affected by an activity."""

    core = footprints.get_core_footprint(activity_id)
    protection = footprints.get_protection_footprint(activity_id)
    result = {core.line_code}
    for location_id in protection.cross_line_locations:
        parts = location_id.split(":")
        if len(parts) >= 2:
            result.add(parts[1])
    return sorted(result)


def compute_score(
    problem: ProblemInstance,
    scenario: Scenario | str,
    access_rows: list[AccessScheduleRow],
    occupancy_rows: list[OccupancyScheduleRow],
) -> ScoreBreakdown:
    """Reconstruct the exact scenario objective from exported schedule rows."""

    selected_scenario = coerce_scenario(scenario)
    weeks_by_activity: dict[str, list[int]] = defaultdict(list)
    for row in access_rows:
        if row.activity_id not in problem._activities_by_id:
            raise ScheduleEvaluationError(f"Unknown activity in access schedule: {row.activity_id}")
        weeks_by_activity[row.activity_id].append(row.week)

    missing = [
        activity.activity_id
        for activity in problem.activities
        if not weeks_by_activity.get(activity.activity_id)
    ]
    if missing:
        raise ScheduleEvaluationError(
            "Cannot score an incomplete schedule; missing accesses for " + ", ".join(missing)
        )

    weighted_lateness_scaled = 0
    for activity in problem.activities:
        last_week = max(weeks_by_activity[activity.activity_id])
        late_days = activity_lateness_days(problem, activity.activity_id, last_week)
        contract = problem.contract(activity.contract_number)
        coefficient = contract.score_weight * (
            10 + _ACTIVITY_NUDGE_TENTHS[int(activity.activity_priority)]
        )
        weighted_lateness_scaled += coefficient * late_days

    occupied_groups: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in occupancy_rows:
        if row.location_id not in problem._locations_by_id:
            raise ScheduleEvaluationError(
                f"Unknown location in occupancy schedule: {row.location_id}"
            )
        occupied_groups[(row.location_id, row.week)].add(row.co_share_group)

    excess_slots = 0
    for (location_id, _week), groups in occupied_groups.items():
        supply = problem.location(location_id).supply_capacity
        excess_slots += max(0, len(groups) - supply)

    eclo_accesses = sum(1 for row in access_rows if row.eclo)
    excess_penalty_scaled = 70 * excess_slots
    eclo_penalty_scaled = 50 * eclo_accesses

    if selected_scenario == Scenario.A:
        objective_scaled = weighted_lateness_scaled
    elif selected_scenario == Scenario.B:
        objective_scaled = excess_penalty_scaled + eclo_penalty_scaled
    else:
        objective_scaled = (
            weighted_lateness_scaled + excess_penalty_scaled + eclo_penalty_scaled
        )

    return ScoreBreakdown(
        weighted_activity_lateness_scaled=weighted_lateness_scaled,
        weighted_activity_lateness=weighted_lateness_scaled / 10,
        excess_slots=excess_slots,
        eclo_accesses=eclo_accesses,
        excess_penalty_scaled=excess_penalty_scaled,
        eclo_penalty_scaled=eclo_penalty_scaled,
        objective_scaled=objective_scaled,
        objective_score=objective_scaled / 10,
    )


def build_contract_results(
    problem: ProblemInstance,
    scenario: Scenario | str,
    access_rows: list[AccessScheduleRow],
) -> list[ScenarioResultRow]:
    """Derive official RESULTS.csv rows from the actual access schedule."""

    selected_scenario = coerce_scenario(scenario)
    weeks_by_activity: dict[str, list[int]] = defaultdict(list)
    for row in access_rows:
        weeks_by_activity[row.activity_id].append(row.week)

    rows: list[ScenarioResultRow] = []
    for contract in sorted(problem.contracts, key=lambda item: item.contract_number):
        activity_ids = [
            activity.activity_id
            for activity in problem.activities
            if activity.contract_number == contract.contract_number
        ]
        if not activity_ids or any(not weeks_by_activity.get(aid) for aid in activity_ids):
            raise ScheduleEvaluationError(
                f"Cannot derive completion for contract {contract.contract_number}: "
                "one or more activities have no accesses"
            )
        last_week = max(max(weeks_by_activity[aid]) for aid in activity_ids)
        completion = problem.parameters.week_end_date(last_week)
        rows.append(
            ScenarioResultRow(
                scenario=selected_scenario.value,
                contract_number=contract.contract_number,
                simulated_completion_date=completion,
                overrun_days=max(0, (completion - contract.planned_completion_date).days),
            )
        )
    return rows


def build_eclo_summary(
    problem: ProblemInstance,
    scenario: Scenario | str,
    access_rows: list[AccessScheduleRow],
    footprints: FootprintCache,
    selected_window_starts: dict[str, int] | None = None,
) -> ECLOSummary:
    """Build weekly ECLO reporting without inventing exact weekdays."""

    selected_scenario = coerce_scenario(scenario)
    eclo_rows = sorted(
        (row for row in access_rows if row.eclo),
        key=lambda row: (row.week, row.activity_id, row.access_seq),
    )
    details: list[ECLOAccessDetail] = []
    rows_by_week: dict[int, int] = defaultdict(int)
    line_weeks: dict[str, set[int]] = defaultdict(set)
    line_counts: dict[str, int] = defaultdict(int)

    for row in eclo_rows:
        activity = problem.activity(row.activity_id)
        lines = affected_line_codes(problem, footprints, row.activity_id)
        details.append(
            ECLOAccessDetail(
                activity_id=row.activity_id,
                access_seq=row.access_seq,
                contract_number=activity.contract_number,
                activity_type=activity.activity_type,
                week=row.week,
                week_start_date=problem.parameters.week_start_date(row.week),
                week_end_date=problem.parameters.week_end_date(row.week),
                access_night=row.access_night,
                affected_line_codes=lines,
            )
        )
        rows_by_week[row.week] += 1
        for line_code in lines:
            line_weeks[line_code].add(row.week)
            line_counts[line_code] += 1

    by_week = [
        ECLOWeekSummary(
            week=week,
            week_start_date=problem.parameters.week_start_date(week),
            week_end_date=problem.parameters.week_end_date(week),
            access_count=rows_by_week[week],
        )
        for week in sorted(rows_by_week)
    ]
    by_line = [
        ECLOLineSummary(
            line_code=line_code,
            usage_weeks=sorted(line_weeks[line_code]),
            affected_access_count=line_counts[line_code],
        )
        for line_code in sorted(line_weeks)
    ]

    windows: list[ECLOWindow] | None = None
    if selected_scenario == Scenario.C:
        windows = []
        for line_code, start_week in sorted((selected_window_starts or {}).items()):
            if not line_weeks.get(line_code):
                continue
            end_week = min(problem.parameters.horizon_weeks, start_week + 1)
            windows.append(
                ECLOWindow(
                    line_code=line_code,
                    start_week=start_week,
                    end_week=end_week,
                    start_date=problem.parameters.week_start_date(start_week),
                    end_date=problem.parameters.week_end_date(end_week),
                )
            )

    return ECLOSummary(
        eclo_accesses_total=len(eclo_rows),
        eclo_penalty=0 if selected_scenario == Scenario.A else 5 * len(eclo_rows),
        accesses=details,
        by_week=by_week,
        by_line=by_line,
        selected_windows=windows,
    )
