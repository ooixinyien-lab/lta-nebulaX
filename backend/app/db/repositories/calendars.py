"""Persistence for immutable source bundles, calendars and dated assignments."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from sqlite3 import Connection
from uuid import uuid4

from backend.app.db.models import (
    CalendarAssignmentRecord,
    CalendarAttemptRecord,
    CalendarRevisionRecord,
    ScheduleBundleRecord,
)
from backend.app.db.records import decode, get, insert, insert_many
from backend.app.db.repositories.instances import fingerprint_files
from backend.app.db.repositories.instances import load_revision
from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    ScenarioResultRow,
)
from backend.app.ps1.calendar_models import (
    CalendarAssignment,
    CalendarisationResult,
    CalendariseOptions,
    CalendarPreviewCalendar,
    CalendarPreviewContext,
    CalendarPreviewInstance,
    CalendarPreviewSource,
    DateCommitment,
    FixedScheduleBundle,
    OperatingCalendarInput,
)


OUTPUT_FILENAMES = (
    "SCHEDULE_ACCESS.csv",
    "SCHEDULE_OCCUPANCY.csv",
    "RESULTS.csv",
)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def find_bundle(
    connection: Connection, revision_id: str, fingerprint: str
) -> ScheduleBundleRecord | None:
    return decode(
        ScheduleBundleRecord,
        connection.execute(
            "SELECT * FROM schedule_bundles WHERE revision_id=? AND fingerprint=?",
            (revision_id, fingerprint),
        ).fetchone(),
    )


def create_schedule_bundle(
    connection: Connection,
    *,
    revision_id: str,
    scenario: str,
    files: dict[str, bytes],
    access_rows: list[AccessScheduleRow],
    occupancy_rows: list[OccupancyScheduleRow],
    result_rows: list[ScenarioResultRow],
    validation: dict,
    created_by: str,
) -> ScheduleBundleRecord:
    fingerprint = fingerprint_files(files)
    existing = find_bundle(connection, revision_id, fingerprint)
    if existing is not None:
        return existing
    bundle = insert(
        connection,
        ScheduleBundleRecord(
            id=_id("bundle"),
            revision_id=revision_id,
            scenario=scenario,
            fingerprint=fingerprint,
            validation=validation,
            created_by=created_by,
        ),
    )
    for filename in OUTPUT_FILENAMES:
        content = files[filename]
        connection.execute(
            "INSERT INTO schedule_bundle_files VALUES (?,?,?,?,?)",
            (
                bundle.id,
                filename,
                content,
                sha256(content).hexdigest(),
                len(content),
            ),
        )
    connection.executemany(
        "INSERT INTO schedule_bundle_accesses VALUES (?,?,?,?,?,?)",
        [
            (
                bundle.id,
                row.activity_id,
                row.access_seq,
                row.week,
                int(row.eclo),
                row.access_night,
            )
            for row in access_rows
        ],
    )
    connection.executemany(
        "INSERT INTO schedule_bundle_occupancies VALUES (?,?,?,?,?)",
        [
            (
                bundle.id,
                row.activity_id,
                row.week,
                row.location_id,
                row.co_share_group,
            )
            for row in occupancy_rows
        ],
    )
    connection.executemany(
        "INSERT INTO schedule_bundle_results VALUES (?,?,?,?,?)",
        [
            (
                bundle.id,
                row.scenario,
                row.contract_number,
                row.simulated_completion_date.isoformat(),
                row.overrun_days,
            )
            for row in result_rows
        ],
    )
    return bundle


def load_schedule_bundle(
    connection: Connection, bundle_id: str
) -> FixedScheduleBundle:
    bundle = get(connection, ScheduleBundleRecord, bundle_id)
    if bundle is None:
        raise KeyError(bundle_id)
    access_rows = [
        AccessScheduleRow.model_validate(dict(row))
        for row in connection.execute(
            """SELECT activity_id,access_seq,week,eclo,access_night
               FROM schedule_bundle_accesses WHERE bundle_id=?
               ORDER BY activity_id,access_seq""",
            (bundle_id,),
        )
    ]
    occupancy_rows = [
        OccupancyScheduleRow.model_validate(dict(row))
        for row in connection.execute(
            """SELECT activity_id,week,location_id,co_share_group
               FROM schedule_bundle_occupancies WHERE bundle_id=?
               ORDER BY week,location_id,activity_id""",
            (bundle_id,),
        )
    ]
    result_rows = [
        ScenarioResultRow.model_validate(dict(row))
        for row in connection.execute(
            """SELECT scenario,contract_number,simulated_completion_date,overrun_days
               FROM schedule_bundle_results WHERE bundle_id=?
               ORDER BY contract_number""",
            (bundle_id,),
        )
    ]
    return FixedScheduleBundle(
        bundle_id=bundle.id,
        instance_revision_id=bundle.revision_id,
        scenario=bundle.scenario,
        fingerprint=bundle.fingerprint,
        access_rows=access_rows,
        occupancy_rows=occupancy_rows,
        result_rows=result_rows,
    )


def get_bundle_file_bytes(
    connection: Connection, bundle_id: str
) -> dict[str, bytes]:
    return {
        row["filename"]: bytes(row["content"])
        for row in connection.execute(
            "SELECT filename,content FROM schedule_bundle_files WHERE bundle_id=?",
            (bundle_id,),
        )
    }


def create_calendar_revision(
    connection: Connection,
    calendar: OperatingCalendarInput,
    *,
    created_by: str,
) -> tuple[CalendarRevisionRecord, bool]:
    definition = calendar.model_dump(mode="json")
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    fingerprint = sha256(canonical.encode("utf-8")).hexdigest()
    existing = decode(
        CalendarRevisionRecord,
        connection.execute(
            "SELECT * FROM calendar_revisions WHERE revision_id=? AND fingerprint=?",
            (calendar.instance_revision_id, fingerprint),
        ).fetchone(),
    )
    if existing is not None:
        return existing, False
    record = insert(
        connection,
        CalendarRevisionRecord(
            id=_id("calendar"),
            revision_id=calendar.instance_revision_id,
            fingerprint=fingerprint,
            timezone=calendar.timezone,
            assumed_calendar=calendar.assumed_calendar,
            assumptions=calendar.assumptions,
            definition=definition,
            created_by=created_by,
        ),
    )
    return record, True


def load_calendar(
    connection: Connection, calendar_id: str
) -> tuple[CalendarRevisionRecord, OperatingCalendarInput]:
    record = get(connection, CalendarRevisionRecord, calendar_id)
    if record is None:
        raise KeyError(calendar_id)
    return record, OperatingCalendarInput.model_validate(record.definition)


def create_calendar_attempt(
    connection: Connection,
    *,
    bundle_id: str,
    calendar_revision_id: str,
    commitments: list[DateCommitment],
    options: CalendariseOptions,
    created_by: str,
) -> CalendarAttemptRecord:
    return insert(
        connection,
        CalendarAttemptRecord(
            id=_id("calendar-run"),
            bundle_id=bundle_id,
            calendar_revision_id=calendar_revision_id,
            requested_time_limit=options.time_limit_seconds,
            commitments=[item.model_dump(mode="json") for item in commitments],
            options=options.model_dump(mode="json"),
            created_by=created_by,
        ),
    )


def claim_next_calendar_attempt(
    connection: Connection, worker_token: str
) -> CalendarAttemptRecord | None:
    row = connection.execute(
        """SELECT id FROM calendarisation_attempts
           WHERE status='QUEUED' ORDER BY created_at,id LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    return claim_calendar_attempt(connection, row["id"], worker_token)


