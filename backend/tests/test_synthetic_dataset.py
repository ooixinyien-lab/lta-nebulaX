"""Validation test suite for standalone synthetic dataset generator.

Validates domain model compliance, entity counts, schema round-trip serialization,
scenario expectations, and constraint geometry without invoking runtime services.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.app.models import (
    EngineeringWindow,
    PhaseType,
    PlanningSnapshot,
    PowerRequirement,
    RequestStatus,
    TimingMode,
)
from scripts.generate_synthetic_dataset import (
    SCENARIO_EXPECTATIONS,
    build_comprehensive_snapshot,
    build_compound_conflict_scenario,
    build_feasible_snapshot,
    build_infeasible_deadlock_scenario,
    build_lexicographic_tradeoff_scenario,
    build_trivial_fastpath_scenario,
    export_comprehensive_dataset,
    resolve_factory,
    validate_all_scenarios,
)


def test_comprehensive_snapshot_counts_and_integrity() -> None:
    """Validate all entity counts, unique keys, references, and integrity rules."""
    snapshot = build_comprehensive_snapshot()
    assert isinstance(snapshot, PlanningSnapshot)

    # 1. Primary entity counts
    assert len(snapshot.stations) == 7
    assert len(snapshot.power_zones) == 3
    assert len(snapshot.sectors) == 6
    assert len(snapshot.engineering_windows) == 2
    assert len(snapshot.blackouts) == 1
    assert len(snapshot.engineers) == 7
    assert len(snapshot.equipment) == 5
    assert len(snapshot.resource_pools) == 2
    assert len(snapshot.vehicles) == 2
    assert len(snapshot.transit_schedules) == 1
    assert len(snapshot.travel_time_matrix.entries) >= 14
    assert len(snapshot.job_catalogue) == 7
    assert len(snapshot.requests) == 12
    assert len(snapshot.committed_allocations) == 2

    # 2. Metadata validation
    meta = snapshot.metadata
    assert meta.schema_version == "1.0"
    assert meta.planning_version == 1
    assert meta.timezone == "Asia/Singapore"
    assert meta.planning_date == "2026-09-14"
    assert meta.synthetic is True
    assert "fictional" in meta.description.lower() or "synthetic" in meta.description.lower()
    assert "not operational" in meta.disclaimer.lower() or "not" in meta.disclaimer.lower()
    assert len(meta.simplifications) >= 1

    # 3. Unique IDs across all entity collections
    assert {s.id for s in snapshot.stations} == {"EW1", "EW2", "EW3", "EW4", "EW5", "EW6", "EW7"}
    assert {s.name for s in snapshot.stations} == {
        "Pasir Ris", "Tampines", "Simei", "Tanah Merah", "Bedok", "Kembangan", "Eunos"
    }
    assert len({pz.id for pz in snapshot.power_zones}) == 3
    assert len({sec.id for sec in snapshot.sectors}) == 6
    assert len({b.id for b in snapshot.blackouts}) == 1
    assert len({e.id for e in snapshot.engineers}) == 7
    assert len({eq.id for eq in snapshot.equipment}) == 5
    assert len({p.id for p in snapshot.resource_pools}) == 2
    assert len({v.id for v in snapshot.vehicles}) == 2
    assert {v.home_depot for v in snapshot.vehicles} == {"CHANGI_DEPOT", "TUAS_DEPOT"}
    assert len({r.id for r in snapshot.requests}) == 12

    # 4. Station, sector, and power-zone cross references
    station_ids = {s.id for s in snapshot.stations}
    for sec in snapshot.sectors:
        assert sec.from_station in station_ids
        assert sec.to_station in station_ids
        assert sec.exclusive_protection is True
        assert sec.direction == "Westbound"

    pz_map = {pz.id: pz for pz in snapshot.power_zones}
    for sec in snapshot.sectors:
        assert sec.power_zone in pz_map
        assert sec.id in pz_map[sec.power_zone].sector_ids

    # 5. Resource references
    sector_ids = {sec.id for sec in snapshot.sectors}
    for e in snapshot.engineers:
        assert e.initial_sector in sector_ids
        assert len(e.availability) >= 1
    for eq in snapshot.equipment:
        assert eq.initial_sector in sector_ids
        assert len(eq.availability) >= 1

    # 6. Request cross references and dependency integrity
    req_ids = {r.id for r in snapshot.requests}
    for r in snapshot.requests:
        assert r.work_sector in sector_ids
        assert all(ps in sector_ids for ps in r.protected_sectors)
        assert r.work_sector in r.protected_sectors
        assert all(dep in req_ids for dep in r.depends_on)
        assert r.id not in r.depends_on

    # 7. Engineering window coverage
    for w in snapshot.engineering_windows:
        assert set(w.sector_ids) == sector_ids
        assert w.handback_buffer_minutes == snapshot.planning_rules.morning_buffer_minutes

    # 8. Allocation / request relationships
    alloc_map = {a.request_id: a for a in snapshot.committed_allocations}
    assert set(alloc_map.keys()) == {"R01", "R02"}
    for req in snapshot.requests:
        if req.status == RequestStatus.scheduled:
            assert req.id in alloc_map
            alloc = alloc_map[req.id]
            dur_mins = int((alloc.end - alloc.start).total_seconds() // 60)
            assert dur_mins == req.duration_minutes
            assert req.existing_start == alloc.start
            assert req.approved is True


def test_primary_request_matrix() -> None:
    """Validate request-specific parameters for all 12 requests in comprehensive snapshot."""
    snapshot = build_comprehensive_snapshot()
    req_map = {r.id: r for r in snapshot.requests}

    # Verify all requests contain exactly four phases: setup, work, test, handback
    for r in snapshot.requests:
        phase_names = [p.name for p in r.phases]
        assert phase_names == [PhaseType.setup, PhaseType.work, PhaseType.test, PhaseType.handback]
        assert len(r.phases) == 4

    # R01: Frozen approved baseline
    r01 = req_map["R01"]
    assert r01.work_type == "rail_replacement"
    assert r01.work_sector == "S02"
    assert r01.protected_sectors == ["S01", "S02"]
    assert r01.power_requirement == PowerRequirement.OFF
    assert r01.duration_minutes == 70
    assert r01.timing_mode == TimingMode.RANGE
    assert r01.preferred_start is not None
    assert r01.preferred_start.strftime("%H:%M") == "01:30"
    assert r01.preferred_engineer == "E01"
    assert r01.required_equipment_ids == ["Q01"]
    assert r01.pooled_resources == {"TECH": 2}
    assert r01.status == RequestStatus.scheduled
    assert r01.approved is True
    assert r01.frozen is True

    # R02: Approved non-frozen baseline
    r02 = req_map["R02"]
    assert r02.work_type == "sensor_inspection"
    assert r02.work_sector == "S05"
    assert r02.protected_sectors == ["S05"]
    assert r02.power_requirement == PowerRequirement.NONE
    assert r02.duration_minutes == 50
    assert r02.timing_mode == TimingMode.RANGE
    assert r02.preferred_start is not None
    assert r02.preferred_start.strftime("%H:%M") == "02:00"
    assert r02.preferred_engineer == "E06"
    assert r02.required_equipment_ids == ["Q02"]
    assert r02.pooled_resources == {"TECH": 1}
    assert r02.status == RequestStatus.scheduled
    assert r02.approved is True
    assert r02.frozen is False

    # R03: Dependency and power transition
    r03 = req_map["R03"]
    assert r03.work_type == "dynamic_signalling_test"
    assert r03.work_sector == "S02"
    assert r03.protected_sectors == ["S02"]
    assert r03.power_requirement == PowerRequirement.ON
    assert r03.duration_minutes == 50
    assert r03.depends_on == ["R01"]
    assert r03.handover_buffer_minutes == 15
    assert r03.deferrable is True
    assert r03.status == RequestStatus.submitted

    # R04: Exact-time footprint conflict
    r04 = req_map["R04"]
    assert r04.work_type == "rail_replacement"
    assert r04.work_sector == "S01"
    assert r04.protected_sectors == ["S01", "S02"]
    assert r04.power_requirement == PowerRequirement.OFF
    assert r04.duration_minutes == 70
    assert r04.timing_mode == TimingMode.EXACT
    assert r04.preferred_start == r04.earliest_start
    assert r04.deadline.strftime("%H:%M") == "03:10"
    assert r04.preferred_start.strftime("%H:%M") == "02:00"
    assert int((r04.deadline - r04.preferred_start).total_seconds() // 60) == 70
    assert r04.status == RequestStatus.submitted

    # R05: Qualification, travel, and unserviceable equipment
    r05 = req_map["R05"]
    assert r05.work_type == "catenary_service"
    assert r05.work_sector == "S06"
    assert r05.protected_sectors == ["S06"]
    assert r05.power_requirement == PowerRequirement.OFF
    assert r05.duration_minutes == 60
    assert r05.required_skill == "power"
    assert set(r05.eligible_engineers) == {"E05", "E06"}
    assert r05.required_equipment_ids == ["Q04"]
    assert r05.pooled_resources == {"TECH": 2, "TPO": 1}

    # R06: Cumulative manpower surge
    r06 = req_map["R06"]
    assert r06.work_type == "track_tamping"
    assert r06.work_sector == "S04"
    assert r06.duration_minutes == 60
    assert r06.pooled_resources == {"TECH": 4, "TPO": 1}
    assert r06.required_equipment_ids == []

    # R07: Blackout and specialist contention
    r07 = req_map["R07"]
    assert r07.work_type == "point_machine_service"
    assert r07.work_sector == "S01"
    assert r07.duration_minutes == 60
    assert r07.preferred_start is not None
    assert r07.preferred_start.strftime("%H:%M") == "03:15"
    assert r07.required_skill == "signalling"
    assert r07.preferred_engineer == "E03"

    # R08: Handback overflow
    r08 = req_map["R08"]
    assert r08.work_type == "rail_replacement"
    assert r08.work_sector == "S03"
    assert r08.duration_minutes == 70
    assert r08.preferred_start is not None
    assert r08.preferred_start.strftime("%H:%M") == "03:30"
    pref_end = r08.preferred_start.strftime("%H:%M")
    assert pref_end == "03:30"
    # End of preferred job is 03:30 + 70m = 04:40 > usable window end 04:25
    assert r08.deadline.strftime("%H:%M") == "04:45"

    # R09: Mandatory service-critical request
    r09 = req_map["R09"]
    assert r09.work_type == "rail_replacement"
    assert r09.work_sector == "S03"
    assert r09.duration_minutes == 60
    assert r09.mandatory is True
    assert r09.deferrable is False
    assert r09.urgency_score == 5
    assert r09.status == RequestStatus.submitted

    # R10: Optional any-time request
    r10 = req_map["R10"]
    assert r10.work_type == "sensor_inspection"
    assert r10.timing_mode == TimingMode.ANY_TIME
    assert r10.preferred_start is None
    assert r10.duration_minutes == 40
    assert r10.mandatory is False
    assert r10.deferrable is True
    assert r10.urgency_score == 2

    # R11: Vehicle transit interaction
    r11 = req_map["R11"]
    assert r11.work_type == "track_inspection"
    assert r11.work_sector == "S01"
    assert r11.duration_minutes == 30
    assert r11.status == RequestStatus.submitted

    # R12: Multi-date request
    r12 = req_map["R12"]
    assert r12.work_type == "catenary_service"
    assert r12.allowed_dates == ["2026-09-14", "2026-09-15"]
    assert r12.timing_mode == TimingMode.RANGE
    assert r12.preferred_start is None
    assert r12.duration_minutes == 60


def test_primary_resource_and_rule_catalogue() -> None:
    """Validate resource pool capacities, unserviceability, and compatibility matrices."""
    snapshot = build_comprehensive_snapshot()

    # Resource pools
    tech_pool = next(p for p in snapshot.resource_pools if p.id == "TECH")
    assert tech_pool.capacity == 5
    tpo_pool = next(p for p in snapshot.resource_pools if p.id == "TPO")
    assert tpo_pool.capacity == 2

    # Equipment serviceability
    q04 = next(eq for eq in snapshot.equipment if eq.id == "Q04")
    assert q04.serviceable is False
    for eq in snapshot.equipment:
        if eq.id != "Q04":
            assert eq.serviceable is True

    # Engineer E07 unavailability
    e07 = next(e for e in snapshot.engineers if e.id == "E07")
    assert len(e07.unavailable) == 1
    unavail = e07.unavailable[0]
    assert unavail.start.strftime("%Y-%m-%dT%H:%M") == "2026-09-14T01:15"
    assert unavail.end.strftime("%Y-%m-%dT%H:%M") == "2026-09-14T02:30"

    # Job catalogue: all seven work types
    expected_work_types = {
        "rail_replacement",
        "dynamic_signalling_test",
        "sensor_inspection",
        "catenary_service",
        "track_tamping",
        "point_machine_service",
        "track_inspection",
    }
    catalogue_types = {j.work_type for j in snapshot.job_catalogue}
    assert catalogue_types == expected_work_types

    # Power zones
    assert {pz.id for pz in snapshot.power_zones} == {"Z01", "Z02", "Z03"}

    # Canonical power compatibility matrix (9 pairs)
    compat = snapshot.planning_rules.power_compatibility
    expected_matrix = {
        (PowerRequirement.ON, PowerRequirement.ON): True,
        (PowerRequirement.ON, PowerRequirement.OFF): False,
        (PowerRequirement.ON, PowerRequirement.NONE): True,
        (PowerRequirement.OFF, PowerRequirement.ON): False,
        (PowerRequirement.OFF, PowerRequirement.OFF): True,
        (PowerRequirement.OFF, PowerRequirement.NONE): True,
        (PowerRequirement.NONE, PowerRequirement.ON): True,
        (PowerRequirement.NONE, PowerRequirement.OFF): True,
        (PowerRequirement.NONE, PowerRequirement.NONE): True,
    }
    for (p1, p2), expected_bool in expected_matrix.items():
        assert compat[p1][p2] == expected_bool

    # Work compatibility rules
    rules = snapshot.planning_rules.work_compatibility_rules
    assert len(rules) == 3
    rule_lookup = {(r.work_type_a, r.work_type_b): (r.compatible, r.transition_minutes) for r in rules}
    assert rule_lookup[("rail_replacement", "dynamic_signalling_test")] == (False, 15)
    assert rule_lookup[("track_tamping", "sensor_inspection")] == (False, 10)
    assert rule_lookup[("point_machine_service", "track_inspection")] == (False, 10)

    # Directional travel time matrix entries
    matrix = snapshot.travel_time_matrix
    assert matrix.get("S01", "S02") == 10
    assert matrix.get("S02", "S01") == 10
    assert matrix.get("S02", "S03") == 10
    assert matrix.get("S03", "S02") == 10
    assert matrix.get("S02", "S04") == 15
    assert matrix.get("S04", "S02") == 15
    assert matrix.get("S02", "S06") == 25
    assert matrix.get("S06", "S02") == 25
    assert matrix.get("S03", "S05") == 15
    assert matrix.get("S05", "S03") == 15
    assert matrix.get("S01", "S05") == 25
    assert matrix.get("S05", "S01") == 25
    assert matrix.get("S01", "S06") == 30
    assert matrix.get("S06", "S01") == 30
    assert matrix.get("S05", "S02") == 25


def test_json_artifact_matches_factory() -> None:
    """Verify data/comprehensive_synthetic_data.json matches build_comprehensive_snapshot."""
    artifact_path = Path("data/comprehensive_synthetic_data.json")
    assert artifact_path.exists(), "Artifact data/comprehensive_synthetic_data.json must exist"

    raw_json = artifact_path.read_text(encoding="utf-8")
    loaded_snapshot = PlanningSnapshot.from_json(raw_json)
    fresh_snapshot = build_comprehensive_snapshot()

    assert loaded_snapshot.to_dict() == fresh_snapshot.to_dict()


def test_snapshot_serialization_round_trip() -> None:
    """Verify round-trip serialization and absence of legacy or computed fields."""
    snapshot = build_comprehensive_snapshot()
    serialized = snapshot.to_dict()

    # Round trip dict comparison
    reimported = PlanningSnapshot.from_dict(serialized)
    assert reimported.to_dict() == serialized

    # Check that computed duration_minutes is not serialized at request root
    for r in serialized["requests"]:
        assert "duration_minutes" not in r

    # Check that computed usable_end is not serialized at window root
    for w in serialized["engineering_windows"]:
        assert "usable_end" not in w

    # Power requirements contain NONE, and serialized JSON contains no legacy 'ANY'
    assert "NONE" in serialized["planning_rules"]["power_values"]
    json_dump = json.dumps(serialized)
    assert '"ANY"' not in json_dump


def test_generation_is_deterministic(tmp_path: Path) -> None:
    """Verify that snapshot generation is strictly deterministic and export writes correctly."""
    s1 = build_comprehensive_snapshot().to_dict()
    s2 = build_comprehensive_snapshot().to_dict()
    assert s1 == s2

    # Export to a temporary path and assert no differences
    temp_target = tmp_path / "deterministic_test.json"
    exported_path = export_comprehensive_dataset(temp_target)
    assert exported_path == temp_target
    assert temp_target.exists()

    loaded = PlanningSnapshot.from_json(temp_target.read_text(encoding="utf-8"))
    assert loaded.to_dict() == s1


def test_feasible_snapshot_is_valid() -> None:
    """Verify the feasible snapshot contains a complete, valid non-conflicting schedule."""
    snapshot = build_feasible_snapshot()
    assert isinstance(snapshot, PlanningSnapshot)

    scheduled_req_ids = {r.id for r in snapshot.requests if r.status == RequestStatus.scheduled}
    alloc_req_ids = {a.request_id for a in snapshot.committed_allocations}
    assert scheduled_req_ids == alloc_req_ids

    # Allocations match phase durations and fall within usable engineering windows
    usable_end = snapshot.engineering_windows[0].usable_end
    for alloc in snapshot.committed_allocations:
        req = next(r for r in snapshot.requests if r.id == alloc.request_id)
        assert int((alloc.end - alloc.start).total_seconds() // 60) == req.duration_minutes
        assert alloc.start >= snapshot.engineering_windows[0].start
        assert alloc.end <= usable_end

    # Serializability
    assert PlanningSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()


@pytest.mark.parametrize("deadlock_type", ["frozen", "manpower", "blackout"])
def test_deadlock_scenarios_are_valid_and_annotated(deadlock_type: str) -> None:
    """Verify deadlock scenarios are valid PlanningSnapshots and registered with INFEASIBLE expectation."""
    snapshot = build_infeasible_deadlock_scenario(deadlock_type)
    assert isinstance(snapshot, PlanningSnapshot)
    assert PlanningSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()

    exp = next((e for e in SCENARIO_EXPECTATIONS if e.name == f"deadlock_{deadlock_type}"), None)
    assert exp is not None
    assert exp.expected_status == "INFEASIBLE"

    if deadlock_type == "frozen":
        assert any(r.frozen and r.approved for r in snapshot.requests)
        assert any(r.mandatory for r in snapshot.requests)
        frozen_alloc = snapshot.committed_allocations[0]
        assert frozen_alloc.end.strftime("%H:%M") == "03:50"
    elif deadlock_type == "manpower":
        assert len(snapshot.requests) == 2
        assert all(r.timing_mode == TimingMode.EXACT and r.mandatory for r in snapshot.requests)
        total_demand = sum(r.pooled_resources.get("TECH", 0) for r in snapshot.requests)
        tech_pool = next(p for p in snapshot.resource_pools if p.id == "TECH")
        assert total_demand > tech_pool.capacity
    elif deadlock_type == "blackout":
        assert len(snapshot.blackouts) == 1
        bo = snapshot.blackouts[0]
        mand_req = next(r for r in snapshot.requests if r.mandatory)
        assert bo.start.strftime("%H:%M") == "02:00"
        assert bo.end.strftime("%H:%M") == "04:30"
        assert mand_req.duration_minutes == 70


@pytest.mark.parametrize("case_type", ["nexus", "vehicle_corridor"])
def test_compound_scenarios_are_valid_and_annotated(case_type: str) -> None:
    """Verify compound constraint scenarios are valid and correctly annotated."""
    snapshot = build_compound_conflict_scenario(case_type)
    assert isinstance(snapshot, PlanningSnapshot)
    assert PlanningSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()

    exp = next((e for e in SCENARIO_EXPECTATIONS if e.name == f"compound_{case_type}"), None)
    assert exp is not None

    if case_type == "nexus":
        assert exp.expected_codes == ("DEPENDENCY", "POWER", "TRANSFER_TIME")
        assert "max(02:55, 02:50, 02:55) = 02:55" in exp.description
        r03 = next(r for r in snapshot.requests if r.id == "R03")
        assert "R01" in r03.depends_on
        assert r03.handover_buffer_minutes == 15
        assert snapshot.travel_time_matrix.get("S05", "S02") == 25
    elif case_type == "vehicle_corridor":
        assert "VEHICLE_TRANSIT" in exp.expected_codes
        assert any(v.id == "V01" for v in snapshot.vehicles)
        assert any(ts.vehicle_id == "V01" for ts in snapshot.transit_schedules)
        assert any("V01" in a.vehicle_ids for a in snapshot.committed_allocations)


@pytest.mark.parametrize("case_type", ["empty", "orthogonal", "domain_impossible", "missing_skill"])
def test_fastpath_scenarios_are_valid_and_annotated(case_type: str) -> None:
    """Verify fast-path scenarios are valid PlanningSnapshots and exhibit target boundary conditions."""
    snapshot = build_trivial_fastpath_scenario(case_type)
    assert isinstance(snapshot, PlanningSnapshot)
    assert PlanningSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()

    exp = next((e for e in SCENARIO_EXPECTATIONS if e.name == f"fastpath_{case_type}"), None)
    assert exp is not None

    if case_type == "empty":
        assert len([r for r in snapshot.requests if r.status == RequestStatus.submitted]) == 0
    elif case_type == "orthogonal":
        assert len(snapshot.requests) == 3
        assert len({r.work_sector for r in snapshot.requests}) == 3
        assert len({r.power_zone for r in snapshot.requests}) == 3
        assert len({r.eligible_engineers[0] for r in snapshot.requests}) == 3
    elif case_type == "domain_impossible":
        r = snapshot.requests[0]
        win = snapshot.engineering_windows[0]
        usable_duration = int((win.usable_end - win.start).total_seconds() // 60)
        assert usable_duration == 190
        assert r.duration_minutes == 240
        assert r.duration_minutes > usable_duration
    elif case_type == "missing_skill":
        r = snapshot.requests[0]
        assert r.mandatory is True
        all_skills = {s for e in snapshot.engineers for s in e.skills}
        assert r.required_skill not in all_skills
        assert len(r.eligible_engineers) == 0


@pytest.mark.parametrize("case_type", ["stability", "load", "handback"])
def test_lexicographic_scenarios_are_valid_and_annotated(case_type: str) -> None:
    """Verify lexicographic trade-off snapshots are valid and encode priority orders."""
    snapshot = build_lexicographic_tradeoff_scenario(case_type)
    assert isinstance(snapshot, PlanningSnapshot)
    assert PlanningSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()

    exp = next((e for e in SCENARIO_EXPECTATIONS if e.name == f"lexicographic_{case_type}"), None)
    assert exp is not None

    if case_type == "stability":
        assert any(r.approved and not r.frozen and r.status == RequestStatus.scheduled for r in snapshot.requests)
        assert any(r.urgency_score == 5 and not r.mandatory for r in snapshot.requests)
    elif case_type == "load":
        assert len(snapshot.requests) == 8
        assert any(r.mandatory for r in snapshot.requests)
        assert any(r.urgency_score in (4, 5) and not r.mandatory for r in snapshot.requests)
        assert any(r.urgency_score in (1, 2) and r.deferrable for r in snapshot.requests)
    elif case_type == "handback":
        assert len(snapshot.requests) >= 2
        assert all(r.timing_mode == TimingMode.ANY_TIME for r in snapshot.requests)
        assert all(r.preferred_start is None for r in snapshot.requests)


def test_all_registered_scenarios_build_successfully() -> None:
    """Resolve every factory named by SCENARIO_EXPECTATIONS and verify serialization round-trip."""
    assert len(SCENARIO_EXPECTATIONS) >= 16, "Must represent at least 16 base scenario expectations"
    for exp in SCENARIO_EXPECTATIONS:
        snapshot = resolve_factory(exp.factory)
        assert isinstance(snapshot, PlanningSnapshot)
        serialized = snapshot.to_dict()
        assert PlanningSnapshot.from_dict(serialized).to_dict() == serialized


def test_validate_all_scenarios() -> None:
    """Verify the generator's reusable validation entry point runs without error."""
    validate_all_scenarios()
