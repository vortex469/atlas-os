"""Immutable candidate-planning intake models."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from app.workflow.models import WorkflowEffectKind

SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})
OPERATIONAL_PLANNING_INTENTS = frozenset({"restart-service"})
OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})
RC1_VALIDATION_SMOKE_INTENT = "rc1-validation-smoke"


class CandidatePlanningSessionStatus(StrEnum):
    """Lifecycle state for side-effect-free candidate-planning sessions."""

    INTAKE_REJECTED = "intake_rejected"
    UNSUPPORTED_INTENT = "unsupported_intent"
    READY_FOR_PLANNING = "ready_for_planning"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    PLANNING_FAILED = "planning_failed"
    PLANNING_NOT_SUPPORTED = "planning_not_supported"
    STALE_BEFORE_PLANNING = "stale_before_planning"
    WORKFLOW_CREATED = "workflow_created"
    STALE_BEFORE_WORKFLOW = "stale_before_workflow"
    WORKFLOW_CONVERSION_FAILED = "workflow_conversion_failed"
    IMPLEMENTATION_READY = "implementation_ready"
    IMPLEMENTATION_NOT_SUPPORTED = "implementation_not_supported"
    IMPLEMENTATION_TRANSLATION_FAILED = "implementation_translation_failed"
    STALE_BEFORE_IMPLEMENTATION = "stale_before_implementation"


class CoreCandidatePlanningIntakeStatus(StrEnum):
    """Atlas Core planning-intake statuses consumed over HTTP."""

    ACCEPTED_FOR_PLANNING = "accepted_for_planning"
    NOT_FOUND = "not_found"
    STALE = "stale"
    NOT_ELIGIBLE = "not_eligible"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    TARGET_UNAVAILABLE = "target_unavailable"
    EXPIRED = "expired"
    POLICY_DENIED = "policy_denied"
    REJECTED = "rejected"


class CandidatePlanningFailureCode(StrEnum):
    """Sanitized service-level failure codes."""

    ATLAS_CORE_UNAVAILABLE = "atlas_core_unavailable"
    INTAKE_REJECTED = "intake_rejected"
    MISSING_CANDIDATE_SNAPSHOT = "missing_candidate_snapshot"
    MISSING_CANDIDATE_FINGERPRINT = "missing_candidate_fingerprint"
    UNSUPPORTED_INTENT = "unsupported_intent"
    CONFLICTING_ACTIVE_SESSION = "conflicting_active_session"
    PERSISTENCE_FAILED = "persistence_failed"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_SESSION_STATUS = "invalid_session_status"
    CANDIDATE_STALE = "candidate_stale"
    CANDIDATE_EXPIRED = "candidate_expired"
    CANDIDATE_NOT_ELIGIBLE = "candidate_not_eligible"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    TARGET_UNAVAILABLE = "target_unavailable"
    REPOSITORY_MAPPING_UNAVAILABLE = "repository_mapping_unavailable"
    REPOSITORY_INSPECTION_FAILED = "repository_inspection_failed"
    PLANNING_VALIDATION_FAILED = "planning_validation_failed"
    UNSAFE_PLAN_CONTENT = "unsafe_plan_content"
    PLAN_NOT_READY = "plan_not_ready"
    CANDIDATE_FINGERPRINT_MISMATCH = "candidate_fingerprint_mismatch"
    PLAN_FINGERPRINT_MISMATCH = "plan_fingerprint_mismatch"
    PLAN_INTEGRITY_FAILED = "plan_integrity_failed"
    WORKFLOW_TRANSLATION_UNSUPPORTED = "workflow_translation_unsupported"
    APPROVAL_CREATION_FAILED = "approval_creation_failed"
    IMPLEMENTATION_NOT_SUPPORTED = "implementation_not_supported"
    REPOSITORY_STALE = "repository_stale"
    UNSAFE_TRANSLATION = "unsafe_translation"
    WORKFLOW_NOT_FOUND = "workflow_not_found"
    WORKFLOW_NOT_CANDIDATE = "workflow_not_candidate"
    WORKFLOW_STATE_INVALID = "workflow_state_invalid"
    MISSING_MUTATION_SPECIFICATION = "missing_mutation_specification"


@dataclass(frozen=True, slots=True)
class ComposeMutationSpecification:
    """Immutable, actionable compose mutation evidence."""

    file: Path
    service: str
    property: str
    operation: str
    desired_value: str
    expected_value: str | None = None
    preservation_constraints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperationalTargetReference:
    """Immutable provider-resource identity supplied by Atlas Core."""

    provider_id: str
    resource_id: str
    resource_type: str
    resource_fingerprint: str
    resource_version: str | None
    expected_state: str


@dataclass(frozen=True, slots=True)
class CandidatePlanRequest:
    """Agent-facing request to create or reuse a planning-only session."""

    candidate_id: str
    expected_candidate_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    """Sanitized authoritative candidate snapshot returned by Atlas Core."""

    candidate_id: str
    candidate_fingerprint: str
    source_recommendation_id: str
    source_subsystem: str
    recommendation_class: str
    catalog_item_id: str | None
    target_id: str
    target_type: str
    execution_category: str
    execution_intent: str
    required_approval_level: str
    rationale: str
    constraints: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    compatibility_assessment_id: str | None
    compatibility_status: str | None
    relationship_ids: tuple[str, ...]
    expires_at: datetime | None
    intake_status: CoreCandidatePlanningIntakeStatus
    intake_reason_codes: tuple[str, ...]
    intake_timestamp: datetime
    effect_kind: WorkflowEffectKind = WorkflowEffectKind.REPOSITORY_CHANGE
    mutation: ComposeMutationSpecification | None = None
    operational_target: OperationalTargetReference | None = None


@dataclass(frozen=True, slots=True)
class CandidatePlanningFailure:
    """Sanitized planning failure attached to a candidate-planning session."""

    code: CandidatePlanningFailureCode
    message: str


@dataclass(frozen=True, slots=True)
class CandidatePlanningContext:
    """Trusted input for read-only candidate-aware plan generation."""

    session_id: str
    candidate_id: str
    candidate_fingerprint: str
    source_recommendation_id: str
    source_subsystem: str
    recommendation_class: str
    catalog_item_id: str | None
    target_id: str
    target_type: str
    execution_category: str
    execution_intent: str
    rationale: str
    constraints: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    compatibility_assessment_id: str | None
    compatibility_status: str | None
    relationship_ids: tuple[str, ...]
    repository_root: Path
    repository_branch: str | None
    repository_head: str | None
    planning_timestamp: datetime
    revalidated_candidate_fingerprint: str
    mutation: ComposeMutationSpecification | None = None


@dataclass(frozen=True, slots=True)
class CandidatePlan:
    """Read-only descriptive plan for a candidate-planning session."""

    identifier: str
    session_id: str
    candidate_id: str
    candidate_fingerprint: str
    title: str
    objective: str
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    proposed_steps: tuple[str, ...]
    likely_affected_components: tuple[str, ...]
    likely_affected_files: tuple[Path, ...]
    verification_strategy: tuple[str, ...]
    rollback_considerations: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    created_at: datetime
    repository_root: Path
    repository_branch: str | None
    repository_head: str | None
    revalidated_candidate_fingerprint: str
    mutation: ComposeMutationSpecification | None = None


@dataclass(frozen=True, slots=True)
class OperationalVerificationSpecification:
    """Non-executable verification contract for a future operational action."""

    pre_state: str
    expected_post_state: str
    identity_fingerprint: str
    health_requirement: str
    unknown_outcome_policy: str


@dataclass(frozen=True, slots=True)
class OperationalCandidatePlan:
    """Repository-independent descriptive plan for an operational action."""

    identifier: str
    session_id: str
    candidate_id: str
    candidate_fingerprint: str
    effect_kind: WorkflowEffectKind
    execution_intent: str
    provider_id: str
    resource_id: str
    resource_type: str
    target_fingerprint: str
    target_version: str | None
    expected_pre_state: str
    intended_action: str
    disruption_scope: str
    verification: OperationalVerificationSpecification
    failure_considerations: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    created_at: datetime
    revalidated_candidate_fingerprint: str

    def __post_init__(self) -> None:
        if self.effect_kind is not WorkflowEffectKind.OPERATIONAL_ACTION:
            raise ValueError("operational plans require operational_action effect kind")


@dataclass(frozen=True, slots=True)
class PlanningDecision:
    """Result of attempting read-only candidate-aware plan generation."""

    status: CandidatePlanningSessionStatus
    plan: CandidatePlan | None = None
    operational_plan: OperationalCandidatePlan | None = None
    failure: CandidatePlanningFailure | None = None


@dataclass(frozen=True, slots=True)
class CandidatePlanningSession:
    """Immutable planning-only session for one accepted current candidate."""

    identifier: str
    candidate_id: str
    candidate_fingerprint: str
    status: CandidatePlanningSessionStatus
    snapshot: CandidateSnapshot
    created_at: datetime
    unsupported_reason: str | None = None
    planning_status: CandidatePlanningSessionStatus = CandidatePlanningSessionStatus.READY_FOR_PLANNING
    plan: CandidatePlan | None = None
    operational_plan: OperationalCandidatePlan | None = None
    planning_failure: CandidatePlanningFailure | None = None
    planning_started_at: datetime | None = None
    planning_completed_at: datetime | None = None
    last_revalidation_fingerprint: str | None = None
    last_revalidation_status: CoreCandidatePlanningIntakeStatus | None = None
    workflow_session_id: str | None = None
    implementation_approval_request_id: str | None = None
    candidate_plan_fingerprint: str | None = None
    workflow_conversion_status: CandidatePlanningSessionStatus | None = None
    workflow_conversion_completed_at: datetime | None = None
    implementation_request_id: str | None = None
    exact_implementation_approval_request_id: str | None = None
    implementation_translation_status: CandidatePlanningSessionStatus | None = None
    implementation_translation_completed_at: datetime | None = None
    predecessor_session_id: str | None = None
    successor_session_id: str | None = None

    def __post_init__(self) -> None:
        if self.plan is not None and self.operational_plan is not None:
            raise ValueError(
                "candidate planning sessions cannot carry both repository and operational plans"
            )


@dataclass(frozen=True, slots=True)
class CandidatePlanResponse:
    """Agent API response for candidate-planning intake."""

    session_id: str | None
    candidate_id: str
    status: CandidatePlanningSessionStatus
    planning_allowed: bool
    intake_status: CoreCandidatePlanningIntakeStatus
    intake_reason_codes: tuple[str, ...]
    candidate_fingerprint: str | None = None
    unsupported_reason: str | None = None
    plan: CandidatePlan | None = None
    operational_plan: OperationalCandidatePlan | None = None
    planning_failure: CandidatePlanningFailure | None = None
    predecessor_session_id: str | None = None
    successor_session_id: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateWorkflowConversionRequest:
    """Request to convert a plan-ready candidate session into a workflow shell."""

    expected_candidate_fingerprint: str | None = None
    expected_plan_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateWorkflowConversionResponse:
    """Response for candidate workflow-shell conversion."""

    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str | None
    candidate_plan_id: str | None
    candidate_plan_fingerprint: str | None
    workflow_session_id: str | None
    workflow_status: str | None
    implementation_approval_request_id: str | None
    conversion_status: CandidatePlanningSessionStatus
    core_revalidation_status: CoreCandidatePlanningIntakeStatus | None
    reason_codes: tuple[str, ...] = ()
    failure: CandidatePlanningFailure | None = None


@dataclass(frozen=True, slots=True)
class CandidateImplementationTranslationRequest:
    """Request to translate a candidate workflow shell into exact implementation approval."""

    expected_candidate_fingerprint: str | None = None
    expected_plan_fingerprint: str | None = None
    expected_repository_head: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateImplementationRequest:
    """Immutable exact candidate-derived implementation request awaiting approval."""

    identifier: str
    workflow_session_id: str
    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str
    candidate_plan_id: str
    candidate_plan_fingerprint: str
    execution_intent: str
    repository_root: Path
    repository_branch: str | None
    repository_head: str
    argv: tuple[str, ...]
    working_directory: Path
    affected_files: tuple[Path, ...]
    evidence_ids: tuple[str, ...]
    compatibility_assessment_id: str | None
    compatibility_status: str | None
    translator_version: str
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class OperationalActionRequest:
    """Immutable non-executable request for a future operational action."""

    request_id: str
    request_digest: str
    idempotency_key: str
    workflow_session_id: str
    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str
    candidate_plan_id: str
    candidate_plan_fingerprint: str
    effect_kind: WorkflowEffectKind
    execution_intent: str
    provider_id: str
    resource_id: str
    resource_type: str
    provider_action_id: str
    target_fingerprint: str
    target_version: str | None
    disruption_scope: str
    evidence_ids: tuple[str, ...]
    expected_pre_state: str
    verification: OperationalVerificationSpecification
    expires_at: datetime
    translator_version: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.effect_kind is not WorkflowEffectKind.OPERATIONAL_ACTION:
            raise ValueError("operational requests require operational_action effect kind")
        from app.candidate_planning.operational_translation import (
            resolve_provider_action_id,
        )

        expected_action = resolve_provider_action_id(
            execution_intent=self.execution_intent,
            provider_id=self.provider_id,
            resource_type=self.resource_type,
        )
        if self.provider_action_id != expected_action:
            raise ValueError("operational request action does not match closed translation")
        if not self.target_fingerprint.strip():
            raise ValueError("operational request requires target fingerprint")
        if self.expires_at <= self.generated_at:
            raise ValueError("operational request expiry must follow generation time")
        expected_digest = operational_action_request_digest(self)
        if not self.request_digest and not self.idempotency_key:
            object.__setattr__(self, "request_digest", expected_digest)
            object.__setattr__(
                self,
                "idempotency_key",
                operational_action_idempotency_key(
                    request_id=self.request_id,
                    request_digest=expected_digest,
                ),
            )
        if self.request_digest != expected_digest:
            raise ValueError("operational request digest does not match immutable payload")
        expected_key = operational_action_idempotency_key(
            request_id=self.request_id,
            request_digest=self.request_digest,
        )
        if self.idempotency_key != expected_key:
            raise ValueError("operational request idempotency key does not match")

    @property
    def identifier(self) -> str:
        """Compatibility alias for generic identifier projections."""

        return self.request_id


@dataclass(frozen=True, slots=True)
class CandidateImplementationTranslationResponse:
    """Response for candidate implementation translation."""

    candidate_planning_session_id: str
    workflow_session_id: str | None
    translation_status: CandidatePlanningSessionStatus
    implementation_request_id: str | None
    exact_approval_request_id: str | None
    candidate_fingerprint: str | None
    plan_fingerprint: str | None
    repository_head: str | None
    translator_version: str | None
    reason_codes: tuple[str, ...] = ()
    failure: CandidatePlanningFailure | None = None


def build_candidate_planning_session_id(
    *,
    candidate_id: str,
    candidate_fingerprint: str,
) -> str:
    """Build a deterministic collision-safe session ID from full fingerprint input."""

    digest = hashlib.sha256(f"{candidate_id}\0{candidate_fingerprint}".encode()).hexdigest()
    return f"candidate-plan-{digest}"


def build_candidate_successor_planning_session_id(
    *,
    candidate_id: str,
    candidate_fingerprint: str,
    predecessor_session_id: str,
    repository_head: str | None,
) -> str:
    """Build a deterministic successor session ID for a planning lineage node."""

    digest = hashlib.sha256(
        f"{candidate_id}\0{candidate_fingerprint}\0{predecessor_session_id}\0{repository_head or ''}".encode()
    ).hexdigest()
    return f"candidate-plan-{digest}"


def is_supported_execution_intent(execution_intent: str) -> bool:
    """Return whether Atlas Agent can create a planning session for an intent."""

    if execution_intent in SUPPORTED_EXECUTION_INTENTS:
        return True
    return (
        execution_intent == RC1_VALIDATION_SMOKE_INTENT
        and os.getenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "false").lower() == "true"
    )


def is_operational_planning_intent(execution_intent: str) -> bool:
    """Return whether an intent may produce a descriptive operational plan only."""

    return execution_intent in OPERATIONAL_PLANNING_INTENTS


def is_operational_execution_enabled(execution_intent: str) -> bool:
    """Return whether an operational intent may cross the execution boundary."""

    return execution_intent in OPERATIONAL_EXECUTION_INTENTS


OPERATIONAL_REQUEST_DIGEST_VERSION = "operational-action-request-digest-v1"
OPERATIONAL_IDEMPOTENCY_KEY_VERSION = "operational-action-execution-key-v1"
OPERATIONAL_VERIFICATION_DIGEST_VERSION = "operational-verification-digest-v1"


def operational_verification_digest(
    verification: OperationalVerificationSpecification,
) -> str:
    """Bind the complete semantic verification contract."""

    payload = {
        "expected_post_state": verification.expected_post_state,
        "health_requirement": verification.health_requirement,
        "identity_fingerprint": verification.identity_fingerprint,
        "pre_state": verification.pre_state,
        "unknown_outcome_policy": verification.unknown_outcome_policy,
        "version": OPERATIONAL_VERIFICATION_DIGEST_VERSION,
    }
    return _versioned_digest(OPERATIONAL_VERIFICATION_DIGEST_VERSION, payload)


def operational_action_request_digest(request: OperationalActionRequest) -> str:
    """Return the canonical digest excluding the digest and derived key fields."""

    payload = {
        "candidate_fingerprint": request.candidate_fingerprint,
        "candidate_id": request.candidate_id,
        "candidate_plan_fingerprint": request.candidate_plan_fingerprint,
        "candidate_plan_id": request.candidate_plan_id,
        "candidate_planning_session_id": request.candidate_planning_session_id,
        "disruption_scope": request.disruption_scope,
        "effect_kind": request.effect_kind.value,
        "evidence_ids": sorted(request.evidence_ids),
        "execution_intent": request.execution_intent,
        "expected_pre_state": request.expected_pre_state,
        "expires_at": request.expires_at.isoformat(),
        "generated_at": request.generated_at.isoformat(),
        "provider_action_id": request.provider_action_id,
        "provider_id": request.provider_id,
        "request_id": request.request_id,
        "resource_id": request.resource_id,
        "resource_type": request.resource_type,
        "target_fingerprint": request.target_fingerprint,
        "target_version": request.target_version,
        "translator_version": request.translator_version,
        "verification_digest": operational_verification_digest(request.verification),
        "version": OPERATIONAL_REQUEST_DIGEST_VERSION,
        "workflow_session_id": request.workflow_session_id,
    }
    return _versioned_digest(OPERATIONAL_REQUEST_DIGEST_VERSION, payload)


def operational_action_idempotency_key(*, request_id: str, request_digest: str) -> str:
    """Derive a stable future execution key from immutable request identity."""

    return _versioned_digest(
        OPERATIONAL_IDEMPOTENCY_KEY_VERSION,
        {
            "request_digest": request_digest,
            "request_id": request_id,
            "version": OPERATIONAL_IDEMPOTENCY_KEY_VERSION,
        },
    )


def _versioned_digest(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}:{hashlib.sha256(encoded.encode()).hexdigest()}"
