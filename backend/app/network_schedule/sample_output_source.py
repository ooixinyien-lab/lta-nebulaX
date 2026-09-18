"""Schedule data source loading and caching solved solver output CSVs."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from backend.app.config import ROOT
from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    ScenarioResultRow,
)
from backend.app.network_schedule.base import NetworkScheduleSource, ScenarioAvailability


class SampleOutputScheduleSource(NetworkScheduleSource):
    """Parses and caches solved solver output CSVs from outputs/{A,B,C}/ or sample_outputs/."""

    def __init__(self, sample_dir: Path | str | None = None) -> None:
        if sample_dir is not None:
            self.base_dir = Path(sample_dir)
        elif (ROOT / "outputs").is_dir() and any((ROOT / "outputs" / sc).is_dir() for sc in ("A", "B", "C")):
            self.base_dir = ROOT / "outputs"
        else:
            self.base_dir = ROOT / "sample_outputs"

        self._accesses_by_scenario: dict[str, list[AccessScheduleRow]] = {}
        self._occupancies_by_scenario: dict[str, list[OccupancyScheduleRow]] = {}
        self._results_by_scenario: dict[str, list[ScenarioResultRow]] = {}
        self._available_scenarios: set[str] = set()
        self._source_type = "solved"
        self._loaded = False
        self._load()

    def _load(self) -> None:
        if self._loaded:
            return

        # 1. Try loading scenario subdirectories (outputs/A, outputs/B, outputs/C)
        has_subdirs = False
        for sc in ("A", "B", "C"):
            sc_dir = self.base_dir / sc
            if not sc_dir.is_dir():
                continue

            has_subdirs = True
            access_file = sc_dir / "SCHEDULE_ACCESS.csv"
            occupancy_file = sc_dir / "SCHEDULE_OCCUPANCY.csv"
            results_file = sc_dir / "RESULTS.csv"

            acc_list: list[AccessScheduleRow] = []
            if access_file.is_file():
                with open(access_file, mode="r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        acc_list.append(
                            AccessScheduleRow(
                                activity_id=row["activity_id"].strip(),
                                access_seq=int(row["access_seq"]),
                                week=int(row["week"]),
                                eclo=row["eclo"],
                                access_night=int(row["access_night"]),
                            )
                        )
            self._accesses_by_scenario[sc] = acc_list

            occ_list: list[OccupancyScheduleRow] = []
            if occupancy_file.is_file():
                with open(occupancy_file, mode="r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        occ_list.append(
                            OccupancyScheduleRow(
                                activity_id=row["activity_id"].strip(),
                                week=int(row["week"]),
                                location_id=row["location_id"].strip(),
                                co_share_group=row["co_share_group"].strip(),
                            )
                        )
            self._occupancies_by_scenario[sc] = occ_list

            res_list: list[ScenarioResultRow] = []
            if results_file.is_file():
                with open(results_file, mode="r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        sc_row = row["scenario"].strip()
                        res_list.append(
                            ScenarioResultRow(
                                scenario=sc_row,
                                contract_number=row["contract_number"].strip(),
                                simulated_completion_date=date.fromisoformat(row["simulated_completion_date"].strip()),
                                overrun_days=int(row["overrun_days"]),
                            )
                        )
            self._results_by_scenario[sc] = res_list

            if acc_list or occ_list or res_list:
                self._available_scenarios.add(sc)

        # 2. Fallback: flat CSV directory (sample_outputs/)
        if not has_subdirs:
            self._source_type = "mock"
            access_file = self.base_dir / "SCHEDULE_ACCESS.csv"
            occupancy_file = self.base_dir / "SCHEDULE_OCCUPANCY.csv"
            results_file = self.base_dir / "RESULTS.csv"

            acc_list = []
            if access_file.is_file():
                with open(access_file, mode="r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        acc_list.append(
                            AccessScheduleRow(
                                activity_id=row["activity_id"].strip(),
                                access_seq=int(row["access_seq"]),
                                week=int(row["week"]),
                                eclo=row["eclo"],
                                access_night=int(row["access_night"]),
                            )
                        )

            occ_list = []
            if occupancy_file.is_file():
                with open(occupancy_file, mode="r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        occ_list.append(
                            OccupancyScheduleRow(
                                activity_id=row["activity_id"].strip(),
                                week=int(row["week"]),
                                location_id=row["location_id"].strip(),
                                co_share_group=row["co_share_group"].strip(),
                            )
                        )

            res_list = []
            if results_file.is_file():
                with open(results_file, mode="r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        sc = row["scenario"].strip()
                        self._available_scenarios.add(sc)
                        res_list.append(
                            ScenarioResultRow(
                                scenario=sc,
                                contract_number=row["contract_number"].strip(),
                                simulated_completion_date=date.fromisoformat(row["simulated_completion_date"].strip()),
                                overrun_days=int(row["overrun_days"]),
                            )
                        )
            else:
                self._available_scenarios.add("A")

            # Assign to scenario A
            self._accesses_by_scenario["A"] = acc_list
            self._occupancies_by_scenario["A"] = occ_list
            self._results_by_scenario["A"] = res_list

        self._loaded = True

    def get_available_scenarios(self) -> list[ScenarioAvailability]:
        all_scenarios = ["A", "B", "C"]
        return [
            ScenarioAvailability(
                scenario=sc,
                available=sc in self._available_scenarios,
                source=self._source_type if sc in self._available_scenarios else None,
            )
            for sc in all_scenarios
        ]

    def get_accesses(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[AccessScheduleRow]:
        if scenario not in self._available_scenarios:
            return []
        results = self._accesses_by_scenario.get(scenario, [])
        if week is not None:
            results = [r for r in results if r.week == week]
        if activity_id is not None:
            results = [r for r in results if r.activity_id == activity_id]
        return list(results)

    def get_occupancies(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[OccupancyScheduleRow]:
        if scenario not in self._available_scenarios:
            return []
        results = self._occupancies_by_scenario.get(scenario, [])
        if week is not None:
            results = [r for r in results if r.week == week]
        if activity_id is not None:
            results = [r for r in results if r.activity_id == activity_id]
        return list(results)

    def get_results(self, scenario: str) -> list[ScenarioResultRow]:
        return list(self._results_by_scenario.get(scenario, []))
