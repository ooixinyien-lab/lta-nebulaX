"""Unit tests for the typed domain model layer (backend/app/models.py).

Verifies all 18 requirements from the CP-SAT typed domain layer specification.
"""
import ast
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from pydantic import ValidationError

from backend.app.models import (
    SGT,
    Allocation,
    Blackout,
    CompatibilityRule,
    Conflict,
    ConflictCode,
    DomainModel,
    EngineeringWindow,
    Engineer,
    Equipment,
    JobTypeEntry,
    MaintenanceRequest,
    Phase,
    PhaseType,
    PlanningRules,
    PlanningSnapshot,
    PowerRequirement,
    PowerZone,
    RequestStatus,
    ResourcePool,
    Sector,
    Station,
    TimeWindow,
    TimingMode,
    TransitLeg,
    TransitRoute,
    TransitSchedule,
    Vehicle,
    VehicleType,
    TravelTimeEntry,
    TravelTimeMatrix,
)
from backend.app.services.checker import check_plan
from backend.app.services.common import preferred_plan

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "demo_data.json"


@pytest.fixture
def raw_fixture():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------------------------------------------------------
# 1. Load demo_data.json through PlanningSnapshot.from_json
# -----------------------------------------------------------------------------

def test_01_load_demo_data_from_json():
    with open(FIXTURE_PATH, "rb") as f:
        payload = f.read()
    snapshot = PlanningSnapshot.from_json(payload)
    assert isinstance(snapshot, PlanningSnapshot)
    assert snapshot.metadata.schema_version == "1.0"
    assert snapshot.metadata.planning_version == 1
    assert snapshot.metadata.timezone == "Asia/Singapore"


# -----------------------------------------------------------------------------
# 2. Verify expected fixture counts and computed durations
# -----------------------------------------------------------------------------

def test_02_fixture_counts_and_computed_durations(raw_fixture):
    snapshot = PlanningSnapshot.from_dict(raw_fixture)
    assert len(snapshot.stations) == 7
    assert len(snapshot.sectors) == 6
    assert len(snapshot.engineering_windows) == 7
    assert len(snapshot.blackouts) == 1
    assert len(snapshot.engineers) == 4
    assert len(snapshot.equipment) == 3
    assert len(snapshot.resource_pools) == 1
    assert len(snapshot.requests) == 4
    assert len(snapshot.committed_allocations) == 2

    # Computed duration on requests: setup + work + test + handback
    req_map = {r.id: r for r in snapshot.requests}
    assert req_map["R01"].duration_minutes == 10 + 50 + 10 + 10  # 80
    assert req_map["R02"].duration_minutes == 10 + 30 + 10 + 10  # 60
    assert req_map["R03"].duration_minutes == 10 + 30 + 10 + 10  # 60
    assert req_map["R04"].duration_minutes == 10 + 45 + 10 + 10  # 75

    # Computed duration on blackout: 03:00 to 04:30 = 90 min
    assert snapshot.blackouts[0].duration_minutes == 90


# -----------------------------------------------------------------------------
# 3. Verify legacy ANY normalization and ambiguity rejection
# -----------------------------------------------------------------------------

