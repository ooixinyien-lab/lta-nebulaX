"""Nondestructive SQLite upgrades from both the baseline and PS1 v1 schema."""
from pathlib import Path
import sqlite3


def upgrade_schema(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS ps1_schema_version (version INTEGER PRIMARY KEY)")
    version = connection.execute("SELECT MAX(version) FROM ps1_schema_version").fetchone()[0] or 0
    if version > 2:
        raise RuntimeError(f"Unsupported PS1 schema version: {version}")
    if version == 0:
        # Do not use executescript: it commits any pending transaction.
        for statement in Path(__file__).with_suffix('.sql').read_text(encoding='utf-8').split(';'):
            if statement.strip():
                connection.execute(statement)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_revision_fingerprint ON instance_revisions(input_fingerprint)")
        connection.execute("CREATE TABLE IF NOT EXISTS instance_file_contents (revision_id TEXT NOT NULL REFERENCES instance_revisions(id), filename TEXT NOT NULL, content BLOB NOT NULL, PRIMARY KEY(revision_id, filename))")
        connection.execute("INSERT INTO ps1_schema_version VALUES (2)")
    elif version == 1:
        # Incremental upgrade from version 1 to 2: create chatbot tables
        connection.execute("""
        CREATE TABLE IF NOT EXISTS explanation_fact_packs (
            id VARCHAR(64) NOT NULL,
            instance_id VARCHAR(64) NOT NULL,
            instance_revision_id VARCHAR(64) NOT NULL,
            run_id VARCHAR(64) NOT NULL,
            baseline_run_id VARCHAR(64),
            activity_id VARCHAR(64) NOT NULL,
            facts_json JSON NOT NULL,
            fallback_summary TEXT NOT NULL,
            evidence_hash VARCHAR(64) NOT NULL,
            builder_version VARCHAR(64) NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(instance_id) REFERENCES instances (id),
            FOREIGN KEY(instance_revision_id) REFERENCES instance_revisions (id),
            FOREIGN KEY(run_id) REFERENCES solver_runs (id)
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_explanation_fact_packs_lookup ON explanation_fact_packs (run_id, activity_id)")
        connection.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id VARCHAR(64) NOT NULL,
            instance_id VARCHAR(64) NOT NULL,
            run_id VARCHAR(64) NOT NULL,
            baseline_run_id VARCHAR(64),
            created_by VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            last_activity_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(instance_id) REFERENCES instances (id),
            FOREIGN KEY(run_id) REFERENCES solver_runs (id)
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_chat_sessions_user ON chat_sessions (created_by, last_activity_at)")
        connection.execute("""
        CREATE TABLE IF NOT EXISTS chat_turns (
            id VARCHAR(64) NOT NULL,
            session_id VARCHAR(64) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            question_redacted TEXT NOT NULL,
            answer_redacted TEXT NOT NULL,
            response_mode VARCHAR(32) NOT NULL,
            provider VARCHAR(64),
            model VARCHAR(64),
            prompt_template_version VARCHAR(64),
            fact_pack_id VARCHAR(64),
            tool_trace_json JSON,
            citation_json JSON,
            uncertainty_json JSON,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(session_id) REFERENCES chat_sessions (id)
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_chat_turns_session ON chat_turns (session_id, created_at)")
        connection.execute("INSERT INTO ps1_schema_version VALUES (2)")
