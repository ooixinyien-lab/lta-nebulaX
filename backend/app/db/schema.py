"""Nondestructive SQLite upgrades from both the baseline and PS1 v1 schema."""
from pathlib import Path
import sqlite3


LATEST_PS1_SCHEMA_VERSION = 3


def _upgrade_to_v2(connection: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS schedule_bundles (
            id TEXT PRIMARY KEY,
            revision_id TEXT NOT NULL REFERENCES instance_revisions(id),
            scenario TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            validation JSON NOT NULL,
            created_by TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE(revision_id, fingerprint)
        )""",
        """CREATE TABLE IF NOT EXISTS schedule_bundle_files (
            bundle_id TEXT NOT NULL REFERENCES schedule_bundles(id),
            filename TEXT NOT NULL,
            content BLOB NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            PRIMARY KEY(bundle_id, filename)
        )""",
        """CREATE TABLE IF NOT EXISTS schedule_bundle_accesses (
            bundle_id TEXT NOT NULL REFERENCES schedule_bundles(id),
            activity_id TEXT NOT NULL,
            access_seq INTEGER NOT NULL,
            week INTEGER NOT NULL,
            eclo BOOLEAN NOT NULL,
            access_night INTEGER NOT NULL,
            PRIMARY KEY(bundle_id, activity_id, access_seq)
        )""",
        """CREATE TABLE IF NOT EXISTS schedule_bundle_occupancies (
            bundle_id TEXT NOT NULL REFERENCES schedule_bundles(id),
            activity_id TEXT NOT NULL,
            week INTEGER NOT NULL,
            location_id TEXT NOT NULL,
            co_share_group TEXT NOT NULL,
            PRIMARY KEY(bundle_id, activity_id, week, location_id)
        )""",
        """CREATE TABLE IF NOT EXISTS schedule_bundle_results (
            bundle_id TEXT NOT NULL REFERENCES schedule_bundles(id),
            scenario TEXT NOT NULL,
            contract_number TEXT NOT NULL,
            simulated_completion_date DATE NOT NULL,
            overrun_days INTEGER NOT NULL,
            PRIMARY KEY(bundle_id, contract_number)
        )""",
        """CREATE TABLE IF NOT EXISTS calendar_revisions (
            id TEXT PRIMARY KEY,
            revision_id TEXT NOT NULL REFERENCES instance_revisions(id),
            fingerprint TEXT NOT NULL,
            timezone TEXT NOT NULL,
            assumed_calendar BOOLEAN NOT NULL,
            assumptions JSON NOT NULL,
            definition JSON NOT NULL,
            created_by TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE(revision_id, fingerprint)
        )""",
        """CREATE TABLE IF NOT EXISTS calendarisation_attempts (
            id TEXT PRIMARY KEY,
            bundle_id TEXT NOT NULL REFERENCES schedule_bundles(id),
            calendar_revision_id TEXT NOT NULL REFERENCES calendar_revisions(id),
            status TEXT NOT NULL,
            solver_status TEXT,
            solver_version TEXT NOT NULL,
            validator_version TEXT NOT NULL,
            complete BOOLEAN NOT NULL,
            preference_value INTEGER,
            requested_time_limit FLOAT NOT NULL,
            commitments JSON NOT NULL,
            options JSON NOT NULL,
            conflicts JSON NOT NULL,
            validation JSON,
            error_message TEXT,
            worker_token TEXT,
            started_at DATETIME,
            finished_at DATETIME,
            created_by TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS ix_calendar_attempt_status
            ON calendarisation_attempts(status, created_at)""",
        """CREATE TABLE IF NOT EXISTS calendar_assignments (
            attempt_id TEXT NOT NULL REFERENCES calendarisation_attempts(id),
            activity_id TEXT NOT NULL,
            access_seq INTEGER NOT NULL,
            access_id TEXT NOT NULL,
            week INTEGER NOT NULL,
            access_night INTEGER NOT NULL,
            eclo BOOLEAN NOT NULL,
            service_date DATE NOT NULL,
            global_night_id TEXT NOT NULL,
            contract_number TEXT NOT NULL,
            contract_description TEXT NOT NULL,
            line_codes JSON NOT NULL,
            location_ids JSON NOT NULL,
            PRIMARY KEY(attempt_id, activity_id, access_seq)
        )""",
        """CREATE TABLE IF NOT EXISTS explanation_fact_packs (
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
        )""",
        "CREATE INDEX IF NOT EXISTS ix_explanation_fact_packs_lookup ON explanation_fact_packs (run_id, activity_id)",
        """CREATE TABLE IF NOT EXISTS chat_sessions (
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
        )""",
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_user ON chat_sessions (created_by, last_activity_at)",
        """CREATE TABLE IF NOT EXISTS chat_turns (
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
        )""",
        "CREATE INDEX IF NOT EXISTS ix_chat_turns_session ON chat_turns (session_id, created_at)",
    )
    for statement in statements:
        connection.execute(statement)


def upgrade_schema(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS ps1_schema_version (version INTEGER PRIMARY KEY)")
    version = connection.execute("SELECT MAX(version) FROM ps1_schema_version").fetchone()[0] or 0
    if version > LATEST_PS1_SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported PS1 schema version: {version}")
    if version == 0:
        # Do not use executescript: it commits any pending transaction.
        for statement in Path(__file__).with_suffix('.sql').read_text(encoding='utf-8').split(';'):
            if statement.strip():
                connection.execute(statement)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_revision_fingerprint ON instance_revisions(input_fingerprint)")
        connection.execute("CREATE TABLE IF NOT EXISTS instance_file_contents (revision_id TEXT NOT NULL REFERENCES instance_revisions(id), filename TEXT NOT NULL, content BLOB NOT NULL, PRIMARY KEY(revision_id, filename))")
        connection.execute("INSERT INTO ps1_schema_version VALUES (1)")
        version = 1
    bundles_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedule_bundles'"
    ).fetchone()
    fact_packs_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='explanation_fact_packs'"
    ).fetchone()
    if version < 2 or bundles_table is None or fact_packs_table is None:
        _upgrade_to_v2(connection)
        from backend.app.schedule_insertion.migrations import upgrade_schedule_insertion_schema
        upgrade_schedule_insertion_schema(connection)
        if version < 2:
            connection.execute("INSERT INTO ps1_schema_version VALUES (2)")
            version = 2
    if version < 3:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS application_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO ps1_schema_version VALUES (3)")
