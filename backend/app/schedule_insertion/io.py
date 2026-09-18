"""CSV import for the operational fixture bundle."""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

from backend.app.schedule_insertion.models import (
    BaselineBundle,
    MaintenanceJob,
    MaintenanceVisit,
    OperationalCalendarDay,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load_baseline_bundle(directory: Path | str) -> BaselineBundle:
    """Load the generated maintenance/calendar bundle without regenerating it."""

    root = Path(directory)
    metadata = {row["key"]: row["value"] for row in _rows(root / "metadata.csv")}
    jobs = [MaintenanceJob.model_validate(row) for row in _rows(root / "maintenance_jobs.csv")]
    visits = [MaintenanceVisit.model_validate(row) for row in _rows(root / "baseline_visits.csv")]
    calendar = [OperationalCalendarDay.model_validate(row) for row in _rows(root / "operating_calendar.csv")]
    return BaselineBundle(
        baseline_id=metadata.get("baseline_id", "baseline-fixture-v1"),
        revision=1,
        horizon_start=metadata["horizon_start"],
        horizon_weeks=int(metadata["horizon_weeks"]),
        timezone=metadata.get("timezone", "Asia/Singapore"),
        config_version=metadata.get("fixture_version", "schedule-insertion-fixture-v1"),
        maintenance_jobs=jobs,
        maintenance_visits=visits,
        calendar=calendar,
        created_at=datetime.combine(
            date.fromisoformat(metadata["horizon_start"]),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
    )
