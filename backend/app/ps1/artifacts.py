"""Strict readers and round-trip checks for official PS1 output bundles."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    PS1Base,
    ScenarioResultRow,
)
from backend.app.ps1.models import PS1SolveResult


class ArtifactFormatError(ValueError):
    """Raised when an output artifact does not match its official schema."""


RowT = TypeVar("RowT", bound=PS1Base)


def _read_rows(
    path: Path | str,
    expected_header: list[str],
    row_type: type[RowT],
) -> list[RowT]:
    artifact_path = Path(path)
    with artifact_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != expected_header:
            raise ArtifactFormatError(
                f"{artifact_path.name} header {reader.fieldnames} does not match "
                f"official schema {expected_header}"
            )
        try:
            return [row_type.model_validate(row) for row in reader]
        except ValidationError as exc:
            raise ArtifactFormatError(
                f"{artifact_path.name} contains an invalid row: {exc}"
            ) from exc


def read_access_schedule(path: Path | str) -> list[AccessScheduleRow]:
    """Read an exact SCHEDULE_ACCESS.csv artifact."""

    return _read_rows(
        path,
        ["activity_id", "access_seq", "week", "eclo", "access_night"],
        AccessScheduleRow,
    )


def read_occupancy_schedule(path: Path | str) -> list[OccupancyScheduleRow]:
    """Read an exact SCHEDULE_OCCUPANCY.csv artifact."""

    return _read_rows(
        path,
        ["activity_id", "week", "location_id", "co_share_group"],
        OccupancyScheduleRow,
    )


def read_results(path: Path | str) -> list[ScenarioResultRow]:
    """Read an exact RESULTS.csv artifact."""

    return _read_rows(
        path,
        ["scenario", "contract_number", "simulated_completion_date", "overrun_days"],
        ScenarioResultRow,
    )


def verify_export_round_trip(
    result: PS1SolveResult,
    paths: dict[str, Path],
) -> None:
    """Re-read a bundle and ensure serialization preserved the validated rows."""

    reloaded_access = read_access_schedule(paths["access"])
    reloaded_occupancy = read_occupancy_schedule(paths["occupancy"])
    reloaded_results = read_results(paths["results"])
    if reloaded_access != result.access_rows:
        raise ArtifactFormatError("SCHEDULE_ACCESS.csv changed during serialization")
    if reloaded_occupancy != result.occupancy_rows:
        raise ArtifactFormatError("SCHEDULE_OCCUPANCY.csv changed during serialization")
    if reloaded_results != result.contract_results:
        raise ArtifactFormatError("RESULTS.csv changed during serialization")
