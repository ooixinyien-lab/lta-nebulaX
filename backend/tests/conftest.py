import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.config import ROOT, Settings
from backend.app.main import create_app

@pytest.fixture
def snapshot():
    return json.loads((ROOT / 'data' / 'demo_data.json').read_text())

@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, app_env='test', auth_mode='demo',
                        solver_engine='demo_search', database_path=str(tmp_path / 'test.sqlite3'))
    with TestClient(create_app(settings)) as test_client:
        yield test_client

@pytest.fixture
def officer():
    return {'X-Demo-User': 'demo-officer'}

@pytest.fixture
def requester():
    return {'X-Demo-User': 'demo-track'}

@pytest.fixture
def new_request(snapshot):
    r = snapshot['requests'][3]
    keys = ['title','work_sector','protected_sectors','power_requirement','required_skill',
            'preferred_engineer','required_equipment_ids','technicians_required','phases',
            'preferred_start','earliest_start','deadline','allowed_dates','depends_on']
    return {k:r[k] for k in keys}
