from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.execution_candidates.api_models import candidate_to_response
from app.execution_candidates.eligibility import (
    ExecutionEligibilityReason,
    validate_candidate_for_planning,
)
from app.execution_candidates.fingerprint import build_candidate_fingerprint
from app.execution_candidates.intake import (
    CandidatePlanningIntakeReasonCode,
    CandidatePlanningIntakeRequest,
    CandidatePlanningIntakeResult,
    CandidatePlanningIntakeStatus,
)
from app.execution_candidates.models import ExecutionCandidate, ExecutionCandidateStatus
from app.services.execution_candidates import (
    ExecutionCandidateCollectionError,
    ExecutionCandidateNotFoundError,
    get_current_execution_candidate,
)

logger = get_logger("atlas.execution_candidate_intake")
EvidenceResolver = Callable[[ExecutionCandidate], Iterable[str]]
CandidateResolver = Callable[..., object]


class ExecutionCandidatePlanningIntakeError(RuntimeError):
    """Raised when planning-intake validation cannot collect current candidates."""


def _sorted_reason_codes(
    codes: Iterable[CandidatePlanningIntakeReasonCode],
) -> tuple[CandidatePlanningIntakeReasonCode, ...]:
    return tuple(sorted(set(codes), key=lambda code: code.value))


def _normalize_available_evidence(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().lower() for value in values if value.strip()}))


def _result(
    *,
    status: CandidatePlanningIntakeStatus,
    candidate_id: str,
    reason_codes: Iterable[CandidatePlanningIntakeReasonCode],
    candidate: ExecutionCandidate | None = None,
    fingerprint: str | None = None,
) -> CandidatePlanningIntakeResult:
    return CandidatePlanningIntakeResult(
        status=status,
        candidate_id=candidate_id,
        planning_allowed=status == CandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
        reason_codes=_sorted_reason_codes(reason_codes),
        current_candidate_fingerprint=fingerprint,
        current_candidate=candidate_to_response(candidate) if candidate is not None else None,
    )


def _default_evidence_resolver(candidate: ExecutionCandidate) -> tuple[str, ...]:
    del candidate
    return ()


def _map_reason(reason: ExecutionEligibilityReason) -> CandidatePlanningIntakeReasonCode:
    mapping = {
        ExecutionEligibilityReason.CANDIDATE_NOT_ELIGIBLE: CandidatePlanningIntakeReasonCode.CANDIDATE_NOT_ELIGIBLE,
        ExecutionEligibilityReason.NON_EXECUTABLE_RECOMMENDATION: CandidatePlanningIntakeReasonCode.NON_EXECUTABLE_RECOMMENDATION,
        ExecutionEligibilityReason.MISSING_TARGET: CandidatePlanningIntakeReasonCode.TARGET_UNAVAILABLE,
        ExecutionEligibilityReason.AMBIGUOUS_TARGET: CandidatePlanningIntakeReasonCode.TARGET_UNAVAILABLE,
        ExecutionEligibilityReason.MISSING_EVIDENCE: CandidatePlanningIntakeReasonCode.MISSING_EVIDENCE,
        ExecutionEligibilityReason.UNREFERENCED_EVIDENCE: CandidatePlanningIntakeReasonCode.EVIDENCE_UNAVAILABLE,
        ExecutionEligibilityReason.MISSING_CATALOG_IDENTITY: CandidatePlanningIntakeReasonCode.VALIDATION_FAILED,
        ExecutionEligibilityReason.INSUFFICIENT_COMPATIBILITY: CandidatePlanningIntakeReasonCode.INSUFFICIENT_COMPATIBILITY,
        ExecutionEligibilityReason.INCOMPATIBLE_COMPATIBILITY: CandidatePlanningIntakeReasonCode.INCOMPATIBLE_COMPATIBILITY,
        ExecutionEligibilityReason.UNRESOLVED_REQUIRED_RELATIONSHIP: CandidatePlanningIntakeReasonCode.UNRESOLVED_REQUIRED_RELATIONSHIP,
        ExecutionEligibilityReason.UNSUPPORTED_SOURCE_SUBSYSTEM: CandidatePlanningIntakeReasonCode.UNSUPPORTED_SOURCE_SUBSYSTEM,
        ExecutionEligibilityReason.EXPIRED_CANDIDATE: CandidatePlanningIntakeReasonCode.CANDIDATE_EXPIRED,
        ExecutionEligibilityReason.UNSUPPORTED_INTENT_CATEGORY: CandidatePlanningIntakeReasonCode.UNSUPPORTED_INTENT_CATEGORY,
        ExecutionEligibilityReason.UNSAFE_PAYLOAD: CandidatePlanningIntakeReasonCode.UNSAFE_PAYLOAD,
        ExecutionEligibilityReason.BYPASSES_AGENT_OR_APPROVAL: CandidatePlanningIntakeReasonCode.BYPASSES_AGENT_OR_APPROVAL,
        ExecutionEligibilityReason.DESTRUCTIVE_APPROVAL_REQUIRED: CandidatePlanningIntakeReasonCode.DESTRUCTIVE_APPROVAL_REQUIRED,
        ExecutionEligibilityReason.SERVICE_DISRUPTION_CONSTRAINT_REQUIRED: CandidatePlanningIntakeReasonCode.SERVICE_DISRUPTION_CONSTRAINT_REQUIRED,
    }
    return mapping[reason]


