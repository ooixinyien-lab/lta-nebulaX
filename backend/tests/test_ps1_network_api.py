"""Test suite for PS1 Network Map API, mock schedule source, and projection service."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.network_schedule import SampleOutputScheduleSource


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_network_context(client: TestClient):
    resp = client.get("/api/ps1/network/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["horizon"]["weeks"] == 30
    assert data["horizon"]["startDate"] == "2027-01-04"
    assert data["scheduleSource"] in ("solved_outputs", "sample_outputs")

    scenarios = {s["scenario"]: s for s in data["scenarios"]}
    assert "A" in scenarios
    assert scenarios["A"]["available"] is True
    assert scenarios["A"]["source"] in ("solved", "mock")

    assert "B" in scenarios
    assert scenarios["B"]["available"] is True
    assert scenarios["B"]["source"] in ("solved", "mock")

    assert "C" in scenarios
    assert scenarios["C"]["available"] is True
    assert scenarios["C"]["source"] in ("solved", "mock")


def test_network_topology(client: TestClient):
    resp = client.get("/api/ps1/network/topology")
    assert resp.status_code == 200
    data = resp.json()

    # Invariants from PS1 specification
    assert len(data["lines"]) == 2
    assert len(data["stations"]) == 20
    assert len(data["sectors"]) == 18
    assert len(data["locations"]) == 76

    line_codes = {l["line_code"] for l in data["lines"]}
    assert line_codes == {"ALP", "BET"}

    # Distinct composite identity for interchange stations
    h01_stations = [s for s in data["stations"] if s["station_id"] == "H01"]
    assert len(h01_stations) == 2
    assert {s["line_code"] for s in h01_stations} == {"ALP", "BET"}
    assert all(s["is_interchange"] for s in h01_stations)


def test_network_activities_and_footprints(client: TestClient):
    resp = client.get("/api/ps1/network/activities")
    assert resp.status_code == 200
    activities = resp.json()
    assert len(activities) == 54

    act_map = {a["activityId"]: a for a in activities}

    # Find a Live activity traversing the interchange (e.g. A074 or check activities)
    live_activities = [a for a in activities if a["natureOfActivity"] == "Live"]
    assert len(live_activities) > 0

    for live_act in live_activities:
        # Live activities must have opposite-bound mirrored locations
        assert len(live_act["mirroredLocations"]) > 0
        # If traversing H01 or H02, crossLineLocations must be present
        if any("H01" in loc or "H02" in loc for loc in live_act["coreLocations"]):
            assert len(live_act["crossLineLocations"]) > 0


def test_mock_schedule_source_direct():
    source = SampleOutputScheduleSource()
    scenarios = {s.scenario: s for s in source.get_available_scenarios()}
    assert scenarios["A"].available is True
    assert scenarios["B"].available is True
    assert scenarios["C"].available is True
    assert scenarios["A"].source in ("solved", "mock")

    # Week 22 accesses
    w22_accesses = source.get_accesses("A", week=22)
    assert len(w22_accesses) > 0
    assert all(a.week == 22 for a in w22_accesses)

    # Filtering by activity
    a001_accesses = source.get_accesses("A", activity_id="A001")
    assert len(a001_accesses) > 0
    assert all(a.activity_id == "A001" for a in a001_accesses)


def test_network_occupancy_weekly_aggregation(client: TestClient):
    resp = client.get("/api/ps1/network/occupancy?scenario=A&week=22")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["week"] == 22
    assert len(data["activeActivities"]) > 0
    assert len(data["locationOccupancy"]) > 0

    # Ensure capacity values are present and structured
    for loc_id, occ in data["locationOccupancy"].items():
        assert "supplyCapacity" in occ
        assert "occupiedGroupCount" in occ
        assert "peakOccupiedGroupCount" in occ
        assert "capacityExceeded" in occ
        assert isinstance(occ["coShareGroups"], list)
        for grp in occ["coShareGroups"]:
            assert "isCompliant" in grp
            assert "activities" in grp


def test_network_occupancy_scenarios_b_and_c(client: TestClient):
    resp_b = client.get("/api/ps1/network/occupancy?scenario=B&week=21")
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["available"] is True
    assert len(data_b["activeActivities"]) > 0

    resp_c = client.get("/api/ps1/network/occupancy?scenario=C&week=21")
    assert resp_c.status_code == 200
    data_c = resp_c.json()
    assert data_c["available"] is True
    assert len(data_c["activeActivities"]) > 0


def test_network_occupancy_scenario_unavailable(client: TestClient):
    resp = client.get("/api/ps1/network/occupancy?scenario=UNKNOWN&week=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert len(data["activeActivities"]) == 0
    assert len(data["locationOccupancy"]) == 0


def test_protection_does_not_consume_core_capacity(client: TestClient):
    resp = client.get("/api/ps1/network/occupancy?scenario=A&week=22")
    assert resp.status_code == 200
    data = resp.json()
    protection = data["protection"]

    # Any location that is ONLY in protection (not in core occupancy)
    # should not have occupancy slots counted against it
    core_locations = set(data["locationOccupancy"].keys())
    buffer_locations = set(protection["bufferLocations"].keys())
    protection_only = buffer_locations - core_locations

    for prot_loc in protection_only:
        assert prot_loc not in data["locationOccupancy"]
