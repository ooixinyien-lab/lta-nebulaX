"""Educational Solver V1: V0 timing plus dependencies and power separation.

V1 remains intentionally incomplete. The canonical full solver implements the
complete approved constraint set; this file preserves the learning progression.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from ortools.sat.python import cp_model


DATA_PATH = Path(__file__).with_name("comprehensive_synthetic_data.json")


def parse_time(value: str) -> datetime:
    """Parse an ISO 8601 timestamp into a timezone-aware datetime."""
    return datetime.fromisoformat(value)


def to_minutes(value: str, origin: datetime) -> int:
    """Convert a timestamp into integer minutes from the planning-window origin."""
    time = parse_time(value)
    difference = time - origin
    return int(difference.total_seconds() // 60)


def request_duration(request: dict) -> int:
    """Return the total reserved duration across all request phases."""
    return sum(phase["duration_minutes"] for phase in request["phases"])


def hhmm(origin: datetime, minutes: int) -> str:
    """Convert an integer minute offset back into HH:MM format."""
    return (origin + timedelta(minutes=minutes)).strftime("%H:%M")


def select_planning_window(data: dict, planning_date=None) -> dict:
    """Return the explicitly selected engineering window."""
    if planning_date is None:
        planning_date = data.get("metadata", {}).get("planning_date")

    if planning_date is None:
        raise ValueError(
            "A planning date is required in metadata.planning_date"
        )

    for window in data["engineering_windows"]:
        if window["date"] == planning_date:
            return window

    raise ValueError(
        f"No engineering window exists for planning date {planning_date}"
    )


def normalize(data: dict, planning_date=None):
    """Extract and normalize one planning night's data for Solver V1."""
    window = select_planning_window(data, planning_date)
    planning_date = window["date"]
    origin = parse_time(window["start"])

    handback_buffer = window["handback_buffer_minutes"]
    rules_buffer = data["planning_rules"]["morning_buffer_minutes"]
    if handback_buffer != rules_buffer:
        raise ValueError(
            "Engineering-window and planning-rule handback buffers differ"
        )

    usable_end = parse_time(window["end"]) - timedelta(
        minutes=handback_buffer
    )
    horizon = to_minutes(usable_end.isoformat(), origin)

    if horizon <= 0:
        raise ValueError(
            "The handback buffer leaves no usable engineering time"
        )

    committed = {
        allocation["request_id"]: allocation
        for allocation in data.get("committed_allocations", [])
        if parse_time(allocation["start"]).date().isoformat()
        == planning_date
    }

    jobs = []

    for request in data["requests"]:
        if (
            request["status"] == "cancelled"
            or planning_date not in request["allowed_dates"]
        ):
            continue

        duration = request_duration(request)

        earliest_start = max(
            0,
            to_minutes(request["earliest_start"], origin),
        )

        latest_finish = min(
            horizon,
            to_minutes(request["deadline"], origin),
        )

        allocation = committed.get(request["id"])
        locked = bool(request.get("frozen", False))

        if locked:
            if allocation is None:
                raise ValueError(
                    f"Frozen request {request['id']} has no committed allocation"
                )

            if not allocation.get("locked"):
                raise ValueError(
                    f"Frozen request {request['id']} has an unlocked allocation"
                )

            locked_start = to_minutes(allocation["start"], origin)
        else:
            locked_start = None

        preferred_value = request.get("preferred_start")
        preferred_start = (
            to_minutes(preferred_value, origin)
            if preferred_value is not None
            else None
        )

        jobs.append(
            {
                "id": request["id"],
                "duration": duration,
                "earliest_start": earliest_start,
                "latest_finish": latest_finish,
                "preferred_start": preferred_start,
                "locked": locked,
                "locked_start": locked_start,
                "depends_on": request.get("depends_on", []),
                "handover_buffer_minutes": request.get(
                    "handover_buffer_minutes",
                    0,
                ),
                "power_zone": request.get("power_zone"),
                "power_requirement": request.get(
                    "power_requirement",
                    "NONE",
                ),
            }
        )

    planning_rules = data["planning_rules"]

    return origin, horizon, jobs, planning_rules


