from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class CoreOperationalTargetReference(BaseModel):
    provider_id: str
    resource_id: str
    resource_type: str
    resource_fingerprint: str
    resource_version: str | None = None
    expected_state: str


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
    effect_kind: str = "repository_change"
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
    operational_target: CoreOperationalTargetReference | None = None


class CoreCandidatePlanningIntakeRequest(BaseModel):
    expected_candidate_fingerprint: str | None = None
    expected_operational_target_fingerprint: str | None = None


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


class CoreOperationalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoreOperationalVerificationSpecification(CoreOperationalModel):
    pre_state: str
    expected_post_state: str
    identity_fingerprint: str
    health_requirement: str
    unknown_outcome_policy: str


class CoreOperationalApprovalBinding(CoreOperationalModel):
    approval_request_id: str
    action_request_id: str
    action_request_digest: str
    candidate_id: str
    candidate_fingerprint: str
    operational_plan_fingerprint: str
    provider_id: str
    resource_id: str
    resource_type: str
    target_fingerprint: str
    target_version: str | None
    operation_intent: str
    disruption_scope: str
    verification_digest: str
    generated_at: datetime
    expires_at: datetime


class CoreOperationalDispatchRequest(CoreOperationalModel):
    schema_version: int = 1
    request_id: str
    request_digest: str
    idempotency_key: str
    workflow_session_id: str
    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str
    candidate_plan_id: str
    candidate_plan_fingerprint: str
    effect_kind: str
    execution_intent: str
    provider_id: str
    resource_id: str
    resource_type: str
    provider_action_id: str
    target_fingerprint: str
    target_version: str | None
    expected_pre_state: str
    disruption_scope: str
    evidence_ids: tuple[str, ...]
    verification: CoreOperationalVerificationSpecification
    generated_at: datetime
    expires_at: datetime
    translator_version: str
    approval: CoreOperationalApprovalBinding


class CoreOperationalDispatchResult(CoreOperationalModel):
    status: Literal["succeeded", "failed", "outcome_unknown"]
    request_id: str
    request_digest: str
    target_fingerprint: str
    provider_operation_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    sanitized_message: str | None = None


class CoreOperationalVerificationResult(CoreOperationalModel):
    status: Literal[
        "succeeded",
        "verification_failed",
        "outcome_unknown",
        "target_replaced",
    ]
    request_id: str
    observed_target_fingerprint: str | None = None
    observed_state: str | None = None
    health_status: str | None = None
    started_at: datetime
    completed_at: datetime
    deadline: datetime


class CoreOperationalLifecycleStatus(CoreOperationalModel):
    request_id: str
    request_digest: str
    ledger_state: Literal[
        "claimed",
        "revalidated",
        "dispatching",
        "succeeded",
        "failed",
        "outcome_unknown",
        "verifying",
        "verified",
        "verification_failed",
        "target_replaced",
    ]
    dispatch_result: CoreOperationalDispatchResult | None = None
    verification_result: CoreOperationalVerificationResult | None = None
    verification_resumable: bool = False


class CoreOperationalLifecycleTransition(CoreOperationalModel):
    sequence: int
    state: str
    occurred_at: datetime


class CoreOperationalLifecycleRead(CoreOperationalModel):
    request_id: str
    request_digest: str
    ledger_state: str
    transitions: tuple[CoreOperationalLifecycleTransition, ...]
    transition_sequence_valid: bool | None = None
    barrier_crossed: bool
    barrier_crossing_count: int
    provider_operation_captured: bool
    provider_operation_capture_count: int
    dispatch_status: str | None
    provider_operation_reference: str | None
    dispatch_started_at: datetime | None
    dispatch_completed_at: datetime | None
    verification_status: str | None
    observed_target_fingerprint: str | None
    observed_state: str | None
    observed_health: str | None
    verification_started_at: datetime | None
    verification_completed_at: datetime | None
    verification_deadline: datetime | None
    terminal: bool
    controlled_reason: str | None
