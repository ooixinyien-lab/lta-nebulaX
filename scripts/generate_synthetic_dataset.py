"""Standalone Deterministic Synthetic Dataset Generator for RailPlan.

Builds typed PlanningSnapshot datasets for testing and solver validation using
only domain models from backend.app.models.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Callable, Literal
from zoneinfo import ZoneInfo

# Ensure repository root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models import (
    Allocation,
    Blackout,
    CompatibilityRule,
    Engineer,
    EngineeringWindow,
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
    SnapshotMetadata,
    Station,
    TimeWindow,
    TimingMode,
    TransitLeg,
    TransitRoute,
    TransitSchedule,
    TravelTimeEntry,
    TravelTimeMatrix,
    Vehicle,
    VehicleType,
)

SGT = ZoneInfo("Asia/Singapore")

# Master calendar constants
DATE_PRIMARY = "2026-09-14"
DATE_SECONDARY = "2026-09-15"

W1_START = datetime(2026, 9, 14, 1, 15, tzinfo=SGT)
W1_END = datetime(2026, 9, 14, 4, 45, tzinfo=SGT)
W2_START = datetime(2026, 9, 15, 1, 15, tzinfo=SGT)
W2_END = datetime(2026, 9, 15, 4, 45, tzinfo=SGT)


@dataclass(frozen=True)
class ScenarioExpectation:
    name: str
    factory: str
    category: str
    request_ids: tuple[str, ...]
    expected_status: str | None
    expected_codes: tuple[str, ...]
    description: str


# =============================================================================
# Topology & Resources Catalog Helpers
# =============================================================================

def _build_stations() -> list[Station]:
    return [
        Station(id="EW1", name="Pasir Ris", schematic_x=0),
        Station(id="EW2", name="Tampines", schematic_x=1),
        Station(id="EW3", name="Simei", schematic_x=2),
        Station(id="EW4", name="Tanah Merah", schematic_x=3),
        Station(id="EW5", name="Bedok", schematic_x=4),
        Station(id="EW6", name="Kembangan", schematic_x=5),
        Station(id="EW7", name="Eunos", schematic_x=6),
    ]


def _build_power_zones() -> list[PowerZone]:
    return [
        PowerZone(id="Z01", sector_ids=["S01", "S02"]),
        PowerZone(id="Z02", sector_ids=["S03", "S04"]),
        PowerZone(id="Z03", sector_ids=["S05", "S06"]),
    ]


def _build_sectors() -> list[Sector]:
    return [
        Sector(id="S01", from_station="EW1", to_station="EW2", direction="Westbound", power_zone="Z01", exclusive_protection=True),
        Sector(id="S02", from_station="EW2", to_station="EW3", direction="Westbound", power_zone="Z01", exclusive_protection=True),
        Sector(id="S03", from_station="EW3", to_station="EW4", direction="Westbound", power_zone="Z02", exclusive_protection=True),
        Sector(id="S04", from_station="EW4", to_station="EW5", direction="Westbound", power_zone="Z02", exclusive_protection=True),
        Sector(id="S05", from_station="EW5", to_station="EW6", direction="Westbound", power_zone="Z03", exclusive_protection=True),
        Sector(id="S06", from_station="EW6", to_station="EW7", direction="Westbound", power_zone="Z03", exclusive_protection=True),
    ]


def _build_blackouts() -> list[Blackout]:
    return [
        Blackout(
            id="B01",
            sector_ids=["S01"],
            start=datetime(2026, 9, 14, 3, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 4, 30, tzinfo=SGT),
            reason="Viaduct structural testing and concrete scanning",
        ),
    ]


def _build_engineering_windows() -> list[EngineeringWindow]:
    all_sectors = ["S01", "S02", "S03", "S04", "S05", "S06"]
    return [
        EngineeringWindow(
            date=DATE_PRIMARY,
            sector_ids=all_sectors,
            start=W1_START,
            end=W1_END,
            handback_buffer_minutes=20,
        ),
        EngineeringWindow(
            date=DATE_SECONDARY,
            sector_ids=all_sectors,
            start=W2_START,
            end=W2_END,
            handback_buffer_minutes=20,
        ),
    ]


def _build_planning_rules() -> PlanningRules:
    return PlanningRules(
        source="synthetic_rules_v1",
        start_grid_minutes=5,
        different_site_transfer_minutes=15,
        opposed_power_transition_minutes=10,
        morning_buffer_minutes=20,
        freeze_horizon_days=3,
        power_values=[PowerRequirement.ON, PowerRequirement.OFF, PowerRequirement.NONE],
        power_compatibility={
            PowerRequirement.ON: {
                PowerRequirement.ON: True,
                PowerRequirement.OFF: False,
                PowerRequirement.NONE: True,
            },
            PowerRequirement.OFF: {
                PowerRequirement.ON: False,
                PowerRequirement.OFF: True,
                PowerRequirement.NONE: True,
            },
            PowerRequirement.NONE: {
                PowerRequirement.ON: True,
                PowerRequirement.OFF: True,
                PowerRequirement.NONE: True,
            },
        },
        work_compatibility_rules=[
            CompatibilityRule(
                work_type_a="rail_replacement",
                work_type_b="dynamic_signalling_test",
                compatible=False,
                transition_minutes=15,
            ),
            CompatibilityRule(
                work_type_a="track_tamping",
                work_type_b="sensor_inspection",
                compatible=False,
                transition_minutes=10,
            ),
            CompatibilityRule(
                work_type_a="point_machine_service",
                work_type_b="track_inspection",
                compatible=False,
                transition_minutes=10,
            ),
        ],
        unknown_rule_policy="REVIEW_REQUIRED",
    )


def _build_engineers() -> list[Engineer]:
    two_night_avail = [
        TimeWindow(start=W1_START, end=W1_END),
        TimeWindow(start=W2_START, end=W2_END),
    ]
    return [
        Engineer(id="E01", name="Engineer E01", skills=["track", "tamping"], initial_sector="S02", availability=two_night_avail),
        Engineer(id="E02", name="Engineer E02", skills=["track", "protection"], initial_sector="S04", availability=two_night_avail),
        Engineer(id="E03", name="Engineer E03", skills=["signalling"], initial_sector="S01", availability=two_night_avail),
        Engineer(id="E04", name="Engineer E04", skills=["signalling", "inspection"], initial_sector="S03", availability=two_night_avail),
        Engineer(id="E05", name="Engineer E05", skills=["power"], initial_sector="S02", availability=two_night_avail),
        Engineer(id="E06", name="Engineer E06", skills=["inspection", "power"], initial_sector="S05", availability=two_night_avail),
        Engineer(
            id="E07",
            name="Engineer E07",
            skills=["track"],
            initial_sector="S01",
            availability=two_night_avail,
            unavailable=[
                TimeWindow(
                    start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                    end=datetime(2026, 9, 14, 2, 30, tzinfo=SGT),
                )
            ],
        ),
    ]


def _build_equipment() -> list[Equipment]:
    two_night_avail = [
        TimeWindow(start=W1_START, end=W1_END),
        TimeWindow(start=W2_START, end=W2_END),
    ]
    return [
        Equipment(id="Q01", type="track_machine", initial_sector="S02", capacity=1, availability=two_night_avail, serviceable=True),
        Equipment(id="Q02", type="inspection_kit", initial_sector="S05", capacity=1, availability=two_night_avail, serviceable=True),
        Equipment(id="Q03", type="signalling_kit", initial_sector="S01", capacity=1, availability=two_night_avail, serviceable=True),
        Equipment(id="Q04", type="tower_wagon", initial_sector="S03", capacity=1, availability=two_night_avail, serviceable=False),
        Equipment(id="Q05", type="portable_test_rig", initial_sector="S04", capacity=1, availability=two_night_avail, serviceable=True),
    ]


def _build_resource_pools() -> list[ResourcePool]:
    return [
        ResourcePool(id="TECH", name="Technicians Pool", capacity=5),
        ResourcePool(id="TPO", name="Track Protection Officers Pool", capacity=2),
    ]


def _build_vehicles() -> list[Vehicle]:
    two_night_avail = [
        TimeWindow(start=W1_START, end=W1_END),
        TimeWindow(start=W2_START, end=W2_END),
    ]
    return [
        Vehicle(
            id="V01",
            name="Tamping Machine 1",
            type=VehicleType.TAMPING_MACHINE,
            home_depot="CHANGI_DEPOT",
            availability=two_night_avail,
            routes=[
                TransitRoute(
                    origin_depot="CHANGI_DEPOT",
                    destination_sector="S02",
                    legs=[
                        TransitLeg(sector_id="S01", travel_minutes=15),
                        TransitLeg(sector_id="S02", travel_minutes=10),
                    ],
                )
            ],
        ),
        Vehicle(
            id="V02",
            name="Inspection Train 1",
            type=VehicleType.INSPECTION_TRAIN,
            home_depot="TUAS_DEPOT",
            availability=two_night_avail,
            routes=[
                TransitRoute(
                    origin_depot="TUAS_DEPOT",
                    destination_sector="S05",
                    legs=[
                        TransitLeg(sector_id="S06", travel_minutes=15),
                        TransitLeg(sector_id="S05", travel_minutes=10),
                    ],
                )
            ],
        ),
    ]


def _build_travel_time_matrix() -> TravelTimeMatrix:
    pairs = [
        ("S01", "S02", 10),
        ("S02", "S03", 10),
        ("S02", "S04", 15),
        ("S02", "S05", 25),
        ("S02", "S06", 25),
        ("S03", "S05", 15),
        ("S01", "S05", 25),
        ("S01", "S06", 30),
    ]
    entries: list[TravelTimeEntry] = []
    for s_from, s_to, mins in pairs:
        entries.append(TravelTimeEntry(from_sector=s_from, to_sector=s_to, travel_minutes=mins))
        entries.append(TravelTimeEntry(from_sector=s_to, to_sector=s_from, travel_minutes=mins))
    return TravelTimeMatrix(entries=entries)


def _build_job_catalogue() -> list[JobTypeEntry]:
    return [
        JobTypeEntry(
            work_type="rail_replacement",
            default_duration_minutes=70,
            required_engineer_roles={"track": 1},
            pooled_resources={"TECH": 2},
            power_requirement=PowerRequirement.OFF,
        ),
        JobTypeEntry(
            work_type="dynamic_signalling_test",
            default_duration_minutes=50,
            required_engineer_roles={"signalling": 1},
            pooled_resources={"TECH": 1},
            power_requirement=PowerRequirement.ON,
        ),
        JobTypeEntry(
            work_type="sensor_inspection",
            default_duration_minutes=50,
            required_engineer_roles={"inspection": 1},
            pooled_resources={"TECH": 1},
            power_requirement=PowerRequirement.NONE,
        ),
        JobTypeEntry(
            work_type="catenary_service",
            default_duration_minutes=60,
            required_engineer_roles={"power": 1},
            pooled_resources={"TECH": 2, "TPO": 1},
            power_requirement=PowerRequirement.OFF,
        ),
        JobTypeEntry(
            work_type="track_tamping",
            default_duration_minutes=60,
            required_engineer_roles={"track": 1},
            pooled_resources={"TECH": 4, "TPO": 1},
            power_requirement=PowerRequirement.NONE,
        ),
        JobTypeEntry(
            work_type="point_machine_service",
            default_duration_minutes=60,
            required_engineer_roles={"signalling": 1},
            pooled_resources={"TECH": 1},
            power_requirement=PowerRequirement.NONE,
        ),
        JobTypeEntry(
            work_type="track_inspection",
            default_duration_minutes=30,
            required_engineer_roles={"inspection": 1},
            pooled_resources={"TECH": 1},
            power_requirement=PowerRequirement.NONE,
        ),
    ]


def _standard_phases(setup: int, work: int, test: int, handback: int) -> list[Phase]:
    return [
        Phase(name=PhaseType.setup, duration_minutes=setup),
        Phase(name=PhaseType.work, duration_minutes=work),
        Phase(name=PhaseType.test, duration_minutes=test),
        Phase(name=PhaseType.handback, duration_minutes=handback),
    ]


# =============================================================================
# Primary Request Matrix (R01 to R12)
# =============================================================================

def _build_comprehensive_requests() -> list[MaintenanceRequest]:
    return [
        # R01: Frozen approved baseline
        MaintenanceRequest(
            id="R01",
            title="Rail replacement at Sector 02",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S02",
            protected_sectors=["S01", "S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 40, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=True,
            frozen=True,
            existing_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            urgency_score=4,
            required_skill="track",
            required_engineer_roles={"track": 1},
            eligible_engineers=["E01", "E02", "E07"],
            preferred_engineer="E01",
            required_equipment_ids=["Q01"],
            pooled_resources={"TECH": 2},
            status=RequestStatus.scheduled,
        ),
        # R02: Approved non-frozen baseline
        MaintenanceRequest(
            id="R02",
            title="Sensor inspection at Sector 05",
            owner_id="team_inspection",
            work_type="sensor_inspection",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=True,
            frozen=False,
            existing_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            urgency_score=3,
            required_skill="inspection",
            required_engineer_roles={"inspection": 1},
            eligible_engineers=["E04", "E06"],
            preferred_engineer="E06",
            required_equipment_ids=["Q02"],
            pooled_resources={"TECH": 1},
            status=RequestStatus.scheduled,
        ),
        # R03: Dependency and power transition
        MaintenanceRequest(
            id="R03",
            title="Dynamic signalling test at Sector 02",
            owner_id="team_signalling",
            work_type="dynamic_signalling_test",
            work_sector="S02",
            protected_sectors=["S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.ON,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="signalling",
            required_engineer_roles={"signalling": 1},
            eligible_engineers=["E03", "E04"],
            required_equipment_ids=["Q03"],
            pooled_resources={"TECH": 1},
            depends_on=["R01"],
            handover_buffer_minutes=15,
            status=RequestStatus.submitted,
        ),
        # R04: Exact-time footprint conflict
        MaintenanceRequest(
            id="R04",
            title="Exact rail replacement at Sector 01",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S01",
            protected_sectors=["S01", "S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 40, 10, 10),
            timing_mode=TimingMode.EXACT,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 3, 10, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="track",
            required_engineer_roles={"track": 1},
            eligible_engineers=["E01", "E02", "E07"],
            preferred_engineer="E01",
            required_equipment_ids=["Q01"],
            pooled_resources={"TECH": 2},
            status=RequestStatus.submitted,
        ),
        # R05: Qualification, travel, and equipment-negative case
        MaintenanceRequest(
            id="R05",
            title="Catenary service at Sector 06",
            owner_id="team_power",
            work_type="catenary_service",
            work_sector="S06",
            protected_sectors=["S06"],
            power_zone="Z03",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 50, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="power",
            required_engineer_roles={"power": 1},
            eligible_engineers=["E05", "E06"],
            required_equipment_ids=["Q04"],  # Unserviceable tower wagon
            pooled_resources={"TECH": 2, "TPO": 1},
            status=RequestStatus.submitted,
        ),
        # R06: Cumulative manpower surge
        MaintenanceRequest(
            id="R06",
            title="Track tamping at Sector 04",
            owner_id="team_track",
            work_type="track_tamping",
            work_sector="S04",
            protected_sectors=["S04"],
            power_zone="Z02",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="track",
            required_engineer_roles={"track": 1},
            eligible_engineers=["E01", "E02", "E07"],
            required_equipment_ids=[],
            pooled_resources={"TECH": 4, "TPO": 1},
            status=RequestStatus.submitted,
        ),
        # R07: Blackout and specialist contention
        MaintenanceRequest(
            id="R07",
            title="Point machine service at Sector 01",
            owner_id="team_signalling",
            work_type="point_machine_service",
            work_sector="S01",
            protected_sectors=["S01"],
            power_zone="Z01",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 3, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="signalling",
            required_engineer_roles={"signalling": 1},
            eligible_engineers=["E03", "E04"],
            preferred_engineer="E03",
            required_equipment_ids=["Q03"],
            pooled_resources={"TECH": 1},
            status=RequestStatus.submitted,
        ),
        # R08: Handback overflow
        MaintenanceRequest(
            id="R08",
            title="Rail replacement at Sector 03 with handback overflow",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S03",
            protected_sectors=["S03"],
            power_zone="Z02",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 40, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 3, 30, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 45, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="track",
            required_engineer_roles={"track": 1},
            eligible_engineers=["E01", "E02", "E07"],
            required_equipment_ids=[],
            pooled_resources={"TECH": 2},
            status=RequestStatus.submitted,
        ),
        # R09: Mandatory service-critical request
        MaintenanceRequest(
            id="R09",
            title="Mandatory service-critical rail replacement",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S03",
            protected_sectors=["S03"],
            power_zone="Z02",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=False,
            mandatory=True,
            approved=False,
            frozen=False,
            urgency_score=5,
            required_skill="track",
            required_engineer_roles={"track": 1},
            eligible_engineers=["E01", "E02", "E07"],
            required_equipment_ids=[],
            pooled_resources={"TECH": 2},
            status=RequestStatus.submitted,
        ),
        # R10: Optional any-time request
        MaintenanceRequest(
            id="R10",
            title="Optional sensor inspection at Sector 05",
            owner_id="team_inspection",
            work_type="sensor_inspection",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(5, 20, 5, 10),
            timing_mode=TimingMode.ANY_TIME,
            preferred_start=None,
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=2,
            required_skill="inspection",
            required_engineer_roles={"inspection": 1},
            eligible_engineers=["E04", "E06"],
            required_equipment_ids=["Q02"],
            pooled_resources={"TECH": 1},
            status=RequestStatus.submitted,
        ),
        # R11: Vehicle transit interaction
        MaintenanceRequest(
            id="R11",
            title="Track inspection at Sector 01",
            owner_id="team_inspection",
            work_type="track_inspection",
            work_sector="S01",
            protected_sectors=["S01"],
            power_zone="Z01",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(5, 15, 5, 5),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="inspection",
            required_engineer_roles={"inspection": 1},
            eligible_engineers=["E04", "E06"],
            required_equipment_ids=[],
            pooled_resources={"TECH": 1},
            status=RequestStatus.submitted,
        ),
        # R12: Multi-date request
        MaintenanceRequest(
            id="R12",
            title="Multi-date catenary service at Sector 04",
            owner_id="team_power",
            work_type="catenary_service",
            work_sector="S04",
            protected_sectors=["S04"],
            power_zone="Z02",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=None,
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 15, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY, DATE_SECONDARY],
            deferrable=True,
            mandatory=False,
            approved=False,
            frozen=False,
            urgency_score=3,
            required_skill="power",
            required_engineer_roles={"power": 1},
            eligible_engineers=["E05", "E06"],
            required_equipment_ids=[],
            pooled_resources={"TECH": 2, "TPO": 1},
            status=RequestStatus.submitted,
        ),
    ]


def _build_comprehensive_allocations() -> list[Allocation]:
    return [
        Allocation(
            request_id="R01",
            start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 40, tzinfo=SGT),
            engineer_id="E01",
            equipment_ids=["Q01"],
            locked=True,
        ),
        Allocation(
            request_id="R02",
            start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 50, tzinfo=SGT),
            engineer_id="E06",
            equipment_ids=["Q02"],
            locked=False,
        ),
    ]


# =============================================================================
# Master Snapshot Factory
# =============================================================================

def build_comprehensive_snapshot() -> PlanningSnapshot:
    """Build and validate the 12-request master snapshot."""
    metadata = SnapshotMetadata(
        schema_version="1.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=DATE_PRIMARY,
        synthetic=True,
        description="Comprehensive synthetic dataset based on Singapore MRT East-West Line (EW1 Pasir Ris to EW7 Eunos) and maintenance depots.",
        disclaimer="NOT operational data. Fictional, synthetic scheduling scenario based on Singapore MRT East-West Line stations and real-world depots (Changi Depot, Tuas Depot).",
        scope="Twelve-request comprehensive benchmark fixture along the East-West Line (EW1-EW7) covering track sectors, power zones, and maintenance depots.",
        simplifications=[
            "Single-direction East-West Line (Westbound) corridor with realistic schematic station spacing.",
            "Exclusive protection footprints across all request phases.",
            "Synthetic planning guards for power transitions and site transfers.",
            "Pooled resources track capacity limits rather than spatial transit.",
        ],
    )

    transit_schedules = [
        TransitSchedule(
            vehicle_id="V01",
            sector_id="S01",
            start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            end=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
        )
    ]

    return PlanningSnapshot(
        metadata=metadata,
        stations=_build_stations(),
        power_zones=_build_power_zones(),
        sectors=_build_sectors(),
        engineering_windows=_build_engineering_windows(),
        blackouts=_build_blackouts(),
        planning_rules=_build_planning_rules(),
        engineers=_build_engineers(),
        equipment=_build_equipment(),
        resource_pools=_build_resource_pools(),
        requests=_build_comprehensive_requests(),
        committed_allocations=_build_comprehensive_allocations(),
        travel_time_matrix=_build_travel_time_matrix(),
        vehicles=_build_vehicles(),
        transit_schedules=transit_schedules,
        job_catalogue=_build_job_catalogue(),
    )


# =============================================================================
# Advanced Scenario Factories
# =============================================================================

def build_feasible_snapshot() -> PlanningSnapshot:
    """Build a small snapshot with a complete reference allocation set."""
    metadata = SnapshotMetadata(
        schema_version="1.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=DATE_PRIMARY,
        synthetic=True,
        description="Feasible reference snapshot with a complete non-conflicting schedule.",
        disclaimer="NOT operational data. Fictional synthetic dataset.",
        scope="Four mutually compatible maintenance requests with valid full allocation set.",
        simplifications=["Exclusive protection footprints", "Synthetic planning guards"],
    )

    # Small mutually compatible subset of requests
    requests = [
        # Frozen R01 (01:30 - 02:40)
        MaintenanceRequest(
            id="R01",
            title="Rail replacement at Sector 02",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S02",
            protected_sectors=["S01", "S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 40, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            frozen=True,
            existing_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            urgency_score=4,
            required_skill="track",
            eligible_engineers=["E01", "E02"],
            preferred_engineer="E01",
            required_equipment_ids=["Q01"],
            pooled_resources={"TECH": 2},
            status=RequestStatus.scheduled,
        ),
        # Approved R02 (02:00 - 02:50)
        MaintenanceRequest(
            id="R02",
            title="Sensor inspection at Sector 05",
            owner_id="team_inspection",
            work_type="sensor_inspection",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            frozen=False,
            existing_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            urgency_score=3,
            required_skill="inspection",
            eligible_engineers=["E04", "E06"],
            preferred_engineer="E06",
            required_equipment_ids=["Q02"],
            pooled_resources={"TECH": 1},
            status=RequestStatus.scheduled,
        ),
        # Mandatory track work on S03 scheduled 01:30 - 02:30 (alongside R01 without exceeding TECH:5)
        MaintenanceRequest(
            id="R09",
            title="Mandatory rail replacement at Sector 03",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S03",
            protected_sectors=["S03"],
            power_zone="Z02",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            mandatory=True,
            deferrable=False,
            approved=True,
            existing_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            urgency_score=5,
            required_skill="track",
            eligible_engineers=["E02"],
            preferred_engineer="E02",
            required_equipment_ids=["Q05"],
            pooled_resources={"TECH": 2},
            status=RequestStatus.scheduled,
        ),
        # Dependent signalling work after R01 beginning at 02:55 (02:40 + 15m handover)
        MaintenanceRequest(
            id="R03",
            title="Dynamic signalling test at Sector 02",
            owner_id="team_signalling",
            work_type="dynamic_signalling_test",
            work_sector="S02",
            protected_sectors=["S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.ON,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 55, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            existing_start=datetime(2026, 9, 14, 2, 55, tzinfo=SGT),
            urgency_score=3,
            required_skill="signalling",
            eligible_engineers=["E03"],
            preferred_engineer="E03",
            required_equipment_ids=["Q03"],
            pooled_resources={"TECH": 1},
            depends_on=["R01"],
            handover_buffer_minutes=15,
            status=RequestStatus.scheduled,
        ),
    ]

    allocations = [
        Allocation(
            request_id="R01",
            start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 40, tzinfo=SGT),
            engineer_id="E01",
            equipment_ids=["Q01"],
            locked=True,
        ),
        Allocation(
            request_id="R02",
            start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 50, tzinfo=SGT),
            engineer_id="E06",
            equipment_ids=["Q02"],
            locked=False,
        ),
        Allocation(
            request_id="R09",
            start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            end=datetime(2026, 9, 14, 2, 30, tzinfo=SGT),
            engineer_id="E02",
            equipment_ids=["Q05"],
            locked=False,
        ),
        Allocation(
            request_id="R03",
            start=datetime(2026, 9, 14, 2, 55, tzinfo=SGT),
            end=datetime(2026, 9, 14, 3, 45, tzinfo=SGT),
            engineer_id="E03",
            equipment_ids=["Q03"],
            locked=False,
        ),
    ]

    return PlanningSnapshot(
        metadata=metadata,
        stations=_build_stations(),
        power_zones=_build_power_zones(),
        sectors=_build_sectors(),
        engineering_windows=_build_engineering_windows(),
        blackouts=_build_blackouts(),
        planning_rules=_build_planning_rules(),
        engineers=_build_engineers(),
        equipment=_build_equipment(),
        resource_pools=_build_resource_pools(),
        requests=requests,
        committed_allocations=allocations,
        travel_time_matrix=_build_travel_time_matrix(),
        vehicles=_build_vehicles(),
        transit_schedules=[],
        job_catalogue=_build_job_catalogue(),
    )


def build_infeasible_deadlock_scenario(
    deadlock_type: Literal["frozen", "manpower", "blackout"] = "frozen",
) -> PlanningSnapshot:
    """Build a typed mandatory-deadlock snapshot."""
    metadata = SnapshotMetadata(
        schema_version="1.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=DATE_PRIMARY,
        synthetic=True,
        description=f"Infeasible deadlock scenario: {deadlock_type}.",
        disclaimer="NOT operational data. Fictional synthetic dataset.",
        scope="Synthetic deadlock test scenario exhibiting structural infeasibility.",
        simplifications=["Exclusive protection footprints", "Fixed capacity limits"],
    )

    requests: list[MaintenanceRequest] = []
    allocations: list[Allocation] = []
    blackouts = _build_blackouts()

    if deadlock_type == "frozen":
        # Frozen booking occupies S02 footprint 01:15 to 03:50 (155 min)
        # Usable handback cutoff is 04:25 (only 35 min left)
        # Mandatory request on S02 requires 60 min -> cannot fit in 35 min
        req_frozen = MaintenanceRequest(
            id="R01_frozen",
            title="Frozen booking blocking sector footprint",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S02",
            protected_sectors=["S01", "S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 125, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            frozen=True,
            existing_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            required_skill="track",
            eligible_engineers=["E01"],
            status=RequestStatus.scheduled,
        )
        req_mand = MaintenanceRequest(
            id="R_mandatory",
            title="Mandatory work blocked by frozen allocation",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S02",
            protected_sectors=["S01", "S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            mandatory=True,
            deferrable=False,
            urgency_score=5,
            required_skill="track",
            eligible_engineers=["E02"],
            status=RequestStatus.submitted,
        )
        requests = [req_frozen, req_mand]
        allocations = [
            Allocation(
                request_id="R01_frozen",
                start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                end=datetime(2026, 9, 14, 3, 50, tzinfo=SGT),
                engineer_id="E01",
                locked=True,
            )
        ]

    elif deadlock_type == "manpower":
        # Two mandatory EXACT requests at 02:00, each needing TECH:3.
        # Pool capacity is 5. Total demand is 6 > 5.
        req_m1 = MaintenanceRequest(
            id="REQ_M1",
            title="Mandatory exact slot work A",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S01",
            protected_sectors=["S01"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.EXACT,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 3, 0, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            mandatory=True,
            deferrable=False,
            urgency_score=5,
            required_skill="track",
            eligible_engineers=["E01"],
            pooled_resources={"TECH": 3},
            status=RequestStatus.submitted,
        )
        req_m2 = MaintenanceRequest(
            id="REQ_M2",
            title="Mandatory exact slot work B",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 30, 10, 10),
            timing_mode=TimingMode.EXACT,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 3, 0, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            mandatory=True,
            deferrable=False,
            urgency_score=5,
            required_skill="track",
            eligible_engineers=["E02"],
            pooled_resources={"TECH": 3},
            status=RequestStatus.submitted,
        )
        requests = [req_m1, req_m2]

    elif deadlock_type == "blackout":
        # Blackout on S01 from 02:00 to 04:30.
        # Mandatory 70m request on S01.
        # Before blackout: 01:15 to 02:00 (45m available < 70m).
        # After blackout: blackout ends 04:30, usable window ends 04:25 (0m available).
        blackouts = [
            Blackout(
                id="B01",
                sector_ids=["S01"],
                start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
                end=datetime(2026, 9, 14, 4, 30, tzinfo=SGT),
                reason="Structural tunnel scanning and concrete coring",
            )
        ]
        req_b1 = MaintenanceRequest(
            id="REQ_B1",
            title="Mandatory rail replacement under long blackout",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S01",
            protected_sectors=["S01"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 40, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            mandatory=True,
            deferrable=False,
            urgency_score=5,
            required_skill="track",
            eligible_engineers=["E01", "E02"],
            pooled_resources={"TECH": 2},
            status=RequestStatus.submitted,
        )
        requests = [req_b1]

    return PlanningSnapshot(
        metadata=metadata,
        stations=_build_stations(),
        power_zones=_build_power_zones(),
        sectors=_build_sectors(),
        engineering_windows=_build_engineering_windows(),
        blackouts=blackouts,
        planning_rules=_build_planning_rules(),
        engineers=_build_engineers(),
        equipment=_build_equipment(),
        resource_pools=_build_resource_pools(),
        requests=requests,
        committed_allocations=allocations,
        travel_time_matrix=_build_travel_time_matrix(),
        vehicles=_build_vehicles(),
        transit_schedules=[],
        job_catalogue=_build_job_catalogue(),
    )


def build_compound_conflict_scenario(
    case_type: Literal["nexus", "vehicle_corridor"] = "nexus",
) -> PlanningSnapshot:
    """Build a typed compound-constraint snapshot."""
    metadata = SnapshotMetadata(
        schema_version="1.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=DATE_PRIMARY,
        synthetic=True,
        description=f"Compound conflict scenario: {case_type}.",
        disclaimer="NOT operational data. Fictional synthetic dataset.",
        scope="Multi-constraint compound interaction benchmark case.",
        simplifications=["Exclusive footprints", "Vehicle corridor reservations"],
    )

    requests: list[MaintenanceRequest] = []
    allocations: list[Allocation] = []
    transit_schedules: list[TransitSchedule] = []

    if case_type == "nexus":
        # Encodes:
        # Predecessor R01 ends at 02:40 on S02 (power OFF)
        # Handover buffer 15m -> 02:55
        # Opposed-power transition 10m -> 02:50
        # Specialist E04 finishes job R_spec on S05 at 02:30; S05 -> S02 transfer is 25m -> 02:55
        # Composite earliest start: max(02:55, 02:50, 02:55) = 02:55
        r01 = MaintenanceRequest(
            id="R01",
            title="Predecessor track job",
            owner_id="team_track",
            work_type="rail_replacement",
            work_sector="S02",
            protected_sectors=["S01", "S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.OFF,
            phases=_standard_phases(10, 40, 10, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            frozen=True,
            existing_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            required_skill="track",
            eligible_engineers=["E01"],
            status=RequestStatus.scheduled,
        )
        r_spec = MaintenanceRequest(
            id="R_spec",
            title="Prior job in S05 by signalling specialist E04",
            owner_id="team_inspection",
            work_type="sensor_inspection",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 40, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            frozen=False,
            existing_start=datetime(2026, 9, 14, 1, 40, tzinfo=SGT),
            required_skill="inspection",
            eligible_engineers=["E04"],
            status=RequestStatus.scheduled,
        )
        r03 = MaintenanceRequest(
            id="R03",
            title="Nexus dynamic signalling test",
            owner_id="team_signalling",
            work_type="dynamic_signalling_test",
            work_sector="S02",
            protected_sectors=["S02"],
            power_zone="Z01",
            power_requirement=PowerRequirement.ON,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 15, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            required_skill="signalling",
            eligible_engineers=["E04"],
            depends_on=["R01"],
            handover_buffer_minutes=15,
            status=RequestStatus.submitted,
        )
        requests = [r01, r_spec, r03]
        allocations = [
            Allocation(
                request_id="R01",
                start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
                end=datetime(2026, 9, 14, 2, 40, tzinfo=SGT),
                engineer_id="E01",
                locked=True,
            ),
            Allocation(
                request_id="R_spec",
                start=datetime(2026, 9, 14, 1, 40, tzinfo=SGT),
                end=datetime(2026, 9, 14, 2, 30, tzinfo=SGT),
                engineer_id="E04",
                locked=False,
            ),
        ]

    elif case_type == "vehicle_corridor":
        # Transit reservation for V01 on S01 (01:15 - 01:45)
        # Allocation for R11 on S01 assigns V01 (01:30 - 02:00), overlapping transit
        transit_schedules = [
            TransitSchedule(
                vehicle_id="V01",
                sector_id="S01",
                start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                end=datetime(2026, 9, 14, 1, 45, tzinfo=SGT),
            )
        ]
        r11 = MaintenanceRequest(
            id="R11",
            title="Track inspection with vehicle allocation",
            owner_id="team_inspection",
            work_type="track_inspection",
            work_sector="S01",
            protected_sectors=["S01"],
            power_zone="Z01",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(5, 15, 5, 5),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            existing_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
            required_skill="inspection",
            eligible_engineers=["E04"],
            status=RequestStatus.scheduled,
        )
        requests = [r11]
        allocations = [
            Allocation(
                request_id="R11",
                start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
                end=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
                engineer_id="E04",
                vehicle_ids=["V01"],
                locked=False,
            )
        ]

    return PlanningSnapshot(
        metadata=metadata,
        stations=_build_stations(),
        power_zones=_build_power_zones(),
        sectors=_build_sectors(),
        engineering_windows=_build_engineering_windows(),
        blackouts=_build_blackouts(),
        planning_rules=_build_planning_rules(),
        engineers=_build_engineers(),
        equipment=_build_equipment(),
        resource_pools=_build_resource_pools(),
        requests=requests,
        committed_allocations=allocations,
        travel_time_matrix=_build_travel_time_matrix(),
        vehicles=_build_vehicles(),
        transit_schedules=transit_schedules,
        job_catalogue=_build_job_catalogue(),
    )


def build_trivial_fastpath_scenario(
    case_type: Literal["empty", "orthogonal", "domain_impossible", "missing_skill"] = "empty",
) -> PlanningSnapshot:
    """Build a typed fast-path data scenario."""
    metadata = SnapshotMetadata(
        schema_version="1.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=DATE_PRIMARY,
        synthetic=True,
        description=f"Fast-path benchmark scenario: {case_type}.",
        disclaimer="NOT operational data. Fictional synthetic dataset.",
        scope="Trivial classification fastpath instance.",
        simplifications=["Disjoint partitions", "Edge case parameters"],
    )

    requests: list[MaintenanceRequest] = []

    if case_type == "empty":
        requests = []

    elif case_type == "orthogonal":
        # 3 requests in S01, S03, S05 with disjoint power zones Z01, Z02, Z03
        # Distinct engineers, distinct equipment, TECH:1 each (total 3 <= 5)
        requests = [
            MaintenanceRequest(
                id="REQ_ORTHO_1",
                title="Orthogonal job 1",
                owner_id="team_signalling",
                work_type="point_machine_service",
                work_sector="S01",
                protected_sectors=["S01"],
                power_zone="Z01",
                power_requirement=PowerRequirement.NONE,
                phases=_standard_phases(10, 30, 10, 10),
                timing_mode=TimingMode.RANGE,
                preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                required_skill="signalling",
                eligible_engineers=["E03"],
                required_equipment_ids=["Q03"],
                pooled_resources={"TECH": 1},
                status=RequestStatus.submitted,
            ),
            MaintenanceRequest(
                id="REQ_ORTHO_2",
                title="Orthogonal job 2",
                owner_id="team_track",
                work_type="rail_replacement",
                work_sector="S03",
                protected_sectors=["S03"],
                power_zone="Z02",
                power_requirement=PowerRequirement.OFF,
                phases=_standard_phases(10, 30, 10, 10),
                timing_mode=TimingMode.RANGE,
                preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                required_skill="track",
                eligible_engineers=["E02"],
                required_equipment_ids=["Q05"],
                pooled_resources={"TECH": 1},
                status=RequestStatus.submitted,
            ),
            MaintenanceRequest(
                id="REQ_ORTHO_3",
                title="Orthogonal job 3",
                owner_id="team_inspection",
                work_type="sensor_inspection",
                work_sector="S05",
                protected_sectors=["S05"],
                power_zone="Z03",
                power_requirement=PowerRequirement.NONE,
                phases=_standard_phases(10, 25, 5, 10),
                timing_mode=TimingMode.RANGE,
                preferred_start=datetime(2026, 9, 14, 1, 30, tzinfo=SGT),
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                required_skill="inspection",
                eligible_engineers=["E06"],
                required_equipment_ids=["Q02"],
                pooled_resources={"TECH": 1},
                status=RequestStatus.submitted,
            ),
        ]

    elif case_type == "domain_impossible":
        # ANY_TIME request duration 240 min against usable engineering window of 190 min
        requests = [
            MaintenanceRequest(
                id="REQ_IMPOSSIBLE",
                title="Statically impossible duration request",
                owner_id="team_track",
                work_type="rail_replacement",
                work_sector="S02",
                protected_sectors=["S02"],
                power_zone="Z01",
                power_requirement=PowerRequirement.OFF,
                phases=_standard_phases(20, 180, 20, 20),  # total 240 min
                timing_mode=TimingMode.ANY_TIME,
                preferred_start=None,
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                required_skill="track",
                eligible_engineers=["E01", "E02"],
                status=RequestStatus.submitted,
            )
        ]

    elif case_type == "missing_skill":
        # Mandatory request requiring non-existent skill
        requests = [
            MaintenanceRequest(
                id="REQ_NO_SKILL",
                title="Mandatory request with missing qualification",
                owner_id="team_track",
                work_type="rail_replacement",
                work_sector="S03",
                protected_sectors=["S03"],
                power_zone="Z02",
                power_requirement=PowerRequirement.OFF,
                phases=_standard_phases(10, 30, 10, 10),
                timing_mode=TimingMode.RANGE,
                preferred_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                mandatory=True,
                deferrable=False,
                urgency_score=5,
                required_skill="underwater_welding",
                required_engineer_roles={"underwater_welding": 1},
                eligible_engineers=[],
                status=RequestStatus.submitted,
            )
        ]

    return PlanningSnapshot(
        metadata=metadata,
        stations=_build_stations(),
        power_zones=_build_power_zones(),
        sectors=_build_sectors(),
        engineering_windows=_build_engineering_windows(),
        blackouts=_build_blackouts(),
        planning_rules=_build_planning_rules(),
        engineers=_build_engineers(),
        equipment=_build_equipment(),
        resource_pools=_build_resource_pools(),
        requests=requests,
        committed_allocations=[],
        travel_time_matrix=_build_travel_time_matrix(),
        vehicles=_build_vehicles(),
        transit_schedules=[],
        job_catalogue=_build_job_catalogue(),
    )


def build_lexicographic_tradeoff_scenario(
    case_type: Literal["stability", "load", "handback"] = "stability",
) -> PlanningSnapshot:
    """Build a typed optimization-trade-off snapshot."""
    metadata = SnapshotMetadata(
        schema_version="1.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=DATE_PRIMARY,
        synthetic=True,
        description=f"Optimization trade-off scenario: {case_type}.",
        disclaimer="NOT operational data. Fictional synthetic dataset.",
        scope="Lexicographic objective hierarchy validation fixture.",
        simplifications=["Prioritized objective trade-offs"],
    )

    requests: list[MaintenanceRequest] = []
    allocations: list[Allocation] = []

    if case_type == "stability":
        # Approved non-frozen booking at 02:00 on S05
        # Urgency-5 optional request competing for exact same slot on S05
        # Stability objective protects existing approved booking from displacement
        r02 = MaintenanceRequest(
            id="R02",
            title="Approved non-frozen booking",
            owner_id="team_inspection",
            work_type="sensor_inspection",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.RANGE,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            approved=True,
            frozen=False,
            existing_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            urgency_score=3,
            required_skill="inspection",
            eligible_engineers=["E06"],
            status=RequestStatus.scheduled,
        )
        req_opt_urgent = MaintenanceRequest(
            id="REQ_OPT_URGENT",
            title="Urgent optional request competing with approved booking",
            owner_id="team_inspection",
            work_type="sensor_inspection",
            work_sector="S05",
            protected_sectors=["S05"],
            power_zone="Z03",
            power_requirement=PowerRequirement.NONE,
            phases=_standard_phases(10, 25, 5, 10),
            timing_mode=TimingMode.EXACT,
            preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            earliest_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
            deadline=datetime(2026, 9, 14, 2, 50, tzinfo=SGT),
            allowed_dates=[DATE_PRIMARY],
            deferrable=True,
            mandatory=False,
            urgency_score=5,
            required_skill="inspection",
            eligible_engineers=["E04"],
            status=RequestStatus.submitted,
        )
        requests = [r02, req_opt_urgent]
        allocations = [
            Allocation(
                request_id="R02",
                start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
                end=datetime(2026, 9, 14, 2, 50, tzinfo=SGT),
                engineer_id="E06",
                locked=False,
            )
        ]

    elif case_type == "load":
        # 8 requests competing for TECH:5 capacity.
        # Mandatory & urgency-4/5 requests vs urgency-1/2 deferrable requests.
        # Lower-urgency deferrable work is the load-shedding candidate.
        for i in range(1, 9):
            is_mandatory = (i == 1)
            urgency = 5 if i in (1, 2) else (4 if i in (3, 4) else (2 if i in (5, 6) else 1))
            sec = f"S0{(i % 6) + 1}"
            pz = "Z01" if sec in ("S01", "S02") else ("Z02" if sec in ("S03", "S04") else "Z03")
            requests.append(
                MaintenanceRequest(
                    id=f"REQ_LOAD_{i}",
                    title=f"Load competition package {i}",
                    owner_id="team_track",
                    work_type="rail_replacement",
                    work_sector=sec,
                    protected_sectors=[sec],
                    power_zone=pz,
                    power_requirement=PowerRequirement.NONE,
                    phases=_standard_phases(5, 20, 5, 5),
                    timing_mode=TimingMode.RANGE,
                    preferred_start=datetime(2026, 9, 14, 2, 0, tzinfo=SGT),
                    earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                    deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                    allowed_dates=[DATE_PRIMARY],
                    mandatory=is_mandatory,
                    deferrable=not is_mandatory,
                    urgency_score=urgency,
                    required_skill="track",
                    eligible_engineers=["E01", "E02", "E07"],
                    pooled_resources={"TECH": 1},
                    status=RequestStatus.submitted,
                )
            )

    elif case_type == "handback":
        # ANY_TIME requests with no preferred start and multiple valid schedules.
        # Primary comparison metric is minimizing latest completion time (makespan).
        requests = [
            MaintenanceRequest(
                id="REQ_HB_1",
                title="Anytime handback optimization package 1",
                owner_id="team_inspection",
                work_type="sensor_inspection",
                work_sector="S03",
                protected_sectors=["S03"],
                power_zone="Z02",
                power_requirement=PowerRequirement.NONE,
                phases=_standard_phases(5, 25, 5, 5),
                timing_mode=TimingMode.ANY_TIME,
                preferred_start=None,
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                urgency_score=3,
                required_skill="inspection",
                eligible_engineers=["E04"],
                status=RequestStatus.submitted,
            ),
            MaintenanceRequest(
                id="REQ_HB_2",
                title="Anytime handback optimization package 2",
                owner_id="team_inspection",
                work_type="sensor_inspection",
                work_sector="S04",
                protected_sectors=["S04"],
                power_zone="Z02",
                power_requirement=PowerRequirement.NONE,
                phases=_standard_phases(5, 25, 5, 5),
                timing_mode=TimingMode.ANY_TIME,
                preferred_start=None,
                earliest_start=datetime(2026, 9, 14, 1, 15, tzinfo=SGT),
                deadline=datetime(2026, 9, 14, 4, 25, tzinfo=SGT),
                allowed_dates=[DATE_PRIMARY],
                urgency_score=3,
                required_skill="inspection",
                eligible_engineers=["E06"],
                status=RequestStatus.submitted,
            ),
        ]

    return PlanningSnapshot(
        metadata=metadata,
        stations=_build_stations(),
        power_zones=_build_power_zones(),
        sectors=_build_sectors(),
        engineering_windows=_build_engineering_windows(),
        blackouts=_build_blackouts(),
        planning_rules=_build_planning_rules(),
        engineers=_build_engineers(),
        equipment=_build_equipment(),
        resource_pools=_build_resource_pools(),
        requests=requests,
        committed_allocations=allocations,
        travel_time_matrix=_build_travel_time_matrix(),
        vehicles=_build_vehicles(),
        transit_schedules=[],
        job_catalogue=_build_job_catalogue(),
    )


# =============================================================================
# Scenario Registry
# =============================================================================

SCENARIO_EXPECTATIONS: tuple[ScenarioExpectation, ...] = (
    # Comprehensive Snapshot 12 Requests
    ScenarioExpectation(
        name="R01_frozen_baseline",
        factory="build_comprehensive_snapshot",
        category="baseline",
        request_ids=("R01",),
        expected_status="scheduled",
        expected_codes=(),
        description="Approved and locked baseline booking on S02 (01:30-02:40). Valid committed schedule instance.",
    ),
    ScenarioExpectation(
        name="R02_approved_baseline",
        factory="build_comprehensive_snapshot",
        category="baseline",
        request_ids=("R02",),
        expected_status="scheduled",
        expected_codes=(),
        description="Approved non-frozen baseline booking on S05 (02:00-02:50). Valid committed schedule instance.",
    ),
    ScenarioExpectation(
        name="R03_dependency_power_transition",
        factory="build_comprehensive_snapshot",
        category="conflict",
        request_ids=("R03", "R01"),
        expected_status="conflict",
        expected_codes=("DEPENDENCY", "POWER"),
        description="Trigger: Preferred start 02:15 on S02 precedes R01 completion (02:40) + 15m handover (02:55), and requires power ON while R01 uses power OFF (needs 10m transition). Direct violation.",
    ),
    ScenarioExpectation(
        name="R04_exact_footprint_conflict",
        factory="build_comprehensive_snapshot",
        category="conflict",
        request_ids=("R04", "R01"),
        expected_status="conflict",
        expected_codes=("SPACE",),
        description="Trigger: EXACT timing request at 02:00-03:10 requires protected sector S02 which is exclusively occupied by locked R01 (01:30-02:40). Direct violation.",
    ),
    ScenarioExpectation(
        name="R05_equipment_transfer_unavailable",
        factory="build_comprehensive_snapshot",
        category="conflict",
        request_ids=("R05",),
        expected_status="conflict",
        expected_codes=("EQUIPMENT_UNAVAILABLE", "TRANSFER_TIME"),
        description="Trigger: Assigned equipment Q04 is unserviceable, and engineer travel from S02 to S06 requires 25m transfer time. Direct violation.",
    ),
    ScenarioExpectation(
        name="R06_manpower_surge",
        factory="build_comprehensive_snapshot",
        category="conflict",
        request_ids=("R06",),
        expected_status="conflict",
        expected_codes=("MANPOWER",),
        description="Trigger: Demand of TECH:4 at 02:00 combined with concurrent R01 (TECH:2) and R02 (TECH:1) totals TECH:7, exceeding capacity 5. Direct violation.",
    ),
    ScenarioExpectation(
        name="R07_blackout_specialist_contention",
        factory="build_comprehensive_snapshot",
        category="conflict",
        request_ids=("R07",),
        expected_status="conflict",
        expected_codes=("BLACKOUT", "ENGINEER"),
        description="Trigger: Preferred window 03:15-04:15 on S01 overlaps blackout B01 (03:00-04:30), and contends for specialist E03. Direct violation.",
    ),
    ScenarioExpectation(
        name="R08_handback_overflow",
        factory="build_comprehensive_snapshot",
        category="conflict",
        request_ids=("R08",),
        expected_status="conflict",
        expected_codes=("ENGINEERING_WINDOW",),
        description="Trigger: Preferred start 03:30 with 70m duration completes at 04:40, exceeding usable engineering window cutoff 04:25. Direct violation.",
    ),
    ScenarioExpectation(
        name="R09_mandatory_service_critical",
        factory="build_comprehensive_snapshot",
        category="mandatory",
        request_ids=("R09",),
        expected_status="submitted",
        expected_codes=(),
        description="Mandatory non-deferrable service-critical work package on S03 with urgency score 5. Valid schedule instance pending solver allocation.",
    ),
    ScenarioExpectation(
        name="R10_optional_anytime",
        factory="build_comprehensive_snapshot",
        category="optional",
        request_ids=("R10",),
        expected_status="submitted",
        expected_codes=(),
        description="Optional deferrable work with ANY_TIME timing mode and no preferred start timestamp. Valid schedule instance.",
    ),
    ScenarioExpectation(
        name="R11_vehicle_transit_interaction",
        factory="build_comprehensive_snapshot",
        category="vehicle",
        request_ids=("R11",),
        expected_status="conflict",
        expected_codes=("VEHICLE_TRANSIT",),
        description="Trigger: Maintenance work at 01:15-01:45 on S01 contends with transit schedule reservation of vehicle V01 on S01 (01:15-01:30). Direct violation.",
    ),
    ScenarioExpectation(
        name="R12_multidate_window",
        factory="build_comprehensive_snapshot",
        category="multidate",
        request_ids=("R12",),
        expected_status="submitted",
        expected_codes=(),
        description="Work request spanning multiple allowed engineering dates (2026-09-14, 2026-09-15) with power OFF requirement. Valid schedule instance.",
    ),
    # Advanced Scenarios
    ScenarioExpectation(
        name="feasible_reference",
        factory="build_feasible_snapshot",
        category="feasible",
        request_ids=("R01", "R02", "R09", "R03"),
        expected_status="FEASIBLE",
        expected_codes=(),
        description="Small snapshot with mutually compatible requests (R01, R02, R09, R03) and complete reference allocations. Valid schedule instance.",
    ),
    ScenarioExpectation(
        name="deadlock_frozen",
        factory="build_infeasible_deadlock_scenario(deadlock_type='frozen')",
        category="deadlock",
        request_ids=("R01_frozen", "R_mandatory"),
        expected_status="INFEASIBLE",
        expected_codes=("SPACE", "LOCKED_BOOKING"),
        description="Locked booking blocks mandatory request footprint until 03:50; only 35m remain before 04:25 handback for 60m job. Infeasible instance.",
    ),
    ScenarioExpectation(
        name="deadlock_manpower",
        factory="build_infeasible_deadlock_scenario(deadlock_type='manpower')",
        category="deadlock",
        request_ids=("REQ_M1", "REQ_M2"),
        expected_status="INFEASIBLE",
        expected_codes=("MANPOWER",),
        description="Two mandatory EXACT requests at 02:00 each demand TECH:3 against pool capacity 5. Infeasible instance.",
    ),
    ScenarioExpectation(
        name="deadlock_blackout",
        factory="build_infeasible_deadlock_scenario(deadlock_type='blackout')",
        category="deadlock",
        request_ids=("REQ_B1",),
        expected_status="INFEASIBLE",
        expected_codes=("BLACKOUT",),
        description="Blackout covers 02:00-04:30 on S01; mandatory 70m request cannot fit in 45m before blackout or 0m after. Infeasible instance.",
    ),
    ScenarioExpectation(
        name="compound_nexus",
        factory="build_compound_conflict_scenario(case_type='nexus')",
        category="compound",
        request_ids=("R01", "R03"),
        expected_status="CONFLICT",
        expected_codes=("DEPENDENCY", "POWER", "TRANSFER_TIME"),
        description="Predecessor finishes 02:40 with 15m handover (02:55), 10m power guard (02:50), and specialist travel from S05 ending 02:30 with 25m travel (02:55). Composite earliest start max(02:55, 02:50, 02:55) = 02:55.",
    ),
    ScenarioExpectation(
        name="compound_vehicle_corridor",
        factory="build_compound_conflict_scenario(case_type='vehicle_corridor')",
        category="compound",
        request_ids=("R11",),
        expected_status="CONFLICT",
        expected_codes=("VEHICLE_TRANSIT",),
        description="Probe allocation assigns V01 to S01 (01:30-02:00) overlapping vehicle V01 transit reservation (01:15-01:45). Expected code VEHICLE_TRANSIT.",
    ),
    ScenarioExpectation(
        name="fastpath_empty",
        factory="build_trivial_fastpath_scenario(case_type='empty')",
        category="fastpath",
        request_ids=(),
        expected_status="EMPTY",
        expected_codes=(),
        description="No active submitted work packages in queue. Trivial fastpath empty classification.",
    ),
    ScenarioExpectation(
        name="fastpath_orthogonal",
        factory="build_trivial_fastpath_scenario(case_type='orthogonal')",
        category="fastpath",
        request_ids=("REQ_ORTHO_1", "REQ_ORTHO_2", "REQ_ORTHO_3"),
        expected_status="FEASIBLE",
        expected_codes=(),
        description="Three independent requests on disjoint power zones Z01, Z02, Z03 with non-overlapping resources. Trivial fastpath orthogonal set.",
    ),
    ScenarioExpectation(
        name="fastpath_domain_impossible",
        factory="build_trivial_fastpath_scenario(case_type='domain_impossible')",
        category="fastpath",
        request_ids=("REQ_IMPOSSIBLE",),
        expected_status="INFEASIBLE",
        expected_codes=("DURATION", "ENGINEERING_WINDOW"),
        description="ANY_TIME request duration of 240m exceeds entire usable window duration of 190m. Statically impossible domain.",
    ),
    ScenarioExpectation(
        name="fastpath_missing_skill",
        factory="build_trivial_fastpath_scenario(case_type='missing_skill')",
        category="fastpath",
        request_ids=("REQ_NO_SKILL",),
        expected_status="INFEASIBLE",
        expected_codes=("QUALIFICATION",),
        description="Mandatory request demands skill not possessed by any engineer in roster. Missing-skill fast failure.",
    ),
    ScenarioExpectation(
        name="lexicographic_stability",
        factory="build_lexicographic_tradeoff_scenario(case_type='stability')",
        category="lexicographic",
        request_ids=("R02", "REQ_OPT_URGENT"),
        expected_status="TRADE_OFF",
        expected_codes=("LOCKED_BOOKING",),
        description="Urgency-5 optional request competes with approved non-frozen booking at 02:00. Prioritizes schedule stability over new optional work.",
    ),
    ScenarioExpectation(
        name="lexicographic_load",
        factory="build_lexicographic_tradeoff_scenario(case_type='load')",
        category="lexicographic",
        request_ids=tuple(f"REQ_LOAD_{i}" for i in range(1, 9)),
        expected_status="TRADE_OFF",
        expected_codes=("MANPOWER",),
        description="Eight requests compete for TECH:5 capacity. Low-urgency deferrable work identified as load-shedding candidate.",
    ),
    ScenarioExpectation(
        name="lexicographic_handback",
        factory="build_lexicographic_tradeoff_scenario(case_type='handback')",
        category="lexicographic",
        request_ids=("REQ_HB_1", "REQ_HB_2"),
        expected_status="TRADE_OFF",
        expected_codes=(),
        description="Multiple ANY_TIME requests with multiple valid orderings. Minimizing latest completion time (handback clearance) is comparison metric.",
    ),
)


# Factory dispatcher map for easy lookup
FACTORY_REGISTRY: dict[str, Callable[[], PlanningSnapshot]] = {
    "build_comprehensive_snapshot": build_comprehensive_snapshot,
    "build_feasible_snapshot": build_feasible_snapshot,
    "build_infeasible_deadlock_scenario(deadlock_type='frozen')": lambda: build_infeasible_deadlock_scenario("frozen"),
    "build_infeasible_deadlock_scenario(deadlock_type='manpower')": lambda: build_infeasible_deadlock_scenario("manpower"),
    "build_infeasible_deadlock_scenario(deadlock_type='blackout')": lambda: build_infeasible_deadlock_scenario("blackout"),
    "build_infeasible_deadlock_scenario(frozen)": lambda: build_infeasible_deadlock_scenario("frozen"),
    "build_infeasible_deadlock_scenario(manpower)": lambda: build_infeasible_deadlock_scenario("manpower"),
    "build_infeasible_deadlock_scenario(blackout)": lambda: build_infeasible_deadlock_scenario("blackout"),
    "build_infeasible_deadlock_scenario": build_infeasible_deadlock_scenario,
    "build_compound_conflict_scenario(case_type='nexus')": lambda: build_compound_conflict_scenario("nexus"),
    "build_compound_conflict_scenario(case_type='vehicle_corridor')": lambda: build_compound_conflict_scenario("vehicle_corridor"),
    "build_compound_conflict_scenario(nexus)": lambda: build_compound_conflict_scenario("nexus"),
    "build_compound_conflict_scenario(vehicle_corridor)": lambda: build_compound_conflict_scenario("vehicle_corridor"),
    "build_compound_conflict_scenario": build_compound_conflict_scenario,
    "build_trivial_fastpath_scenario(case_type='empty')": lambda: build_trivial_fastpath_scenario("empty"),
    "build_trivial_fastpath_scenario(case_type='orthogonal')": lambda: build_trivial_fastpath_scenario("orthogonal"),
    "build_trivial_fastpath_scenario(case_type='domain_impossible')": lambda: build_trivial_fastpath_scenario("domain_impossible"),
    "build_trivial_fastpath_scenario(case_type='missing_skill')": lambda: build_trivial_fastpath_scenario("missing_skill"),
    "build_trivial_fastpath_scenario(empty)": lambda: build_trivial_fastpath_scenario("empty"),
    "build_trivial_fastpath_scenario(orthogonal)": lambda: build_trivial_fastpath_scenario("orthogonal"),
    "build_trivial_fastpath_scenario(domain_impossible)": lambda: build_trivial_fastpath_scenario("domain_impossible"),
    "build_trivial_fastpath_scenario(missing_skill)": lambda: build_trivial_fastpath_scenario("missing_skill"),
    "build_trivial_fastpath_scenario": build_trivial_fastpath_scenario,
    "build_lexicographic_tradeoff_scenario(case_type='stability')": lambda: build_lexicographic_tradeoff_scenario("stability"),
    "build_lexicographic_tradeoff_scenario(case_type='load')": lambda: build_lexicographic_tradeoff_scenario("load"),
    "build_lexicographic_tradeoff_scenario(case_type='handback')": lambda: build_lexicographic_tradeoff_scenario("handback"),
    "build_lexicographic_tradeoff_scenario(stability)": lambda: build_lexicographic_tradeoff_scenario("stability"),
    "build_lexicographic_tradeoff_scenario(load)": lambda: build_lexicographic_tradeoff_scenario("load"),
    "build_lexicographic_tradeoff_scenario(handback)": lambda: build_lexicographic_tradeoff_scenario("handback"),
    "build_lexicographic_tradeoff_scenario": build_lexicographic_tradeoff_scenario,
}


def resolve_factory(factory_repr: str) -> PlanningSnapshot:
    """Resolve a factory description or callable name to a PlanningSnapshot instance."""
    clean = factory_repr.strip()
    if clean in FACTORY_REGISTRY:
        return FACTORY_REGISTRY[clean]()

    # Fallback to local scope function if name matches
    func = globals().get(clean)
    if callable(func):
        return func()

    raise ValueError(f"Unknown scenario factory representation: '{factory_repr}'")


def export_comprehensive_dataset(output_path: Path | None = None) -> Path:
    """Export the comprehensive snapshot as formatted JSON."""
    if output_path is None:
        target = PROJECT_ROOT / "data" / "comprehensive_synthetic_data.json"
    else:
        target = Path(output_path)

    snapshot = build_comprehensive_snapshot()
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False) + "\n"
    target.write_text(serialized, encoding="utf-8")
    return target


def validate_all_scenarios() -> None:
    """Validate every factory and its serialization round trip."""
    factories_to_test: list[Callable[[], PlanningSnapshot]] = [
        build_comprehensive_snapshot,
        build_feasible_snapshot,
        lambda: build_infeasible_deadlock_scenario("frozen"),
        lambda: build_infeasible_deadlock_scenario("manpower"),
        lambda: build_infeasible_deadlock_scenario("blackout"),
        lambda: build_compound_conflict_scenario("nexus"),
        lambda: build_compound_conflict_scenario("vehicle_corridor"),
        lambda: build_trivial_fastpath_scenario("empty"),
        lambda: build_trivial_fastpath_scenario("orthogonal"),
        lambda: build_trivial_fastpath_scenario("domain_impossible"),
        lambda: build_trivial_fastpath_scenario("missing_skill"),
        lambda: build_lexicographic_tradeoff_scenario("stability"),
        lambda: build_lexicographic_tradeoff_scenario("load"),
        lambda: build_lexicographic_tradeoff_scenario("handback"),
    ]

    for factory in factories_to_test:
        snapshot = factory()
        if not isinstance(snapshot, PlanningSnapshot):
            raise TypeError(f"Factory {factory} returned {type(snapshot).__name__}, expected PlanningSnapshot")

        # Round-trip dictionary validation
        dumped = snapshot.to_dict()
        reimported = PlanningSnapshot.from_dict(dumped)
        re_dumped = reimported.to_dict()
        if dumped != re_dumped:
            raise ValueError(f"Serialization round-trip mismatch for factory {factory}")

        # Round-trip JSON validation
        json_str = snapshot.model_dump_json()
        reimported_json = PlanningSnapshot.from_json(json_str)
        if reimported_json.to_dict() != dumped:
            raise ValueError(f"JSON round-trip mismatch for factory {factory}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone Synthetic Dataset Generator for LTA NebulaX railway maintenance scheduling."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Path to output JSON file (default: data/comprehensive_synthetic_data.json)",
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Validate every scenario factory and round-trip serialization",
    )
    parser.add_argument(
        "--list-scenarios",
        "-l",
        action="store_true",
        help="List all registered scenarios and expectations",
    )
    args = parser.parse_args()

    if args.list_scenarios:
        print(f"Registered Scenarios ({len(SCENARIO_EXPECTATIONS)} total):")
        for i, exp in enumerate(SCENARIO_EXPECTATIONS, 1):
            codes_str = ", ".join(exp.expected_codes) if exp.expected_codes else "None"
            print(f"{i:2d}. [{exp.category}] {exp.name}")
            print(f"    Factory: {exp.factory}")
            print(f"    Requests: {', '.join(exp.request_ids) if exp.request_ids else 'None'}")
            print(f"    Expected Status: {exp.expected_status} | Codes: {codes_str}")
            print(f"    Description: {exp.description}")
        return

    if args.validate:
        print("Validating all scenario factories and serialization round trips...")
        validate_all_scenarios()
        print("All scenarios successfully validated!")
        return

    # Default export
    out = export_comprehensive_dataset(args.output)
    print(f"Comprehensive synthetic dataset exported to: {out}")


if __name__ == "__main__":
    main()
