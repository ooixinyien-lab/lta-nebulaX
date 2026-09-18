"""Independent row-based validation for understood PS1 schedule semantics.

The organiser's executable checker is absent from the supplied materials. This
module therefore validates the adopted accounting, packing, date, and scenario
rules while reporting protection compatibility as explicitly unverified.
"""

from __future__ import annotations

from collections import defaultdict

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    OccupancyScheduleRow,
    ProblemInstance,
)
from backend.app.ps1.models import (
    OfficialCheckerStatus,
    SafetyValidationStatus,
    Scenario,
    ValidationIssue,
    ValidationSummary,
    coerce_scenario,
)
from backend.app.ps1.scoring import affected_line_codes
from backend.app.topology import FootprintCache


PROVISIONAL_PREDECESSOR_POLICY = (
    "A successor access must occur in a strictly later week than its "
    "predecessor's final access."
)
UNRESOLVED_SAFETY_POLICY = (
    "Protection footprints are computed, but the official checker is required "
    "to resolve group-dependent buffer/closure exemptions and exact cross-line "
    "compatibility."
)
PROVISIONAL_SCORE_POLICY = (
    "Use the handout's detailed per-activity priority multiplier with P in A, "
    "7V+5E in B, and P+7V+5E in C, following the adoption plan's reconciliation."
)
PROVISIONAL_LOCAL_NIGHT_POLICY = (
    "access_night is local to contract/type/week and independent of possession "
    "group labels; no cross-contract calendar-night synchronization is inferred."
)