def claim_calendar_attempt(
    connection: Connection, attempt_id: str, worker_token: str
) -> CalendarAttemptRecord | None:
    """Claim exactly one queued attempt in the caller's write transaction."""

    now = datetime.now(timezone.utc).isoformat()
    cursor = connection.execute(
        """UPDATE calendarisation_attempts
           SET status='RUNNING',worker_token=?,started_at=?
           WHERE id=? AND status='QUEUED'""",
        (worker_token, now, attempt_id),
    )
    if cursor.rowcount != 1:
        return None
    return get(connection, CalendarAttemptRecord, attempt_id)


def recover_stale_calendar_attempts(
    connection: Connection,
    *,
    now: datetime | None = None,
    grace_seconds: float = 300.0,
) -> list[str]:
    """Fail expired worker leases without touching attempts that may still be active."""

    current_time = now or datetime.now(timezone.utc)
    recovered: list[str] = []
    rows = connection.execute(
        """SELECT id,worker_token,started_at,requested_time_limit
           FROM calendarisation_attempts WHERE status='RUNNING'"""
    ).fetchall()
    for row in rows:
        if row["started_at"] is None:
            continue
        started_at = datetime.fromisoformat(row["started_at"])
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        expires_at = started_at + timedelta(
            seconds=float(row["requested_time_limit"]) + grace_seconds
        )
        if current_time <= expires_at:
            continue
        cursor = connection.execute(
            """UPDATE calendarisation_attempts
               SET status='FAILED',error_message=?,finished_at=?
               WHERE id=? AND status='RUNNING' AND worker_token=? AND started_at=?""",
            (
                "Calendar worker lease expired before a complete result was stored.",
                current_time.isoformat(),
                row["id"],
                row["worker_token"],
                row["started_at"],
            ),
        )
        if cursor.rowcount == 1:
            recovered.append(row["id"])
    return recovered


