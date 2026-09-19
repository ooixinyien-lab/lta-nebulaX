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
