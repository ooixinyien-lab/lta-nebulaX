"""Schedule data source loading and caching sample solver output CSVs."""
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
    """Parses and caches outputs/{scenario}/*.csv and sample_outputs/*.csv."""

    def __init__(self, sample_dir: Path | str | None = None) -> None:
        self.sample_dir = Path(sample_dir) if sample_dir else None
        self._accesses: dict[str, list[AccessScheduleRow]] = {"A": [], "B": [], "C": []}
        self._occupancies: dict[str, list[OccupancyScheduleRow]] = {"A": [], "B": [], "C": []}
        self._results: dict[str, list[ScenarioResultRow]] = {"A": [], "B": [], "C": []}
        self._available_scenarios: set[str] = set()
        self._loaded = False
        self._load()

    def _find_dir_for_scenario(self, scenario: str) -> Path | None:
        """Find directory containing output CSVs for a scenario."""
        candidates = [
            ROOT / "outputs" / scenario,
            ROOT / "sample_outputs" / scenario,
        ]
        if self.sample_dir:
            candidates.insert(0, self.sample_dir / scenario)
            candidates.append(self.sample_dir)
        candidates.append(ROOT / "sample_outputs")

        for d in candidates:
            if (d / "SCHEDULE_ACCESS.csv").is_file():
                return d
        return None

    def _load(self) -> None:
        if self._loaded:
            return

        for sc in ["A", "B", "C"]:
            sc_dir = self._find_dir_for_scenario(sc)
            if sc_dir is None:
                continue

            access_file = sc_dir / "SCHEDULE_ACCESS.csv"
            occupancy_file = sc_dir / "SCHEDULE_OCCUPANCY.csv"
            results_file = sc_dir / "RESULTS.csv"

            if access_file.is_file():
                with open(access_file, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self._accesses[sc].append(
                            AccessScheduleRow(
                                activity_id=row["activity_id"].strip(),
                                access_seq=int(row["access_seq"]),
                                week=int(row["week"]),
                                eclo=row["eclo"],
                                access_night=int(row["access_night"]),
                            )
                        )
                self._available_scenarios.add(sc)

            if occupancy_file.is_file():
                with open(occupancy_file, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self._occupancies[sc].append(
                            OccupancyScheduleRow(
                                activity_id=row["activity_id"].strip(),
                                week=int(row["week"]),
                                location_id=row["location_id"].strip(),
                                co_share_group=row["co_share_group"].strip(),
                            )
                        )

            if results_file.is_file():
                with open(results_file, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        row_sc = row["scenario"].strip() if "scenario" in row else sc
                        self._results[sc].append(
                            ScenarioResultRow(
                                scenario=row_sc,
                                contract_number=row["contract_number"].strip(),
                                simulated_completion_date=date.fromisoformat(row["simulated_completion_date"].strip()),
                                overrun_days=int(row["overrun_days"]),
                            )
                        )

        self._loaded = True

    def get_available_scenarios(self) -> list[ScenarioAvailability]:
        all_scenarios = ["A", "B", "C"]
        return [
            ScenarioAvailability(
                scenario=sc,
                available=sc in self._available_scenarios,
                source="outputs" if sc in self._available_scenarios else None,
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
        results = self._accesses.get(scenario, [])
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
        results = self._occupancies.get(scenario, [])
        if week is not None:
            results = [r for r in results if r.week == week]
        if activity_id is not None:
            results = [r for r in results if r.activity_id == activity_id]
        return list(results)

    def get_results(self, scenario: str) -> list[ScenarioResultRow]:
        return list(self._results.get(scenario, []))
