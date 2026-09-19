"""Strictly read-only tools for the schedule explanation assistant."""
from __future__ import annotations

from typing import Any
from backend.app.auth.resource_access import ChatScope
from backend.app.ps1.chat_models import EvidenceItem
from backend.app.ps1.explanations import ExplanationScheduleSource


ALLOWLISTED_TOOLS = {
    "get_run_summary",
    "get_activity",
    "get_activity_placement",
    "get_activity_diff",
    "get_activity_locations",
    "get_location_week_status",
    "get_score_components",
    "get_run_conflicts",
    "get_counterfactuals",
    "get_recurrence_context",
}

TOOL_DECLARATIONS = [
    {
        "name": "get_run_summary",
        "description": "Returns high-level status, scenario, and score for the current run.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_activity",
        "description": "Retrieves contract, priority, workload, and predecessor constraints for an activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "The activity identifier (e.g. A017)"},
            },
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_activity_placement",
        "description": "Retrieves the scheduled access weeks, nights, and ECLO flags for an activity in the current run.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "The activity identifier (e.g. A017)"},
            },
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_activity_diff",
        "description": "Compares an activity's current placement against the baseline run (displacement, ECLO changes).",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "The activity identifier (e.g. A017)"},
            },
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_activity_locations",
        "description": "Retrieves the track/station locations occupied by an activity during its accesses.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "The activity identifier (e.g. A017)"},
            },
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_location_week_status",
        "description": "Retrieves all activities occupying a specific railway location in a given week and their co-share groups.",
        "parameters": {
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "The location code (e.g. SEC:BET:S15_S16)"},
                "week": {"type": "integer", "description": "The calendar week number (1 to 30)"},
            },
            "required": ["location_id", "week"],
        },
    },
    {
        "name": "get_score_components",
        "description": "Retrieves the scenario score breakdown (weighted lateness, excess supply slots, ECLO count).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_run_conflicts",
        "description": "Retrieves recorded capacity or physical conflicts for the run or a specific activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "Optional activity ID filter"},
            },
            "required": [],
        },
    },
    {
        "name": "get_counterfactuals",
        "description": "Retrieves measured alternative placement evaluations for an activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "The activity identifier (e.g. A017)"},
            },
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_recurrence_context",
        "description": "Retrieves recurrence policy and boundary interval constraints.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "Optional activity ID filter"},
            },
            "required": [],
        },
    },
]


