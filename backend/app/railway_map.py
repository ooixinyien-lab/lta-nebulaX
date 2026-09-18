"""Railway Network Map projection service.

Combines SQLite PS1 instance data, NetworkScheduleSource (mock or solver),
and FootprintCache into rich presentation-ready models for the React Network Map.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import ROOT, Settings
from backend.app.db.models import (
    ActivityRow,
    ContractRow,
    Instance,
    InstanceRevision,
    LineRow,
    LocationRow,
    ParameterRow,
    SectorRow,
    StationRow,
)
from backend.app.domain_models import ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.network_schedule import NetworkScheduleSource, get_schedule_source
from backend.app.topology import FootprintCache, NetworkTopology


class NetworkMapService:
    """Provides projection queries for the interactive SVG railway network map."""

    def __init__(
        self,
        db_session_factory: Any,
        settings: Settings | None = None,
        schedule_source: NetworkScheduleSource | None = None,
    ) -> None:
        self.db_session_factory = db_session_factory
        self.settings = settings or Settings()
        self.schedule_source = schedule_source or get_schedule_source(db_session_factory)
        self._problem: ProblemInstance | None = None
        self._footprint_cache: FootprintCache | None = None

    def _get_problem_and_cache(self) -> tuple[ProblemInstance, FootprintCache]:
        if self._problem is None or self._footprint_cache is None:
            data_dir = Path(self.settings.official_data_path)
            if not data_dir.is_dir():
                data_dir = ROOT / "data"
            self._problem = load_problem_from_directory(data_dir)
            self._footprint_cache = FootprintCache(self._problem)
        return self._problem, self._footprint_cache

    def get_context(self) -> dict[str, Any]:
        """Bootstrap information for the Network Map client."""
        scenarios = self.schedule_source.get_available_scenarios()
        with self.db_session_factory.session() as session:
            rev = session.scalar(
                select(InstanceRevision)
                .order_by(InstanceRevision.created_at.desc(), InstanceRevision.revision_number.desc())
                .limit(1)
            )
            revision_id = rev.id if rev else "default-rev"
            revision_num = rev.revision_number if rev else 1

            horizon_start = "2027-01-04"
            horizon_weeks = 30
            if rev:
                params = session.scalars(
                    select(ParameterRow).where(ParameterRow.revision_id == rev.id)
                ).all()
                for p in params:
                    if p.key == "horizon_start":
                        horizon_start = p.value
                    elif p.key == "horizon_weeks":
                        horizon_weeks = int(p.value)

        source_type = "sample_outputs" if any(s.source == "mock" for s in scenarios if s.available) else "solver"
        return {
            "revision": {
                "id": revision_id,
                "number": revision_num,
            },
            "horizon": {
                "startDate": horizon_start,
                "weeks": horizon_weeks,
            },
            "scheduleSource": source_type,
            "scenarios": [
                {
                    "scenario": s.scenario,
                    "available": s.available,
                    "source": s.source,
                }
                for s in scenarios
            ],
        }

    def get_topology(self) -> dict[str, Any]:
        """Return logical network topology (lines, stations, sectors, locations)."""
        with self.db_session_factory.session() as session:
            rev = session.scalar(
                select(InstanceRevision)
                .order_by(InstanceRevision.created_at.desc(), InstanceRevision.revision_number.desc())
                .limit(1)
            )
            rid = rev.id if rev else None

            line_rows = session.scalars(
                select(LineRow).where(LineRow.revision_id == rid) if rid else select(LineRow)
            ).all()
            stn_rows = session.scalars(
                select(StationRow).where(StationRow.revision_id == rid).order_by(StationRow.seq) if rid else select(StationRow).order_by(StationRow.seq)
            ).all()
            sec_rows = session.scalars(
                select(SectorRow).where(SectorRow.revision_id == rid).order_by(SectorRow.seq) if rid else select(SectorRow).order_by(SectorRow.seq)
            ).all()
            loc_rows = session.scalars(
                select(LocationRow).where(LocationRow.revision_id == rid) if rid else select(LocationRow)
            ).all()

        return {
            "lines": [
                {"line_code": r.line_code, "line_name": r.line_name}
                for r in line_rows
            ],
            "stations": [
                {
                    "line_code": r.line_code,
                    "station_id": r.station_id,
                    "seq": r.seq,
                    "is_interchange": r.is_interchange,
                }
                for r in stn_rows
            ],
            "sectors": [
                {
                    "sector_id": r.sector_id,
                    "line_code": r.line_code,
                    "from_station_id": r.from_station_id,
                    "to_station_id": r.to_station_id,
                    "seq": r.seq,
                    "is_shared": r.is_shared,
                }
                for r in sec_rows
            ],
            "locations": [
                {
                    "location_id": r.location_id,
                    "location_kind": r.location_kind,
                    "line_code": r.line_code,
                    "bound": r.bound,
                    "supply_capacity": r.supply_capacity,
                }
                for r in loc_rows
            ],
        }

    def get_activities(self) -> list[dict[str, Any]]:
        """Return all activities together with static precomputed footprints."""
        problem, cache = self._get_problem_and_cache()
        results: list[dict[str, Any]] = []

        for act in problem.activities:
            contract = problem.contract(act.contract_number)
            prot = cache.get_protection_footprint(act.activity_id)
            core = prot.core

            results.append({
                "activityId": act.activity_id,
                "contractNumber": act.contract_number,
                "activityType": act.activity_type.value,
                "natureOfActivity": contract.nature_of_activity.value,
                "activityPriority": int(act.activity_priority),
                "contractPriority": int(contract.contract_priority),
                "startLocationId": act.start_location_id,
                "endLocationId": act.end_location_id,
                "plannedStartDate": act.planned_start_date.isoformat(),
                "totalAccesses": act.total_accesses,
                "lineCode": core.line_code,
                "bound": core.bound.value,
                "coreLocations": list(core.core_locations),
                "bufferLocations": list(prot.buffer_locations),
                "mirroredLocations": list(prot.mirrored_locations),
                "crossLineLocations": list(prot.cross_line_locations),
                "allProtectedLocations": list(prot.all_protected_locations),
            })

        return results

    def get_weekly_occupancy(
        self,
        scenario: str,
        week: int,
        activity_id: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate scheduled accesses, physical occupancy and protection for a week."""
        scenarios = self.schedule_source.get_available_scenarios()
        sc_info = next((s for s in scenarios if s.scenario == scenario), None)
        if sc_info is None or not sc_info.available:
            return {
                "scenario": scenario,
                "week": week,
                "available": False,
                "reason": f"No schedule output available for Scenario {scenario}",
                "activeActivities": [],
                "locationOccupancy": {},
                "protection": {
                    "bufferLocations": {},
                    "mirroredLocations": {},
                    "crossLineLocations": {},
                    "explanations": [],
                },
                "results": [],
            }

        problem, cache = self._get_problem_and_cache()
        contract_map = {c.contract_number: c for c in problem.contracts}
        activity_map = {a.activity_id: a for a in problem.activities}
        locations_supply = {loc.location_id: loc.supply_capacity for loc in problem.locations}

        # 1. Fetch scheduled accesses and occupancies for the week
        access_rows = self.schedule_source.get_accesses(scenario=scenario, week=week)
        occupancy_rows = self.schedule_source.get_occupancies(scenario=scenario, week=week)
        contract_results = self.schedule_source.get_results(scenario=scenario)

        # Build access night map: activity_id -> access_night
        act_night_map: dict[str, int] = {}
        for acc in access_rows:
            act_night_map[acc.activity_id] = acc.access_night

        scheduled_act_ids = {a.activity_id for a in access_rows}
        occupancy_act_ids = {o.activity_id for o in occupancy_rows}
        active_act_ids = sorted(scheduled_act_ids | occupancy_act_ids)

        if activity_id and activity_id in active_act_ids:
            # We preserve all active activities for context, but highlight activity_id
            pass

        # 2. Group core occupancy by location
        # location_id -> list of occupancy rows
        loc_occupancy_rows: dict[str, list[Any]] = {}
        for row in occupancy_rows:
            loc_occupancy_rows.setdefault(row.location_id, []).append(row)

        location_occupancy_dict: dict[str, dict[str, Any]] = {}

        for loc_id, rows in loc_occupancy_rows.items():
            loc_act_ids = sorted({r.activity_id for r in rows})
            supply_cap = locations_supply.get(loc_id, 2)

            # Group activities by co_share_group
            groups_dict: dict[str, list[str]] = {}
            for r in rows:
                groups_dict.setdefault(r.co_share_group, []).append(r.activity_id)

            co_share_groups_list: list[dict[str, Any]] = []
            night_to_groups: dict[int, set[str]] = {}

            for grp_name, g_acts in sorted(groups_dict.items()):
                unique_g_acts = sorted(set(g_acts))
                pm_count = 0
                pc_count = 0
                c_count = 0

                for aid in unique_g_acts:
                    act_obj = activity_map.get(aid)
                    c_num = act_obj.contract_number if act_obj else None
                    c_obj = contract_map.get(c_num) if c_num else None
                    access_type = c_obj.access_type.value if c_obj else "C"

                    if access_type == "PM":
                        pm_count += 1
                    elif access_type == "PC":
                        pc_count += 1
                    else:
                        c_count += 1

                    # track access night
                    night = act_night_map.get(aid, 1)
                    night_to_groups.setdefault(night, set()).add(grp_name)

                # Co-sharing legality invariant:
                # 1 PM alone OR 1 PC + <=3 C (total <=4) OR <=4 C
                is_compliant = (
                    (pm_count == 1 and pc_count == 0 and c_count == 0)
                    or (pm_count == 0 and pc_count <= 1 and (pc_count + c_count) <= 4)
                )

                co_share_groups_list.append({
                    "group": grp_name,
                    "activities": unique_g_acts,
                    "pmCount": pm_count,
                    "pcCount": pc_count,
                    "cCount": c_count,
                    "isCompliant": is_compliant,
                })

            occupied_group_count = len(co_share_groups_list)
            # peak occupied group count: max concurrent groups on any access night
            if night_to_groups:
                peak_occupied_group_count = max(len(grp_set) for grp_set in night_to_groups.values())
            else:
                peak_occupied_group_count = occupied_group_count

            capacity_exceeded = peak_occupied_group_count > supply_cap

            location_occupancy_dict[loc_id] = {
                "locationId": loc_id,
                "supplyCapacity": supply_cap,
                "activeActivities": loc_act_ids,
                "coShareGroups": co_share_groups_list,
                "occupiedGroupCount": occupied_group_count,
                "peakOccupiedGroupCount": peak_occupied_group_count,
                "capacityExceeded": capacity_exceeded,
            }

        # 3. Dynamic protection footprint aggregation for this week
        buffer_locs_map: dict[str, list[str]] = {}
        mirrored_locs_map: dict[str, list[str]] = {}
        cross_line_locs_map: dict[str, list[str]] = {}
        explanations: list[dict[str, Any]] = []

        for aid in active_act_ids:
            try:
                prot = cache.get_protection_footprint(aid)
            except KeyError:
                continue

            for bloc in prot.buffer_locations:
                buffer_locs_map.setdefault(bloc, []).append(aid)
                explanations.append({
                    "locationId": bloc,
                    "type": "buffer",
                    "activityId": aid,
                    "reason": f"Safety buffer protection for active work in {aid}",
                })

            for mloc in prot.mirrored_locations:
                mirrored_locs_map.setdefault(mloc, []).append(aid)
                explanations.append({
                    "locationId": mloc,
                    "type": "mirrored",
                    "activityId": aid,
                    "reason": f"Opposite-bound mirrored closure required for Live activity {aid}",
                })

            for cloc in prot.cross_line_locations:
                cross_line_locs_map.setdefault(cloc, []).append(aid)
                explanations.append({
                    "locationId": cloc,
                    "type": "cross_line",
                    "activityId": aid,
                    "reason": f"Live activity {aid} traverses the H01-H02 interchange zone",
                })

        return {
            "scenario": scenario,
            "week": week,
            "available": True,
            "activeActivities": active_act_ids,
            "locationOccupancy": location_occupancy_dict,
            "protection": {
                "bufferLocations": buffer_locs_map,
                "mirroredLocations": mirrored_locs_map,
                "crossLineLocations": cross_line_locs_map,
                "explanations": explanations,
            },
            "results": [
                {
                    "scenario": r.scenario,
                    "contractNumber": r.contract_number,
                    "simulatedCompletionDate": r.simulated_completion_date.isoformat(),
                    "overrunDays": r.overrun_days,
                }
                for r in contract_results
            ],
        }
