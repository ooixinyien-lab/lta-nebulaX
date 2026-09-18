"""Nondestructive SQLite upgrades from both the baseline and PS1 v1 schema."""
from pathlib import Path
import sqlite3


def upgrade_schema(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS ps1_schema_version (version INTEGER PRIMARY KEY)")
    version = connection.execute("SELECT MAX(version) FROM ps1_schema_version").fetchone()[0] or 0
    if version > 1:
        raise RuntimeError(f"Unsupported PS1 schema version: {version}")
    if version == 0:
        # Do not use executescript: it commits any pending transaction.
        for statement in Path(__file__).with_suffix('.sql').read_text(encoding='utf-8').split(';'):
            if statement.strip():
                connection.execute(statement)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_revision_fingerprint ON instance_revisions(input_fingerprint)")
        connection.execute("CREATE TABLE IF NOT EXISTS instance_file_contents (revision_id TEXT NOT NULL REFERENCES instance_revisions(id), filename TEXT NOT NULL, content BLOB NOT NULL, PRIMARY KEY(revision_id, filename))")
        connection.execute("INSERT INTO ps1_schema_version VALUES (1)")
