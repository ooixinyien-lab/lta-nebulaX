"""Calendar job executor shared by the web app and optional CLI worker."""

from __future__ import annotations

import argparse
from time import sleep
from uuid import uuid4

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.db.models import CalendarAttemptRecord
from backend.app.db.repositories.calendars import (
    claim_calendar_attempt,
    claim_next_calendar_attempt,
    complete_calendar_attempt,
    fail_calendar_attempt,
    load_calendar,
    load_schedule_bundle,
    recover_stale_calendar_attempts,
)
from backend.app.db.repositories.instances import load_revision
from backend.app.ps1.calendar_models import CalendariseOptions, DateCommitment
from backend.app.ps1.calendarisation import calendarise


def process_next(database: Database, worker_token: str | None = None) -> bool:
    token = worker_token or f"worker-{uuid4().hex}"
    with database.connection(write=True) as connection:
        recover_stale_calendar_attempts(connection)
        attempt = claim_next_calendar_attempt(connection, token)
    if attempt is None:
        return False
    return _execute_claimed(database, attempt, token)


def process_attempt(database: Database, attempt_id: str) -> bool:
    """Run the requested web job; another worker may already own or have finished it."""

    token = f"web-worker-{uuid4().hex}"
    with database.connection(write=True) as connection:
        recover_stale_calendar_attempts(connection)
        attempt = claim_calendar_attempt(connection, attempt_id, token)
    if attempt is None:
        return False
    return _execute_claimed(database, attempt, token)


def _execute_claimed(
    database: Database, attempt: CalendarAttemptRecord, token: str
) -> bool:
    try:
        with database.connection() as connection:
            bundle = load_schedule_bundle(connection, attempt.bundle_id)
            problem = load_revision(connection, bundle.instance_revision_id)
            _record, calendar = load_calendar(
                connection, attempt.calendar_revision_id
            )
        result = calendarise(
            problem,
            bundle,
            attempt.calendar_revision_id,
            calendar,
            [DateCommitment.model_validate(item) for item in attempt.commitments],
            CalendariseOptions.model_validate(attempt.options),
        )
        with database.connection(write=True) as connection:
            complete_calendar_attempt(connection, attempt.id, token, result)
    except Exception as exc:
        with database.connection(write=True) as connection:
            fail_calendar_attempt(connection, attempt.id, token, str(exc))
        return True
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Process NebulaX calendar jobs")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings.database_path, settings.dataset_path)
    database.initialize()
    if args.once:
        process_next(database)
        return 0
    while True:
        if not process_next(database):
            sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