def validate_schedule(
    problem: ProblemInstance,
    scenario: Scenario | str,
    access_rows: list[AccessScheduleRow],
    occupancy_rows: list[OccupancyScheduleRow],
    footprints: FootprintCache | None = None,
    selected_window_starts: dict[str, int] | None = None,
) -> ValidationSummary:
    """Validate a schedule independently from CP-SAT decision variables."""

    selected_scenario = coerce_scenario(scenario)
    cache = footprints or FootprintCache(problem)
    issues: list[ValidationIssue] = []

    def add_issue(
        rule: str,
        detail: str,
        *,
        activity_id: str | None = None,
        week: int | None = None,
        location_id: str | None = None,
    ) -> None:
        issues.append(
            ValidationIssue(
                rule=rule,
                detail=detail,
                activity_id=activity_id,
                week=week,
                location_id=location_id,
            )
        )

    accesses_by_activity: dict[str, list[AccessScheduleRow]] = defaultdict(list)
    valid_access_keys: set[tuple[str, int]] = set()
    seen_access_keys: set[tuple[str, int]] = set()

    for row in access_rows:
        if row.activity_id not in problem._activities_by_id:
            add_issue("artifact", f"Unknown activity {row.activity_id} in access schedule")
            continue
        if not 1 <= row.week <= problem.parameters.horizon_weeks:
            add_issue(
                "horizon",
                f"Week {row.week} is outside the planning horizon",
                activity_id=row.activity_id,
                week=row.week,
            )
            continue
        key = (row.activity_id, row.week)
        if key in seen_access_keys:
            add_issue(
                "weekly_frequency",
                "Activity has more than one access row in the same week",
                activity_id=row.activity_id,
                week=row.week,
            )
        seen_access_keys.add(key)
        valid_access_keys.add(key)
        accesses_by_activity[row.activity_id].append(row)

        activity = problem.activity(row.activity_id)
        contract = problem.contract(activity.contract_number)
        release_week = problem.planned_start_week(activity)
        if row.week < release_week:
            add_issue(
                "planned_start",
                f"Access precedes release week {release_week}",
                activity_id=row.activity_id,
                week=row.week,
            )
        if not 1 <= row.access_night <= contract.number_of_maximum_access_per_week:
            add_issue(
                "weekly_allocation",
                f"access_night {row.access_night} is outside 1.."
                f"{contract.number_of_maximum_access_per_week}",
                activity_id=row.activity_id,
                week=row.week,
            )
        if selected_scenario == Scenario.A and row.eclo:
            add_issue(
                "eclo",
                "Scenario A forbids ECLO",
                activity_id=row.activity_id,
                week=row.week,
            )

    for activity in problem.activities:
        rows = accesses_by_activity.get(activity.activity_id, [])
        if not rows:
            add_issue(
                "workload",
                "Activity has no scheduled accesses",
                activity_id=activity.activity_id,
            )
            continue
        ordered_by_seq = sorted(rows, key=lambda row: row.access_seq)
        expected_sequences = list(range(1, len(rows) + 1))
        actual_sequences = [row.access_seq for row in ordered_by_seq]
        if actual_sequences != expected_sequences:
            add_issue(
                "artifact",
                f"access_seq values must be consecutive from 1; got {actual_sequences}",
                activity_id=activity.activity_id,
            )
        if [row.week for row in ordered_by_seq] != sorted(row.week for row in rows):
            add_issue(
                "artifact",
                "access_seq is not in chronological week order",
                activity_id=activity.activity_id,
            )
        delivered = sum(2 + int(row.eclo) for row in rows)
        if delivered < activity.doubled_workload:
            add_issue(
                "workload",
                f"Delivered doubled workload {delivered} is below required "
                f"{activity.doubled_workload}",
                activity_id=activity.activity_id,
            )
        if selected_scenario == Scenario.B:
            finish = problem.parameters.week_end_date(max(row.week for row in rows))
            deadline = problem.contract(activity.contract_number).planned_completion_date
            if finish > deadline:
                add_issue(
                    "planned_date",
                    f"Completion {finish.isoformat()} is after planned deadline "
                    f"{deadline.isoformat()}",
                    activity_id=activity.activity_id,
                    week=max(row.week for row in rows),
                )

    workfront_members: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    for activity_id, rows in accesses_by_activity.items():
        contract_number = problem.activity(activity_id).contract_number
        for row in rows:
            workfront_members[(contract_number, row.week, row.access_night)].add(activity_id)
    for (contract_number, week, access_night), members in workfront_members.items():
        limit = problem.contract(contract_number).number_of_workfronts
        if len(members) > limit:
            add_issue(
                "workfront",
                f"Contract {contract_number} local night {access_night} has "
                f"{len(members)} activities, above workfront limit {limit}",
                week=week,
            )

    for activity in problem.activities:
        predecessor_id = activity.predecessor_activity_id
        if not predecessor_id:
            continue
        predecessor_rows = accesses_by_activity.get(predecessor_id, [])
        successor_rows = accesses_by_activity.get(activity.activity_id, [])
        if predecessor_rows and successor_rows:
            predecessor_finish = max(row.week for row in predecessor_rows)
            successor_start = min(row.week for row in successor_rows)
            if successor_start <= predecessor_finish:
                add_issue(
                    "precedence",
                    f"Successor starts in week {successor_start}, which is not after "
                    f"predecessor {predecessor_id}'s final week {predecessor_finish}",
                    activity_id=activity.activity_id,
                    week=successor_start,
                )

    occupancy_by_key: dict[tuple[str, int, str], list[OccupancyScheduleRow]] = defaultdict(list)
    group_members: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    groups_by_location_week: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in occupancy_rows:
        if row.activity_id not in problem._activities_by_id:
            add_issue("artifact", f"Unknown activity {row.activity_id} in occupancy schedule")
            continue
        if row.location_id not in problem._locations_by_id:
            add_issue(
                "artifact",
                f"Unknown location {row.location_id} in occupancy schedule",
                activity_id=row.activity_id,
                week=row.week,
                location_id=row.location_id,
            )
            continue
        if not row.co_share_group.strip():
            add_issue(
                "artifact",
                "co_share_group must not be empty",
                activity_id=row.activity_id,
                week=row.week,
                location_id=row.location_id,
            )
        if (row.activity_id, row.week) not in valid_access_keys:
            add_issue(
                "occupancy",
                "Occupancy row has no corresponding access row",
                activity_id=row.activity_id,
                week=row.week,
                location_id=row.location_id,
            )
        key = (row.activity_id, row.week, row.location_id)
        occupancy_by_key[key].append(row)
        group_key = (row.location_id, row.week, row.co_share_group)
        group_members[group_key].add(row.activity_id)
        groups_by_location_week[(row.location_id, row.week)].add(row.co_share_group)

    for activity_id, rows in accesses_by_activity.items():
        expected_locations = set(cache.get_core_footprint(activity_id).core_locations)
        for access in rows:
            for location_id in expected_locations:
                count = len(occupancy_by_key.get((activity_id, access.week, location_id), []))
                if count != 1:
                    add_issue(
                        "occupancy",
                        f"Expected exactly one core occupancy row; found {count}",
                        activity_id=activity_id,
                        week=access.week,
                        location_id=location_id,
                    )

    for (activity_id, week, location_id), rows in occupancy_by_key.items():
        if activity_id not in problem._activities_by_id:
            continue
        core_locations = set(cache.get_core_footprint(activity_id).core_locations)
        if location_id not in core_locations:
            add_issue(
                "occupancy",
                "Output occupancy contains a non-core location",
                activity_id=activity_id,
                week=week,
                location_id=location_id,
            )
        if len(rows) > 1:
            add_issue(
                "occupancy",
                f"Duplicate core occupancy rows found: {len(rows)}",
                activity_id=activity_id,
                week=week,
                location_id=location_id,
            )

    for (location_id, week, group), members in group_members.items():
        roles = [
            problem.contract(problem.activity(activity_id).contract_number).access_type
            for activity_id in members
        ]
        pm_count = roles.count(AccessType.PM)
        pc_count = roles.count(AccessType.PC)
        c_count = roles.count(AccessType.C)
        legal = (
            (pm_count == 1 and pc_count == 0 and c_count == 0)
            or (pm_count == 0 and pc_count == 1 and c_count <= 3)
            or (pm_count == 0 and pc_count == 0 and 1 <= c_count <= 4)
        )
        if not legal:
            add_issue(
                "legal_mix",
                f"Illegal group {group}: PM={pm_count}, PC={pc_count}, C={c_count}",
                week=week,
                location_id=location_id,
            )

    for (location_id, week), groups in groups_by_location_week.items():
        supply = problem.location(location_id).supply_capacity
        used = len(groups)
        if selected_scenario == Scenario.A and used > supply:
            add_issue(
                "capacity",
                f"Used {used} groups above nominal supply {supply}",
                week=week,
                location_id=location_id,
            )
        if selected_scenario == Scenario.C and used > supply + 1:
            add_issue(
                "capacity",
                f"Used {used} groups above Scenario C limit {supply + 1}",
                week=week,
                location_id=location_id,
            )

    if selected_scenario == Scenario.C:
        line_usage: dict[str, set[int]] = defaultdict(set)
        for row in access_rows:
            if not row.eclo or row.activity_id not in problem._activities_by_id:
                continue
            for line_code in affected_line_codes(problem, cache, row.activity_id):
                line_usage[line_code].add(row.week)
        for line_code, weeks in line_usage.items():
            if selected_window_starts is not None:
                start = selected_window_starts.get(line_code)
                if start is None:
                    add_issue(
                        "eclo_window",
                        f"Line {line_code} uses ECLO but has no selected window",
                    )
                    continue
                if not 1 <= start <= problem.parameters.horizon_weeks:
                    add_issue(
                        "eclo_window",
                        f"Line {line_code} selected invalid start week {start}",
                    )
                    continue
                allowed = {start, start + 1}
                if any(week not in allowed for week in weeks):
                    add_issue(
                        "eclo_window",
                        f"Line {line_code} uses ECLO in weeks {sorted(weeks)} outside "
                        f"selected window {sorted(allowed)}",
                    )
            elif max(weeks) - min(weeks) > 1:
                add_issue(
                    "eclo_window",
                    f"Line {line_code} ECLO weeks {sorted(weeks)} do not fit one "
                    "two-week window",
                )

    return ValidationSummary(
        local_accounting_passed=not issues,
        issues=issues,
        provisional_policies=[
            PROVISIONAL_PREDECESSOR_POLICY,
            PROVISIONAL_SCORE_POLICY,
            PROVISIONAL_LOCAL_NIGHT_POLICY,
            UNRESOLVED_SAFETY_POLICY,
        ],
        safety_status=SafetyValidationStatus.UNVERIFIED,
        official_checker_status=OfficialCheckerStatus.UNAVAILABLE,
    )
