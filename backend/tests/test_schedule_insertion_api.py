"""API registration, immutable baseline revisions and export isolation."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.main import create_app
from backend.app.schedule_insertion.io import load_baseline_bundle


def test_operational_baseline_api_is_versioned_and_not_an_official_export(tmp_path: Path) -> None:
    app = create_app(Settings(
        _env_file=None,
        app_env="test",
        auth_mode="demo",
        database_path=str(tmp_path / "schedule-insertion.sqlite3"),
        dataset_path=str(tmp_path / "unused.json"),
        official_data_path=str(ROOT / "data"),
    ))
    bundle = load_baseline_bundle(ROOT / "data" / "schedule_insertion")
    with TestClient(app) as client:
        response = client.post(
            "/api/ps1/schedule-insertion/baselines",
            headers={"X-Demo-User": "demo-officer"},
            json={"baseline": bundle.model_dump(mode="json")},
        )
        assert response.status_code == 201, response.text
        assert response.json()["baseline"]["revision"] == 1
        baseline_id = response.json()["baseline"]["baseline_id"]
        fetched = client.get(f"/api/ps1/schedule-insertion/baselines/{baseline_id}", headers={"X-Demo-User": "demo-officer"})
        assert fetched.status_code == 200
        assert fetched.json()["revisions"][0]["revision"] == 1
        assert client.get("/api/ps1/schedule-insertion/runs/no-official-export", headers={"X-Demo-User": "demo-officer"}).status_code == 404