def test_03_legacy_any_normalization_and_conflict_rejection(raw_fixture):
    snapshot = PlanningSnapshot.from_dict(raw_fixture)
    # R02 had "ANY" in the raw fixture
    r02 = next(r for r in snapshot.requests if r.id == "R02")
    assert r02.power_requirement == PowerRequirement.NONE

    # Rules power_values had ["ON", "OFF", "ANY"] -> normalized to NONE
    assert PowerRequirement.NONE in snapshot.planning_rules.power_values
    assert "ANY" not in [v.value for v in snapshot.planning_rules.power_values]

    # Rules power_compatibility keys had "ANY" -> normalized to NONE
    compat = snapshot.planning_rules.power_compatibility
    assert PowerRequirement.NONE in compat
    assert "ANY" not in [k.value for k in compat.keys()]
    assert PowerRequirement.NONE in compat[PowerRequirement.ON]

    # Reject ambiguous conflicting definitions in power_values
    bad_rules = deepcopy(raw_fixture["planning_rules"])
    bad_rules["power_values"] = ["ON", "OFF", "ANY", "NONE"]
    with pytest.raises(ValidationError, match="Ambiguous conflicting definitions"):
        PlanningRules.model_validate(bad_rules)

    # Reject ambiguous conflicting definitions in outer compatibility keys
    bad_rules2 = deepcopy(raw_fixture["planning_rules"])
    bad_rules2["power_compatibility"]["NONE"] = {"ON": True, "OFF": True, "NONE": True}
    with pytest.raises(ValidationError, match="Ambiguous conflicting definitions"):
        PlanningRules.model_validate(bad_rules2)

    # Reject ambiguous conflicting definitions in inner compatibility keys
    bad_rules3 = deepcopy(raw_fixture["planning_rules"])
    bad_rules3["power_compatibility"]["ON"]["NONE"] = True
    with pytest.raises(ValidationError, match="Ambiguous conflicting definitions"):
        PlanningRules.model_validate(bad_rules3)


# -----------------------------------------------------------------------------
# 4. Verify legacy mandatory_in_this_demo and string priority
# -----------------------------------------------------------------------------

def test_04_mandatory_in_this_demo_and_priority_preservation(raw_fixture):
    snapshot = PlanningSnapshot.from_dict(raw_fixture)
    r01 = next(r for r in snapshot.requests if r.id == "R01")
    assert r01.mandatory is True
    assert r01.priority == "normal"
    assert r01.urgency_score == 3  # default 3 maintained; not mapped to arbitrary score


# -----------------------------------------------------------------------------
# 5. Verify scheduled requests derive approval and existing starts
# -----------------------------------------------------------------------------

def test_05_scheduled_requests_derive_approval_and_existing_starts(raw_fixture):
    snapshot = PlanningSnapshot.from_dict(raw_fixture)
    r01 = next(r for r in snapshot.requests if r.id == "R01")
    r02 = next(r for r in snapshot.requests if r.id == "R02")
    r03 = next(r for r in snapshot.requests if r.id == "R03")

    assert r01.status == RequestStatus.scheduled
    assert r01.approved is True
    assert r01.existing_start == datetime(2026, 9, 14, 1, 0, tzinfo=SGT)

    assert r02.status == RequestStatus.scheduled
    assert r02.approved is True
    assert r02.existing_start == datetime(2026, 9, 14, 1, 30, tzinfo=SGT)

    assert r03.status == RequestStatus.submitted
    assert r03.approved is False
    assert r03.existing_start is None


# -----------------------------------------------------------------------------
# 6. Verify committed locked allocations do not set request frozen=True
# -----------------------------------------------------------------------------

def test_06_locked_allocations_do_not_infer_request_frozen(raw_fixture):
    snapshot = PlanningSnapshot.from_dict(raw_fixture)
    for a in snapshot.committed_allocations:
        assert a.locked is True

    r01 = next(r for r in snapshot.requests if r.id == "R01")
    r02 = next(r for r in snapshot.requests if r.id == "R02")
    assert r01.frozen is False
    assert r02.frozen is False


# -----------------------------------------------------------------------------
# 7. Verify timezone-naive, second-precision, reversed, and zero-duration rejected
# -----------------------------------------------------------------------------

def test_07_invalid_time_windows_rejected():
    # Naive datetime rejected
    with pytest.raises(ValidationError, match="timezone-aware"):
        TimeWindow(
            start=datetime(2026, 9, 14, 1, 0),
            end=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
        )

    # Second precision rejected
    with pytest.raises(ValidationError, match="whole-minute precision"):
        TimeWindow(
            start=datetime(2026, 9, 14, 1, 0, 15, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 0, 0, tzinfo=SGT),
        )

    # Microsecond precision rejected
    with pytest.raises(ValidationError, match="whole-minute precision"):
        TimeWindow(
            start=datetime(2026, 9, 14, 1, 0, 0, 500, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 0, 0, 0, tzinfo=SGT),
        )

    # Reversed interval (start > end) rejected
    with pytest.raises(ValidationError, match="before end"):
        TimeWindow(
            start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
        )

    # Zero duration (start == end) rejected
    with pytest.raises(ValidationError, match="before end"):
        TimeWindow(
            start=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
        )


