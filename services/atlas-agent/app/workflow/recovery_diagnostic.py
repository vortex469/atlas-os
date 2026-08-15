"""Deterministic read-only recovery diagnostics for workflow lifecycle facts."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class DiagnosticStatus(StrEnum):
    HEALTHY = "healthy"
    PENDING = "pending"
    ATTENTION_REQUIRED = "attention_required"
    RECOVERY_IN_PROGRESS = "recovery_in_progress"
    OUTCOME_UNCERTAIN = "outcome_uncertain"
    UNAVAILABLE = "unavailable"


class DiagnosticConsistency(StrEnum):
    CONSISTENT = "consistent"
    AGENT_ONLY = "agent_only"
    CORE_UNAVAILABLE = "core_unavailable"
    IMMUTABLE_MISMATCH = "immutable_mismatch"
    TRANSITION_MISMATCH = "transition_mismatch"
    TERMINAL_MISMATCH = "terminal_mismatch"


class DiagnosticReason(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    CORE_UNAVAILABLE = "core_unavailable"
    MISSING_CORE_RECORD = "missing_core_record"
    IMMUTABLE_REQUEST_MISMATCH = "immutable_request_mismatch"
    INVALID_TRANSITION_SEQUENCE = "invalid_transition_sequence"
    DISPATCH_OUTCOME_UNKNOWN = "dispatch_outcome_unknown"
    DISPATCH_FAILED = "dispatch_failed"
    VERIFICATION_PENDING = "verification_pending"
    VERIFICATION_FAILED = "verification_failed"
    TARGET_REPLACED = "target_replaced"
    TERMINAL_STATE_DISAGREEMENT = "terminal_state_disagreement"


class SafeNextAction(StrEnum):
    NONE = "none"
    WAIT_FOR_VERIFICATION = "wait_for_verification"
    RESTORE_CORE_AVAILABILITY = "restore_core_availability"
    INSPECT_TARGET_READ_ONLY = "inspect_target_read_only"
    PRESERVE_EVIDENCE = "preserve_evidence"
    OPERATOR_REVIEW_REQUIRED = "operator_review_required"
    NEW_REQUEST_ONLY_AFTER_TERMINAL = "new_request_only_after_terminal"


class TargetFingerprintState(StrEnum):
    UNCHANGED = "unchanged"
    REPLACED = "replaced"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class DiagnosticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecoveryCorrelation(DiagnosticModel):
    workflow_id: str
    request_id: str | None
    request_digest_match: bool | None
    agent_record_present: bool
    core_record_present: bool


class DispatchDiagnosticEvidence(DiagnosticModel):
    barrier_crossed: bool
    provider_operation_captured: bool
    dispatch_result_known: bool
    transition_sequence_valid: bool | None


class VerificationDiagnosticEvidence(DiagnosticModel):
    status: str | None
    target_fingerprint_state: TargetFingerprintState
    observed_state: str | None
    observed_health: str | None
    terminal_evidence: bool


class WorkflowRecoveryDiagnostic(DiagnosticModel):
    applicable: bool
    diagnostic_status: DiagnosticStatus
    consistency: DiagnosticConsistency
    correlation: RecoveryCorrelation
    dispatch_evidence: DispatchDiagnosticEvidence
    verification_evidence: VerificationDiagnosticEvidence
    controlled_reason: DiagnosticReason | None
    safe_next_action: SafeNextAction


class LifecycleFacts(Protocol):
    applicable: bool
    workflow_id: str
    agent_execution_record_present: bool
    core_record_present: bool
    request_digest_match: bool | None
    action_request_id: str | None
    availability: str
    consistency_status: str
    transition_sequence_valid: bool | None
    barrier_crossed: bool
    provider_operation_captured: bool
    dispatch_status: str | None
    verification_status: str | None
    target_fingerprint: str | None
    observed_target_fingerprint: str | None
    observed_state: str | None
    observed_health: str | None
    agent_terminal: bool
    terminal: bool
    core_record_state: str | None


def project_recovery_diagnostic(lifecycle: LifecycleFacts) -> WorkflowRecoveryDiagnostic:
    """Classify already-projected facts without reconciliation or provider access."""

    fingerprint_state = _fingerprint_state(lifecycle)
    correlation = RecoveryCorrelation(
        workflow_id=lifecycle.workflow_id,
        request_id=lifecycle.action_request_id,
        request_digest_match=lifecycle.request_digest_match,
        agent_record_present=lifecycle.agent_execution_record_present,
        core_record_present=lifecycle.core_record_present,
    )
    dispatch = DispatchDiagnosticEvidence(
        barrier_crossed=lifecycle.barrier_crossed,
        provider_operation_captured=lifecycle.provider_operation_captured,
        dispatch_result_known=lifecycle.dispatch_status is not None,
        transition_sequence_valid=lifecycle.transition_sequence_valid,
    )
    verification = VerificationDiagnosticEvidence(
        status=lifecycle.verification_status,
        target_fingerprint_state=fingerprint_state,
        observed_state=lifecycle.observed_state,
        observed_health=lifecycle.observed_health,
        terminal_evidence=lifecycle.terminal,
    )

    status, consistency, reason, action = _classification(lifecycle)
    return WorkflowRecoveryDiagnostic(
        applicable=lifecycle.applicable,
        diagnostic_status=status,
        consistency=consistency,
        correlation=correlation,
        dispatch_evidence=dispatch,
        verification_evidence=verification,
        controlled_reason=reason,
        safe_next_action=action,
    )


def _classification(
    lifecycle: LifecycleFacts,
) -> tuple[
    DiagnosticStatus,
    DiagnosticConsistency,
    DiagnosticReason | None,
    SafeNextAction,
]:
    if not lifecycle.applicable:
        return (
            DiagnosticStatus.HEALTHY,
            DiagnosticConsistency.AGENT_ONLY,
            DiagnosticReason.NOT_APPLICABLE,
            SafeNextAction.NONE,
        )
    if lifecycle.availability == "unavailable":
        return (
            DiagnosticStatus.UNAVAILABLE,
            DiagnosticConsistency.CORE_UNAVAILABLE,
            DiagnosticReason.CORE_UNAVAILABLE,
            SafeNextAction.RESTORE_CORE_AVAILABILITY,
        )
    if lifecycle.agent_execution_record_present and not lifecycle.core_record_present:
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.AGENT_ONLY,
            DiagnosticReason.MISSING_CORE_RECORD,
            SafeNextAction.OPERATOR_REVIEW_REQUIRED,
        )
    if lifecycle.request_digest_match is False or lifecycle.consistency_status == "mismatch":
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.IMMUTABLE_MISMATCH,
            DiagnosticReason.IMMUTABLE_REQUEST_MISMATCH,
            SafeNextAction.OPERATOR_REVIEW_REQUIRED,
        )
    if lifecycle.core_record_present and lifecycle.transition_sequence_valid is not True:
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.TRANSITION_MISMATCH,
            DiagnosticReason.INVALID_TRANSITION_SEQUENCE,
            SafeNextAction.PRESERVE_EVIDENCE,
        )
    if lifecycle.core_record_present and lifecycle.agent_terminal != lifecycle.terminal:
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.TERMINAL_MISMATCH,
            DiagnosticReason.TERMINAL_STATE_DISAGREEMENT,
            SafeNextAction.OPERATOR_REVIEW_REQUIRED,
        )
    if lifecycle.barrier_crossed and (
        lifecycle.dispatch_status in {None, "outcome_unknown"}
        or lifecycle.core_record_state == "outcome_unknown"
    ):
        return (
            DiagnosticStatus.OUTCOME_UNCERTAIN,
            DiagnosticConsistency.CONSISTENT,
            DiagnosticReason.DISPATCH_OUTCOME_UNKNOWN,
            SafeNextAction.PRESERVE_EVIDENCE,
        )
    if lifecycle.dispatch_status == "failed" or lifecycle.core_record_state == "failed":
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.CONSISTENT,
            DiagnosticReason.DISPATCH_FAILED,
            SafeNextAction.OPERATOR_REVIEW_REQUIRED,
        )
    if (
        lifecycle.observed_target_fingerprint is not None
        and lifecycle.target_fingerprint is not None
        and lifecycle.observed_target_fingerprint != lifecycle.target_fingerprint
    ):
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.CONSISTENT,
            DiagnosticReason.TARGET_REPLACED,
            SafeNextAction.NEW_REQUEST_ONLY_AFTER_TERMINAL,
        )
    if lifecycle.verification_status == "target_replaced":
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.CONSISTENT,
            DiagnosticReason.TARGET_REPLACED,
            SafeNextAction.NEW_REQUEST_ONLY_AFTER_TERMINAL,
        )
    if lifecycle.verification_status == "verification_failed":
        return (
            DiagnosticStatus.ATTENTION_REQUIRED,
            DiagnosticConsistency.CONSISTENT,
            DiagnosticReason.VERIFICATION_FAILED,
            SafeNextAction.INSPECT_TARGET_READ_ONLY,
        )
    if lifecycle.core_record_state == "verifying":
        return (
            DiagnosticStatus.RECOVERY_IN_PROGRESS,
            DiagnosticConsistency.CONSISTENT,
            DiagnosticReason.VERIFICATION_PENDING,
            SafeNextAction.WAIT_FOR_VERIFICATION,
        )
    if lifecycle.terminal and lifecycle.verification_status == "succeeded":
        return (
            DiagnosticStatus.HEALTHY,
            DiagnosticConsistency.CONSISTENT,
            None,
            SafeNextAction.NONE,
        )
    return (
        DiagnosticStatus.PENDING,
        DiagnosticConsistency.CONSISTENT if lifecycle.core_record_present else DiagnosticConsistency.AGENT_ONLY,
        DiagnosticReason.VERIFICATION_PENDING,
        SafeNextAction.WAIT_FOR_VERIFICATION,
    )


def _fingerprint_state(lifecycle: LifecycleFacts) -> TargetFingerprintState:
    if not lifecycle.applicable:
        return TargetFingerprintState.NOT_APPLICABLE
    if lifecycle.observed_target_fingerprint is None or lifecycle.target_fingerprint is None:
        return TargetFingerprintState.UNAVAILABLE
    if lifecycle.observed_target_fingerprint == lifecycle.target_fingerprint:
        return TargetFingerprintState.UNCHANGED
    return TargetFingerprintState.REPLACED
