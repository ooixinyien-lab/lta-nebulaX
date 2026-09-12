"""FastAPI integration tests for the comprehensive dataset and full solver."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.main import create_app


OFFICER = {"X-Demo-User": "demo-officer"}


@pytest.fixture
def canonical_client(tmp_path):
    """Start an isolated app backed by the comprehensive synthetic snapshot."""
    settings = Settings(
        _env_file=None,
        app_env="test",
        auth_mode="demo",
        solver_engine="cp_sat",
        database_path=str(tmp_path / "canonical.sqlite3"),
        dataset_path=str(ROOT / "data" / "comprehensive_synthetic_data.json"),
    )
    with TestClient(create_app(settings)) as client:
        yield client


def test_full_solver_proposal_can_be_generated_and_committed(canonical_client) -> None:
    """The app seeds, solves, validates and publishes the canonical recovery plan."""
    snapshot = canonical_client.get("/api/planning-snapshot", headers=OFFICER).json()
    response = canonical_client.post("/api/schedule/proposals", headers=OFFICER, json={})
    proposal = response.json()

    assert len(snapshot["requests"]) == 12
    assert proposal["strict_status"] == "INFEASIBLE"
    assert proposal["recovery_status"] == "OPTIMAL"
    assert proposal["validation"]["valid"] is True
    assert len(proposal["allocations"]) == 7

    commit = canonical_client.post(
        f"/api/proposals/{proposal['id']}/commit",
        headers=OFFICER,
        json={"expected_version": proposal["planning_version"]},
    )

    assert commit.status_code == 200
    published = canonical_client.get("/api/planning-snapshot", headers=OFFICER).json()
    assert len(published["committed_allocations"]) == 7


def test_full_validator_blocks_a_tampered_canonical_proposal(canonical_client) -> None:
    """Commit repeats nine-rule validation rather than trusting stored solver output."""
    proposal = canonical_client.post(
        "/api/schedule/proposals", headers=OFFICER, json={}
    ).json()
    proposal["allocations"][0]["end"] = proposal["allocations"][0]["start"]
    with canonical_client.app.state.db.connection(write=True) as connection:
        connection.execute(
            "UPDATE proposals SET payload=? WHERE id=?",
            (json.dumps(proposal), proposal["id"]),
        )

    response = canonical_client.post(
        f"/api/proposals/{proposal['id']}/commit",
        headers=OFFICER,
        json={"expected_version": proposal["planning_version"]},
    )

    assert response.status_code == 409
    assert "DURATION" in response.text


def test_catalogue_backed_request_remains_compatible_with_full_solver(
    canonical_client,
) -> None:
    """New requests carry canonical work data and are not requester-marked mandatory."""
    snapshot = canonical_client.get("/api/planning-snapshot", headers=OFFICER).json()
    source = next(item for item in snapshot["requests"] if item["id"] == "R03")
    fields = {
        "title",
        "work_type",
        "work_sector",
        "protected_sectors",
        "power_requirement",
        "required_skill",
        "preferred_engineer",
        "required_equipment_ids",
        "technicians_required",
        "phases",
        "preferred_start",
        "earliest_start",
        "deadline",
        "allowed_dates",
        "depends_on",
    }
    payload = {key: source[key] for key in fields}
    payload["depends_on"] = []
    response = canonical_client.post(
        "/api/requests",
        headers={"X-Demo-User": "demo-track"},
        json=payload,
    )
    created = response.json()

    assert response.status_code == 201
    assert created["work_type"] == "dynamic_signalling_test"
    assert created["required_engineer_roles"] == {"signalling": 1}
    assert created["mandatory"] is False
    assert created["deferrable"] is True

    result = canonical_client.post(
        "/api/schedule/proposals", headers=OFFICER, json={}
    ).json()
    assert result["status"] != "INPUT_ERROR"


def test_canonical_manual_staging_uses_the_full_validation_contract(
    canonical_client,
) -> None:
    """Editing a valid recovery plan keeps nine-rule validation through commit."""
    automatic = canonical_client.post(
        "/api/schedule/proposals", headers=OFFICER, json={}
    ).json()
    drafts = [
        {
            "request_id": item["request_id"],
            "start": item["start"],
            "engineer_id": item["engineer_id"],
            "locked": item["locked"],
        }
        for item in automatic["allocations"]
    ]

    checked = canonical_client.post(
        "/api/schedule/check",
        headers=OFFICER,
        json={"allocations": drafts},
    )
    staged = canonical_client.post(
        "/api/schedule/manual-proposals",
        headers=OFFICER,
        json={"allocations": drafts},
    )

    assert checked.json()["valid"] is True
    assert staged.json()["validation_contract"] == "full"
    assert staged.json()["validation"]["valid"] is True
