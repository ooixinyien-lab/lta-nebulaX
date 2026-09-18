"""Persistence regressions for the c156c5a interface and official PS1 storage."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import json
import sqlite3
import pytest

from backend.app.config import ROOT
from backend.app.database import Database
from backend.app.db.models import Plan, SolverRun, RunArtifact, RunValidationReport
from backend.app.db.records import get, insert
from backend.app.db.repositories.instances import fingerprint_files, load_revision
from backend.app.db.repositories.plans import create_plan, publish_plan, replace_draft_rows
from backend.app.db.repositories.runs import create_run, claim_next_run, update_progress, finish_run, store_results
from backend.app.db.seed import OFFICIAL_FILES, seed_official_instance
from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow, ScenarioResultRow
from backend.app.io import load_problem_from_directory


@pytest.fixture
def database(tmp_path):
    db = Database(str(tmp_path / 'state.sqlite3'), str(ROOT / 'data/demo_data.json'))
    db.initialize()
    return db


def dump(database):
    with database.connection() as c:
        return list(c.iterdump())


def test_fresh_repeated_startup_counts_and_round_trip(database):
    first = seed_official_instance(database, ROOT / 'data')
    before = dump(database)
    database.initialize()
    assert seed_official_instance(database, ROOT / 'data') == first
    assert dump(database) == before
    expected = {'lines': 2, 'stations': 20, 'sectors': 18, 'locations': 76,
                'buffer_rules': 3, 'parameters': 2, 'contracts': 14, 'activities': 54, 'files': 8}
    with database.connection() as c:
        for table, count in expected.items():
            assert c.execute(f'SELECT COUNT(*) FROM instance_{table}').fetchone()[0] == count
        assert c.execute('SELECT COUNT(*) FROM meta').fetchone()[0] == 0
        assert c.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert c.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert c.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
        assert load_revision(c, first[1]) == load_problem_from_directory(ROOT / 'data')
        for name, content in c.execute('SELECT filename,content FROM instance_file_contents'):
            assert content == (ROOT / 'data' / name).read_bytes()


@pytest.mark.parametrize('invalid', [False, True])
def test_bad_startup_rolls_back(database, tmp_path, invalid):
    folder = tmp_path / 'input'
    folder.mkdir()
    for name in OFFICIAL_FILES:
        (folder / name).write_bytes((ROOT / 'data' / name).read_bytes())
    if invalid:
        (folder / OFFICIAL_FILES[0]).write_text('bad header\ninvalid\n')
    else:
        (folder / OFFICIAL_FILES[-1]).unlink()
    before = dump(database)
    with pytest.raises(ValueError, match='Official CSV startup import failed'):
        seed_official_instance(database, folder)
    assert dump(database) == before


def test_legacy_baseline_interface_and_reset_isolation(database):
    seed_official_instance(database, ROOT / 'data')
    # Explicit baseline seeding, never part of the official startup path.
    database.initialize(seed_legacy=True)
    original = database.snapshot()
    assert original['metadata']['planning_version'] == 1
    with database.connection(write=True) as c:
        snapshot = database.snapshot(c)
        snapshot['metadata']['compatibility_marker'] = 'retained'
        database.save_catalog(c, snapshot)
        database.bump(c)
        database.audit(c, 'tester', 'catalog_changed', 'baseline interface')
        c.execute('INSERT INTO proposals VALUES (?,?)', ('proposal-legacy', '{"state":"draft"}'))
    database.initialize()
    assert database.snapshot()['metadata']['planning_version'] == 2
    assert database.snapshot()['metadata']['compatibility_marker'] == 'retained'
    assert database.snapshot()['requests'] == original['requests']
    assert database.snapshot()['committed_allocations'] == original['committed_allocations']
    before = dump(database)
    with pytest.raises(RuntimeError, match='abort'):
        with database.connection(write=True) as c:
            database.bump(c)
            database.audit(c, 'tester', 'abort', 'must roll back')
            raise RuntimeError('abort')
    assert dump(database) == before
    with database.connection(write=True) as c:
        ps1_before = [tuple(r) for r in c.execute('SELECT * FROM instance_revisions')]
        audit_before = [tuple(r) for r in c.execute('SELECT * FROM audit_events')]
        database.seed(c)
        assert [tuple(r) for r in c.execute('SELECT * FROM instance_revisions')] == ps1_before
        assert [tuple(r) for r in c.execute('SELECT * FROM audit_events')] == audit_before
    assert database.snapshot()['metadata']['planning_version'] == 3


def test_upgrade_preserves_preexisting_legacy_tables(tmp_path):
    path = tmp_path / 'baseline.sqlite3'
    # Exact baseline layouts, populated before the replacement initializes.
    with sqlite3.connect(path) as c:
        c.executescript("""
        CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, catalog TEXT NOT NULL);
        CREATE TABLE requests (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE allocations (request_id TEXT PRIMARY KEY REFERENCES requests(id), payload TEXT NOT NULL);
        CREATE TABLE proposals (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE audit (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
        """)
        c.execute('INSERT INTO meta VALUES (1,42,?)', (json.dumps({'metadata': {'planning_version': 42}}),))
        c.execute('INSERT INTO requests VALUES (?,?,?)', ('old', 'owner', '{"id":"old"}'))
        c.execute('INSERT INTO allocations VALUES (?,?)', ('old', '{"request_id":"old"}'))
        c.execute('INSERT INTO proposals VALUES (?,?)', ('proposal', '{"unchanged":true}'))
        c.execute('INSERT INTO audit VALUES (1,?,?,?,?)', ('2026-01-01', 'actor', 'action', 'detail'))
        before = {t: c.execute(f'SELECT * FROM {t}').fetchall() for t in ('meta','requests','allocations','proposals','audit')}
    db = Database(str(path))
    db.initialize()
    seed_official_instance(db, ROOT / 'data')
    with db.connection() as c:
        for table, rows in before.items():
            assert [tuple(r) for r in c.execute(f'SELECT * FROM {table}')] == rows
    assert db.snapshot()['metadata']['planning_version'] == 42


def test_runs_results_plans_and_stale_checks(database):
    _, revision = seed_official_instance(database, ROOT / 'data')
    access = [AccessScheduleRow(activity_id='A001', access_seq=i, week=i, eclo=False, access_night=1) for i in (1,2)]
    occupancy = [OccupancyScheduleRow(activity_id='A001', week=1, location_id='L1', co_share_group='G1')]
    with database.connection(write=True) as c:
        run = create_run(c, revision_id=revision, scenario='A', created_by='tester', time_limit=10)
        plan = create_plan(c, revision_id=revision, scenario='A', created_by='tester', base_run_id=run.id)
    with database.connection(write=True) as c:
        assert claim_next_run(c).id == run.id
        assert claim_next_run(c) is None
        update_progress(c, run.id, phase='DONE', score=12.5, workload_complete=True)
        store_results(c, run.id, access, occupancy, [ScenarioResultRow(scenario='A', contract_number='C1', simulated_completion_date=date(2027,1,17), overrun_days=0)])
        insert(c, RunArtifact(run_id=run.id, artifact_type='access', storage_key='old.csv', sha256='abc', content_type='text/csv'))
        insert(c, RunValidationReport(run_id=run.id, provenance='validator_unavailable', local_checks_passed=True, rule_results={'ok': True}))
        finish_run(c, run.id, status='SUCCEEDED')
        assert replace_draft_rows(c, plan.id, expected_version=1, actor='tester', access=access, occupancy=occupancy).version == 2
    before = dump(database)
    with pytest.raises(RuntimeError, match='stale'):
        with database.connection(write=True) as c:
            replace_draft_rows(c, plan.id, expected_version=1, actor='tester', access=[], occupancy=[])
    assert dump(database) == before
    with database.connection(write=True) as c:
        assert publish_plan(c, plan.id, expected_version=2, actor='officer').version == 3
    with pytest.raises(ValueError):
        with database.connection(write=True) as c:
            replace_draft_rows(c, plan.id, expected_version=3, actor='tester', access=[], occupancy=[])
    with database.connection() as c:
        assert get(c, SolverRun, run.id).status == 'SUCCEEDED'
        assert get(c, SolverRun, run.id).workload_complete
        assert get(c, Plan, plan.id).status == 'PUBLISHED'
        assert c.execute('SELECT COUNT(*) FROM run_accesses').fetchone()[0] == 2
        assert c.execute('SELECT COUNT(*) FROM plan_accesses').fetchone()[0] == 2
        assert c.execute('SELECT COUNT(*) FROM plan_change_events').fetchone()[0] == 2
    before = dump(database)
    seed_official_instance(database, ROOT / 'data')
    database.initialize()
    assert dump(database) == before


def test_foreign_keys_and_unique_fingerprint(database):
    _, revision = seed_official_instance(database, ROOT / 'data')
    before = dump(database)
    with pytest.raises(sqlite3.IntegrityError):
        with database.connection(write=True) as c:
            create_run(c, revision_id='missing', scenario='A', created_by='tester', time_limit=1)
    with pytest.raises(sqlite3.IntegrityError):
        with database.connection(write=True) as c:
            c.execute("INSERT INTO instance_revisions SELECT 'duplicate',instance_id,2,input_fingerprint,parser_version,validation_status,validation_errors,created_by,created_at FROM instance_revisions WHERE id=?", (revision,))
    assert dump(database) == before


def test_concurrent_startup_and_run_claim(database):
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: seed_official_instance(database, ROOT / 'data'), range(2)))
    assert ids[0] == ids[1]
    with database.connection(write=True) as c:
        run = create_run(c, revision_id=ids[0][1], scenario='A', created_by='tester', time_limit=1)
    def claim(_):
        with database.connection(write=True) as c:
            result = claim_next_run(c)
            return result.id if result else None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert results.count(run.id) == 1
    assert results.count(None) == 1


def test_upgrade_existing_ps1_layout_preserves_all_records(database):
    # The previous branch's SQLite layouts are retained verbatim. Removing only
    # the new migration ledger and blob table models an unversioned PS1 database.
    _, revision = seed_official_instance(database, ROOT / 'data')
    with database.connection(write=True) as c:
        run = create_run(c, revision_id=revision, scenario='A', created_by='old-worker', time_limit=5)
        create_plan(c, revision_id=revision, scenario='A', created_by='old-officer', base_run_id=run.id)
        store_results(c, run.id, [AccessScheduleRow(activity_id='A001', access_seq=1, week=1, eclo=False, access_night=1)], [], [])
        c.execute('DROP TABLE ps1_schema_version')
        c.execute('DROP TABLE instance_file_contents')
        c.execute('DROP INDEX ux_revision_fingerprint')
        c.execute('CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)')
        c.execute("INSERT INTO alembic_version VALUES ('0001_ps1_database')")
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before = {t: [tuple(r) for r in c.execute(f'SELECT * FROM {t}')] for t in tables}
    database.initialize()
    seed_official_instance(database, ROOT / 'data')
    with database.connection() as c:
        for table, rows in before.items():
            assert [tuple(r) for r in c.execute(f'SELECT * FROM {table}')] == rows


def test_fingerprint_matches_existing_algorithm():
    from hashlib import sha256
    assert fingerprint_files({'b.csv': b'2', 'a.csv': b'1'}) == sha256(b'a.csv\0' + b'1\0' + b'b.csv\0' + b'2\0').hexdigest()


def test_failed_result_write_rolls_back_and_plan_edits_compete(database):
    _, revision = seed_official_instance(database, ROOT / 'data')
    access = AccessScheduleRow(activity_id='A001', access_seq=1, week=1, eclo=False, access_night=1)
    with database.connection(write=True) as c:
        run = create_run(c, revision_id=revision, scenario='A', created_by='tester', time_limit=1)
        plan = create_plan(c, revision_id=revision, scenario='A', created_by='tester')
    before = dump(database)
    with pytest.raises(sqlite3.IntegrityError):
        with database.connection(write=True) as c:
            store_results(c, run.id, [access, access], [], [])
    assert dump(database) == before
    def edit(_):
        try:
            with database.connection(write=True) as c:
                return replace_draft_rows(c, plan.id, expected_version=1, actor='tester', access=[access], occupancy=[]).version
        except RuntimeError:
            return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, range(2)))
    assert results.count(2) == 1 and results.count('stale') == 1
    with database.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM plan_change_events').fetchone()[0] == 1


def test_initialization_closes_every_connection(tmp_path, monkeypatch):
    opened = []
    connect = sqlite3.connect
    def track(*args, **kwargs):
        connection = connect(*args, **kwargs)
        opened.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, 'connect', track)
    Database(str(tmp_path / 'closed.sqlite3')).initialize()
    assert len(opened) == 2
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            connection.execute('SELECT 1')
