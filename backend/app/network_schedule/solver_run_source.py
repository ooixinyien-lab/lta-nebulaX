"""Future solver-backed schedule source querying SQLite/PostgreSQL solver_runs."""
from __future__ import annotations

from typing import Any
from backend.app.database import select, C  # local SQLite-backed shim

from backend.app.db.models import RunAccess, RunContractResult, RunOccupancy, SolverRun
from backend.app.domain_models import (
    AccessScheduleRow,
    OccupancyScheduleRow,
    ScenarioResultRow,
)
from backend.app.network_schedule.base import NetworkScheduleSource, ScenarioAvailability


class SolverRunScheduleSource(NetworkScheduleSource):
    """Queries persistent solver_runs and child tables once solver execution is complete."""

    def __init__(self, session_factory: Any, revision_id: str | None = None) -> None:
        self.session_factory = session_factory
        self.revision_id = revision_id

    def get_available_scenarios(self) -> list[ScenarioAvailability]:
        with self.session_factory.session() as session:
            stmt = select(SolverRun).where(C(SolverRun).status == "SUCCESS")
            if self.revision_id:
                stmt = stmt.where(C(SolverRun).revision_id == self.revision_id)
            runs = session.scalars(stmt).all()
            available = {r.scenario for r in runs}
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
        with self.session_factory.session() as session:
            run_stmt = select(SolverRun).where(
                C(SolverRun).scenario == scenario,
                C(SolverRun).status == "SUCCESS",
            ).order_by(C(SolverRun).created_at.desc())
            if self.revision_id:
                run_stmt = run_stmt.where(C(SolverRun).revision_id == self.revision_id)
            run = session.scalar(run_stmt.limit(1))
            if not run:
                return []
            run_id = run.id

            stmt = select(RunAccess).where(C(RunAccess).run_id == run_id)
            if week is not None:
                stmt = stmt.where(C(RunAccess).week == week)
            if activity_id is not None:
                stmt = stmt.where(C(RunAccess).activity_id == activity_id)
            rows = session.scalars(stmt).all()
            return [
                AccessScheduleRow(
                    activity_id=r.activity_id,
                    access_seq=r.access_seq,
                    week=r.week,
                    eclo=r.eclo,
                    access_night=r.access_night,
                )
                for r in rows
            ]

    def get_occupancies(
        self,
        scenario: str,
        week: int | None = None,
        activity_id: str | None = None,
    ) -> list[OccupancyScheduleRow]:
        with self.session_factory.session() as session:
            run_stmt = select(SolverRun).where(
                C(SolverRun).scenario == scenario,
                C(SolverRun).status == "SUCCESS",
            ).order_by(C(SolverRun).created_at.desc())
            if self.revision_id:
                run_stmt = run_stmt.where(C(SolverRun).revision_id == self.revision_id)
            run = session.scalar(run_stmt.limit(1))
            if not run:
                return []
            run_id = run.id

            stmt = select(RunOccupancy).where(C(RunOccupancy).run_id == run_id)
            if week is not None:
                stmt = stmt.where(C(RunOccupancy).week == week)
            if activity_id is not None:
                stmt = stmt.where(C(RunOccupancy).activity_id == activity_id)
            rows = session.scalars(stmt).all()
            return [
                OccupancyScheduleRow(
                    activity_id=r.activity_id,
                    week=r.week,
                    location_id=r.location_id,
                    co_share_group=r.co_share_group,
                )
                for r in rows
            ]

    def get_results(self, scenario: str) -> list[ScenarioResultRow]:
        with self.session_factory.session() as session:
            run_stmt = select(SolverRun).where(
                C(SolverRun).scenario == scenario,
                C(SolverRun).status == "SUCCESS",
            ).order_by(C(SolverRun).created_at.desc())
            if self.revision_id:
                run_stmt = run_stmt.where(C(SolverRun).revision_id == self.revision_id)
            run = session.scalar(run_stmt.limit(1))
            if not run:
                return []
            run_id = run.id

            stmt = select(RunContractResult).where(
                C(RunContractResult).run_id == run_id,
                C(RunContractResult).scenario == scenario,
            )
            rows = session.scalars(stmt).all()
            return [
                ScenarioResultRow(
                    scenario=r.scenario,
                    contract_number=r.contract_number,
                    simulated_completion_date=r.simulated_completion_date,
                    overrun_days=r.overrun_days,
                )
                for r in rows
            ]
