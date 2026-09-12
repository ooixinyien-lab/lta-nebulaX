import json
from datetime import datetime, timedelta
from pathlib import Path

from ortools.sat.python import cp_model


# Solver V0 uses the confirmed comprehensive mock dataset stored beside this
# script. Using __file__ keeps the path reliable even when the script is
# launched from a different working directory.
DATA_PATH = Path(__file__).with_name("comprehensive_synthetic_data.json")


# ---------------------------------------------------------
# 1. CONVERT AND CALCULATE TIME VALUES
# ---------------------------------------------------------

def parse_time(value: str) -> datetime:
    """
    Convert an ISO-formatted timestamp from the JSON dataset into a
    Python datetime object so that time calculations can be performed.
    """
    return datetime.fromisoformat(value)


def to_minutes(value: str, origin: datetime) -> int:
    """
    Represent a timestamp as the number of whole minutes that have passed
    since the beginning of the selected engineering window.

    CP-SAT works with integer variables, so real timestamps are converted
    into integers before they are provided to the optimisation model.
    """
    time = parse_time(value)

    # Subtracting the window's start time gives the timestamp's position
    # relative to the beginning of the planning period.
    difference = time - origin

    # Convert the resulting time difference from seconds to whole minutes.
    return int(difference.total_seconds() // 60)


def request_duration(request: dict) -> int:
    """
    Calculate the complete amount of time reserved for one request.

    A request is treated as one continuous job consisting of its setup,
    work, testing, and handback phases. Solver V0 therefore schedules the
    sum of all phase durations rather than scheduling each phase separately.
    """
    return sum(
        phase["duration_minutes"]
        for phase in request["phases"]
    )


def hhmm(origin: datetime, minutes: int) -> str:
    """
    Convert a solver time value back into a human-readable clock time.

    For example, if the planning window begins at 01:00 and the solver
    returns 90 minutes, this function displays the result as 02:30.
    """
    return (origin + timedelta(minutes=minutes)).strftime("%H:%M")


# ---------------------------------------------------------
# 2. PREPARE THE JSON DATA FOR THE SOLVER
# ---------------------------------------------------------

def select_planning_window(data: dict, planning_date=None) -> dict:
    """
    Return the engineering window for the night being planned.

    The comprehensive dataset declares its default planning night in
    metadata.planning_date. The optional planning_date argument lets a caller
    select another night later without changing the dataset or this function.
    """
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
    """
    Extract and transform the parts of the full JSON dataset required by
    Solver V0.

    The original dataset contains detailed domain information, but the first
    solver version only requires each job's duration, timing boundaries,
    optional preferred start time, and frozen-allocation status.
    """

    # Select one planning night explicitly instead of assuming that the first
    # list entry is always the intended night.
    window = select_planning_window(data, planning_date)
    planning_date = window["date"]

    # The beginning of the engineering window becomes minute zero for all
    # subsequent solver calculations.
    origin = parse_time(window["start"])

    # The final part of the engineering window is reserved for morning
    # handback. Maintenance jobs must finish before this buffer begins.
    handback_buffer = window["handback_buffer_minutes"]
    rules_buffer = data["planning_rules"]["morning_buffer_minutes"]

    # The same rule is stored with the window and in the global planning
    # rules. Rejecting a mismatch prevents the solver from silently choosing
    # one of two conflicting values.
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


    # Index committed allocations by request ID instead of repeatedly
    # searching through a list. This allows a request's existing allocation
    # to be retrieved directly using committed.get(request["id"]).
    #
    # The resulting structure has the following general form:
    #
    # {
    #     "R01": allocation details,
    #     "R02": allocation details
    # }
    committed = {
        allocation["request_id"]: allocation
        for allocation in data.get("committed_allocations", [])
        if parse_time(allocation["start"]).date().isoformat()
        == planning_date
    }


    # Each normalised job will be appended to this list before the completed
    # collection is passed into the CP-SAT model.
    jobs = []


    # Process every maintenance request individually and convert it into the
    # smaller, consistent structure required by Solver V0.
    for request in data["requests"]:

        # A cancelled request must not re-enter the schedule. Requests that
        # cannot run on this planning date belong to another nightly model.
        if (
            request["status"] == "cancelled"
            or planning_date not in request["allowed_dates"]
        ):
            continue

        # Combine all phases because this version schedules each request as
        # one uninterrupted block of work.
        duration = request_duration(request)

        # Convert the request's earliest permitted start into solver minutes.
        # The maximum with zero prevents a request from starting before the
        # beginning of the selected engineering window.
        earliest_start = max(
            0,
            to_minutes(request["earliest_start"], origin)
        )

        # A request may have a deadline extending beyond the engineering
        # window. Solver V0 cannot schedule beyond the current window, so its
        # effective latest finish is clipped to the planning horizon.
        latest_finish = min(
            horizon,
            to_minutes(request["deadline"], origin)
        )


        # Look for an existing committed allocation belonging to this request.
        # If none exists, get() returns None instead of raising an error.
        allocation = committed.get(request["id"])

        # The request's frozen flag is the ground-truth booking rule. Its
        # committed allocation supplies the start time that must be preserved.
        locked = bool(request.get("frozen", False))


        # Locked requests must retain their existing allocated start time.
        # Unlocked requests use None here because the solver is free to choose
        # their start time later.
        if locked:
            if allocation is None:
                raise ValueError(
                    f"Frozen request {request['id']} has no committed allocation"
                )

            if not allocation.get("locked"):
                raise ValueError(
                    f"Frozen request {request['id']} has an unlocked allocation"
                )

            locked_start = to_minutes(
                allocation["start"],
                origin
            )
        else:
            locked_start = None


        # ANY_TIME requests legitimately have no preferred timestamp. JSON
        # null becomes Python None, which must not be passed to parse_time().
        preferred_value = request.get("preferred_start")
        preferred_start = (
            to_minutes(preferred_value, origin)
            if preferred_value is not None
            else None
        )

        # Store only the fields required to construct the initial mathematical
        # model. All timestamps are represented as integer minute offsets.
        job = {
            "id": request["id"],
            "duration": duration,
            "earliest_start": earliest_start,
            "latest_finish": latest_finish,
            "preferred_start": preferred_start,
            "locked": locked,
            "locked_start": locked_start,
        }


        jobs.append(job)


    # Return the time origin for display purposes, the planning horizon, and
    # the complete collection of solver-ready jobs.
    return origin, horizon, jobs


# ---------------------------------------------------------
# 3. BUILD AND SOLVE THE INITIAL CP-SAT MODEL
# ---------------------------------------------------------

def build_and_solve(jobs):

    # CpModel is the container in which all decision variables, constraints,
    # intervals, and the objective function are defined.
    model = cp_model.CpModel()


    # Keep each request's CP-SAT variables indexed by request ID. This makes
    # it straightforward to retrieve the solved start and end values later.
    variables = {}


    # Create the required scheduling variables for every normalised job.
    for job in jobs:

        # A job must start early enough for its entire duration to finish by
        # latest_finish. Subtracting the duration gives the final valid start.
        latest_start = (
            job["latest_finish"]
            - job["duration"]
        )

        # An empty start range means that the request cannot fit inside its
        # individual time bounds, even before later constraints are added.
        if latest_start < job["earliest_start"]:
            raise ValueError(
                f"{job['id']} cannot fit inside its allowed time window"
            )


        # This integer decision variable represents the job's starting minute.
        # CP-SAT selects a value between the earliest and latest valid starts.
        start = model.new_int_var(
            job["earliest_start"],
            latest_start,
            f"start_{job['id']}",
        )


        # This integer decision variable represents the job's finishing minute.
        # Its permitted range reflects the duration and latest-finish boundary.
        end = model.new_int_var(
            job["earliest_start"] + job["duration"],
            job["latest_finish"],
            f"end_{job['id']}",
        )


        # Link the two decision variables with a hard constraint. Any valid
        # solution must place the end exactly one job duration after the start.
        model.add(
            end == start + job["duration"]
        )


        # Represent the request as a continuous occupied time interval.
        # This prepares the model for later scheduling constraints involving
        # shared resources or non-overlapping jobs. Solver V0 creates these
        # intervals but does not yet add a global no-overlap constraint.
        interval = model.new_interval_var(
            start,
            job["duration"],
            end,
            f"interval_{job['id']}",
        )


        # A locked allocation is an existing commitment that the optimiser
        # must preserve. Fixing its start variable prevents CP-SAT from moving it.
        if job["locked"]:
            model.add(
                start == job["locked_start"]
            )


        # Save the variables together under the request ID so their values can
        # be retrieved after the model has been solved.
        variables[job["id"]] = {
            "start": start,
            "end": end,
            "interval": interval,
        }


    # Solver V0 uses a temporary objective that minimises the sum of all job
    # start times. This encourages movable jobs to begin as early as their
    # current constraints allow and produces results that are easy to inspect.
    #
    # This is a technical demonstration objective, not the final operational
    # objective. Later versions can consider priorities, delays, disruption,
    # resource usage, preferred times, or other business requirements.
    model.minimize(
        sum(
            variable["start"]
            for variable in variables.values()
        )
    )


    # Create the CP-SAT solver that will search for a solution to the model.
    solver = cp_model.CpSolver()


    # Run the optimisation process. The returned status indicates whether the
    # solver found an optimal solution, a feasible solution, or no solution.
    status = solver.solve(model)


    # Return the completed solver, its result status, and the variables needed
    # to extract and display the generated schedule.
    return solver, status, variables


# ---------------------------------------------------------
# 4. LOAD THE DATA, RUN THE SOLVER, AND DISPLAY RESULTS
# ---------------------------------------------------------

def main():

    # Open the JSON dataset located beside this script and convert its contents
    # into a Python dictionary.
    with DATA_PATH.open() as file:
        data = json.load(file)


    # Reduce the full dataset to the time values and job fields required by
    # the initial CP-SAT model.
    origin, horizon, jobs = normalize(data)


    # Display the engineering window being planned. The internal minute-based
    # horizon is converted back into a readable clock time for the user.
    print(
        f"Usable planning window: "
        f"{origin.strftime('%H:%M')} -> "
        f"{hhmm(origin, horizon)}"
    )

    print(
        "V0 scope: duration, request time bounds, handback, "
        "and frozen starts only"
    )


    # Print the normalised records so that the input passed to the solver can
    # be reviewed during development and testing.
    print("\nNORMALIZED JOBS")

    for job in jobs:
        print(job)


    # Construct the CP-SAT model and ask the solver to find a schedule.
    solver, status, variables = build_and_solve(jobs)


    # Convert the solver's numeric status into a readable status name.
    print(
        "\nSolver status:",
        solver.status_name(status)
    )


    # A schedule can only be displayed when CP-SAT has found either an optimal
    # solution or at least one valid feasible solution.
    if status in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    ):

        print("\nSOLVER V0 SCHEDULE")


        # Retrieve the selected start and end minute for every job, convert the
        # values back into clock times, and print the resulting schedule.
        for job in jobs:

            start = solver.value(
                variables[job["id"]]["start"]
            )

            end = solver.value(
                variables[job["id"]]["end"]
            )


            print(
                f"{job['id']}: "
                f"{hhmm(origin, start)} "
                f"-> "
                f"{hhmm(origin, end)}"
            )


# Only run main() when this file is executed directly. This prevents the solver
# from running automatically if its functions are imported into another module.
if __name__ == "__main__":
    main()
    
