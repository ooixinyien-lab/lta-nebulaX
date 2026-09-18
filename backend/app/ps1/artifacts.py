"""Strict readers and round-trip checks for official PS1 output bundles."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import TextIO, TypeVar

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


def _read_rows_stream(
    stream: TextIO,
    artifact_name: str,
    expected_header: list[str],
    row_type: type[RowT],
) -> list[RowT]:
    reader = csv.DictReader(stream)
    if reader.fieldnames != expected_header:
        raise ArtifactFormatError(
            f"{artifact_name} header {reader.fieldnames} does not match "
            f"official schema {expected_header}"
        )
    try:
        return [row_type.model_validate(row) for row in reader]
    except ValidationError as exc:
        raise ArtifactFormatError(
            f"{artifact_name} contains an invalid row: {exc}"
        ) from exc


def _read_rows(
    path: Path | str,
    expected_header: list[str],
    row_type: type[RowT],
) -> list[RowT]:
    artifact_path = Path(path)
    with artifact_path.open(encoding="utf-8", newline="") as stream:
        return _read_rows_stream(stream, artifact_path.name, expected_header, row_type)


def _read_rows_bytes(
    content: bytes,
    artifact_name: str,
    expected_header: list[str],
    row_type: type[RowT],
) -> list[RowT]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ArtifactFormatError(f"{artifact_name} is not valid UTF-8") from exc
    return _read_rows_stream(StringIO(text, newline=""), artifact_name, expected_header, row_type)


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


def read_access_schedule_bytes(content: bytes) -> list[AccessScheduleRow]:
    """Read uploaded access bytes without rewriting the immutable artifact."""

    return _read_rows_bytes(
        content,
        "SCHEDULE_ACCESS.csv",
        ["activity_id", "access_seq", "week", "eclo", "access_night"],
        AccessScheduleRow,
    )


def read_occupancy_schedule_bytes(content: bytes) -> list[OccupancyScheduleRow]:
    """Read uploaded occupancy bytes without rewriting the immutable artifact."""

    return _read_rows_bytes(
        content,
        "SCHEDULE_OCCUPANCY.csv",
        ["activity_id", "week", "location_id", "co_share_group"],
        OccupancyScheduleRow,
    )


def read_results_bytes(content: bytes) -> list[ScenarioResultRow]:
    """Read uploaded result bytes without rewriting the immutable artifact."""

    return _read_rows_bytes(
        content,
        "RESULTS.csv",
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
