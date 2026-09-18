"""Startup, upload, failure atomicity and retained PS1 response contracts."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi.testclient import TestClient
from backend.app.config import ROOT, Settings
from backend.app.main import create_app
from backend.app.db.seed import OFFICIAL_FILES
from backend.app.db.repositories.instances import load_revision
from backend.app.db.repositories.runs import claim_next_run, finish_run, store_results
from backend.app.domain_models import AccessScheduleRow

HEADERS = {'X-Demo-User': 'demo-officer'}


def bundle():
    return {name: (ROOT / 'data' / name).read_bytes() for name in OFFICIAL_FILES}


def changed_bundle():
    files = bundle()
    files['01_LINES.csv'] = files['01_LINES.csv'].replace(b'Alpha', b'Changed Alpha')
    if files == bundle():
        files['01_LINES.csv'] += b'\n'
    return files


def upload(client, files):
    return client.post('/api/ps1/instances/upload', headers=HEADERS,
        files=[('files', (name, content, 'text/csv')) for name, content in files.items()])


def state(db):
    with db.connection() as c:
        return list(c.iterdump())


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(_env_file=None, app_env='test', auth_mode='demo',
        database_path=str(tmp_path / 'app.sqlite3'), dataset_path=str(tmp_path / 'absent.json'),
        official_data_path=str(ROOT / 'data')))


def test_startup_needs_no_legacy_dataset_and_reuses_duplicate(app, tmp_path):
    with TestClient(app) as client:
        before = state(app.state.db)
        files_before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*.csv')}
        response = upload(client, bundle())
        assert response.status_code == 409
        detail = response.json()['detail']
        assert detail['instance_id'] and detail['revision_id'] and len(detail['fingerprint']) == 64
        assert 'already exists' in detail['message']
        assert state(app.state.db) == before
        assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*.csv')} == files_before
        response = client.get('/api/ps1/instances/' + detail['instance_id'], headers=HEADERS)
        assert response.status_code == 200
        assert response.json()['revisions'][0]['id'] == detail['revision_id']
        assert client.get('/api/ps1/instances/' + detail['instance_id']).status_code == 401
    with TestClient(app):
        assert state(app.state.db) == before


def test_changed_bundle_is_immutable_and_rejected_on_second_upload(app):
    with TestClient(app) as client:
        with app.state.db.connection() as c:
            old_id = c.execute('SELECT id FROM instance_revisions').fetchone()[0]
            original = load_revision(c, old_id)
        response = upload(client, changed_bundle())
        assert response.status_code == 201, response.text
        created = response.json()
        assert created['entity_counts']['activities'] == 54
        assert created['revision_id'] != old_id
        before = state(app.state.db)
        duplicate = upload(client, changed_bundle())
        assert duplicate.status_code == 409
        assert duplicate.json()['detail']['revision_id'] == created['revision_id']
        assert state(app.state.db) == before
        with app.state.db.connection() as c:
            assert load_revision(c, old_id) == original
            assert c.execute('SELECT COUNT(*) FROM instances').fetchone()[0] == 2
            assert c.execute('SELECT COUNT(*) FROM instance_files').fetchone()[0] == 16


@pytest.mark.parametrize('kind', ['missing', 'extra', 'invalid', 'encoding', 'duplicate_filename'])
def test_rejected_upload_changes_nothing(app, kind):
    with TestClient(app) as client:
        files = bundle()
        if kind == 'missing':
            files.pop(OFFICIAL_FILES[-1])
        elif kind == 'extra':
            files['unexpected.csv'] = b'bad'
        elif kind == 'invalid':
            files[OFFICIAL_FILES[0]] = b'bad header\n'
        elif kind == 'encoding':
            files[OFFICIAL_FILES[0]] = b'\xff'
        before = state(app.state.db)
        if kind == 'duplicate_filename':
            response = client.post('/api/ps1/instances/upload', headers=HEADERS,
                files=[('files', (OFFICIAL_FILES[0], files[OFFICIAL_FILES[0]]))] * 8)
        else:
            response = upload(client, files)
        assert response.status_code == 422
        assert state(app.state.db) == before


def test_concurrent_duplicate_uploads(app):
    # Independent clients/connections exercise the database write lock across
    # simultaneous requests, rather than relying on one async event loop.
    with TestClient(app) as first, TestClient(app) as second:
        barrier = Barrier(2)
        def submit(client):
            barrier.wait(timeout=5)
            return upload(client, changed_bundle())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [first, second]))
        assert sorted(r.status_code for r in results) == [201, 409]
        success = next(r.json() for r in results if r.status_code == 201)
        conflict = next(r.json()['detail'] for r in results if r.status_code == 409)
        assert conflict['instance_id'] == success['instance_id']
        assert conflict['revision_id'] == success['revision_id']
        with app.state.db.connection() as c:
            assert c.execute('SELECT COUNT(*) FROM instances').fetchone()[0] == 2
            assert c.execute("SELECT COUNT(*) FROM audit_events WHERE action='instance_uploaded'").fetchone()[0] == 1


def test_mid_import_failure_has_no_records_or_orphan_files(app, tmp_path, monkeypatch):
    import backend.app.db.seed as seed
    with TestClient(app, raise_server_exceptions=False) as client:
        before = state(app.state.db)
        def fail_audit(*args, **kwargs):
            raise RuntimeError('injected failure after entities and blobs')
        with monkeypatch.context() as patch:
            patch.setattr(seed, 'record_event', fail_audit)
            assert upload(client, changed_bundle()).status_code == 500
        assert state(app.state.db) == before
        assert not list(tmp_path.rglob('*.csv'))
        assert upload(client, changed_bundle()).status_code == 201


@pytest.mark.parametrize('missing', [True, False])
def test_startup_errors_are_explicit_and_empty(tmp_path, missing):
    directory = tmp_path / 'data'
    directory.mkdir()
    for name, content in bundle().items():
        (directory / name).write_bytes(content)
    if missing:
        (directory / OFFICIAL_FILES[-1]).unlink()
    else:
        (directory / OFFICIAL_FILES[0]).write_text('bad header\n')
    app = create_app(Settings(_env_file=None, database_path=str(tmp_path / 'failed.sqlite3'), official_data_path=str(directory)))
    with pytest.raises(ValueError, match='Official CSV startup import failed'):
        with TestClient(app):
            pass
    with app.state.db.connection() as c:
        for table in ('instances', 'instance_revisions', 'instance_files', 'instance_file_contents', 'audit_events'):
            assert c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0


def test_run_lifecycle_response_contract_and_restart(app):
    with TestClient(app) as client:
        instance = upload(client, bundle()).json()['detail']['instance_id']
        response = client.post('/api/ps1/solve', headers=HEADERS, json={'instance_id': instance, 'scenario': 'A'})
        assert response.status_code == 202
        run_id = response.json()['run_id']
        assert response.json()['status'] == 'QUEUED'
        with app.state.db.connection(write=True) as c:
            assert claim_next_run(c).id == run_id
            store_results(c, run_id, [AccessScheduleRow(activity_id='A001', access_seq=i, week=i, eclo=False, access_night=1) for i in (1,2)], [], [])
            finish_run(c, run_id, status='SUCCEEDED')
            # Older SQLAlchemy SQLite rows used naive timestamps.
            c.execute("UPDATE solver_runs SET started_at='2026-09-19 01:00:00',finished_at='2026-09-19 01:00:01' WHERE id=?", (run_id,))
        response = client.get(f'/api/ps1/runs/{run_id}/progress', headers=HEADERS)
        assert response.status_code == 200
        assert response.json()['status'] == 'SUCCEEDED'
        assert response.json()['elapsed_seconds'] >= 0
        response = client.get(f'/api/ps1/runs/{run_id}/results', headers=HEADERS)
        assert response.status_code == 200
        assert len(response.json()['accesses']) == 2
        assert response.json()['accesses'][0] == {'activity_id': 'A001', 'access_seq': 1, 'week': 1, 'eclo': False, 'access_night': 1}
        assert client.get('/api/ps1/runs/missing/progress', headers=HEADERS).status_code == 404
        before = state(app.state.db)
    with TestClient(app) as client:
        assert state(app.state.db) == before
        assert client.get(f'/api/ps1/runs/{run_id}/results', headers=HEADERS).json() == response.json()