def power_compatible(
    requirement_a: str,
    requirement_b: str,
    compatibility_table: dict,
) -> bool:
    """Return the configured compatibility result for two traction-power states."""
    try:
        return compatibility_table[requirement_a][requirement_b]
    except KeyError as exc:
        raise ValueError(
            f"Missing power compatibility rule for "
            f"{requirement_a}/{requirement_b}"
        ) from exc


def add_dependencies(model, jobs_by_id, variables):
    """Enforce predecessor completion before dependent work can start."""
    for job in jobs_by_id.values():
        for predecessor_id in job["depends_on"]:
            if predecessor_id not in jobs_by_id:
                raise ValueError(
                    f"{job['id']} references unknown predecessor "
                    f"{predecessor_id}"
                )

            buffer_minutes = job["handover_buffer_minutes"]

            model.add(
                variables[job["id"]]["start"]
                >= variables[predecessor_id]["end"] + buffer_minutes
            )


def add_power_constraints(
    model,
    jobs,
    variables,
    planning_rules,
):
    """Separate jobs that require incompatible power states in the same zone."""
    compatibility_table = planning_rules["power_compatibility"]
    transition_minutes = planning_rules[
        "opposed_power_transition_minutes"
    ]

    for index, job_a in enumerate(jobs):
        for job_b in jobs[index + 1 :]:
            if job_a["power_zone"] != job_b["power_zone"]:
                continue

            compatible = power_compatible(
                job_a["power_requirement"],
                job_b["power_requirement"],
                compatibility_table,
            )

            if compatible:
                continue

            a_before_b = model.new_bool_var(
                f"{job_a['id']}_before_{job_b['id']}_power"
            )

            model.add(
                variables[job_a["id"]]["end"] + transition_minutes
                <= variables[job_b["id"]]["start"]
            ).only_enforce_if(a_before_b)

            model.add(
                variables[job_b["id"]]["end"] + transition_minutes
                <= variables[job_a["id"]]["start"]
            ).only_enforce_if(a_before_b.Not())


def build_and_solve(jobs, planning_rules):
    """Build and solve the current CP-SAT scheduling model."""
    model = cp_model.CpModel()
    variables = {}

    for job in jobs:
        latest_start = job["latest_finish"] - job["duration"]

        if latest_start < job["earliest_start"]:
            raise ValueError(
                f"{job['id']} cannot fit inside its allowed time window"
            )

        start = model.new_int_var(
            job["earliest_start"],
            latest_start,
            f"start_{job['id']}",
        )

        end = model.new_int_var(
            job["earliest_start"] + job["duration"],
            job["latest_finish"],
            f"end_{job['id']}",
        )

        model.add(end == start + job["duration"])

        interval = model.new_interval_var(
            start,
            job["duration"],
            end,
            f"interval_{job['id']}",
        )

        if job["locked"]:
            model.add(start == job["locked_start"])

        variables[job["id"]] = {
            "start": start,
            "end": end,
            "interval": interval,
        }

    jobs_by_id = {job["id"]: job for job in jobs}

    add_dependencies(
        model,
        jobs_by_id,
        variables,
    )

    add_power_constraints(
        model,
        jobs,
        variables,
        planning_rules,
    )

    model.minimize(
        sum(variable["start"] for variable in variables.values())
    )

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    return solver, status, variables


def main():
    with DATA_PATH.open() as file:
        data = json.load(file)

    origin, horizon, jobs, planning_rules = normalize(data)

    print(
        f"Usable planning window: "
        f"{origin.strftime('%H:%M')} -> "
        f"{hhmm(origin, horizon)}"
    )

    print(
        "V1 scope: V0 timing plus dependency/handover and "
        "traction-power separation"
    )

    solver, status, variables = build_and_solve(
        jobs,
        planning_rules,
    )

    print("\nSolver status:", solver.status_name(status))

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return

    print("\nSOLVER V1 SCHEDULE")

    for job in jobs:
        start = solver.value(variables[job["id"]]["start"])
        end = solver.value(variables[job["id"]]["end"])

        print(
            f"{job['id']}: "
            f"{hhmm(origin, start)} -> {hhmm(origin, end)}"
        )


if __name__ == "__main__":
    main()