# -----------------------------------------------------------------------------
# 8. Verify engineering-window handback and usable_end
# -----------------------------------------------------------------------------

def test_08_engineering_window_handback_and_usable_end():
    ew = EngineeringWindow(
        date="2026-09-14",
        sector_ids=["S01", "S02"],
        start=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
        end=datetime(2026, 9, 14, 4, 30, tzinfo=SGT),
        handback_buffer_minutes=20,
    )
    assert ew.usable_end == datetime(2026, 9, 14, 4, 10, tzinfo=SGT)

    # Handback buffer exceeds total window duration
    with pytest.raises(ValidationError, match="positive usable window"):
        EngineeringWindow(
            date="2026-09-14",
            sector_ids=["S01"],
            start=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            handback_buffer_minutes=20,
        )

    # Date string mismatch with start date in project timezone
    with pytest.raises(ValidationError, match="does not match declared date"):
        EngineeringWindow(
            date="2026-09-15",
            sector_ids=["S01"],
            start=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 4, 30, tzinfo=SGT),
            handback_buffer_minutes=20,
        )


# -----------------------------------------------------------------------------
# 9. Verify phase ordering, timing modes, date bounds, deferral, and frozen
# -----------------------------------------------------------------------------

def test_09_phase_ordering_timing_modes_and_invariants(raw_fixture):
    base_req = deepcopy(raw_fixture["requests"][0])

    # Out-of-order phases rejected
    bad_phases = deepcopy(base_req)
    bad_phases["phases"] = [
        {"name": "work", "duration_minutes": 50},
        {"name": "setup", "duration_minutes": 10},
        {"name": "test", "duration_minutes": 10},
        {"name": "handback", "duration_minutes": 10},
    ]
    with pytest.raises(ValidationError, match="setup, work, test, handback in that exact order"):
        MaintenanceRequest.model_validate(bad_phases)

    # Work phase duration <= 0 rejected
    zero_work = deepcopy(base_req)
    zero_work["phases"][1]["duration_minutes"] = 0
    with pytest.raises(ValidationError, match="Work phase duration must be positive"):
        MaintenanceRequest.model_validate(zero_work)

    # Mismatched legacy duration_minutes input rejected
    mismatched_dur = deepcopy(base_req)
    mismatched_dur["duration_minutes"] = 120
    with pytest.raises(ValidationError, match="does not match sum of phases"):
        MaintenanceRequest.model_validate(mismatched_dur)

    # TimingMode.EXACT requires preferred_start and exact bounds
    exact_req = deepcopy(base_req)
    exact_req["timing_mode"] = "EXACT"
    exact_req["preferred_start"] = "2026-09-14T01:00:00+08:00"
    exact_req["earliest_start"] = "2026-09-14T01:00:00+08:00"
    exact_req["deadline"] = "2026-09-14T02:20:00+08:00"  # 01:00 + 80m
    m_exact = MaintenanceRequest.model_validate(exact_req)
    assert m_exact.timing_mode == TimingMode.EXACT

    # TimingMode.EXACT with mismatched deadline rejected
    exact_bad_deadline = deepcopy(exact_req)
    exact_bad_deadline["deadline"] = "2026-09-14T03:00:00+08:00"
    with pytest.raises(ValidationError, match="EXACT timing mode requires deadline"):
        MaintenanceRequest.model_validate(exact_bad_deadline)

    # TimingMode.ANY_TIME cannot have preferred_start
    anytime_bad = deepcopy(base_req)
    anytime_bad["timing_mode"] = "ANY_TIME"
    anytime_bad["preferred_start"] = "2026-09-14T01:00:00+08:00"
    with pytest.raises(ValidationError, match="ANY_TIME timing mode permits no preferred_start"):
        MaintenanceRequest.model_validate(anytime_bad)

    # TimingMode.ANY_TIME with preferred_start=None is valid
    anytime_good = deepcopy(base_req)
    anytime_good["timing_mode"] = "ANY_TIME"
    anytime_good["preferred_start"] = None
    m_anytime = MaintenanceRequest.model_validate(anytime_good)
    assert m_anytime.timing_mode == TimingMode.ANY_TIME

    # preferred_start date not in allowed_dates rejected
    bad_date_bound = deepcopy(base_req)
    bad_date_bound["allowed_dates"] = ["2026-09-15"]
    bad_date_bound["preferred_start"] = "2026-09-14T01:00:00+08:00"
    with pytest.raises(ValidationError, match="preferred_start date must be included in allowed_dates"):
        MaintenanceRequest.model_validate(bad_date_bound)

    # frozen=True requires approved=True
    bad_frozen = deepcopy(base_req)
    bad_frozen["frozen"] = True
    bad_frozen["approved"] = False
    with pytest.raises(ValidationError, match="Request cannot be frozen=True unless approved=True"):
        MaintenanceRequest.model_validate(bad_frozen)

    # Urgency score constrained to 1-5
    bad_urgency = deepcopy(base_req)
    bad_urgency["urgency_score"] = 6
    with pytest.raises(ValidationError):
        MaintenanceRequest.model_validate(bad_urgency)


