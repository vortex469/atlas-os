from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ServiceHealth(BaseModel):
    provider_id: str
    status: str
    latency_ms: float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

class AtlasCoreHealth(BaseModel):
    atlas: str
    services: dict[str, ServiceHealth]

class AtlasCoreStatus(BaseModel):
    atlas: str
    assistant: str
    engine: str
    release: str


class AtlasCoreIntelligenceFinding(BaseModel):
    id: str
    severity: str
    category: str
    source: str
    title: str
    message: str
    recommendation: str | None = None
    component: str | None = None
    affects_health: bool


class AtlasCoreIntelligenceAssessment(BaseModel):
    title: str
    priority: str
    component: str | None = None


class AtlasCoreIntelligenceRecommendation(BaseModel):
    title: str
    reason: str
    priority: str
    confidence: float
    estimated_effort: str
    component: str | None = None


class AtlasCoreIntelligenceSummary(BaseModel):
    score: int
    status: str
    summary: str
    findings: tuple[AtlasCoreIntelligenceFinding, ...] = ()
    assessments: tuple[AtlasCoreIntelligenceAssessment, ...] = ()
    recommendations: tuple[AtlasCoreIntelligenceRecommendation, ...] = ()




class CoreComposeMutationSpecification(BaseModel):
    file: str
    service: str
    property: str
    operation: str
    desired_value: str
    expected_value: str | None = None
    preservation_constraints: tuple[str, ...] = ()


class CoreExecutionCandidateSnapshot(BaseModel):
    id: str
    source_recommendation_id: str
    source_subsystem: str
    recommendation_class: str
    catalog_item_id: str | None = None
    target_id: str
    target_type: str
    execution_category: str
    execution_intent: str
    status: str
    required_approval_level: str
    rationale: str
    constraints: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    compatibility_assessment_id: str | None = None
    compatibility_status: str | None = None
    relationship_ids: tuple[str, ...] = ()
    created_at: datetime
    expires_at: datetime | None = None
    mutation: CoreComposeMutationSpecification | None = None


class CoreCandidatePlanningIntakeRequest(BaseModel):
    expected_candidate_fingerprint: str | None = None


class CoreCandidatePlanningIntakeResponse(BaseModel):
    status: str
    candidate_id: str
    planning_allowed: bool
    reason_codes: tuple[str, ...] = ()
    current_candidate_fingerprint: str | None = None
    current_candidate: CoreExecutionCandidateSnapshot | None = None


class AtlasCoreActionHistoryEntry(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    action_id: str
    action_label: str
    status: Literal["succeeded", "failed"]
    success: bool
    message: str
    confirmed: bool
    destructive: bool
    parameter_names: tuple[str, ...] = ()
    request_id: str | None = None
    started_at: datetime
    completed_at: datetime
    duration_ms: float