def complete_calendar_attempt(
    connection: Connection,
    attempt_id: str,
    worker_token: str,
    result: CalendarisationResult,
) -> CalendarAttemptRecord:
    current = get(connection, CalendarAttemptRecord, attempt_id)
    if (
        current is None
        or current.status != "RUNNING"
        or current.worker_token != worker_token
    ):
        raise RuntimeError("Calendar attempt is stale or owned by another worker")
    if result.complete:
        insert_many(
            connection,
            [
                CalendarAssignmentRecord(
                    attempt_id=attempt_id,
                    **assignment.model_dump(),
                )
                for assignment in result.assignments
            ],
        )
    now = datetime.now(timezone.utc).isoformat()
    cursor = connection.execute(
        """UPDATE calendarisation_attempts
           SET status='SUCCEEDED',solver_status=?,complete=?,preference_value=?,
               conflicts=?,validation=?,finished_at=?
           WHERE id=? AND status='RUNNING' AND worker_token=?""",
        (
            result.solver_status.value,
            int(result.complete),
            result.preference_value,
            json.dumps([item.model_dump(mode="json") for item in result.conflicts]),
            json.dumps(result.validation.model_dump(mode="json"))
            if result.validation
            else None,
            now,
            attempt_id,
            worker_token,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("Calendar attempt changed before completion")
    return get(connection, CalendarAttemptRecord, attempt_id)


def fail_calendar_attempt(
    connection: Connection, attempt_id: str, worker_token: str, message: str
) -> CalendarAttemptRecord:
    now = datetime.now(timezone.utc).isoformat()
    cursor = connection.execute(
        """UPDATE calendarisation_attempts
           SET status='FAILED',error_message=?,finished_at=?
           WHERE id=? AND status='RUNNING' AND worker_token=?""",
        (message, now, attempt_id, worker_token),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("Calendar attempt is stale or owned by another worker")
    return get(connection, CalendarAttemptRecord, attempt_id)


def load_assignments(
    connection: Connection, attempt_id: str
) -> list[CalendarAssignment]:
    return [
        CalendarAssignment.model_validate(
            decode(CalendarAssignmentRecord, row).model_dump(exclude={"attempt_id"})
        )
        for row in connection.execute(
            """SELECT * FROM calendar_assignments WHERE attempt_id=?
               ORDER BY week,service_date,activity_id,access_seq""",
            (attempt_id,),
        )
    ]


def load_preview_context(
    connection: Connection, bundle_id: str | None = None
) -> CalendarPreviewContext:
    """Restore preview inputs without generating data or choosing sample files."""

    if bundle_id is not None:
        bundle = get(connection, ScheduleBundleRecord, bundle_id)
        if bundle is None:
            raise KeyError(bundle_id)
    else:
        bundle = decode(
            ScheduleBundleRecord,
            connection.execute(
                "SELECT * FROM schedule_bundles ORDER BY created_at DESC,id DESC LIMIT 1"
            ).fetchone(),
        )
    context = CalendarPreviewContext()
    revision_filter = "AND r.id=?" if bundle else ""
    revision = connection.execute(
        f"""SELECT r.id,i.name FROM instance_revisions r
            JOIN instances i ON i.id=r.instance_id
            WHERE r.validation_status='VALID' {revision_filter}
            ORDER BY r.created_at DESC,r.revision_number DESC,r.id DESC LIMIT 1""",
        (bundle.revision_id,) if bundle else (),
    ).fetchone()
    if revision is None:
        return context
    problem = load_revision(connection, revision["id"])
    context.instance = CalendarPreviewInstance(
        revision_id=revision["id"],
        name=revision["name"],
        horizon_start=problem.parameters.horizon_start,
        horizon_end=problem.parameters.horizon_end,
        horizon_weeks=problem.parameters.horizon_weeks,
    )
    latest_attempt = None
    if bundle is not None:
        count = connection.execute(
            "SELECT COUNT(*) FROM schedule_bundle_accesses WHERE bundle_id=?",
            (bundle.id,),
        ).fetchone()[0]
        context.bundle = CalendarPreviewSource(
            bundle_id=bundle.id,
            instance_revision_id=bundle.revision_id,
            scenario=bundle.scenario,
            access_count=count,
            created_at=bundle.created_at,
        )
        latest_attempt = connection.execute(
            """SELECT id,calendar_revision_id FROM calendarisation_attempts
               WHERE bundle_id=? ORDER BY created_at DESC,id DESC LIMIT 1""",
            (bundle.id,),
        ).fetchone()
        last_complete = connection.execute(
            """SELECT id FROM calendarisation_attempts
               WHERE bundle_id=? AND status='SUCCEEDED' AND complete=1
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (bundle.id,),
        ).fetchone()
        context.latest_attempt_id = latest_attempt["id"] if latest_attempt else None
        context.last_complete_attempt_id = last_complete["id"] if last_complete else None
    if latest_attempt:
        calendar = get(
            connection, CalendarRevisionRecord, latest_attempt["calendar_revision_id"]
        )
    else:
        calendar = decode(
            CalendarRevisionRecord,
            connection.execute(
                """SELECT * FROM calendar_revisions WHERE revision_id=?
                   ORDER BY created_at DESC,id DESC LIMIT 1""",
                (revision["id"],),
            ).fetchone(),
        )
    if calendar is not None and calendar.revision_id == revision["id"]:
        context.calendar = CalendarPreviewCalendar(
            calendar_revision_id=calendar.id,
            instance_revision_id=calendar.revision_id,
            assumed_calendar=calendar.assumed_calendar,
            assumptions=calendar.assumptions,
        )
    return context