# -----------------------------------------------------------------------------
# 10. Verify unknown sectors, stations, engineers, equipment, etc. rejected
# -----------------------------------------------------------------------------

def test_10_unknown_references_rejected(raw_fixture):
    # Unknown station in sector
    data = deepcopy(raw_fixture)
    data["sectors"][0]["from_station"] = "UNKNOWN_STA"
    with pytest.raises(ValidationError, match="not reference a known station"):
        PlanningSnapshot.model_validate(data)

    # Unknown work sector in request
    data = deepcopy(raw_fixture)
    data["requests"][0]["work_sector"] = "UNKNOWN_SEC"
    data["requests"][0]["protected_sectors"] = ["UNKNOWN_SEC"]
    with pytest.raises(ValidationError, match="not found in sectors"):
        PlanningSnapshot.model_validate(data)

    # Unknown eligible engineer
    data = deepcopy(raw_fixture)
    data["requests"][0]["eligible_engineers"].append("E99")
    with pytest.raises(ValidationError, match="unknown eligible engineer"):
        PlanningSnapshot.model_validate(data)

    # Unknown required equipment
    data = deepcopy(raw_fixture)
    data["requests"][0]["required_equipment_ids"].append("Q99")
    with pytest.raises(ValidationError, match="unknown equipment"):
        PlanningSnapshot.model_validate(data)

    # Unknown dependency
    data = deepcopy(raw_fixture)
    data["requests"][0]["depends_on"].append("R99")
    with pytest.raises(ValidationError, match="unknown dependency"):
        PlanningSnapshot.model_validate(data)

    # Unknown request in allocation
    data = deepcopy(raw_fixture)
    data["committed_allocations"][0]["request_id"] = "R99"
    with pytest.raises(ValidationError, match="unknown request"):
        PlanningSnapshot.model_validate(data)

    # Unknown sector in explicit power zone
    data = deepcopy(raw_fixture)
    data["power_zones"] = [{"id": "Z01", "sector_ids": ["UNKNOWN_SEC"]}]
    with pytest.raises(ValidationError, match="unknown sector"):
        PlanningSnapshot.model_validate(data)


# -----------------------------------------------------------------------------
# 11. Verify duplicate IDs, list members, self-dependencies, cycles rejected
# -----------------------------------------------------------------------------

