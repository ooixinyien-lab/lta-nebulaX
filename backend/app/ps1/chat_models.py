"""Domain models and schemas for the PS1 Grounded Schedule Chatbot."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import Field
from backend.app.domain_models import PS1Base

EvidenceClassification = Literal["stored_fact", "solver_derived", "inference"]


class EvidenceItem(PS1Base):
    evidence_id: str
    classification: EvidenceClassification
    entity_type: str
    entity_id: str
    run_id: str | None = None
    description: str


class ChatScopeModel(PS1Base):
    instance_id: str
    instance_revision_id: str
    run_id: str
    baseline_run_id: str | None = None
    scenario: str
    data_source: Literal["solver", "mock"]


class ActivityMetadataModel(PS1Base):
    activity_id: str
    contract_number: str
    activity_type: str
    priority: int
    planned_start_date: str
    predecessor_activity_id: str | None = None
    required_accesses: int


class PlacementItem(PS1Base):
    access_seq: int
    week: int
    eclo: bool
    access_night: int
    locations: list[str] = Field(default_factory=list)
    co_share_group: str | None = None


class PlacementRecord(PS1Base):
    available: bool
    placements: list[PlacementItem] = Field(default_factory=list)


class DiffModel(PS1Base):
    changed: bool = False
    week_displacement: int | None = None
    date_displacement_days: int | None = None
    eclo_changed: bool = False
    summary: str | None = None


class FrozenStateModel(PS1Base):
    is_frozen: bool = False
    reason: str | None = None


class ScoreInfoModel(PS1Base):
    available: bool = False
    baseline: dict[str, Any] | None = None
    current: dict[str, Any] | None = None
    delta: dict[str, Any] | None = None


class ExplanationFactPack(PS1Base):
    fact_pack_id: str
    generated_at: str
    scope: ChatScopeModel
    activity: ActivityMetadataModel
    baseline: PlacementRecord
    current: PlacementRecord
    diff: DiffModel
    frozen_state: FrozenStateModel
    score: ScoreInfoModel
    binding_constraints: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    recurrence: dict[str, Any] = Field(default_factory=lambda: {"available": False})
    counterfactuals: list[dict[str, Any]] = Field(default_factory=list)
    availability: dict[str, bool] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    fallback_summary: str


class ProvenanceModel(PS1Base):
    provider: str
    model: str
    prompt_template_version: str
    instance_revision_id: str
    run_id: str
    baseline_run_id: str | None = None


class ChatRequest(PS1Base):
    session_id: str | None = None
    instance_id: str | None = None
    run_id: str
    baseline_run_id: str | None = None
    question: str
    selected_activity_id: str | None = None
    selected_location_id: str | None = None
    selected_week: int | None = None


class ChatResponse(PS1Base):
    session_id: str
    answer: str
    response_mode: Literal["gemini", "deterministic_fallback"]
    fact_pack_id: str | None = None
    citations: list[EvidenceItem] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    provenance: ProvenanceModel
    tools_used: list[str] = Field(default_factory=list)


class ExplanationResponse(PS1Base):
    fact_pack: ExplanationFactPack
    fallback_summary: str
    provenance: ProvenanceModel
