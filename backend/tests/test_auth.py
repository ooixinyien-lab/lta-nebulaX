import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.auth import dependencies


def test_production_refuses_demo_auth():
    with pytest.raises(ValidationError):
        Settings(_env_file=None,app_env='production',auth_mode='demo')


def test_reject_secret_key_in_browser_config():
    with pytest.raises(ValidationError):
        Settings(_env_file=None,auth_mode='supabase',supabase_url='https://example.supabase.co',supabase_publishable_key='sb_secret_do-not-expose')


def test_supabase_user_metadata_cannot_grant_officer(tmp_path,monkeypatch):
    async def verified(token, settings):
        assert token=='test-token'
        return {'id':'ordinary-user','email':'test@example.invalid','user_metadata':{'role':'officer'}}
    monkeypatch.setattr(dependencies,'verify_supabase',verified)
    settings=Settings(_env_file=None,app_env='test',auth_mode='supabase',database_path=str(tmp_path/'auth.sqlite3'),
                      supabase_url='https://example.supabase.co',supabase_publishable_key='sb_publishable_test',officer_user_ids='trusted-officer')
    with TestClient(create_app(settings)) as client:
        headers={'Authorization':'Bearer test-token','X-Demo-User':'demo-officer'}
        assert client.get('/api/me',headers=headers).json()['role']=='requester'
        assert client.post('/api/schedule/proposals',headers=headers).status_code==403
        assert client.get('/api/me',headers={'X-Demo-User':'demo-officer'}).status_code==401


def test_supabase_verified_allowlisted_id_is_officer(tmp_path,monkeypatch):
    async def verified(token, settings):
        return {'id':'trusted-officer','email':'officer@example.invalid'}
    monkeypatch.setattr(dependencies,'verify_supabase',verified)
    settings=Settings(_env_file=None,app_env='test',auth_mode='supabase',database_path=str(tmp_path/'auth.sqlite3'),
                      supabase_url='https://example.supabase.co',supabase_publishable_key='sb_publishable_test',officer_user_ids='trusted-officer')
    with TestClient(create_app(settings)) as client:
        headers={'Authorization':'Bearer test-token'}
        assert client.get('/api/me',headers=headers).json()['role']=='officer'
        assert client.post('/api/demo/reset',headers=headers).status_code==404
