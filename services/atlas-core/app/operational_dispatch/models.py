"""Strict semantic contracts for internal operational dispatch."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

REQUEST_DIGEST_VERSION = "operational-action-request-digest-v1"
IDEMPOTENCY_KEY_VERSION = "operational-action-execution-key-v1"
VERIFICATION_DIGEST_VERSION = "operational-verification-digest-v1"
_CLOSED_ACTIONS = {
    ("restart-service", "proxmox", "qemu"): "proxmox-qemu-graceful-restart-v1",
}


class OperationalDispatchModel(BaseModel):
    """Immutable strict base for security-bound operational artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def validate_strings(cls, value: object) -> object:
        if isinstance(value, str) and (not value or value != value.strip()):
            raise ValueError("operational string fields must be exact and nonblank")
        return value


class OperationalVerificationSpecification(OperationalDispatchModel):
    pre_state: str
    expected_post_state: str
    identity_fingerprint: str
    health_requirement: str
    unknown_outcome_policy: str


class OperationalApprovalBinding(OperationalDispatchModel):
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


class OperationalDispatchRequest(OperationalDispatchModel):
    """Exact Agent-approved semantic request accepted by the Core boundary."""

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
    verification: OperationalVerificationSpecification
    generated_at: datetime
    expires_at: datetime
    translator_version: str
    approval: OperationalApprovalBinding

    @model_validator(mode="after")
    def validate_contract(self) -> OperationalDispatchRequest:
        if self.schema_version != 1:
            raise ValueError("unsupported operational dispatch schema")
        if self.effect_kind != "operational_action":
            raise ValueError("operational dispatch requires operational_action effect")
        if self.expires_at <= self.generated_at:
            raise ValueError("operational request expiry must follow generation")
        expected_action = _CLOSED_ACTIONS.get(
            (self.execution_intent, self.provider_id, self.resource_type)
        )
        if expected_action is None or self.provider_action_id != expected_action:
            raise ValueError("provider action does not match closed semantic translation")
        if self.request_digest != operational_request_digest(self):
            raise ValueError("operational request digest mismatch")
        if self.idempotency_key != operational_idempotency_key(
            self.request_id, self.request_digest
        ):
            raise ValueError("operational idempotency key mismatch")
        approval = self.approval
        if (
            approval.action_request_id != self.request_id
            or approval.action_request_digest != self.request_digest
            or approval.candidate_id != self.candidate_id
            or approval.candidate_fingerprint != self.candidate_fingerprint
            or approval.operational_plan_fingerprint
            != self.candidate_plan_fingerprint
            or approval.provider_id != self.provider_id
            or approval.resource_id != self.resource_id
            or approval.resource_type != self.resource_type
            or approval.target_fingerprint != self.target_fingerprint
            or approval.target_version != self.target_version
            or approval.operation_intent != self.execution_intent
            or approval.disruption_scope != self.disruption_scope
            or approval.verification_digest
            != operational_verification_digest(self.verification)
            or approval.generated_at != self.generated_at
            or approval.expires_at != self.expires_at
        ):
            raise ValueError("operational approval does not bind exact request")
        return self


class OperationalDispatchStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class OperationalDispatchAuditStatus(StrEnum):
    AUTH_ATTEMPTED = "auth_attempted"
    AUTH_REJECTED = "auth_rejected"
    REQUEST_ACCEPTED = "request_accepted"
    EXECUTION_DISABLED = "execution_disabled"
    NO_HANDLER = "no_handler"
    REQUEST_CONFLICT = "request_conflict"
    TARGET_BLOCKED = "target_blocked"
    DISPATCH_RESULT = "dispatch_result"
    BARRIER_CROSSED = "barrier_crossed"
    PROVIDER_OPERATION_CAPTURED = "provider_operation_captured"
    OUTCOME_UNKNOWN = "outcome_unknown"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_RESUMED = "verification_resumed"
    VERIFICATION_SUCCEEDED = "verification_succeeded"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_TARGET_REPLACED = "verification_target_replaced"
    RECOVERY_RECONCILED = "recovery_reconciled"


class OperationalDispatchAuditEvent(OperationalDispatchModel):
    event_id: str
    status: OperationalDispatchAuditStatus
    occurred_at: datetime
    request_id: str | None = None
    request_digest: str | None = None
    workflow_session_id: str | None = None
    candidate_planning_session_id: str | None = None
    candidate_id: str | None = None
    candidate_plan_id: str | None = None
    provider_id: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None
    target_fingerprint: str | None = None


class OperationalDispatchResult(OperationalDispatchModel):
    status: OperationalDispatchStatus
    request_id: str
    request_digest: str
    target_fingerprint: str
    provider_operation_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    sanitized_message: str | None = None


class OperationalVerificationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    VERIFICATION_FAILED = "verification_failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    TARGET_REPLACED = "target_replaced"


class OperationalVerificationResult(OperationalDispatchModel):
    status: OperationalVerificationStatus
    request_id: str
    observed_target_fingerprint: str | None = None
    observed_state: str | None = None
    health_status: str | None = None
    started_at: datetime
    completed_at: datetime
    deadline: datetime


class OperationalLifecycleStatus(OperationalDispatchModel):
    request_id: str
    request_digest: str
    ledger_state: str
    dispatch_result: OperationalDispatchResult | None = None
    verification_result: OperationalVerificationResult | None = None
    verification_resumable: bool = False


def operational_verification_digest(
    verification: OperationalVerificationSpecification,
) -> str:
    payload = {
        "expected_post_state": verification.expected_post_state,
        "health_requirement": verification.health_requirement,
        "identity_fingerprint": verification.identity_fingerprint,
        "pre_state": verification.pre_state,
        "unknown_outcome_policy": verification.unknown_outcome_policy,
        "version": VERIFICATION_DIGEST_VERSION,
    }
    return _digest(VERIFICATION_DIGEST_VERSION, payload)


def operational_request_digest(request: OperationalDispatchRequest) -> str:
    payload = {
        "candidate_fingerprint": request.candidate_fingerprint,
        "candidate_id": request.candidate_id,
        "candidate_plan_fingerprint": request.candidate_plan_fingerprint,
        "candidate_plan_id": request.candidate_plan_id,
        "candidate_planning_session_id": request.candidate_planning_session_id,
        "disruption_scope": request.disruption_scope,
        "effect_kind": request.effect_kind,
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
        "version": REQUEST_DIGEST_VERSION,
        "workflow_session_id": request.workflow_session_id,
    }
    return _digest(REQUEST_DIGEST_VERSION, payload)


def operational_idempotency_key(request_id: str, request_digest: str) -> str:
    return _digest(
        IDEMPOTENCY_KEY_VERSION,
        {
            "request_digest": request_digest,
            "request_id": request_id,
            "version": IDEMPOTENCY_KEY_VERSION,
        },
    )


def _digest(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}:{hashlib.sha256(encoded.encode()).hexdigest()}"
