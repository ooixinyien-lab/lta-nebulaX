"""Transactional removal of user planning data while preserving the schema."""

from __future__ import annotations

from sqlite3 import Connection


PLANNING_TABLES = (
    "calendar_assignments",
    "calendarisation_attempts",
    "calendar_revisions",
    "schedule_bundle_results",
    "schedule_bundle_occupancies",
    "schedule_bundle_accesses",
    "schedule_bundle_files",
    "schedule_bundles",
    "schedule_insertion_runs",
    "schedule_insertion_baselines",
    "plan_change_events",
    "plan_occupancies",
    "plan_accesses",
    "plans",
    "run_validation_reports",
    "run_occupancies",
    "run_contract_results",
    "run_artifacts",
    "run_accesses",
    "solver_runs",
    "instance_file_contents",
    "instance_files",
    "instance_activities",
    "instance_contracts",
    "instance_parameters",
    "instance_buffer_rules",
    "instance_locations",
    "instance_sectors",
    "instance_stations",
    "instance_lines",
    "instance_revisions",
    "instances",
    "audit_events",
)


def clear_planning_data(connection: Connection) -> dict[str, int]:
    """Delete planning records in foreign-key order and disable implicit reseeding."""

    existing = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    deleted: dict[str, int] = {}
    for table in PLANNING_TABLES:
        if table not in existing:
            continue
        count = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        connection.execute(f"DELETE FROM {table}")
        deleted[table] = count
    connection.execute(
        "INSERT INTO application_settings(key,value) VALUES('auto_seed_official','false') "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    )
    return deleted


def should_auto_seed(connection: Connection) -> bool:
    row = connection.execute(
        "SELECT value FROM application_settings WHERE key='auto_seed_official'"
    ).fetchone()
    return row is None or str(row[0]).lower() != "false"
