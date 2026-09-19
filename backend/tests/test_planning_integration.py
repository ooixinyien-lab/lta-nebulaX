"""End-to-end identity, reset, and two-engine routing regressions."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.db.repositories.runs import create_run, finish_run, store_results
from backend.app.db.seed import OFFICIAL_FILES
from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow
from backend.app.main import create_app


HEADERS = {"X-Demo-User": "demo-officer"}


def _app(tmp_path: Path):
    return create_app(Settings(
        _env_file=None, app_env="test", auth_mode="demo",
        database_path=str(tmp_path / "planning.sqlite3"),
        dataset_path=str(tmp_path / "unused.json"), official_data_path=str(ROOT / "data"),
    ))


def _files():
    return [("files", (name, (ROOT / "data" / name).read_bytes(), "text/csv")) for name in OFFICIAL_FILES]


def test_reset_leaves_valid_empty_database_and_allows_fresh_upload(tmp_path: Path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.delete("/api/ps1/planning-data", headers=HEADERS)
        assert response.status_code == 200
        context = client.get("/api/ps1/planning-context", headers=HEADERS).json()
        assert context == {"instances": [], "official_runs": [], "operational_baselines": [], "operational_runs": []}
        uploaded = client.post("/api/ps1/instances/upload", files=_files(), headers=HEADERS)
        assert uploaded.status_code == 201, uploaded.text
    # A user reset disables the implicit startup fixture on subsequent restarts.
    with TestClient(app) as client:
        context = client.get("/api/ps1/planning-context", headers=HEADERS).json()
        assert len(context["instances"]) == 1


def test_official_solve_routes_to_persisted_official_worker(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    calls = []
    monkeypatch.setattr("backend.app.api.ps1_routes.execute_official_run", lambda database, run_id: calls.append(run_id))
    with TestClient(app) as client:
        context = client.get("/api/ps1/planning-context", headers=HEADERS).json()
        revision = context["instances"][0]
        response = client.post("/api/ps1/solve", headers=HEADERS, json={
            "instance_id": revision["instance_id"], "instance_revision_id": revision["revision_id"],
            "scenario": "C", "time_limit_seconds": 1,
        })
        assert response.status_code == 202
        assert calls == []
        executed = client.post(f"/api/ps1/runs/{response.json()['run_id']}/execute", headers=HEADERS)
        assert executed.status_code == 202
        assert calls == [response.json()["run_id"]]


def test_explicit_official_run_identity_wins_over_newer_run(tmp_path: Path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        revision = client.get("/api/ps1/planning-context", headers=HEADERS).json()["instances"][0]
        with app.state.db.connection(write=True) as connection:
            older = create_run(connection, revision_id=revision["revision_id"], scenario="A", created_by="test", time_limit=1)
            newer = create_run(connection, revision_id=revision["revision_id"], scenario="A", created_by="test", time_limit=1)
            store_results(connection, older.id, [AccessScheduleRow(activity_id="A001", access_seq=1, week=2, eclo=False, access_night=1)], [OccupancyScheduleRow(activity_id="A001", week=2, location_id="SEC:ALP:S01_S02:EB", co_share_group="G1")], [])
            store_results(connection, newer.id, [AccessScheduleRow(activity_id="A001", access_seq=1, week=9, eclo=False, access_night=1)], [OccupancyScheduleRow(activity_id="A001", week=9, location_id="SEC:ALP:S01_S02:EB", co_share_group="G1")], [])
            finish_run(connection, older.id, status="SUCCEEDED")
            finish_run(connection, newer.id, status="SUCCEEDED")
        params = f"mode=requirements&scenario=A&instance_revision_id={revision['revision_id']}&run_id={older.id}"
        schedule = client.get(f"/api/ps1/schedules/project?{params}", headers=HEADERS).json()
        map_week = client.get(f"/api/ps1/schedules/project?{params}&week=2", headers=HEADERS).json()
        assert schedule["identity"]["runId"] == older.id
        assert schedule["accesses"][0]["week"] == 2
        assert map_week["identity"] == schedule["identity"]
        mismatch = client.get(f"/api/ps1/schedules/project?{params.replace('scenario=A', 'scenario=B')}", headers=HEADERS)
        assert mismatch.status_code == 409


def test_operational_revision_addition_maintenance_and_stale_guard(tmp_path: Path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        revision = client.get("/api/ps1/planning-context", headers=HEADERS).json()["instances"][0]
        created = client.post("/api/ps1/schedule-insertion/baselines/from-official", headers=HEADERS, json={"official_revision_id": revision["revision_id"]})
        assert created.status_code == 201
        baseline = created.json()["baseline"]
        job = {
            "job_id": "EM-IDENTITY", "contract_number": "EM-IDENTITY", "activity_type": "Renewal",
            "nature_of_activity": "Non-live (Others)", "access_type": "C",
            "start_location_id": "SEC:ALP:S01_S02:EB", "end_location_id": "SEC:ALP:S01_S02:EB",
            "total_accesses": 1, "planned_start_date": "2027-05-03", "planned_completion_date": "2027-05-10",
            "hard_completion_date": "2027-05-10", "source": "emergency",
        }
        added = client.post(f"/api/ps1/schedule-insertion/baselines/{baseline['baseline_id']}/additions", headers=HEADERS, json={"baseline_revision": 1, "additions": [{"requested_source": "emergency", "job": job}]})
        assert added.status_code == 201, added.text
        assert added.json()["baseline"]["revision"] == 2
        stale = client.post(f"/api/ps1/schedule-insertion/baselines/{baseline['baseline_id']}/additions", headers=HEADERS, json={"baseline_revision": 1, "additions": [{"requested_source": "emergency", "job": {**job, "job_id": "EM-STALE"}}]})
        assert stale.status_code == 409
        params = f"mode=operations&scenario=B&baseline_id={baseline['baseline_id']}&baseline_revision=2"
        projection = client.get(f"/api/ps1/schedules/project?{params}", headers=HEADERS)
        assert projection.status_code == 200, projection.text
        payload = projection.json()
        assert payload["identity"]["mode"] == "operations"
        assert any(row["activity_id"] == "EM-IDENTITY" for row in payload["activities"])
        assert payload["maintenance"]
        assert all(row["source"] != "recurring" for row in payload["accesses"])
        validation = client.get(f"/api/ps1/schedule-insertion/validate?baseline_id={baseline['baseline_id']}&baseline_revision=2&scenario=B", headers=HEADERS)
        assert validation.status_code == 200
        assert isinstance(validation.json()["findings"], list)
