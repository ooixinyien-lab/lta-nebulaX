"""Schedule data source abstractions for Network Map."""
from __future__ import annotations

import os
from typing import Any

from backend.app.network_schedule.base import NetworkScheduleSource, ScenarioAvailability
from backend.app.network_schedule.sample_output_source import SampleOutputScheduleSource
from backend.app.network_schedule.solver_run_source import SolverRunScheduleSource

_SAMPLE_SOURCE: SampleOutputScheduleSource | None = None


def get_schedule_source(session_factory: Any = None, revision_id: str | None = None) -> NetworkScheduleSource:
    """Returns the configured schedule source (sample mock output by default)."""
    global _SAMPLE_SOURCE
    source_type = os.environ.get("NETWORK_SCHEDULE_SOURCE", "sample").lower()
    if source_type in ("solver", "database") and session_factory is not None:
        return SolverRunScheduleSource(session_factory, revision_id=revision_id)
    if _SAMPLE_SOURCE is None:
        _SAMPLE_SOURCE = SampleOutputScheduleSource()
    return _SAMPLE_SOURCE


__all__ = [
    "NetworkScheduleSource",
    "ScenarioAvailability",
    "SampleOutputScheduleSource",
    "SolverRunScheduleSource",
    "get_schedule_source",
]
