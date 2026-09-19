"""Integration tests for the explanation and chat REST endpoints."""
import pytest


def test_get_explanation_endpoint_mock_source(client, officer):
    # Retrieve explanation for sample/mock run
    resp = client.get(
        "/api/ps1/runs/sample_run/explanations/A001",
        headers=officer,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "fact_pack" in data
    assert "fallback_summary" in data
    assert data["fact_pack"]["scope"]["data_source"] == "mock"
    assert data["fact_pack"]["activity"]["activity_id"] == "A001"
    assert "22" in data["fallback_summary"]


def test_post_chat_turn_deterministic_fallback(client, officer):
    payload = {
        "run_id": "sample_run",
        "question": "Why is A001 scheduled here?",
        "selected_activity_id": "A001",
    }
    resp = client.post("/api/ps1/chat", headers=officer, json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()
    assert res["response_mode"] == "deterministic_fallback"
    assert "A001" in res["answer"]
    assert len(res["citations"]) > 0
    assert "session_id" in res
    assert res["provenance"]["prompt_template_version"] == "schedule-explainer-v1"


def test_chat_unauthenticated_request_rejected(client):
    resp = client.get("/api/ps1/runs/sample_run/explanations/A001")
    assert resp.status_code == 401

    resp = client.post("/api/ps1/chat", json={"run_id": "sample_run", "question": "test"})
    assert resp.status_code == 401


def test_chat_max_question_length_enforced(client, officer):
    payload = {
        "run_id": "sample_run",
        "question": "A" * 3000,
    }
    resp = client.post("/api/ps1/chat", headers=officer, json=payload)
    assert resp.status_code == 400
    assert "exceeds maximum allowed length" in resp.json()["detail"]


def test_post_chat_turn_database_source_auto_resolution(client, officer):
    from backend.app.config import ROOT
    from backend.app.db.seed import OFFICIAL_FILES
    from backend.app.db.repositories.runs import create_run, finish_run, store_results
    from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow

    # Upload bundle or retrieve existing revision if already present
    bundle_files = [("files", (name, (ROOT / "data" / name).read_bytes(), "text/csv")) for name in OFFICIAL_FILES]
    up_resp = client.post("/api/ps1/instances/upload", headers=officer, files=bundle_files)
    if up_resp.status_code == 201:
        rev_id = up_resp.json()["revision_id"]
    else:
        assert up_resp.status_code == 409
        rev_id = up_resp.json()["detail"]["revision_id"]

    # Insert a succeeded solver run
    app = client.app
    db = getattr(app.state, "db", getattr(app.state, "ps1_db", None))
    with db.connection(write=True) as conn:
        run = create_run(conn, revision_id=rev_id, scenario="A", created_by="demo-officer", time_limit=10.0)
        store_results(
            conn,
            run.id,
            [AccessScheduleRow(activity_id="A001", access_seq=1, week=12, eclo=0, access_night=1)],
            [OccupancyScheduleRow(activity_id="A001", week=12, location_id="SEC:BET:S15_S16", co_share_group="g1")],
            [],
        )
        conn.execute("UPDATE solver_runs SET incumbent_score=15.0 WHERE id=?", (run.id,))
        finish_run(conn, run.id, status="SUCCEEDED")

    # Send chat turn without run_id, expecting auto-resolution to the database solver run
    payload = {
        "question": "Where is A001 scheduled?",
        "selected_activity_id": "A001",
        "scenario": "A",
    }
    resp = client.post("/api/ps1/chat", headers=officer, json=payload)
    assert resp.status_code == 200, resp.text
    res = resp.json()
    assert res["response_mode"] == "deterministic_fallback"
    assert "A001" in res["answer"]
    assert res["provenance"]["run_id"] == run.id
    # Assert citation comes from database placement
    citations = res["citations"]
    assert any(c["run_id"] == run.id for c in citations)
