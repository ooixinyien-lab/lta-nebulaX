"""Comprehensive test suite for PS1 Data Adaptation Layer.

Verifies:
1. Ingestion & Cardinalities
2. Topology & 2k+1 Structural Invariant
3. Protection Footprints (Buffer expansion, Live mirroring, Interchange cross-line effects, Clamping)
4. Negative Test Cases (DAG cycles, invalid FKs, mismatched types, bounds, dates)
5. CSV Export Roundtrip (Exact schema, formats, integer 0/1 ECLO)
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
import pytest

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    Activity,
    ActivityPriority,
    ActivityType,
    Bound,
    BufferRule,
    Contract,
    ContractPriority,
    Line,
    LocationKind,
    LocationSupply,
    NatureOfWorks,
    OccupancyScheduleRow,
    PlanningParameters,
    ProblemInstance,
    ScenarioResultRow,
    Sector,
    Station,
)
from backend.app.io import (
    DataLayerError,
    HorizonBoundError,
    PredecessorCycleError,
    RelationalIntegrityError,
    export_access_schedule,
    export_bundle,
    export_occupancy_schedule,
    export_results,
    load_problem_from_directory,
    load_problem_from_streams,
    validate_problem_instance,
)
from backend.app.topology import (
    ActivityFootprint,
    FootprintCache,
    NetworkTopology,
    ProtectionFootprint,
    compute_core_footprint,
    compute_protection_footprint,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def official_problem() -> ProblemInstance:
    """Fixture providing loaded official PS1 ProblemInstance from data/."""
    return load_problem_from_directory(DATA_DIR)


@pytest.fixture
def network_topology(official_problem: ProblemInstance) -> NetworkTopology:
    """Fixture providing NetworkTopology built from official problem."""
    return NetworkTopology.from_problem(official_problem)


# ============================================================================
# 1. Ingestion & Cardinalities
# ============================================================================


def test_ingestion_cardinalities(official_problem: ProblemInstance) -> None:
    """Load from data/ and verify exact cardinalities across all 8 tables."""
    assert len(official_problem.lines) == 2
    assert {l.line_code for l in official_problem.lines} == {"ALP", "BET"}

    assert len(official_problem.stations) == 20
    alp_stations = [s for s in official_problem.stations if s.line_code == "ALP"]
    bet_stations = [s for s in official_problem.stations if s.line_code == "BET"]
    assert len(alp_stations) == 10
    assert len(bet_stations) == 10

    # Verify interchange stations
    interchanges = [s for s in official_problem.stations if s.is_interchange]
    assert len(interchanges) == 4
    interchange_keys = {(s.line_code, s.station_id) for s in interchanges}
    assert interchange_keys == {("ALP", "H01"), ("ALP", "H02"), ("BET", "H01"), ("BET", "H02")}

    assert len(official_problem.sectors) == 18
    alp_sectors = [s for s in official_problem.sectors if s.line_code == "ALP"]
    bet_sectors = [s for s in official_problem.sectors if s.line_code == "BET"]
    assert len(alp_sectors) == 9
    assert len(bet_sectors) == 9

    assert len(official_problem.locations) == 76
    tunnels = [l for l in official_problem.locations if l.location_kind == LocationKind.TUNNEL_SECTOR]
    platforms = [l for l in official_problem.locations if l.location_kind == LocationKind.PLATFORM_SECTOR]
    assert len(tunnels) == 36  # 18 sectors * 2 bounds
    assert len(platforms) == 40  # 20 stations * 2 bounds

    assert len(official_problem.buffer_rules) == 3
    assert {b.nature_of_works for b in official_problem.buffer_rules} == {
        NatureOfWorks.LIVE,
        NatureOfWorks.NON_LIVE_CONSIST,
        NatureOfWorks.NON_LIVE_OTHERS,
    }

    assert len(official_problem.contracts) == 14
    assert len(official_problem.activities) == 54


def test_activity_ids_and_doubled_workload(official_problem: ProblemInstance) -> None:
    """Verify non-contiguous activity IDs and doubled workload values."""
    act_ids = [a.activity_id for a in official_problem.activities]
    assert "A001" in act_ids
    assert "A002" in act_ids
    assert "A003" in act_ids
    assert "A004" in act_ids
    # Non-contiguous gap: A005 is not in public data
    assert "A005" not in act_ids
    assert "A006" in act_ids
    assert "A075" in act_ids

    total_accesses = sum(a.total_accesses for a in official_problem.activities)
    assert total_accesses == 192

    total_doubled = sum(a.doubled_workload for a in official_problem.activities)
    assert total_doubled == 384

    # Verify score nudge and weight values
    for act in official_problem.activities:
        assert act.doubled_workload == act.total_accesses * 2
        if act.activity_priority == ActivityPriority.P1:
            assert act.score_nudge == 0.3
        elif act.activity_priority == ActivityPriority.P2:
            assert act.score_nudge == 0.2
        elif act.activity_priority == ActivityPriority.P3:
            assert act.score_nudge == 0.0

    for c in official_problem.contracts:
        if c.contract_priority == ContractPriority.P1:
            assert c.score_weight == 100
        elif c.contract_priority == ContractPriority.P2:
            assert c.score_weight == 10
        elif c.contract_priority == ContractPriority.P3:
            assert c.score_weight == 1


def test_planning_parameters_dates_and_weeks(official_problem: ProblemInstance) -> None:
    """Verify horizon bounds, Sunday completion semantics, and week calculations."""
    params = official_problem.parameters
    assert params.horizon_start == date(2027, 1, 4)
    assert params.horizon_start.isoweekday() == 1  # Monday
    assert params.horizon_weeks == 30
    assert params.horizon_end == date(2027, 8, 1)  # Sunday

    # Week 1 bounds
    assert params.week_start_date(1) == date(2027, 1, 4)
    assert params.week_end_date(1) == date(2027, 1, 10)

    # Week 30 bounds
    assert params.week_start_date(30) == date(2027, 7, 26)
    assert params.week_end_date(30) == date(2027, 8, 1)

    # Date to week mappings
    assert params.date_to_week(date(2027, 1, 4)) == 1
    assert params.date_to_week(date(2027, 1, 10)) == 1
    assert params.date_to_week(date(2027, 1, 11)) == 2
    assert params.date_to_week(date(2027, 8, 1)) == 30


def test_enums_normalization() -> None:
    """Verify enum case-insensitivity, short-forms, and alias normalizations."""
    # NatureOfWorks
    assert NatureOfWorks("Live") == NatureOfWorks.LIVE
    assert NatureOfWorks("live") == NatureOfWorks.LIVE
    assert NatureOfWorks("Consist") == NatureOfWorks.NON_LIVE_CONSIST
    assert NatureOfWorks("non-live (consist)") == NatureOfWorks.NON_LIVE_CONSIST
    assert NatureOfWorks("Others") == NatureOfWorks.NON_LIVE_OTHERS
    assert NatureOfWorks("non-live (others)") == NatureOfWorks.NON_LIVE_OTHERS

    # Bound aliases
    assert Bound("EB") == Bound.EB
    assert Bound("WB") == Bound.WB
    assert Bound("NB") == Bound.EB
    assert Bound("SB") == Bound.WB
    assert Bound("Northbound") == Bound.EB
    assert Bound("Southbound") == Bound.WB
    assert Bound.EB.opposite == Bound.WB
    assert Bound.WB.opposite == Bound.EB

    # Priorities
    assert ContractPriority(1) == ContractPriority.P1
    assert ContractPriority("2") == ContractPriority.P2
    assert ActivityPriority(3) == ActivityPriority.P3


# ============================================================================
# 2. Topology & 2k+1 Structural Invariant
# ============================================================================


def test_core_footprint_invariant_2k_plus_1(
    official_problem: ProblemInstance,
    network_topology: NetworkTopology,
) -> None:
    """Verify that all 54 public activities satisfy the 2k+1 core location invariant."""
    span_1_count = 0
    span_2_count = 0
    span_3_count = 0

    location_set = {loc.location_id for loc in official_problem.locations}

    for act in official_problem.activities:
        core = compute_core_footprint(act, network_topology, official_problem._locations_by_id)
        k = len(core.sectors)
        expected_len = 2 * k + 1

        assert len(core.tunnels) == k if hasattr(core, "tunnels") else len(core.tunnel_locations) == k
        assert len(core.platform_locations) == k + 1
        assert len(core.core_locations) == expected_len
        assert len(set(core.core_locations)) == expected_len

        # Verify all locations exist in official locations table
        for loc_id in core.core_locations:
            assert loc_id in location_set

        # Station connectivity continuity check
        for i in range(len(core.sectors) - 1):
            assert core.sectors[i].to_station_id == core.sectors[i + 1].from_station_id

        if k == 1:
            span_1_count += 1
            assert len(core.core_locations) == 3
        elif k == 2:
            span_2_count += 1
            assert len(core.core_locations) == 5
        elif k == 3:
            span_3_count += 1
            assert len(core.core_locations) == 7
        else:
            pytest.fail(f"Unexpected sector span count {k} for activity {act.activity_id}")

    # Verify public data distribution exactly matches specification
    assert span_1_count == 17
    assert span_2_count == 23
    assert span_3_count == 14
    assert span_1_count + span_2_count + span_3_count == 54


def test_line_topology_traversal(network_topology: NetworkTopology) -> None:
    """Verify LineTopology sector slicing and station extraction."""
    alp = network_topology.get_line("ALP")
    sectors = alp.get_sectors_between("SEC:ALP:S01_S02", "SEC:ALP:S03_S04")
    assert len(sectors) == 3
    assert [s.sector_id for s in sectors] == [
        "SEC:ALP:S01_S02",
        "SEC:ALP:S02_S03",
        "SEC:ALP:S03_S04",
    ]

    stations = alp.get_stations_for_sectors(sectors)
    assert len(stations) == 4
    assert [s.station_id for s in stations] == ["S01", "S02", "S03", "S04"]


# ============================================================================
# 3. Protection Footprints
# ============================================================================


def test_protection_footprints_buffer_expansion(
    official_problem: ProblemInstance,
    network_topology: NetworkTopology,
) -> None:
    """Verify buffer sector counts: 2 for Live, 1 for Consist, 0 for Others."""
    cache = FootprintCache(official_problem, network_topology)

    for act in official_problem.activities:
        contract = official_problem.contract(act.contract_number)
        prot = cache.get_protection_footprint(act.activity_id)

        if contract.nature_of_activity == NatureOfWorks.NON_LIVE_OTHERS:
            assert len(prot.buffer_sectors) == 0
            assert len(prot.buffer_locations) == 0
        elif contract.nature_of_activity == NatureOfWorks.NON_LIVE_CONSIST:
            # Consist expands up to 1 upstream and 1 downstream (at most 2 buffer sectors)
            assert 1 <= len(prot.buffer_sectors) <= 2
        elif contract.nature_of_activity == NatureOfWorks.LIVE:
            # Live expands up to 2 upstream and 2 downstream (at most 4 buffer sectors)
            assert 1 <= len(prot.buffer_sectors) <= 4


def test_protection_footprints_live_mirroring_and_interchange(
    official_problem: ProblemInstance,
    network_topology: NetworkTopology,
) -> None:
    """Verify opposite-bound mirroring and cross-line interchange effects for Live activities."""
    cache = FootprintCache(official_problem, network_topology)

    # Activity A074 (Contract C013, Live, ALP EB at H01_H02)
    prot_a074 = cache.get_protection_footprint("A074")
    assert prot_a074.core.bound == Bound.EB
    assert len(prot_a074.mirrored_locations) > 0
    assert "SEC:ALP:H01_H02:WB" in prot_a074.mirrored_tunnel_locations
    assert "PLAT:ALP:H01:WB" in prot_a074.mirrored_platform_locations
    assert "PLAT:ALP:H02:WB" in prot_a074.mirrored_platform_locations

    # Cross-line on BET
    assert "SEC:BET:H01_H02:EB" in prot_a074.cross_line_tunnel_locations
    assert "SEC:BET:H01_H02:WB" in prot_a074.cross_line_tunnel_locations
    assert "PLAT:BET:H01:EB" in prot_a074.cross_line_platform_locations
    assert "PLAT:BET:H01:WB" in prot_a074.cross_line_platform_locations

    # Activity A075 (Contract C014, Live, BET WB at H01_H02)
    prot_a075 = cache.get_protection_footprint("A075")
    assert prot_a075.core.bound == Bound.WB
    assert "SEC:BET:H01_H02:EB" in prot_a075.mirrored_tunnel_locations
    assert "SEC:ALP:H01_H02:EB" in prot_a075.cross_line_tunnel_locations


def test_protection_footprints_boundary_clamping(
    official_problem: ProblemInstance,
    network_topology: NetworkTopology,
) -> None:
    """Verify buffer expansion clamps properly at terminal stations (S01, S08, S11, S18)."""
    alp = network_topology.get_line("ALP")
    bet = network_topology.get_line("BET")

    # Clamping at ALP upstream start: S01_S02 has no upstream sectors
    upstream_s01 = alp.get_upstream_sectors("SEC:ALP:S01_S02", 2)
    assert len(upstream_s01) == 0

    # Clamping at ALP downstream end: S07_S08 has no downstream sectors
    downstream_s08 = alp.get_downstream_sectors("SEC:ALP:S07_S08", 2)
    assert len(downstream_s08) == 0

    # Clamping at BET upstream start: S11_S12 has no upstream sectors
    upstream_s11 = bet.get_upstream_sectors("SEC:BET:S11_S12", 2)
    assert len(upstream_s11) == 0

    # Clamping at BET downstream end: S17_S18 has no downstream sectors
    downstream_s18 = bet.get_downstream_sectors("SEC:BET:S17_S18", 2)
    assert len(downstream_s18) == 0


# ============================================================================
# 4. Negative Test Cases
# ============================================================================


def test_negative_cycle_detection(official_problem: ProblemInstance) -> None:
    """Predecessor circular dependency detection in activity DAG."""
    # Introduce circular dependency: A004 -> A003 -> A004
    acts = [a.model_copy() for a in official_problem.activities]
    a003 = next(a for a in acts if a.activity_id == "A003")
    a003.predecessor_activity_id = "A004"

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(PredecessorCycleError) as exc_info:
        validate_problem_instance(prob)
    assert "Circular dependency detected" in str(exc_info.value)
    assert "A003" in str(exc_info.value)
    assert "A004" in str(exc_info.value)


def test_negative_unknown_contract_fk(official_problem: ProblemInstance) -> None:
    """Activity referencing non-existent contract raises RelationalIntegrityError."""
    acts = [a.model_copy() for a in official_problem.activities]
    acts[0].contract_number = "C999"

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "references non-existent contract 'C999'" in str(exc_info.value)


def test_negative_unknown_location_fk(official_problem: ProblemInstance) -> None:
    """Activity referencing non-existent location raises RelationalIntegrityError."""
    acts = [a.model_copy() for a in official_problem.activities]
    acts[0].start_location_id = "SEC:BET:S99_S98:EB"

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "references non-existent start_location_id" in str(exc_info.value)


def test_negative_cross_contract_predecessor(official_problem: ProblemInstance) -> None:
    """Activity with predecessor from a different contract violates intra-contract rule."""
    acts = [a.model_copy() for a in official_problem.activities]
    a001 = next(a for a in acts if a.activity_id == "A001")  # Contract C001
    a008 = next(a for a in acts if a.activity_id == "A008")  # Contract C002
    a008.predecessor_activity_id = a001.activity_id

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "violating intra-contract dependency" in str(exc_info.value)


def test_negative_mismatched_activity_type(official_problem: ProblemInstance) -> None:
    """Activity type not matching contract activity type raises RelationalIntegrityError."""
    acts = [a.model_copy() for a in official_problem.activities]
    # A001 is Renewal, C001 is Renewal; flip A001 to Construction
    acts[0].activity_type = ActivityType.CONSTRUCTION

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "does not match contract" in str(exc_info.value)


def test_negative_incompatible_bounds(official_problem: ProblemInstance) -> None:
    """Activity spanning EB and WB raises RelationalIntegrityError."""
    acts = [a.model_copy() for a in official_problem.activities]
    # A001 end location switched to WB
    acts[0].end_location_id = acts[0].end_location_id.replace(":EB", ":WB")

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "bound" in str(exc_info.value).lower()


def test_negative_incompatible_lines(official_problem: ProblemInstance) -> None:
    """Activity spanning different lines raises RelationalIntegrityError."""
    acts = [a.model_copy() for a in official_problem.activities]
    # A001 is on BET; replace end location with ALP location
    acts[0].end_location_id = "SEC:ALP:S01_S02:EB"

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "line" in str(exc_info.value).lower()


def test_negative_reverse_spatial_direction(official_problem: ProblemInstance) -> None:
    """Activity with start sector seq > end sector seq raises RelationalIntegrityError."""
    acts = [a.model_copy() for a in official_problem.activities]
    # Swap start and end locations of A001
    start = acts[0].start_location_id
    end = acts[0].end_location_id
    acts[0].start_location_id = end
    acts[0].end_location_id = start

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "reversed spatial direction" in str(exc_info.value).lower()


def test_negative_date_outside_horizon(official_problem: ProblemInstance) -> None:
    """Activity planned start date outside horizon raises HorizonBoundError."""
    acts = [a.model_copy() for a in official_problem.activities]
    acts[0].planned_start_date = date(2026, 12, 28)  # Before 2027-01-04

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=acts,
    )

    with pytest.raises(HorizonBoundError) as exc_info:
        validate_problem_instance(prob)
    assert "outside planning horizon" in str(exc_info.value)


def test_negative_horizon_not_monday(official_problem: ProblemInstance) -> None:
    """Horizon start not a Monday raises HorizonBoundError."""
    params = PlanningParameters(
        horizon_start=date(2027, 1, 5),  # Tuesday
        horizon_weeks=30,
    )

    prob = ProblemInstance(
        lines=official_problem.lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=params,
        contracts=official_problem.contracts,
        activities=official_problem.activities,
    )

    with pytest.raises(HorizonBoundError) as exc_info:
        validate_problem_instance(prob)
    assert "horizon_start must be a Monday" in str(exc_info.value)


def test_negative_duplicate_pk(official_problem: ProblemInstance) -> None:
    """Duplicate Line primary key raises RelationalIntegrityError."""
    lines = list(official_problem.lines) + [Line(line_code="ALP", line_name="Duplicate Line")]

    with pytest.raises(RelationalIntegrityError) as exc_info:
        ProblemInstance(
            lines=lines,
            stations=official_problem.stations,
            sectors=official_problem.sectors,
            locations=official_problem.locations,
            buffer_rules=official_problem.buffer_rules,
            parameters=official_problem.parameters,
            contracts=official_problem.contracts,
            activities=official_problem.activities,
        )
        validate_problem_instance(
            ProblemInstance(
                lines=lines,
                stations=official_problem.stations,
                sectors=official_problem.sectors,
                locations=official_problem.locations,
                buffer_rules=official_problem.buffer_rules,
                parameters=official_problem.parameters,
                contracts=official_problem.contracts,
                activities=official_problem.activities,
            )
        )
    # The duplicate is caught during validation
    prob = ProblemInstance.model_construct(
        lines=lines,
        stations=official_problem.stations,
        sectors=official_problem.sectors,
        locations=official_problem.locations,
        buffer_rules=official_problem.buffer_rules,
        parameters=official_problem.parameters,
        contracts=official_problem.contracts,
        activities=official_problem.activities,
    )
    with pytest.raises(RelationalIntegrityError) as exc_info:
        validate_problem_instance(prob)
    assert "Duplicate Line primary key" in str(exc_info.value)


# ============================================================================
# 5. CSV Export Roundtrip
# ============================================================================


def test_export_roundtrip(tmp_path: Path) -> None:
    """Verify exact output schema formatting, integer 0/1 ECLO, and roundtrip re-parsing."""
    access_rows = [
        AccessScheduleRow(activity_id="A001", access_seq=1, week=1, eclo=False, access_night=1),
        AccessScheduleRow(activity_id="A001", access_seq=2, week=2, eclo=True, access_night=2),
    ]
    occupancy_rows = [
        OccupancyScheduleRow(activity_id="A001", week=1, location_id="SEC:BET:S15_S16:EB", co_share_group="G1"),
        OccupancyScheduleRow(activity_id="A001", week=1, location_id="PLAT:BET:S15:EB", co_share_group="G1"),
    ]
    results_rows = [
        ScenarioResultRow(
            scenario="A",
            contract_number="C001",
            simulated_completion_date=date(2027, 6, 13),
            overrun_days=0,
        ),
        ScenarioResultRow(
            scenario="A",
            contract_number="C006",
            simulated_completion_date=date(2027, 7, 18),
            overrun_days=14,
        ),
    ]

    bundle_paths = export_bundle(access_rows, occupancy_rows, results_rows, tmp_path)

    # 1. Check Access CSV
    access_csv = bundle_paths["access"].read_text(encoding="utf-8")
    assert access_csv.startswith("activity_id,access_seq,week,eclo,access_night\n")
    access_lines = access_csv.strip().split("\n")
    assert len(access_lines) == 3  # header + 2 rows
    assert access_lines[1] == "A001,1,1,0,1"
    assert access_lines[2] == "A001,2,2,1,2"

    # Re-parse Access CSV
    reader = csv.DictReader(access_csv.splitlines())
    parsed_access = [AccessScheduleRow.model_validate(r) for r in reader]
    assert len(parsed_access) == 2
    assert parsed_access[0].eclo is False
    assert parsed_access[1].eclo is True

    # 2. Check Occupancy CSV
    occ_csv = bundle_paths["occupancy"].read_text(encoding="utf-8")
    assert occ_csv.startswith("activity_id,week,location_id,co_share_group\n")
    occ_lines = occ_csv.strip().split("\n")
    assert len(occ_lines) == 3
    assert occ_lines[1] == "A001,1,SEC:BET:S15_S16:EB,G1"

    # Re-parse Occupancy CSV
    reader = csv.DictReader(occ_csv.splitlines())
    parsed_occ = [OccupancyScheduleRow.model_validate(r) for r in reader]
    assert len(parsed_occ) == 2
    assert parsed_occ[0].location_id == "SEC:BET:S15_S16:EB"

    # 3. Check Results CSV
    res_csv = bundle_paths["results"].read_text(encoding="utf-8")
    assert res_csv.startswith("scenario,contract_number,simulated_completion_date,overrun_days\n")
    res_lines = res_csv.strip().split("\n")
    assert len(res_lines) == 3
    assert res_lines[1] == "A,C001,2027-06-13,0"
    assert res_lines[2] == "A,C006,2027-07-18,14"

    # Re-parse Results CSV
    reader = csv.DictReader(res_csv.splitlines())
    parsed_res = [ScenarioResultRow.model_validate(r) for r in reader]
    assert len(parsed_res) == 2
    assert parsed_res[1].overrun_days == 14
    assert parsed_res[1].simulated_completion_date == date(2027, 7, 18)
