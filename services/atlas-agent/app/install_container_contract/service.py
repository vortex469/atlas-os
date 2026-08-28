"""Pure validation service for the frozen install-container v1 contract.

The values in this module are injected, already-validated proof facts.  The
service deliberately has no adapters: importing and calling it cannot perform
I/O, reserve a request, dispatch work, or execute a container.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .models import (
    AgentInstallContainerAuditEvidenceV1,
    AgentInstallContainerErrorV1,
    AgentInstallContainerRequestV1,
    AgentInstallContainerValidationV1,
    CorrelationId,
    FingerprintV1,
    InstallationSubjectV1,
    ReasonCode,
    StrictContractError,
    evidence_fingerprint,
    parse_request_json,
    runtime_limit_policy_fingerprint,
    validation_fingerprint,
)


@dataclass(frozen=True, slots=True)
class CandidateProofFactsV1:
    """Closed facts copied from one fingerprint-valid v0.20 envelope."""

    operator_id: str
    active: bool
    candidate_record_id: str
    candidate_envelope_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    subject: InstallationSubjectV1
    source_plan_fingerprint: FingerprintV1
    source_repository_path: str
    source_service: str
    source_content_digest: str


@dataclass(frozen=True, slots=True)
class ApprovalProofFactsV1:
    """Closed facts copied from one fingerprint-valid v0.21 approval intent."""

    operator_id: str
    approval_intent_id: str
    approval_intent_fingerprint: FingerprintV1
    candidate_record_id: str
    candidate_envelope_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1


@dataclass(frozen=True, slots=True)
class NoReplayEvidenceV1:
    """Injected atomic-reservation result; this service never creates it.

    ``fresh`` is the only state that may be newly validated.  An exact
    duplicate returns its original closed value.  Conflict and ambiguity fail
    closed, so absence of durable evidence can never become replay authority.
    """

    state: Literal["fresh", "exact_duplicate", "conflict", "ambiguous"]
    original_validation: AgentInstallContainerValidationV1 | None = None

    def __post_init__(self) -> None:
        if self.state not in {"fresh", "exact_duplicate", "conflict", "ambiguous"}:
            raise ValueError("unknown no-replay evidence state")
        if (self.state == "exact_duplicate") != (self.original_validation is not None):
            raise ValueError("only an exact duplicate has original validation evidence")


@dataclass(frozen=True, slots=True)
class ValidationFactsV1:
    authenticated_operator_id: str
    candidate: CandidateProofFactsV1 | None
    approval: ApprovalProofFactsV1 | None
    current_destination_fingerprint: str | None
    replay: NoReplayEvidenceV1


@dataclass(frozen=True, slots=True)
class InstallContainerValidationService:
    """Explicit local-only composition boundary for one closed validation.

    The caller must inject both the already-validated proof facts and the
    trusted whole-second validation instant.  No production adapter or clock
    is resolved here, which keeps construction explicit and prevents this
    service from becoming runtime intake by configuration drift.
    """

    facts: ValidationFactsV1
    validated_at: str

    def validate(
        self,
        payload: bytes | str,
        *,
        correlation_id: CorrelationId,
    ) -> AgentInstallContainerValidationV1 | AgentInstallContainerErrorV1:
        """Return only the frozen validation or redacted-error contract."""
        return validate_install_container_json(
            payload,
            facts=self.facts,
            validated_at=self.validated_at,
            correlation_id=correlation_id,
        )


def validate_install_container_request(
    request: AgentInstallContainerRequestV1,
    *,
    facts: ValidationFactsV1,
    validated_at: str,
) -> AgentInstallContainerValidationV1:
    """Validate one parsed request using only injected immutable facts."""
    if facts.replay.state == "exact_duplicate":
        original = facts.replay.original_validation
        assert original is not None
        if (
            original.request_id == request.request_id
            and original.request_fingerprint == request.request_fingerprint
        ):
            return original
        reasons = (ReasonCode.REQUEST_REPLAY_OR_DUPLICATE,)
        return _result(request, validated_at, reasons)

    reasons: list[ReasonCode] = []
    if facts.replay.state != "fresh":
        reasons.append(ReasonCode.REQUEST_REPLAY_OR_DUPLICATE)

    now = _parse_second(validated_at)
    issued = _parse_second(request.issued_at)
    expires = _parse_second(request.expires_at)
    if not issued <= now < expires:
        reasons.append(ReasonCode.REQUEST_NOT_CURRENT)

    candidate = facts.candidate
    if candidate is None:
        reasons.append(ReasonCode.CANDIDATE_PROOF_MISSING)
    else:
        candidate_tuple = (
            candidate.candidate_record_id,
            candidate.candidate_envelope_fingerprint,
            candidate.admission_fingerprint,
            candidate.candidate_record_fingerprint,
        )
        request_candidate_tuple = (
            request.approval.candidate_record_id,
            request.approval.candidate_envelope_fingerprint,
            request.approval.admission_fingerprint,
            request.approval.candidate_record_fingerprint,
        )
        if candidate_tuple != request_candidate_tuple:
            reasons.append(ReasonCode.CANDIDATE_PROOF_MISMATCH)
        if not candidate.active:
            reasons.append(ReasonCode.CANDIDATE_NOT_ACTIVE)

    approval = facts.approval
    if approval is None:
        reasons.append(ReasonCode.APPROVAL_PROOF_MISSING)
    else:
        approval_identity = (
            approval.approval_intent_id,
            approval.approval_intent_fingerprint,
        )
        request_approval_identity = (
            request.approval.approval_intent_id,
            request.approval.approval_intent_fingerprint,
        )
        approved_candidate_tuple = (
            approval.candidate_record_id,
            approval.candidate_envelope_fingerprint,
            approval.admission_fingerprint,
            approval.candidate_record_fingerprint,
        )
        request_candidate_tuple = (
            request.approval.candidate_record_id,
            request.approval.candidate_envelope_fingerprint,
            request.approval.admission_fingerprint,
            request.approval.candidate_record_fingerprint,
        )
        operators_match = (
            approval.operator_id == facts.authenticated_operator_id
            and candidate is not None
            and candidate.operator_id == facts.authenticated_operator_id
        )
        if (
            approval_identity != request_approval_identity
            or approved_candidate_tuple != request_candidate_tuple
            or not operators_match
        ):
            reasons.append(ReasonCode.APPROVAL_PROOF_MISMATCH)

    if candidate is not None:
        if request.subject != candidate.subject:
            reasons.append(ReasonCode.DESTINATION_IDENTITY_MISMATCH)
        source = (
            request.artifact.source_plan_fingerprint,
            request.artifact.source_repository_path,
            request.artifact.source_service,
            request.artifact.source_content_digest,
        )
        expected_source = (
            candidate.source_plan_fingerprint,
            candidate.source_repository_path,
            candidate.source_service,
            candidate.source_content_digest,
        )
        if source != expected_source:
            reasons.append(ReasonCode.ARTIFACT_SOURCE_MISMATCH)

    if (
        facts.current_destination_fingerprint is None
        or facts.current_destination_fingerprint != request.subject.destination_fingerprint
    ):
        reasons.append(ReasonCode.DESTINATION_IDENTITY_MISMATCH)

    return _result(request, validated_at, _ordered_unique(reasons))


def validate_install_container_json(
    payload: bytes | str,
    *,
    facts: ValidationFactsV1,
    validated_at: str,
    correlation_id: CorrelationId,
) -> AgentInstallContainerValidationV1 | AgentInstallContainerErrorV1:
    """Parse and validate without ever returning hostile input or exceptions."""
    try:
        request = parse_request_json(payload)
    except StrictContractError as error:
        reason = _safe_parse_reason(error)
        return _redacted_error(reason, correlation_id)
    except Exception:  # noqa: BLE001 - the public boundary must redact every parser failure
        return _redacted_error(ReasonCode.VALIDATION_CONTRACT_FAILURE, correlation_id)
    try:
        return validate_install_container_request(
            request, facts=facts, validated_at=validated_at
        )
    except Exception:  # noqa: BLE001 - the public boundary must redact every internal failure
        return AgentInstallContainerErrorV1(
            schema="agent-install-container-error-v1",
            reason_code=ReasonCode.VALIDATION_CONTRACT_FAILURE,
            request_id=request.request_id,
            request_fingerprint=request.request_fingerprint,
            correlation_id=correlation_id,
            redacted=True,
        )


def _result(
    request: AgentInstallContainerRequestV1,
    validated_at: str,
    reasons: tuple[ReasonCode, ...],
) -> AgentInstallContainerValidationV1:
    status = "rejected" if reasons else "valid_but_unsupported"
    authority = {
        "execution_supported": False,
        "dispatch_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    evidence_data = {
        "evidence_schema": "agent-install-container-audit-evidence-v1",
        "request_id": request.request_id,
        "request_fingerprint": request.request_fingerprint,
        "approval": request.approval,
        "subject": request.subject,
        "artifact_kind": request.artifact.kind,
        "source_plan_fingerprint": request.artifact.source_plan_fingerprint,
        "source_repository_path": request.artifact.source_repository_path,
        "source_service": request.artifact.source_service,
        "source_content_digest": request.artifact.source_content_digest,
        "image_digest": request.artifact.image_digest,
        "runtime_limit_policy_fingerprint": runtime_limit_policy_fingerprint(
            request.artifact, request.limits
        ),
        "validated_at": validated_at,
        "status": status,
        "reason_codes": reasons,
        **authority,
    }
    evidence_json = {
        key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for key, value in evidence_data.items()
    }
    evidence_json["reason_codes"] = [reason.value for reason in reasons]
    evidence_data["evidence_fingerprint"] = evidence_fingerprint(evidence_json)
    evidence = AgentInstallContainerAuditEvidenceV1.model_validate(evidence_data)
    validation_data = {
        "schema": "agent-install-container-validation-v1",
        "request_id": request.request_id,
        "request_fingerprint": request.request_fingerprint,
        "validated_at": validated_at,
        "status": status,
        "reason_codes": reasons,
        **authority,
        "evidence": evidence,
    }
    validation_json = {
        key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for key, value in validation_data.items()
    }
    validation_json["reason_codes"] = [reason.value for reason in reasons]
    validation_json["evidence"] = evidence.model_dump(mode="json")
    validation_data["validation_fingerprint"] = validation_fingerprint(validation_json)
    return AgentInstallContainerValidationV1.model_validate(validation_data)


def _parse_second(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _ordered_unique(reasons: list[ReasonCode]) -> tuple[ReasonCode, ...]:
    order = {reason: index for index, reason in enumerate(ReasonCode)}
    return tuple(sorted(set(reasons), key=order.__getitem__))


def _safe_parse_reason(error: StrictContractError) -> ReasonCode:
    try:
        return ReasonCode(str(error))
    except ValueError:
        return ReasonCode.CONTRACT_MALFORMED


def _redacted_error(
    reason: ReasonCode, correlation_id: CorrelationId
) -> AgentInstallContainerErrorV1:
    return AgentInstallContainerErrorV1(
        schema="agent-install-container-error-v1",
        reason_code=reason,
        request_id=None,
        request_fingerprint=None,
        correlation_id=correlation_id,
        redacted=True,
    )
