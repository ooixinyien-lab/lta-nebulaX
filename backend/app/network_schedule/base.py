"""Abstract schedule source interface for the Network Map."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    PS1Base,
    ScenarioResultRow,
)


class ScenarioAvailability(PS1Base):
    """Availability status of a problem scenario in the current schedule source."""

    scenario: str
    available: bool
    source: str | None = None


class NetworkScheduleSource(ABC):
    """Abstract interface for querying solved accesses and occupancies."""

    @abstractmethod
    def get_available_scenarios(self) -> list[ScenarioAvailability]:
        """Return list of scenarios and whether schedule data exists for each."""
        ...

    @abstractmethod
    def get_accesses(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[AccessScheduleRow]:
        """Return scheduled access records matching optional week and activity filters."""
        ...

    @abstractmethod
    def get_occupancies(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[OccupancyScheduleRow]:
        """Return physical occupancy records matching optional week and activity filters."""
        ...

    @abstractmethod
    def get_results(self, scenario: str) -> list[ScenarioResultRow]:
        """Return scenario contract completion results."""
        ...
