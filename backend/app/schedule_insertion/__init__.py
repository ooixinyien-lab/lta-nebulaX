"""Operational schedule insertion and low-churn replanning.

This package is deliberately separate from :mod:`backend.app.ps1`.  It reuses
the official domain and topology as inputs, but its output is an operational
schedule with maintenance visits and exact Singapore service dates rather
than an official three-CSV submission bundle.
"""

from .config import ScheduleInsertionConfig
from .models import (
    BaselineBundle,
    EffectiveChange,
    ProjectAddition,
    ReplanRequest,
    ScheduleInsertionResult,
    ScheduleScenario,
)
from .validation import validate_operational_schedule


def solve_schedule_insertion(*args, **kwargs):
    """Lazy import so fixture generation and validation do not require OR-Tools."""

    from .solver import solve_schedule_insertion as _solve

    return _solve(*args, **kwargs)

__all__ = [
    "BaselineBundle",
    "EffectiveChange",
    "ProjectAddition",
    "ReplanRequest",
    "ScheduleInsertionConfig",
    "ScheduleInsertionResult",
    "ScheduleScenario",
    "solve_schedule_insertion",
    "validate_operational_schedule",
]
