# Local SQLite persistence

NebulaX uses Python's built-in `sqlite3` through `backend/app/database.py`. Both legacy and PS1 repositories use the same `app.state.db`, with one file at `Settings.database_path` (default `backend/nebulax.sqlite3`). There is no SQLAlchemy, Alembic, PostgreSQL driver, or `DATABASE_URL` configuration.

## Startup and schema upgrades

Set `OFFICIAL_DATA_PATH` to a directory containing exactly the eight required input filenames, `01_LINES.csv` through `08_ACTIVITY_DETAILS.csv`. Other directory files are ignored. Startup reads all required files, validates the exact bytes using the official loader and typed domain models, then imports the entire bundle in one transaction. Missing files, invalid UTF-8, or invalid CSV data cause a clear startup error. An unsuccessful import adds no instance, input entities, file metadata, bytes, or audit event.

Schema upgrades run in development, test, and production. Version 1 creates missing PS1 tables without replacing the baseline legacy tables or the PS1 layouts introduced after `c156c5a368e0ee411f0b305dfa7987995d2f5492`. It adds a schema ledger, a unique revision fingerprint index, and a table holding original CSV bytes. Existing instance/revision IDs, metadata, input rows, runs/results, plans, audit rows, and older file storage keys remain intact. Existing Alembic ledger data is left untouched. A newer unsupported schema version stops initialization rather than downgrading the file.

Every connection enables foreign keys and a five-second busy timeout. Initialization enables WAL. Writers use `with db.connection(write=True) as connection`, which acquires `BEGIN IMMEDIATE`; readers use `db.connection()`. Repository functions participate in the caller's transaction and do not commit independently. An exception leaving the context rolls back the transaction. Keep validation and other long-running work outside write transactions.

## Bundles and duplicate uploads

The fingerprint algorithm is unchanged from the previous branch: iterate filenames in sorted order and feed UTF-8 filename, a zero byte, the original file bytes, and another zero byte into SHA-256. Formatting and encoding changes therefore represent different bundles. Per-file metadata for new imports uses ordinary SHA-256 of the file contents.

Startup reuses a matching instance/revision without modifying records or audit history. A changed validated bundle creates a new instance and revision 1; older snapshots and their runs/plans remain available. `load_revision(connection, revision_id)` reconstructs a typed `ProblemInstance` from relational storage without reopening source CSVs.

`POST /api/ps1/instances/upload` accepts exactly eight multipart `files` parts, each with a different required official filename. A new bundle returns HTTP 201. A duplicate, including a startup-loaded bundle, returns HTTP 409:

```json
{
  "detail": {
    "message": "Identical eight-file CSV bundle already exists",
    "instance_id": "inst-...",
    "revision_id": "rev-...",
    "fingerprint": "..."
  }
}
```

The duplicate check and insert share the same write transaction, and unique indexes also enforce fingerprints. Concurrent identical uploads yield one success and one conflict. Rejected duplicates do not write audit events or files.

New startup and upload imports store the original eight CSV byte strings in `instance_file_contents` inside SQLite. Their `instance_files.storage_key` is a logical `sqlite:<revision_id>/<filename>` reference, not a filesystem path. This removes cross-filesystem commit and orphan-file problems. Older filesystem storage keys and files are preserved, but new imports no longer use an upload directory.

## Baseline compatibility

The compatibility baseline is `c156c5a368e0ee411f0b305dfa7987995d2f5492`. The layouts and behavior of legacy `connection(write=False)`, `snapshot()`, `bump()`, `audit()`, and `save_catalog()` are retained. Existing catalogs, request/allocation payloads, proposals, revisions, and audit records survive initialization. Official activities are stored separately and are never converted to legacy single-night requests.

PS1 startup does not require `DATASET_PATH`. To explicitly initialize legacy state, construct `Database(database_path, dataset_path)` and call `initialize(seed_legacy=True)`. Explicit reset still uses `db.seed(connection)` within a write transaction. It increments the legacy revision and resets only legacy tables; it cannot erase PS1 records or PS1 audit events. Calling `snapshot()` before legacy state exists gives an explicit initialization error.

The deleted `backend.app.models` module is a pre-existing limitation: the baseline legacy router/solver cannot import it. The app logs that the legacy router is unavailable. This refactor does not restore the legacy solver or certify the historical API as operational. PS1 run endpoints persist queue/progress/results; they do not introduce a solver worker or claim official validation.

## Verification (19 September 2026)

Executed with the available Python 3.11 interpreter on Windows:

```sh
python -m pytest backend/tests/test_data_layer.py backend/tests/test_ps1_database.py backend/tests/test_ps1_startup_upload.py -q
```

Result: **45 passed** (21 official data-layer, 12 database, 12 startup/upload tests), with one third-party Starlette/AnyIO deprecation warning. Coverage includes entity counts, round trips, fresh/repeated startup, missing/invalid inputs, changed bundles, concurrent duplicate uploads/startups, rollback after partial writes, original SQLite layouts and stored-data preservation, repeated accesses, results, concurrent worker claims, optimistic plan conflicts, and legacy reset isolation.

A separate differential check executed the exact baseline `database.py` from Git against the replacement: initial seeded snapshots, catalog updates, revision bumps, audit writes, and reset snapshots matched.

Pre-existing limitations were checked separately:

- `test_full_solver.py --collect-only` fails because `backend.app.models` is missing. `test_api.py` itself collects, but its legacy routes are unavailable.
- A probe of `test_api.py::test_no_identity_cannot_read_data` and all four `test_auth.py` tests gives **2 passed, 3 failed**. The failed tests expect `/api/planning-snapshot` and `/api/me`, which are absent with the legacy router disabled. The identical result was reproduced in a temporary untouched checkout of `ed7ae42`, the branch head before this refactor.
- No full legacy-suite pass is claimed. Authentication dependencies remain unchanged and are exercised by the PS1 endpoints.