def test_11_duplicates_self_dependencies_and_cycles_rejected(raw_fixture):
    # Duplicate station ID
    data = deepcopy(raw_fixture)
    data["stations"].append(deepcopy(data["stations"][0]))
    with pytest.raises(ValidationError, match="Duplicate station ID"):
        PlanningSnapshot.model_validate(data)

    # Duplicate sector ID
    data = deepcopy(raw_fixture)
    data["sectors"].append(deepcopy(data["sectors"][0]))
    with pytest.raises(ValidationError, match="Duplicate sector ID"):
        PlanningSnapshot.model_validate(data)

    # Duplicate request ID
    data = deepcopy(raw_fixture)
    data["requests"].append(deepcopy(data["requests"][0]))
    with pytest.raises(ValidationError, match="Duplicate request ID"):
        PlanningSnapshot.model_validate(data)

    # Duplicate protected sectors in request
    req = deepcopy(raw_fixture["requests"][0])
    req["protected_sectors"] = ["S02", "S02"]
    with pytest.raises(ValidationError, match="Duplicate sectors"):
        MaintenanceRequest.model_validate(req)

    # Duplicate equipment IDs in request
    req = deepcopy(raw_fixture["requests"][0])
    req["required_equipment_ids"] = ["Q01", "Q01"]
    with pytest.raises(ValidationError, match="Duplicate equipment IDs"):
        MaintenanceRequest.model_validate(req)

    # Self dependency
    req = deepcopy(raw_fixture["requests"][0])
    req["depends_on"] = [req["id"]]
    with pytest.raises(ValidationError, match="cannot depend on itself"):
        MaintenanceRequest.model_validate(req)

    # Dependency cycle (R01 depends on R03, while R03 depends on R01)
    data = deepcopy(raw_fixture)
    data["requests"][0]["depends_on"] = ["R03"]  # R01 -> R03, and R03 -> R01 already exists
    with pytest.raises(ValidationError, match="Dependency cycle detected"):
        PlanningSnapshot.model_validate(data)


# -----------------------------------------------------------------------------
# 12. Verify predecessor-specific handover-buffer overrides
# -----------------------------------------------------------------------------

def test_12_predecessor_specific_handover_buffer_overrides(raw_fixture):
    req_dict = deepcopy(raw_fixture["requests"][2])  # R03 depends on R01
    req_dict["depends_on"] = ["R01", "R04"]
    req_dict["handover_buffer_minutes"] = 15
    req_dict["handover_buffers"] = {"R01": 30}
    r = MaintenanceRequest.model_validate(req_dict)

    # Predecessor with override returns custom buffer
    assert r.get_handover_buffer("R01") == 30
    # Predecessor without override returns default buffer
    assert r.get_handover_buffer("R04") == 15
    # Non-predecessor fallback
    assert r.get_handover_buffer("R99") == 15

    # Handover buffer key not in depends_on rejected
    bad_buffers = deepcopy(req_dict)
    bad_buffers["handover_buffers"] = {"R02": 25}  # R02 not in depends_on
    with pytest.raises(ValidationError, match="subset of depends_on"):
        MaintenanceRequest.model_validate(bad_buffers)


# -----------------------------------------------------------------------------
# 13. Verify travel matrix directional lookup, duplicates, and serialization
# -----------------------------------------------------------------------------

def test_13_travel_time_matrix():
    entry1 = TravelTimeEntry(from_sector="S01", to_sector="S02", travel_minutes=15)
    entry2 = TravelTimeEntry(from_sector="S02", to_sector="S01", travel_minutes=20)
    matrix = TravelTimeMatrix(entries=[entry1, entry2])

    assert matrix.get("S01", "S02") == 15
    assert matrix.get("S02", "S01") == 20
    assert matrix.get("S01", "S03") is None

    # Duplicate directional entry rejected
    with pytest.raises(ValidationError, match="Duplicate travel time entry"):
        TravelTimeMatrix(entries=[entry1, entry1])

    # Negative travel minutes rejected
    with pytest.raises(ValidationError):
        TravelTimeEntry(from_sector="S01", to_sector="S02", travel_minutes=-5)

    # JSON serialization round trip
    dumped = matrix.model_dump(mode="json")
    matrix2 = TravelTimeMatrix.model_validate(dumped)
    assert matrix2.get("S01", "S02") == 15


