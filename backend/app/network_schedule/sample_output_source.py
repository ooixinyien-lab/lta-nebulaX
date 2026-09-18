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
    """Parses and caches sample_outputs/*.csv as a mock schedule source."""

    def __init__(self, sample_dir: Path | str | None = None) -> None:
        self.sample_dir = Path(sample_dir or (ROOT / "sample_outputs"))
        self._accesses: list[AccessScheduleRow] = []
        self._occupancies: list[OccupancyScheduleRow] = []
        self._results: list[ScenarioResultRow] = []
        self._available_scenarios: set[str] = set()
        self._loaded = False
        self._load()

    def _load(self) -> None:
        if self._loaded:
            return

        access_file = self.sample_dir / "SCHEDULE_ACCESS.csv"
        occupancy_file = self.sample_dir / "SCHEDULE_OCCUPANCY.csv"
        results_file = self.sample_dir / "RESULTS.csv"

        if access_file.is_file():
            with open(access_file, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._accesses.append(
                        AccessScheduleRow(
                            activity_id=row["activity_id"].strip(),
                            access_seq=int(row["access_seq"]),
                            week=int(row["week"]),
                            eclo=row["eclo"],
                            access_night=int(row["access_night"]),
                        )
                    )

        if occupancy_file.is_file():
            with open(occupancy_file, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._occupancies.append(
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
                    sc = row["scenario"].strip()
                    self._available_scenarios.add(sc)
                    self._results.append(
                        ScenarioResultRow(
                            scenario=sc,
                            contract_number=row["contract_number"].strip(),
                            simulated_completion_date=date.fromisoformat(row["simulated_completion_date"].strip()),
                            overrun_days=int(row["overrun_days"]),
                        )
                    )
        else:
            self._available_scenarios.add("A")

        self._loaded = True

    def get_available_scenarios(self) -> list[ScenarioAvailability]:
        all_scenarios = ["A", "B", "C"]
        return [
            ScenarioAvailability(
                scenario=sc,
                available=sc in self._available_scenarios,
                source="mock" if sc in self._available_scenarios else None,
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
        results = self._accesses
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
        results = self._occupancies
        if week is not None:
            results = [r for r in results if r.week == week]
        if activity_id is not None:
            results = [r for r in results if r.activity_id == activity_id]
        return list(results)

    def get_results(self, scenario: str) -> list[ScenarioResultRow]:
        return [r for r in self._results if r.scenario == scenario]
