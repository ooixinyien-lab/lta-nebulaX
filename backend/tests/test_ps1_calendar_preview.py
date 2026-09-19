"""Calendar preview discovery and automatic date-assignment integration."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.db.models import CalendarAttemptRecord
from backend.app.db.records import get
from backend.app.db.repositories.calendars import (
    create_calendar_attempt,
    get_bundle_file_bytes,
)
from backend.app.db.repositories.instances import create_instance_revision
from backend.app.main import create_app
from backend.app.ps1.calendar_models import (
    CalendariseOptions,
    ContractCalendarRule,
    demo_calendar,
)
from backend.tests.test_ps1_calendarisation import problem


HEADERS = {"X-Demo-User": "demo-officer"}
SOURCE_BYTES = {
    "SCHEDULE_ACCESS.csv": (
        b"\xef\xbb\xbfactivity_id,access_seq,week,eclo,access_night\r\n"
        b"A001,1,1,0,1\r\nA002,1,1,0,2\r\n"
    ),
    "SCHEDULE_OCCUPANCY.csv": (
        b"activity_id,week,location_id,co_share_group\n"
        b"A001,1,SEC:TST:S01_S02:EB,G1\n"
        b"A001,1,PLAT:TST:S01:EB,G1\n"
        b"A001,1,PLAT:TST:S02:EB,G1\n"
        b"A002,1,SEC:TST:S01_S02:EB,G1\n"
        b"A002,1,PLAT:TST:S01:EB,G1\n"
        b"A002,1,PLAT:TST:S02:EB,G1\n"
    ),
    "RESULTS.csv": (
        b"scenario,contract_number,simulated_completion_date,overrun_days\r\n"
        b"A,C001,2027-01-10,0\r\n"
    ),
}


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            auth_mode="demo",
            database_path=str(tmp_path / "preview.sqlite3"),
            dataset_path=str(tmp_path / "absent.json"),
            official_data_path=str(ROOT / "data"),
        )
    )
    with TestClient(app) as session:
        yield session


def create_revision(client, name="Preview instance", validation_status="VALID"):
    with client.app.state.db.connection(write=True) as connection:
        _instance, revision = create_instance_revision(
            connection,
            problem(),
            name=name,
            created_by="test",
            input_fingerprint=name,
            validation_status=validation_status,
        )
    return revision.id


def import_source(client, revision_id):
    response = client.post(
        "/api/ps1/schedule-bundles",
        headers=HEADERS,
        data={"instance_revision_id": revision_id},
        files=[
            ("files", (name, content, "text/csv"))
            for name, content in SOURCE_BYTES.items()
        ],
    )
    assert response.status_code == 201, response.text
    return response.json()["bundle_id"]


def create_demo(client, revision_id):
    response = client.post(
        "/api/ps1/enrichments/demo-calendar",
        headers=HEADERS,
        json={"instance_revision_id": revision_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["calendar_revision_id"]


def assign_dates(client, bundle_id, revision_id, calendar_id):
    response = client.post(
        f"/api/ps1/schedule-bundles/{bundle_id}/calendarize",
        headers=HEADERS,
        json={
            "calendar_revision_id": calendar_id,
            "expected_instance_revision_id": revision_id,
            "options": {"time_limit_seconds": 5, "num_search_workers": 1},
        },
    )
    assert response.status_code == 202, response.text
    attempt_id = response.json()["attempt_id"]
    result = client.get(f"/api/ps1/calendarisations/{attempt_id}", headers=HEADERS)
    assert result.status_code == 200, result.text
    return result.json()


def database_state(client):
    with client.app.state.db.connection() as connection:
        return tuple(connection.iterdump())


def test_context_requires_auth_and_explicit_missing_bundle_is_not_replaced(client):
    assert client.get("/api/ps1/calendar-preview/context").status_code == 401
    assert client.get(
        "/api/ps1/calendar-preview/context?bundle_id=missing", headers=HEADERS
    ).status_code == 404


def test_empty_source_context_uses_latest_valid_instance_without_creating_data(
    client, monkeypatch
):
    revision_id = create_revision(client)
    create_revision(client, "Newer invalid instance", validation_status="INVALID")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Reading calendar context must not invoke a solver")

    monkeypatch.setattr("backend.app.ps1.calendar_worker.calendarise", forbidden)
    monkeypatch.setattr("backend.app.ps1.solver.solve_ps1", forbidden)
    before = database_state(client)
    response = client.get("/api/ps1/calendar-preview/context", headers=HEADERS)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["bundle"] is None
    assert payload["calendar"] is None
    assert payload["latest_attempt_id"] is None
    assert payload["last_complete_attempt_id"] is None
    assert payload["instance"] == {
        "revision_id": revision_id,
        "name": "Preview instance",
        "horizon_start": "2027-01-04",
        "horizon_end": "2027-01-17",
        "horizon_weeks": 2,
    }
    assert database_state(client) == before


def test_context_matches_latest_bundle_to_its_own_instance_and_calendar(client):
    first_revision_id = create_revision(client, "First source")
    first_bundle_id = import_source(client, first_revision_id)
    first_calendar_id = create_demo(client, first_revision_id)
    revision_id = create_revision(client, "Latest imported source")
    bundle_id = import_source(client, revision_id)
    calendar_id = create_demo(client, revision_id)
    unrelated_id = create_revision(client, "Newer unrelated instance")
    create_demo(client, unrelated_id)

    before = database_state(client)
    response = client.get("/api/ps1/calendar-preview/context", headers=HEADERS)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["bundle"]["bundle_id"] == bundle_id
    assert payload["bundle"]["instance_revision_id"] == revision_id
    assert payload["bundle"]["scenario"] == "A"
    assert payload["bundle"]["access_count"] == 2
    assert payload["bundle"]["created_at"]
    assert payload["instance"]["revision_id"] == revision_id
    assert payload["instance"]["name"] == "Latest imported source"
    assert payload["calendar"]["calendar_revision_id"] == calendar_id
    assert payload["calendar"]["instance_revision_id"] == revision_id
    assert payload["calendar"]["assumed_calendar"] is True
    assert all(payload["calendar"]["assumptions"])

    chosen = client.get(
        f"/api/ps1/calendar-preview/context?bundle_id={first_bundle_id}",
        headers=HEADERS,
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["bundle"]["bundle_id"] == first_bundle_id
    assert chosen.json()["instance"]["revision_id"] == first_revision_id
    assert chosen.json()["calendar"]["calendar_revision_id"] == first_calendar_id
    assert database_state(client) == before


def test_automatic_assignment_and_failed_retry_preserve_source_and_previous_result(
    client, monkeypatch
):
    from backend.app.ps1 import calendar_worker

    revision_id = create_revision(client)
    bundle_id = import_source(client, revision_id)
    calendar_id = create_demo(client, revision_id)
    real_calendarise = calendar_worker.calendarise
    called = []

    def without_writer_lock(*args, **kwargs):
        # The CPU-bound solve must not keep the request's write transaction open.
        connection = sqlite3.connect(client.app.state.db.path, timeout=0.1)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
        finally:
            connection.close()
        called.append(True)
        return real_calendarise(*args, **kwargs)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Calendar preview must never rerun the weekly solver")

    monkeypatch.setattr(calendar_worker, "calendarise", without_writer_lock)
    monkeypatch.setattr("backend.app.ps1.solver.solve_ps1", forbidden)
    success = assign_dates(client, bundle_id, revision_id, calendar_id)
    assert success["status"] == "SUCCEEDED"
    assert success["complete"] is True
    assert len(success["assignments"]) == 2
    assert success["source_score_unchanged"] is True
    assert success["validation"]["passed"] is True
    with client.app.state.db.connection() as connection:
        assert get_bundle_file_bytes(connection, bundle_id) == SOURCE_BYTES

    restrictive = demo_calendar(revision_id).model_copy(
        update={
            "contract_rules": [
                ContractCalendarRule(contract_number="C001", nightly_workfront_limit=1)
            ]
        }
    )
    response = client.post(
        "/api/ps1/enrichments",
        headers=HEADERS,
        json=restrictive.model_dump(mode="json"),
    )
    assert response.status_code == 201, response.text
    restrictive_id = response.json()["calendar_revision_id"]
    failed = assign_dates(client, bundle_id, revision_id, restrictive_id)
    assert failed["complete"] is False
    assert failed["assignments"] == []
    assert any(
        item["rule_code"] == "SHARING_EXCEEDS_WORKFRONTS"
        for item in failed["conflicts"]
    )
    assert len(called) == 2

    # A newer unattempted calendar must not relabel the failed attempt's policy.
    unattempted = demo_calendar(revision_id).model_copy(
        update={
            "contract_rules": [
                ContractCalendarRule(
                    contract_number="C001", eligible_dates=[date(2027, 1, 6)]
                )
            ]
        }
    )
    assert client.post(
        "/api/ps1/enrichments", headers=HEADERS,
        json=unattempted.model_dump(mode="json"),
    ).status_code == 201
    response = client.get("/api/ps1/calendar-preview/context", headers=HEADERS)
    assert response.status_code == 200, response.text
    context = response.json()
    assert context["latest_attempt_id"] == failed["attempt_id"]
    assert context["last_complete_attempt_id"] == success["attempt_id"]
    assert context["calendar"]["calendar_revision_id"] == restrictive_id
    retained = client.get(
        f"/api/ps1/calendarisations/{success['attempt_id']}", headers=HEADERS
    )
    assert retained.json() == success
    with client.app.state.db.connection() as connection:
        assert get_bundle_file_bytes(connection, bundle_id) == SOURCE_BYTES


def test_targeted_processing_does_not_claim_another_or_repeat_completed_attempt(client):
    from backend.app.ps1.calendar_worker import process_attempt

    revision_id = create_revision(client)
    bundle_id = import_source(client, revision_id)
    calendar_id = create_demo(client, revision_id)
    database = client.app.state.db
    with database.connection(write=True) as connection:
        attempts = [
            create_calendar_attempt(
                connection,
                bundle_id=bundle_id,
                calendar_revision_id=calendar_id,
                commitments=[],
                options=CalendariseOptions(time_limit_seconds=5, num_search_workers=1),
                created_by="test",
            )
            for _ in range(2)
        ]
    assert process_attempt(database, attempts[1].id)
    with database.connection() as connection:
        assert get(connection, CalendarAttemptRecord, attempts[0].id).status == "QUEUED"
        completed = get(connection, CalendarAttemptRecord, attempts[1].id)
        assert completed.complete
    before = database_state(client)
    assert not process_attempt(database, attempts[1].id)
    assert not process_attempt(database, "missing")
    assert database_state(client) == before


def test_assign_default_success_and_invariance(client, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Calendar preview must never rerun the weekly solver")

    monkeypatch.setattr("backend.app.ps1.solver.solve_ps1", forbidden)

    # 1. No request body required & configured scenario directory is actually read
    scenario_dir = Path(client.app.state.settings.actual_nights_output_dir) / "A"
    before_csv = {
        name: (scenario_dir / name).read_bytes()
        for name in ("SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv", "RESULTS.csv")
    }
    response = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert response.status_code == 202, response.text
    data = response.json()
    assert "attempt_id" in data
    bundle_id = data["bundle_id"]
    calendar_id = data["calendar_revision_id"]
    assert data["scenario"] == "A"

    # Source CSV bytes on disk remain exactly unchanged
    after_csv = {
        name: (scenario_dir / name).read_bytes()
        for name in ("SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv", "RESULTS.csv")
    }
    assert before_csv == after_csv

    # Bundle stored in DB has exact matching bytes
    with client.app.state.db.connection() as connection:
        assert get_bundle_file_bytes(connection, bundle_id) == before_csv

    # Repeated calls reuse the same source bundle & calendar fingerprints
    repeated = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert repeated.status_code == 202
    assert repeated.json()["bundle_id"] == bundle_id
    assert repeated.json()["calendar_revision_id"] == calendar_id

    # Feasible mocked outputs produce complete assignment under assumed calendar without conflicts
    result = client.get(f"/api/ps1/calendarisations/{data['attempt_id']}", headers=HEADERS)
    assert result.status_code == 200
    res_json = result.json()
    assert res_json["status"] == "SUCCEEDED"
    assert res_json["complete"] is True
    assert len(res_json["conflicts"]) == 0
    assert res_json["source_score_unchanged"] is True


def test_assign_default_successful_assignment_returns_all_source_accesses(
    client, tmp_path, monkeypatch
):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Calendar preview must never rerun the weekly solver")

    monkeypatch.setattr("backend.app.ps1.solver.solve_ps1", forbidden)

    # Use problem() and SOURCE_BYTES which are known to be completely feasible
    revision_id = create_revision(client, "Feasible test revision")
    client.app.state.official_revision_id = revision_id

    test_out = tmp_path / "feasible_outputs" / "A"
    test_out.mkdir(parents=True)
    for name, content in SOURCE_BYTES.items():
        (test_out / name).write_bytes(content)

    client.app.state.settings.actual_nights_output_dir = tmp_path / "feasible_outputs"

    res = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert res.status_code == 202, res.text
    attempt_id = res.json()["attempt_id"]

    result = client.get(f"/api/ps1/calendarisations/{attempt_id}", headers=HEADERS)
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "SUCCEEDED"
    assert data["complete"] is True
    assert len(data["assignments"]) == 2
    assert {a["activity_id"] for a in data["assignments"]} == {"A001", "A002"}
    assert data["source_score_unchanged"] is True


def test_assign_default_security_and_validation_guards(client, tmp_path):
    # Requester gets 403
    assert client.post(
        "/api/ps1/calendar-preview/assign-default",
        headers={"X-Demo-User": "demo-track"},
    ).status_code == 403

    # Missing file fails clearly & no fallback to sample_outputs
    empty_dir = tmp_path / "empty_outputs"
    client.app.state.settings.actual_nights_output_dir = empty_dir
    res_empty = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert res_empty.status_code == 404
    assert "not found" in res_empty.text.lower()

    # Missing one of the three files fails clearly
    partial_dir = tmp_path / "partial_outputs" / "A"
    partial_dir.mkdir(parents=True)
    (partial_dir / "SCHEDULE_ACCESS.csv").write_bytes(b"activity_id\n")
    (partial_dir / "SCHEDULE_OCCUPANCY.csv").write_bytes(b"activity_id\n")
    client.app.state.settings.actual_nights_output_dir = tmp_path / "partial_outputs"
    res_missing = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert res_missing.status_code == 404
    assert "RESULTS.csv" in res_missing.text

    # Scenario in RESULTS.csv must match configured scenario
    mismatch_dir = tmp_path / "mismatch_outputs" / "A"
    mismatch_dir.mkdir(parents=True)
    for name in ("SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv"):
        (mismatch_dir / name).write_bytes((ROOT / "outputs" / "A" / name).read_bytes())
    (mismatch_dir / "RESULTS.csv").write_bytes(
        b"scenario,contract_number,simulated_completion_date,overrun_days\r\nB,C001,2027-01-10,0\r\n"
    )
    client.app.state.settings.actual_nights_output_dir = tmp_path / "mismatch_outputs"
    res_scen = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert res_scen.status_code == 422
    assert "does not match configured scenario" in res_scen.text

    # Output bundle must validate against seeded official revision
    invalid_dir = tmp_path / "invalid_outputs" / "A"
    invalid_dir.mkdir(parents=True)
    (invalid_dir / "SCHEDULE_ACCESS.csv").write_bytes(
        b"activity_id,access_seq,week,eclo,access_night\r\nNONEXISTENT,1,1,0,1\r\n"
    )
    (invalid_dir / "SCHEDULE_OCCUPANCY.csv").write_bytes(
        b"activity_id,week,location_id,co_share_group\r\nNONEXISTENT,1,SEC:TST:S01_S02:EB,G1\r\n"
    )
    (invalid_dir / "RESULTS.csv").write_bytes(
        b"scenario,contract_number,simulated_completion_date,overrun_days\r\nA,NONEXISTENT,2027-01-10,0\r\n"
    )
    client.app.state.settings.actual_nights_output_dir = tmp_path / "invalid_outputs"
    res_inv = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS)
    assert res_inv.status_code == 422


def test_assign_default_changed_output_bytes_creates_new_bundle(client, tmp_path):
    revision_id = create_revision(client, "Dynamic revision")
    client.app.state.official_revision_id = revision_id

    out_dir = tmp_path / "dynamic_outputs" / "A"
    out_dir.mkdir(parents=True)
    for name, content in SOURCE_BYTES.items():
        (out_dir / name).write_bytes(content)

    client.app.state.settings.actual_nights_output_dir = tmp_path / "dynamic_outputs"

    first = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS).json()
    first_bundle_id = first["bundle_id"]

    # Change bytes (add a trailing newline to SCHEDULE_ACCESS.csv)
    (out_dir / "SCHEDULE_ACCESS.csv").write_bytes(
        SOURCE_BYTES["SCHEDULE_ACCESS.csv"] + b"\r\n"
    )

    second = client.post("/api/ps1/calendar-preview/assign-default", headers=HEADERS).json()
    second_bundle_id = second["bundle_id"]

    assert first_bundle_id != second_bundle_id


def test_assign_scenario_toggle_and_context_filtering(client, tmp_path):
    revision_id = create_revision(client, "Multi-scenario revision")
    client.app.state.official_revision_id = revision_id

    # Create dummy outputs for scenario B
    out_b = tmp_path / "multi_outputs" / "B"
    out_b.mkdir(parents=True)
    (out_b / "SCHEDULE_ACCESS.csv").write_bytes(SOURCE_BYTES["SCHEDULE_ACCESS.csv"])
    (out_b / "SCHEDULE_OCCUPANCY.csv").write_bytes(SOURCE_BYTES["SCHEDULE_OCCUPANCY.csv"])
    (out_b / "RESULTS.csv").write_bytes(
        b"scenario,contract_number,simulated_completion_date,overrun_days\r\nB,C001,2027-01-10,0\r\n"
    )

    client.app.state.settings.actual_nights_output_dir = tmp_path / "multi_outputs"

    # Invalid scenario returns 422
    assert client.post(
        "/api/ps1/calendar-preview/assign-default?scenario=X", headers=HEADERS
    ).status_code == 422

    # Assign Scenario B via query param
    res_b = client.post(
        "/api/ps1/calendar-preview/assign-default?scenario=B", headers=HEADERS
    )
    assert res_b.status_code == 202, res_b.text
    data_b = res_b.json()
    assert data_b["scenario"] == "B"

    # Context query with scenario=B returns bundle for scenario B
    ctx_b = client.get("/api/ps1/calendar-preview/context?scenario=B", headers=HEADERS)
    assert ctx_b.status_code == 200
    assert ctx_b.json()["bundle"]["scenario"] == "B"


@pytest.mark.parametrize("scenario,expected_access_count", [
    ("A", 114),
    ("B", 104),
    ("C", 91),
])
def test_mocked_outputs_produce_feasible_calendar_for_all_scenarios(
    client, scenario, expected_access_count
):
    res = client.post(
        f"/api/ps1/calendar-preview/assign-default?scenario={scenario}",
        headers=HEADERS,
    )
    assert res.status_code == 202, res.text
    attempt_id = res.json()["attempt_id"]
    assert res.json()["scenario"] == scenario

    cal_res = client.get(f"/api/ps1/calendarisations/{attempt_id}", headers=HEADERS)
    assert cal_res.status_code == 200
    data = cal_res.json()
    assert data["status"] == "SUCCEEDED"
    assert data["solver_status"] == "OPTIMAL"
    assert data["complete"] is True
    assert len(data["conflicts"]) == 0
    assert len(data["assignments"]) == expected_access_count
    assert data["source_score_unchanged"] is True


