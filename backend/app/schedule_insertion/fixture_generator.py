"""Deterministic generator for the checked-in operational CSV fixture.

The generator reads the official sector and location CSVs through the normal
PS1 loader.  It never hardcodes the number of lines, sectors or locations.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.app.domain_models import ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.schedule_insertion.config import ScheduleInsertionConfig
from backend.app.schedule_insertion.models import (
    BaselineBundle,
    MaintenanceJob,
    MaintenanceVisit,
    MaintenanceVisitStatus,
    OperationalCalendarDay,
)


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_fixture(problem: ProblemInstance, config: ScheduleInsertionConfig | None = None) -> BaselineBundle:
    """Build stable maintenance jobs, visits and an explicit calendar."""

    config = config or ScheduleInsertionConfig()
    start = problem.parameters.horizon_start
    end = start + timedelta(days=config.horizon_weeks * 7 - 1)
    # Include one complete prior and next cadence so rolling checks have facts
    # on both sides of the planning horizon.
    first_anchor = start - timedelta(days=config.maintenance_cycle_days)
    last_anchor = end + timedelta(days=config.maintenance_cycle_days)

    jobs: list[MaintenanceJob] = []
    visits: list[MaintenanceVisit] = []
    ordered_sectors = sorted(problem.sectors, key=lambda sector: (sector.line_code, sector.seq, sector.sector_id))
    visit_offsets = (0, 2, 4)
    for sector_index, sector in enumerate(ordered_sectors):
        # Spread sector occurrences across the cadence instead of making a
        # whole multi-sector project footprint unavailable for every night of
        # one week.  The visits within an occurrence remain split across
        # distinct dates, and the explicit daily capacity validator remains
        # authoritative.
        offset = timedelta(days=(sector_index % 18) * 10)
        anchor = first_anchor + offset
        while anchor <= last_anchor:
            occurrence = f"OCC:{sector.sector_id}:{anchor.isoformat()}"
            job_id = f"RM:{sector.sector_id}:{anchor.isoformat()}"
            jobs.append(
                MaintenanceJob(
                    job_id=job_id,
                    occurrence_id=occurrence,
                    line_code=sector.line_code,
                    sector_id=sector.sector_id,
                    occurrence_anchor=anchor,
                    cycle_days=config.maintenance_cycle_days,
                    coverage_interval_days=config.coverage_interval_days,
                )
            )
            for seq, day_offset in enumerate(visit_offsets, start=1):
                visit_date = anchor + timedelta(days=day_offset)
                historical = visit_date < start
                future_lookahead = visit_date > end
                status = (
                    MaintenanceVisitStatus.HISTORICAL
                    if historical
                    else MaintenanceVisitStatus.COMMITTED
                    if future_lookahead
                    else MaintenanceVisitStatus.SCHEDULED
                )
                visits.append(
                    MaintenanceVisit(
                        visit_id=f"{job_id}:VISIT:{seq}",
                        job_id=job_id,
                        occurrence_id=occurrence,
                        line_code=sector.line_code,
                        sector_id=sector.sector_id,
                        service_date=visit_date,
                        visit_seq=seq,
                        status=status,
                        locked=historical or future_lookahead,
                        actual=historical,
                    )
                )
            anchor += timedelta(days=config.maintenance_cycle_days)

    calendar_start = min(v.service_date for v in visits)
    calendar_end = max(v.service_date for v in visits)
    calendar = [
        OperationalCalendarDay(
            service_date=day,
            global_night_id=f"synthetic-calendar-v1:{day.isoformat()}",
            gross_capacity=config.default_project_gross_capacity,
            nominal_weekly_limit=config.default_nominal_weekly_limit,
        )
        for day in (calendar_start + timedelta(days=i) for i in range((calendar_end - calendar_start).days + 1))
    ]
    return BaselineBundle(
        baseline_id="baseline-fixture-v1",
        revision=1,
        official_fingerprint=None,
        horizon_start=start,
        horizon_weeks=config.horizon_weeks,
        timezone=config.timezone,
        config_version=config.fixture_version,
        maintenance_jobs=jobs,
        maintenance_visits=visits,
        calendar=calendar,
        created_at=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
    )


def write_fixture(bundle: BaselineBundle, output_dir: Path | str) -> Path:
    """Write the operational input bundle as documented CSVs."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_rows(
        out / "metadata.csv",
        ["key", "value"],
        [
            {"key": "fixture_version", "value": bundle.config_version},
            {"key": "baseline_id", "value": bundle.baseline_id},
            {"key": "horizon_start", "value": bundle.horizon_start.isoformat()},
            {"key": "horizon_weeks", "value": bundle.horizon_weeks},
            {"key": "timezone", "value": bundle.timezone},
            {"key": "maintenance_cycle_days", "value": 245},
            {"key": "coverage_interval_days", "value": 364},
            {"key": "maintenance_daily_capacity", "value": 3},
            {"key": "maintenance_reservation_policy", "value": "separate_from_official_residual_supply"},
        ],
    )
    _write_rows(
        out / "maintenance_jobs.csv",
        [
            "job_id", "occurrence_id", "job_type", "line_code", "sector_id",
            "required_visits", "cycle_days", "coverage_interval_days", "occurrence_anchor", "source",
        ],
        [job.model_dump(mode="json") for job in bundle.maintenance_jobs],
    )
    _write_rows(
        out / "baseline_visits.csv",
        [
            "visit_id", "job_id", "occurrence_id", "line_code", "sector_id", "service_date",
            "visit_seq", "status", "locked", "actual",
        ],
        [visit.model_dump(mode="json") for visit in bundle.maintenance_visits],
    )
    _write_rows(
        out / "operating_calendar.csv",
        [
            "service_date", "global_night_id", "timezone", "eligible", "physical_available",
            "eclo_eligible", "gross_capacity", "nominal_weekly_limit", "calendar_revision",
        ],
        [day.model_dump(mode="json") for day in bundle.calendar],
    )
    _write_rows(out / "project_jobs.csv", ["job_id"], [])
    _write_rows(out / "project_accesses.csv", ["access_id"], [])
    return out


def generate_fixture(official_data_dir: Path | str, output_dir: Path | str) -> BaselineBundle:
    problem = load_problem_from_directory(official_data_dir)
    bundle = build_fixture(problem)
    write_fixture(bundle, output_dir)
    return bundle


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    generate_fixture(root / "data", root / "data" / "schedule_insertion")
