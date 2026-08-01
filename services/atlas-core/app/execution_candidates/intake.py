from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.execution_candidates.api_models import ExecutionCandidateResponse
from app.execution_candidates.models import ExecutionCandidateModel


class CandidatePlanningIntakeStatus(StrEnum):
    """Controlled planning-intake outcomes."""

    ACCEPTED_FOR_PLANNING = "accepted_for_planning"
    NOT_FOUND = "not_found"
    STALE = "stale"
    NOT_ELIGIBLE = "not_eligible"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    TARGET_UNAVAILABLE = "target_unavailable"
    EXPIRED = "expired"
    POLICY_DENIED = "policy_denied"
    REJECTED = "rejected"


class CandidatePlanningIntakeReasonCode(StrEnum):
    """Stable sanitized reason codes for planning intake."""

    ACCEPTED_FOR_PLANNING = "accepted_for_planning"
    CANDIDATE_NOT_FOUND = "candidate_not_found"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    CANDIDATE_NOT_ELIGIBLE = "candidate_not_eligible"
    MISSING_EVIDENCE = "missing_evidence"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    TARGET_UNAVAILABLE = "target_unavailable"
    CANDIDATE_EXPIRED = "candidate_expired"
    POLICY_DENIED = "policy_denied"
    VALIDATION_FAILED = "validation_failed"
    UNSUPPORTED_SOURCE_SUBSYSTEM = "unsupported_source_subsystem"
    UNSAFE_PAYLOAD = "unsafe_payload"
    BYPASSES_AGENT_OR_APPROVAL = "bypasses_agent_or_approval"
    NON_EXECUTABLE_RECOMMENDATION = "non_executable_recommendation"
    UNSUPPORTED_INTENT_CATEGORY = "unsupported_intent_category"
    INSUFFICIENT_COMPATIBILITY = "insufficient_compatibility"
    INCOMPATIBLE_COMPATIBILITY = "incompatible_compatibility"
    UNRESOLVED_REQUIRED_RELATIONSHIP = "unresolved_required_relationship"
    DESTRUCTIVE_APPROVAL_REQUIRED = "destructive_approval_required"
    SERVICE_DISRUPTION_CONSTRAINT_REQUIRED = "service_disruption_constraint_required"


class CandidatePlanningIntakeRequest(ExecutionCandidateModel):
    """Side-effect-free request to revalidate a current candidate for planning."""

    expected_candidate_fingerprint: str | None = None
    requested_by: str | None = Field(default=None, max_length=200)


class CandidatePlanningIntakeResult(ExecutionCandidateModel):
    """Public side-effect-free response for planning-intake validation."""

    status: CandidatePlanningIntakeStatus
    candidate_id: str
    planning_allowed: bool
    reason_codes: tuple[CandidatePlanningIntakeReasonCode, ...]
    current_candidate_fingerprint: str | None = None
    current_candidate: ExecutionCandidateResponse | None = None
