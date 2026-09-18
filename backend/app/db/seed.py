"""Atomic official bundle imports, shared by startup and upload."""
from hashlib import sha256
from pathlib import Path
from sqlite3 import Connection

from backend.app.database import Database
from backend.app.domain_models import ProblemInstance
from backend.app.db.models import Instance, InstanceFile, InstanceRevision
from backend.app.db.records import insert
from backend.app.db.repositories.instances import create_instance_revision, fingerprint_files, find_fingerprint
from backend.app.db.repositories.audit import record_event
from backend.app.io import DataLayerError, load_problem_from_streams

OFFICIAL_FILES = (
    "01_LINES.csv", "02_STATIONS.csv", "03_SECTORS.csv", "04_LOCATION_SUPPLY.csv",
    "05_BUFFER_LOCATION.csv", "06_PARAMETERS.csv", "07_PROJECT_DETAILS.csv", "08_ACTIVITY_DETAILS.csv",
)


def validate_bundle(files: dict[str, bytes]) -> ProblemInstance:
    if set(files) != set(OFFICIAL_FILES):
        raise ValueError("Exactly the eight official CSV files are required")
    return load_problem_from_streams({name: content.decode('utf-8-sig') for name, content in files.items()})


def import_bundle(connection: Connection, files: dict[str, bytes], problem: ProblemInstance, *, actor: str, name: str) -> tuple[Instance, InstanceRevision]:
    """Caller holds a write transaction and has checked duplicate policy."""
    fingerprint = fingerprint_files(files)
    instance, revision = create_instance_revision(connection, problem, name=name, created_by=actor, input_fingerprint=fingerprint)
    for filename, content in files.items():
        insert(connection, InstanceFile(revision_id=revision.id, file_type=filename,
            original_filename=filename, storage_key=f"sqlite:{revision.id}/{filename}",
            sha256=sha256(content).hexdigest(), size_bytes=len(content)))
        connection.execute("INSERT INTO instance_file_contents VALUES (?,?,?)", (revision.id, filename, content))
    record_event(connection, actor=actor, action='instance_seeded' if actor == 'system' else 'instance_uploaded',
                 entity_type='instance_revision', entity_id=revision.id, detail={'file_count': len(files)})
    return instance, revision


def seed_official_instance(database: Database, data_path: str | Path) -> tuple[str, str]:
    directory = Path(data_path)
    try:
        files = {filename: (directory / filename).read_bytes() for filename in OFFICIAL_FILES}
        problem = validate_bundle(files)
    except (OSError, ValueError, DataLayerError) as exc:
        raise ValueError(f"Official CSV startup import failed at {directory}: {exc}") from exc
    fingerprint = fingerprint_files(files)
    with database.connection(write=True) as connection:
        existing = find_fingerprint(connection, fingerprint)
        if existing is not None:
            return existing.instance_id, existing.id
        instance, revision = import_bundle(connection, files, problem, actor='system', name='Official CSV instance')
        return instance.id, revision.id