# -----------------------------------------------------------------------------
# 14. Verify compatibility rules, vehicles, transit schedules, catalogue
# -----------------------------------------------------------------------------

def test_14_compatibility_vehicles_transit_and_catalogue():
    # Compatibility rule
    rule = CompatibilityRule(
        work_type_a="track",
        work_type_b="signalling",
        compatible=False,
        transition_minutes=15,
    )
    assert rule.compatible is False
    assert rule.transition_minutes == 15

    # Transit leg & route
    leg1 = TransitLeg(sector_id="S01", travel_minutes=10)
    leg2 = TransitLeg(sector_id="S02", travel_minutes=15)
    route = TransitRoute(origin_depot="DEPOT_A", destination_sector="S02", legs=[leg1, leg2])
    assert route.total_transit_minutes == 25

    # Transit leg must have positive travel minutes
    with pytest.raises(ValidationError):
        TransitLeg(sector_id="S01", travel_minutes=0)

    # Transit schedule
    sched = TransitSchedule(
        vehicle_id="V01",
        sector_id="S01",
        start=datetime(2026, 9, 14, 1, 0, tzinfo=SGT),
        end=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
    )
    assert sched.vehicle_id == "V01"

    # Vehicle
    v = Vehicle(
        id="V01",
        name="Loco 1",
        type=VehicleType.LOCOMOTIVE,
        home_depot="DEPOT_A",
        availability=[TimeWindow(start="2026-09-14T01:00:00+08:00", end="2026-09-14T04:30:00+08:00")],
        routes=[route],
    )
    assert v.type == VehicleType.LOCOMOTIVE

    # Job catalogue
    cat = JobTypeEntry(
        work_type="track_maintenance",
        default_duration_minutes=80,
        required_engineer_roles={"track": 1},
        pooled_resources={"TECH": 2},
        power_requirement=PowerRequirement.OFF,
        default_protection_rule="adjacent_buffer",
    )
    assert cat.work_type == "track_maintenance"

    # Job catalogue normalizes legacy ANY
    cat_any = JobTypeEntry(
        work_type="inspection",
        default_duration_minutes=30,
        power_requirement="ANY",
    )
    assert cat_any.power_requirement == PowerRequirement.NONE


# -----------------------------------------------------------------------------
# 15. Verify allocation duration and resource references against snapshot
# -----------------------------------------------------------------------------

def test_15_allocation_validation_against_snapshot(raw_fixture):
    # Allocation duration mismatch with request phases
    data = deepcopy(raw_fixture)
    data["committed_allocations"][0]["end"] = "2026-09-14T02:10:00+08:00"  # 70m instead of 80m
    with pytest.raises(ValidationError, match="does not match request phase duration"):
        PlanningSnapshot.model_validate(data)

    # Allocation unknown engineer
    data = deepcopy(raw_fixture)
    data["committed_allocations"][0]["engineer_id"] = "E99"
    with pytest.raises(ValidationError, match="Allocation engineer 'E99' does not exist"):
        PlanningSnapshot.model_validate(data)

    # Allocation unknown equipment
    data = deepcopy(raw_fixture)
    data["committed_allocations"][0]["equipment_ids"].append("Q99")
    with pytest.raises(ValidationError, match="Allocation equipment 'Q99' does not exist"):
        PlanningSnapshot.model_validate(data)

    # Scheduled request without committed allocation rejected
    data = deepcopy(raw_fixture)
    data["committed_allocations"] = []  # R01 and R02 are scheduled but have no allocations
    with pytest.raises(ValidationError, match="must have a matching committed allocation"):
        PlanningSnapshot.model_validate(data)

    # Cancelled request committed rejected
    data = deepcopy(raw_fixture)
    data["requests"][0]["status"] = "cancelled"
    with pytest.raises(ValidationError, match="Cancelled request 'R01' cannot have a committed allocation"):
        PlanningSnapshot.model_validate(data)


