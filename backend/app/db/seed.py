"""Idempotent startup seed for the official CSV instance."""
from __future__ import annotations

from pathlib import Path

from backend.app.db.engine import DatabaseSession
from backend.app.db.repositories.instances import create_instance_revision, fingerprint_files
from backend.app.io import load_problem_from_directory

OFFICIAL_FILES = (
    "01_LINES.csv", "02_STATIONS.csv", "03_SECTORS.csv", "04_LOCATION_SUPPLY.csv",
    "05_BUFFER_LOCATION.csv", "06_PARAMETERS.csv", "07_PROJECT_DETAILS.csv", "08_ACTIVITY_DETAILS.csv",
)


def seed_official_instance(database: DatabaseSession, data_path: str | Path) -> tuple[str, str] | None:
    directory = Path(data_path)
    if not directory.is_dir() or not all((directory / filename).is_file() for filename in OFFICIAL_FILES):
        return None
    files = {filename: (directory / filename).read_bytes() for filename in OFFICIAL_FILES}
    fingerprint = fingerprint_files(files)
    problem = load_problem_from_directory(directory)
    metadata = {filename: {"filename": filename, "storage_key": str(directory / filename), "sha256": fingerprint_files({filename: content}), "size_bytes": len(content)} for filename, content in files.items()}
    with database.session() as session:
        instance, revision = create_instance_revision(session, problem, name="Official CSV instance", created_by="system", input_fingerprint=fingerprint, files=metadata)
        return instance.id, revision.id