class ScheduleReadTools:
    """Read-only tools executing solely under an authenticated, verified ChatScope."""

    def __init__(self, source: ExplanationScheduleSource):
        self.source = source

    def execute_tool(
        self,
        scope: ChatScope,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], list[EvidenceItem]]:
        if tool_name not in ALLOWLISTED_TOOLS:
            raise PermissionError(f"Tool '{tool_name}' is not in the read-only allowlist")

        method = getattr(self, tool_name, None)
        if not callable(method):
            raise NotImplementedError(f"Tool '{tool_name}' is not implemented")

        return method(scope, **arguments)

    def get_run_summary(self, scope: ChatScope) -> tuple[dict[str, Any], list[EvidenceItem]]:
        score = self.source.get_score(scope.run_id)
        evidence = [
            EvidenceItem(
                evidence_id=f"run:{scope.run_id}",
                classification="solver_derived",
                entity_type="solver_run",
                entity_id=scope.run_id,
                run_id=scope.run_id,
                description=f"Run {scope.run_id} is on Scenario {scope.scenario}.",
            )
        ]
        return {
            "run_id": scope.run_id,
            "scenario": scope.scenario,
            "baseline_run_id": scope.baseline_run_id,
            "score": score,
            "data_source": self.source.data_source,
        }, evidence

    def get_activity(self, scope: ChatScope, activity_id: str) -> tuple[dict[str, Any], list[EvidenceItem]]:
        act = self.source.get_activity(activity_id)
        if act is None:
            return {"found": False, "activity_id": activity_id}, []

        evidence = [
            EvidenceItem(
                evidence_id=f"activity:{activity_id}",
                classification="stored_fact",
                entity_type="activity",
                entity_id=activity_id,
                run_id=scope.run_id,
                description=f"Activity {activity_id} under contract {act.contract_number} ({act.activity_type}).",
            )
        ]
        return act.model_dump(), evidence

    def get_activity_placement(self, scope: ChatScope, activity_id: str) -> tuple[dict[str, Any], list[EvidenceItem]]:
        placements = self.source.get_placements(scope.run_id, activity_id)
        evidence = [
            EvidenceItem(
                evidence_id=f"placement:{scope.run_id}:{activity_id}:{p.access_seq}",
                classification="solver_derived",
                entity_type="run_access",
                entity_id=activity_id,
                run_id=scope.run_id,
                description=f"Access {p.access_seq} in week {p.week} (night {p.access_night}, eclo={p.eclo}).",
            )
            for p in placements
        ]
        return {
            "activity_id": activity_id,
            "run_id": scope.run_id,
            "placements": [p.model_dump() for p in placements],
        }, evidence

    def get_activity_diff(self, scope: ChatScope, activity_id: str) -> tuple[dict[str, Any], list[EvidenceItem]]:
        if not scope.baseline_run_id:
            return {
                "available": False,
                "message": "No baseline run was provided for diff comparison.",
            }, []

        curr = self.source.get_placements(scope.run_id, activity_id)
        base = self.source.get_placements(scope.baseline_run_id, activity_id)

        curr_w = min([p.week for p in curr], default=None)
        base_w = min([p.week for p in base], default=None)
        disp = (curr_w - base_w) if (curr_w is not None and base_w is not None) else None

        evidence = []
        if disp is not None and disp != 0:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"diff:{scope.baseline_run_id}:{scope.run_id}:{activity_id}",
                    classification="solver_derived",
                    entity_type="run_diff",
                    entity_id=activity_id,
                    run_id=scope.run_id,
                    description=f"Activity {activity_id} displaced by {disp} week(s) from baseline.",
                )
            )

        return {
            "available": True,
            "activity_id": activity_id,
            "baseline_run_id": scope.baseline_run_id,
            "current_run_id": scope.run_id,
            "baseline_start_week": base_w,
            "current_start_week": curr_w,
            "week_displacement": disp,
        }, evidence

    def get_activity_locations(self, scope: ChatScope, activity_id: str) -> tuple[dict[str, Any], list[EvidenceItem]]:
        placements = self.source.get_placements(scope.run_id, activity_id)
        locs: set[str] = set()
        for p in placements:
            locs.update(p.locations)
        return {
            "activity_id": activity_id,
            "occupied_locations": sorted(locs),
        }, []

    def get_location_week_status(
        self,
        scope: ChatScope,
        location_id: str,
        week: int,
    ) -> tuple[dict[str, Any], list[EvidenceItem]]:
        occupancies = self.source.get_location_week_status(scope.run_id, location_id, week)
        evidence = [
            EvidenceItem(
                evidence_id=f"occupancy:{scope.run_id}:{location_id}:W{week}",
                classification="solver_derived",
                entity_type="run_occupancy",
                entity_id=location_id,
                run_id=scope.run_id,
                description=f"Location {location_id} in week {week} is occupied by {len(occupancies)} activities.",
            )
        ]
        return {
            "location_id": location_id,
            "week": week,
            "occupying_activities": occupancies,
        }, evidence

    def get_score_components(self, scope: ChatScope) -> tuple[dict[str, Any], list[EvidenceItem]]:
        score = self.source.get_score(scope.run_id)
        if not score:
            return {"score": None, "available": False, "message": "Score data unavailable."}, []
        components = score.get("components") or {}
        total = float(score.get("total_score", 0.0))
        p = float(score.get("penalty_p", components.get("weighted_lateness_P", 0.0)))
        v = int(score.get("excess_v", components.get("excess_supply_V", 0)))
        e = int(score.get("eclo_e", components.get("eclo_count_E", 0)))
        return {
            "score": score,
            "total_score": total,
            "lateness_penalty": p,
            "excess_possession_slots": v,
            "weekend_closures": e,
            "primary_driver": "activity completion lateness" if p > 0 else "none",
            "plain_english_summary": (
                f"The overall penalty score is {total:.1f}, caused by activity completion lateness "
                f"({p:.1f} penalty points). "
                f"Excess possession slots: {v}. Weekend closures: {e}."
            ),
        }, []

    def get_run_conflicts(
        self,
        scope: ChatScope,
        activity_id: str | None = None,
    ) -> tuple[dict[str, Any], list[EvidenceItem]]:
        conflicts = self.source.get_conflicts(scope.run_id, activity_id)
        evidence = [
            EvidenceItem(
                evidence_id=f"conflict:{c.get('conflict_id', 'cf')}",
                classification="solver_derived",
                entity_type="conflict",
                entity_id=activity_id or "run",
                run_id=scope.run_id,
                description=c.get("description", "Recorded conflict"),
            )
            for c in conflicts
        ]
        return {"conflicts": conflicts}, evidence

    def get_counterfactuals(self, scope: ChatScope, activity_id: str) -> tuple[dict[str, Any], list[EvidenceItem]]:
        cfs = self.source.get_counterfactuals(activity_id)
        evidence = [
            EvidenceItem(
                evidence_id=f"counterfactual:{cf.get('counterfactual_id', 'cf')}",
                classification="solver_derived",
                entity_type="counterfactual",
                entity_id=activity_id,
                run_id=scope.run_id,
                description=cf.get("description", "Evaluated proposal"),
            )
            for cf in cfs
        ]
        return {"counterfactuals": cfs}, evidence

    def get_recurrence_context(
        self,
        scope: ChatScope,
        activity_id: str | None = None,
    ) -> tuple[dict[str, Any], list[EvidenceItem]]:
        return {"available": False, "message": "Recurrence policies not configured for this run."}, []
