"""Immutable candidate-planning intake models."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})
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
    mutation: ComposeMutationSpecification | None = None


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
class PlanningDecision:
    """Result of attempting read-only candidate-aware plan generation."""

    status: CandidatePlanningSessionStatus
    plan: CandidatePlan | None = None
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
