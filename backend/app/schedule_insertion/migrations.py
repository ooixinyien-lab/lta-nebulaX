"""Additive SQLite migration for schedule insertion records."""

from __future__ import annotations

import sqlite3


def upgrade_schedule_insertion_schema(connection: sqlite3.Connection) -> None:
    for statement in (
        """
        CREATE TABLE IF NOT EXISTS schedule_insertion_baselines (
            id TEXT PRIMARY KEY,
            baseline_key TEXT NOT NULL,
            revision INTEGER NOT NULL,
            official_revision_id TEXT,
            fingerprint TEXT NOT NULL,
            config_version TEXT NOT NULL,
            payload JSON NOT NULL,
            created_by TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE (baseline_key, revision)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS schedule_insertion_runs (
            id TEXT PRIMARY KEY,
            baseline_key TEXT NOT NULL,
            baseline_revision INTEGER NOT NULL,
            official_revision_id TEXT,
            scenario TEXT NOT NULL,
            status TEXT NOT NULL,
            solver_version TEXT NOT NULL,
            validator_version TEXT NOT NULL,
            scenario_cost REAL,
            payload JSON NOT NULL,
            created_by TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_schedule_insertion_runs_baseline ON schedule_insertion_runs (baseline_key, baseline_revision, scenario)",
    ):
        connection.execute(statement)