def _status_for_reasons(
    reasons: Iterable[ExecutionEligibilityReason],
) -> CandidatePlanningIntakeStatus:
    reason_set = set(reasons)
    if ExecutionEligibilityReason.EXPIRED_CANDIDATE in reason_set:
        return CandidatePlanningIntakeStatus.EXPIRED
    if reason_set & {
        ExecutionEligibilityReason.MISSING_TARGET,
        ExecutionEligibilityReason.AMBIGUOUS_TARGET,
    }:
        return CandidatePlanningIntakeStatus.TARGET_UNAVAILABLE
    if ExecutionEligibilityReason.UNREFERENCED_EVIDENCE in reason_set:
        return CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE
    if reason_set & {
        ExecutionEligibilityReason.UNSUPPORTED_SOURCE_SUBSYSTEM,
        ExecutionEligibilityReason.UNSAFE_PAYLOAD,
        ExecutionEligibilityReason.BYPASSES_AGENT_OR_APPROVAL,
        ExecutionEligibilityReason.UNSUPPORTED_INTENT_CATEGORY,
        ExecutionEligibilityReason.NON_EXECUTABLE_RECOMMENDATION,
    }:
        return CandidatePlanningIntakeStatus.REJECTED
    if ExecutionEligibilityReason.DESTRUCTIVE_APPROVAL_REQUIRED in reason_set:
        return CandidatePlanningIntakeStatus.POLICY_DENIED
    return CandidatePlanningIntakeStatus.NOT_ELIGIBLE


async def validate_candidate_planning_intake(
    candidate_id: str,
    request: CandidatePlanningIntakeRequest | None = None,
    *,
    now: datetime | None = None,
    candidate_resolver: Callable[..., object] = get_current_execution_candidate,
    evidence_resolver: EvidenceResolver | None = None,
) -> CandidatePlanningIntakeResult:
    """Re-resolve and validate the authoritative current candidate for planning."""

    validation_time = now or datetime.now(UTC)
    intake_request = request or CandidatePlanningIntakeRequest()
    resolver = evidence_resolver or _default_evidence_resolver

    try:
        resolved = candidate_resolver(candidate_id, now=validation_time)
        candidate = await resolved if hasattr(resolved, "__await__") else resolved
    except ExecutionCandidateNotFoundError:
        return _result(
            status=CandidatePlanningIntakeStatus.NOT_FOUND,
            candidate_id=candidate_id,
            reason_codes=(CandidatePlanningIntakeReasonCode.CANDIDATE_NOT_FOUND,),
        )
    except ExecutionCandidateCollectionError as error:
        raise ExecutionCandidatePlanningIntakeError(
            "Unable to collect current execution candidates for planning intake."
        ) from error
    except Exception as error:
        logger.exception("Unable to resolve execution candidate for planning intake")
        raise ExecutionCandidatePlanningIntakeError(
            "Unable to collect current execution candidates for planning intake."
        ) from error

    current_fingerprint = build_candidate_fingerprint(candidate)
    if (
        intake_request.expected_candidate_fingerprint is not None
        and intake_request.expected_candidate_fingerprint != current_fingerprint
    ):
        return _result(
            status=CandidatePlanningIntakeStatus.STALE,
            candidate_id=candidate_id,
            reason_codes=(CandidatePlanningIntakeReasonCode.FINGERPRINT_MISMATCH,),
            candidate=candidate,
            fingerprint=current_fingerprint,
        )

    if candidate.expires_at is not None and candidate.expires_at <= validation_time:
        return _result(
            status=CandidatePlanningIntakeStatus.EXPIRED,
            candidate_id=candidate_id,
            reason_codes=(CandidatePlanningIntakeReasonCode.CANDIDATE_EXPIRED,),
            candidate=candidate,
            fingerprint=current_fingerprint,
        )

    available_evidence_ids = _normalize_available_evidence(resolver(candidate))
    missing_evidence = tuple(
        evidence_id for evidence_id in candidate.evidence_ids if evidence_id not in available_evidence_ids
    )
    if missing_evidence:
        return _result(
            status=CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE,
            candidate_id=candidate_id,
            reason_codes=(CandidatePlanningIntakeReasonCode.EVIDENCE_UNAVAILABLE,),
            candidate=candidate,
            fingerprint=current_fingerprint,
        )

    eligibility = validate_candidate_for_planning(
        candidate,
        available_evidence_ids=available_evidence_ids,
        now=validation_time,
    )
    if eligibility.status == ExecutionCandidateStatus.ELIGIBLE:
        return _result(
            status=CandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
            candidate_id=candidate_id,
            reason_codes=(CandidatePlanningIntakeReasonCode.ACCEPTED_FOR_PLANNING,),
            candidate=candidate,
            fingerprint=current_fingerprint,
        )

    eligibility_reasons = tuple(finding.reason for finding in eligibility.findings)
    return _result(
        status=_status_for_reasons(eligibility_reasons),
        candidate_id=candidate_id,
        reason_codes=tuple(_map_reason(reason) for reason in eligibility_reasons),
        candidate=candidate,
        fingerprint=current_fingerprint,
    )
