"""Solver-backed schedule source querying the active SQLite repository."""
from __future__ import annotations

from backend.app.database import Database
from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    ScenarioResultRow,
)
from backend.app.network_schedule.base import NetworkScheduleSource, ScenarioAvailability


class SolverRunScheduleSource(NetworkScheduleSource):
    """Queries persistent solver_runs and child tables once solver execution is complete."""

    def __init__(self, database: Database, revision_id: str | None = None) -> None:
        self.database = database
        self.revision_id = revision_id

    def _latest_run_id(self, connection, scenario: str) -> str | None:
        query = (
            "SELECT id FROM solver_runs WHERE scenario=? "
            "AND status IN ('SUCCESS','SUCCEEDED')"
        )
        parameters: list[str] = [scenario]
        if self.revision_id:
            query += " AND revision_id=?"
            parameters.append(self.revision_id)
        query += " ORDER BY created_at DESC,id DESC LIMIT 1"
        row = connection.execute(query, parameters).fetchone()
        return row["id"] if row else None

    def get_available_scenarios(self) -> list[ScenarioAvailability]:
        query = "SELECT DISTINCT scenario FROM solver_runs WHERE status IN ('SUCCESS','SUCCEEDED')"
        parameters: list[str] = []
        if self.revision_id:
            query += " AND revision_id=?"
            parameters.append(self.revision_id)
        with self.database.connection() as connection:
            available = {row["scenario"] for row in connection.execute(query, parameters)}
            return [
                ScenarioAvailability(
                    scenario=sc,
                    available=sc in available,
                    source="solver" if sc in available else None,
                )
                for sc in ["A", "B", "C"]
            ]

    def get_accesses(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[AccessScheduleRow]:
        with self.database.connection() as connection:
            run_id = self._latest_run_id(connection, scenario)
            if not run_id:
                return []
            query = "SELECT activity_id,access_seq,week,eclo,access_night FROM run_accesses WHERE run_id=?"
            parameters: list[str | int] = [run_id]
            if week is not None:
                query += " AND week=?"
                parameters.append(week)
            if activity_id is not None:
                query += " AND activity_id=?"
                parameters.append(activity_id)
            query += " ORDER BY week,activity_id,access_seq"
            return [AccessScheduleRow.model_validate(dict(row)) for row in connection.execute(query, parameters)]

    def get_occupancies(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[OccupancyScheduleRow]:
        with self.database.connection() as connection:
            run_id = self._latest_run_id(connection, scenario)
            if not run_id:
                return []
            query = "SELECT activity_id,week,location_id,co_share_group FROM run_occupancies WHERE run_id=?"
            parameters: list[str | int] = [run_id]
            if week is not None:
                query += " AND week=?"
                parameters.append(week)
            if activity_id is not None:
                query += " AND activity_id=?"
                parameters.append(activity_id)
            query += " ORDER BY week,location_id,activity_id"
            return [OccupancyScheduleRow.model_validate(dict(row)) for row in connection.execute(query, parameters)]

    def get_results(self, scenario: str) -> list[ScenarioResultRow]:
        with self.database.connection() as connection:
            run_id = self._latest_run_id(connection, scenario)
            if not run_id:
                return []
            rows = connection.execute(
                """SELECT scenario,contract_number,simulated_completion_date,overrun_days
                   FROM run_contract_results WHERE run_id=? AND scenario=?
                   ORDER BY contract_number""",
                (run_id, scenario),
            )
            return [ScenarioResultRow.model_validate(dict(row)) for row in rows]
