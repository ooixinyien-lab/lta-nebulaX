"""NEBULA X Enterprise Architecture Demo.

Validates MaintenanceRequests against a PlanningSnapshot state using Pydantic domain models.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from checker import conflict_checker
from models import (
    Allocation,
    EngineeringWindow,
    Equipment,
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
    TimingMode,
)

SGT = ZoneInfo("Asia/Singapore")


def build_base_snapshot(planning_date_str: str, base_time: datetime) -> PlanningSnapshot:
    """Constructs a minimal, valid PlanningSnapshot topology."""
    # 1. Stations
    stn_a = Station(id="STN_A", name="Jurong East", schematic_x=0.0)
    stn_b = Station(id="STN_B", name="Clementi", schematic_x=5.0)
    stn_c = Station(id="STN_C", name="Buona Vista", schematic_x=10.0)

    # 2. Power Zones & Sectors
    pz1 = PowerZone(id="PZ_01", sector_ids=["SEC_AB", "SEC_BC"])

    sec_ab = Sector(
        id="SEC_AB",
        from_station="STN_A",
        to_station="STN_B",
        direction="INBOUND",
        power_zone="PZ_01",
    )
    sec_bc = Sector(
        id="SEC_BC",
        from_station="STN_B",
        to_station="STN_C",
        direction="INBOUND",
        power_zone="PZ_01",
    )

    # 3. Engineering Window (01:00 AM to 04:30 AM = 210 mins, 20-min handback buffer)
    window_end = base_time + timedelta(minutes=210)
    eng_win = EngineeringWindow(
        date=planning_date_str,
        sector_ids=["SEC_AB", "SEC_BC"],
        start=base_time,
        end=window_end,
        handback_buffer_minutes=20,
    )

    # 4. Inventory & Equipment
    # Pass availability when creating equipment
    eq_grinder = Equipment(
        id="GRINDER_01", 
        type="RAIL_GRINDER", 
        initial_sector="SEC_AB",
        availability=[]
    )
    eq_tamping = Equipment(
        id="TAMPING_01", 
        type="TAMPING_MACHINE", 
        initial_sector="SEC_BC",
        availability=[]
    )
    pool_tech = ResourcePool(id="TECH", name="Technician Pool", capacity=5)

    # 5. Metadata & Planning Rules
    metadata = SnapshotMetadata(
        schema_version="2.0.0",
        planning_version=1,
        timezone="Asia/Singapore",
        planning_date=planning_date_str,
        synthetic=True,
        description="NEBULA X Test Topology",
        disclaimer="Internal Testing Only",
        scope="East-West Line",
        simplifications=["Fixed power grid"],
    )

    rules = PlanningRules(
        morning_buffer_minutes=20,
        power_values=[PowerRequirement.ON, PowerRequirement.OFF, PowerRequirement.NONE],
        power_compatibility={
            PowerRequirement.ON: {PowerRequirement.ON: True, PowerRequirement.OFF: False, PowerRequirement.NONE: True},
            PowerRequirement.OFF: {PowerRequirement.ON: False, PowerRequirement.OFF: True, PowerRequirement.NONE: True},
            PowerRequirement.NONE: {PowerRequirement.ON: True, PowerRequirement.OFF: True, PowerRequirement.NONE: True},
        },
    )

    return PlanningSnapshot(
        metadata=metadata,
        stations=[stn_a, stn_b, stn_c],
        power_zones=[pz1],
        sectors=[sec_ab, sec_bc],
        engineering_windows=[eng_win],
        planning_rules=rules,
        engineers=[],
        equipment=[eq_grinder, eq_tamping],
        resource_pools=[pool_tech],
        requests=[],
        committed_allocations=[],
    )


def create_standard_phases(work_duration_mins: int) -> list[Phase]:
    """Helper to generate standard 4-phase work packages."""
    return [
        Phase(name=PhaseType.setup, duration_minutes=10),
        Phase(name=PhaseType.work, duration_minutes=work_duration_mins),
        Phase(name=PhaseType.test, duration_minutes=10),
        Phase(name=PhaseType.handback, duration_minutes=10),
    ]


def main():
    print("==================================================")
    print("      NEBULA X ENTERPRISE SCHEDULER DEMO          ")
    print("==================================================\n")

    # Base Time: Tonight at 01:00 AM SGT
    planning_date_str = "2026-09-15"
    base_time = datetime(2026, 9, 15, 1, 0, tzinfo=SGT)

    # 1. Initialize Snapshot
    snapshot = build_base_snapshot(planning_date_str, base_time)

    # -------------------------------------------------------------
    # REQUEST 1: Rail Grinding on SEC_AB (Scheduled 01:00 AM - 02:00 AM / 60 mins)
    # -------------------------------------------------------------
    req1 = MaintenanceRequest(
        id="REQ-001",
        title="Rail Grinding Section A",
        status=RequestStatus.scheduled,
        owner_id="DEPT_TRACK",
        work_sector="SEC_AB",
        protected_sectors=["SEC_AB"],
        power_requirement=PowerRequirement.OFF,
        phases=create_standard_phases(30),  # Total package = 10+30+10+10 = 60 mins
        timing_mode=TimingMode.RANGE,
        earliest_start=base_time,
        deadline=base_time + timedelta(minutes=180),
        allowed_dates=[planning_date_str],
        required_skill="TRACK_MAINTENANCE",
        required_equipment_ids=["GRINDER_01"],
        approved=True,
        existing_start=base_time,
    )

    alloc1 = Allocation(
        request_id=req1.id,
        start=base_time,
        end=base_time + timedelta(minutes=60),
        equipment_ids=["GRINDER_01"],
    )

    # -------------------------------------------------------------
    # REQUEST 2: Signal Inspection on SEC_BC (Scheduled 02:15 AM - 03:15 AM / 60 mins)
    # -------------------------------------------------------------
    req2_start = base_time + timedelta(minutes=75)
    req2 = MaintenanceRequest(
        id="REQ-002",
        title="Signal Equipment Inspection",
        status=RequestStatus.scheduled,
        owner_id="DEPT_SIGNALS",
        work_sector="SEC_BC",
        protected_sectors=["SEC_BC"],
        power_requirement=PowerRequirement.ON,
        phases=create_standard_phases(30),  # Total package = 60 mins
        timing_mode=TimingMode.RANGE,
        earliest_start=base_time,
        deadline=base_time + timedelta(minutes=180),
        allowed_dates=[planning_date_str],
        required_skill="SIGNAL_INSPECTION",
        depends_on=[req1.id],  # Depends on REQ-001
        approved=True,
        existing_start=req2_start,
    )

    alloc2 = Allocation(
        request_id=req2.id,
        start=req2_start,
        end=req2_start + timedelta(minutes=60),
    )

    # Populate baseline schedule into snapshot
    snapshot.requests.extend([req1, req2])
    snapshot.committed_allocations.extend([alloc1, alloc2])

    print("Baseline Schedule State:")
    for alloc in snapshot.committed_allocations:
        print(f" - [{alloc.request_id}] {alloc.start.strftime('%H:%M')} -> {alloc.end.strftime('%H:%M')}")
    print("-" * 50 + "\n")

    # -------------------------------------------------------------
    # TARGET REQUEST: Candidate submission that triggers multiple conflicts
    # Scheduled at 01:30 AM (Overlaps REQ-001 and REQ-002)
    # Violations:
    # 1. Spatial & Safety Footprint: Claims SEC_AB (occupied by REQ-001)
    # 2. Power: Requires Power ON while REQ-001 requires Power OFF on same zone
    # 3. Equipment: Tries to claim GRINDER_01 (in use by REQ-001)
    # 4. Dependency: Depends on REQ-002, but starts BEFORE REQ-002 finishes!
    # -------------------------------------------------------------
    target_start = base_time + timedelta(minutes=30)  # 01:30 AM
    target_req = MaintenanceRequest(
        id="REQ-003",
        title="Emergency Track Repair",
        status=RequestStatus.submitted,
        owner_id="DEPT_EMERGENCY",
        work_sector="SEC_AB",
        protected_sectors=["SEC_AB", "SEC_BC"],
        power_requirement=PowerRequirement.ON,
        phases=create_standard_phases(30),
        timing_mode=TimingMode.RANGE,
        earliest_start=target_start,
        deadline=base_time + timedelta(minutes=180),
        allowed_dates=[planning_date_str],
        required_skill="TRACK_REPAIR",
        required_equipment_ids=["GRINDER_01"],
        depends_on=[req2.id],  # Sequence conflict (REQ-002 ends at 03:15 AM)
    )

    print(f"[EVALUATING] Candidate Request: {target_req.id} ('{target_req.title}') at {target_start.strftime('%H:%M')}...")
    conflicts = conflict_checker(snapshot, target_req)

    if conflicts:
        print(f"\n[REJECTED] {len(conflicts)} Conflict(s) Detected:\n")
        for idx, conflict in enumerate(conflicts, start=1):
            print(f"   Conflict {idx}:")
            print(f"   - Code:        {conflict.code.value}")
            print(f"   - Severity:    {conflict.severity}")
            print(f"   - Request IDs: {conflict.request_ids}")
            print(f"   - Resource:    {conflict.resource}")
            print(f"   - Message:     {conflict.message}\n")
    else:
        print("\n[SUCCESS] Candidate Request passed all validation checks!")


if __name__ == "__main__":
    main()