# -----------------------------------------------------------------------------
# 16. Validate representative current checker issue dictionaries through Conflict
# -----------------------------------------------------------------------------

def test_16_conflict_model_validates_checker_issues(raw_fixture):
    issues = check_plan(raw_fixture, preferred_plan(raw_fixture), require_all=True)
    assert len(issues) > 0
    for issue_dict in issues:
        conflict = Conflict.model_validate(issue_dict)
        assert isinstance(conflict.code, ConflictCode)
        assert conflict.severity in ("error", "warning")
        assert len(conflict.request_ids) > 0
        assert len(conflict.message) > 0

    # Explicit check of individual ConflictCodes
    sample_codes = [
        "DURATION", "START_GRID", "REQUEST_WINDOW", "ENGINEERING_WINDOW",
        "BLACKOUT", "SPACE", "POWER", "WORK_COMPATIBILITY", "ENGINEER",
        "QUALIFICATION", "EQUIPMENT", "EQUIPMENT_ASSIGNMENT", "EQUIPMENT_UNAVAILABLE",
        "RESOURCE_WINDOW", "RESOURCE_UNAVAILABLE", "TRANSFER_TIME", "DEPENDENCY",
        "LOCKED_BOOKING", "MANDATORY_DROPPED", "MANPOWER", "DUPLICATE",
        "UNKNOWN_REQUEST", "MISSING_WORK", "CANCELLED", "VEHICLE_TRANSIT",
        "REVIEW_REQUIRED",
    ]
    for code in sample_codes:
        c = Conflict(code=code, request_ids=["R01"], message=f"Test message for {code}")
        assert c.code.value == code

    # Reject empty request_ids
    with pytest.raises(ValidationError, match="at least one request ID"):
        Conflict(code=ConflictCode.POWER, request_ids=[], message="Bad conflict")

    # Reject blank message
    with pytest.raises(ValidationError, match="must not be blank"):
        Conflict(code=ConflictCode.POWER, request_ids=["R01"], message="   ")


# -----------------------------------------------------------------------------
# 17. Verify PlanningSnapshot to_dict followed by from_dict idempotence
# -----------------------------------------------------------------------------

def test_17_serialization_idempotence(raw_fixture):
    snap1 = PlanningSnapshot.from_dict(raw_fixture)
    d1 = snap1.to_dict()

    # JSON serializable
    json_str = json.dumps(d1)
    assert isinstance(json_str, str)

    # Re-import and re-dump
    snap2 = PlanningSnapshot.from_dict(d1)
    d2 = snap2.to_dict()

    assert d1 == d2

    # Computed properties are not serialized
    for r in d1["requests"]:
        assert "duration_minutes" not in r
    for w in d1["engineering_windows"]:
        assert "usable_end" not in w

    # Legacy ANY serialized as NONE
    r02 = next(r for r in d1["requests"] if r["id"] == "R02")
    assert r02["power_requirement"] == "NONE"


# -----------------------------------------------------------------------------
# 18. Verify model import remains independent of solver and database modules
# -----------------------------------------------------------------------------

def test_18_import_independence():
    source_path = Path(__file__).resolve().parents[1] / "app" / "models.py"
    with open(source_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="models.py")

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module)

    forbidden_prefixes = (
        "ortools",
        "backend.app.database",
        "backend.app.services",
        "fastapi",
        "sqlalchemy",
    )
    for imp in imported_names:
        for forbidden in forbidden_prefixes:
            assert not (imp == forbidden or imp.startswith(forbidden + ".")), (
                f"backend/app/models.py must not import {imp}"
            )
