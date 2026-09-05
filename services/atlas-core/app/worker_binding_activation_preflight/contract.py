"""Closed immutable v0.47 worker binding activation preflight models.

This module is pure contract validation. It has no persistence, store contact,
queue I/O, claim, lease, ack, worker contact, runtime contact, Agent
invocation, execution, installation, deployment, publication, or mutation
behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.execution_permission_grant.contract import (
    CanonicalUuid5,
    OperatorId,
    canonical_json,
)
from app.installation_execution_admission.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.one_shot_dequeue_worker_binding.contract import (
    SUCCESS_BLOCKERS as V046_SUCCESS_BLOCKERS,
)
from app.one_shot_dequeue_worker_binding.contract import (
    OneShotDequeueWorkerBindingStatusV1,
    OneShotDequeueWorkerBindingV1,
)
from app.one_shot_dequeue_worker_binding.contract import (
    binding_record_fingerprint as v046_binding_record_fingerprint,
)
from app.one_shot_dequeue_worker_binding.contract import (
    status_fingerprint as v046_status_fingerprint,
)

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 192 * 1024
MAX_COLLECTION_RECORDS = 100
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.worker_binding_activation_preflight.record"
SCOPE = "worker_binding_activation_preflight_only"
SAFE_MESSAGE = "worker binding activation preflight request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"
_UUID5_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")
_CREDENTIAL_KEYS = frozenset({"credential", "credentials", "secret", "token"})
_ENDPOINT_KEYS = frozenset({"endpoint", "endpoints", "url", "uri"})
_COMMAND_KEYS = frozenset({"command", "commands", "cmd", "shell", "payload"})
_AUTHORITY_FLAGS = frozenset(
    {
        "caller_supplied_credentials_allowed",
        "caller_supplied_endpoint_allowed",
        "caller_supplied_command_allowed",
        "caller_supplied_payload_allowed",
        "payload_schema_defined",
        "payload_constructed",
        "payload_serialized",
        "queue_polling_allowed",
        "queue_claim_allowed",
        "queue_lease_allowed",
        "queue_ack_allowed",
        "queue_consume_allowed",
        "queue_mutation_allowed",
        "worker_store_contact_allowed",
        "worker_runtime_contact_allowed",
        "worker_contact_allowed",
        "worker_start_allowed",
        "worker_invocation_allowed",
        "agent_invocation_allowed",
        "execution_authorization_allowed",
        "execution_start_allowed",
        "process_execution_allowed",
        "store_contact_allowed",
        "runtime_contact_allowed",
        "dispatch_allowed",
        "retry_allowed",
        "resend_allowed",
        "scheduler_allowed",
        "workflow_start_allowed",
        "shell_execution_allowed",
        "provider_mutation_allowed",
        "repository_mutation_allowed",
        "in_guest_mutation_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "replay_bypass_allowed",
        "artifact_publication_allowed",
        "tag_push_allowed",
        "release_publication_allowed",
        "binding_activation_allowed",
    }
)

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v046_binding_not_active",
    "v046_binding_not_recorded",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "unsupported_authority",
    "worker_binding_activation_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v046_binding_not_active",
    "v046_binding_not_recorded",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "unsupported_authority",
    "worker_binding_activation_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
    "worker_binding_activation_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
)


class StrictContractError(ValueError):
    pass


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _visible(value: str) -> str:
    if _VISIBLE.fullmatch(value) is None:
        raise ValueError("idempotency key must be 16-128 visible ASCII bytes")
    return value


VisibleIdempotencyKey = Annotated[str, AfterValidator(_visible)]


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def fingerprint(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _without(value: BaseModel | dict[str, Any], field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


def _bounded(value: BaseModel) -> None:
    if len(canonical_json(value)) > MAX_MODEL_BYTES:
        raise ValueError("contract envelope exceeds bound")


def _ordered(blockers: tuple[BlockerV1, ...]) -> None:
    if len(blockers) != len(set(blockers)):
        raise ValueError("v0.47 blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("v0.47 blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    caller_supplied_credentials_allowed: Literal[False] = False
    caller_supplied_endpoint_allowed: Literal[False] = False
    caller_supplied_command_allowed: Literal[False] = False
    caller_supplied_payload_allowed: Literal[False] = False
    credential_material_present: bool = False
    endpoint_material_present: bool = False
    command_material_present: bool = False
    payload_material_present: bool = False
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    queue_polling_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    queue_consume_allowed: Literal[False] = False
    queue_mutation_allowed: Literal[False] = False
    worker_store_contact_allowed: Literal[False] = False
    worker_runtime_contact_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    worker_invocation_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    execution_authorization_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    process_execution_allowed: Literal[False] = False
    store_contact_allowed: Literal[False] = False
    runtime_contact_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    scheduler_allowed: Literal[False] = False
    workflow_start_allowed: Literal[False] = False
    shell_execution_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False
    artifact_publication_allowed: Literal[False] = False
    tag_push_allowed: Literal[False] = False
    release_publication_allowed: Literal[False] = False
    binding_activation_allowed: Literal[False] = False


class WorkerBindingActivationPreflightCreateV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-create-v1"] = (
        "worker-binding-activation-preflight-create-v1"
    )
    binding_id: CanonicalUuid5
    binding_record_fingerprint: FingerprintV1
    binding_status_fingerprint: FingerprintV1
    binding_valid_until: UtcSecond
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class WorkerBindingActivationPreflightAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-authority-context-v1"] = (
        "worker-binding-activation-preflight-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class WorkerBindingActivationPreflightEvaluationV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-evaluation-v1"] = (
        "worker-binding-activation-preflight-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    preflight_state: Literal["readiness_gated", "blocked"]
    eligibility: Literal["worker_binding_activation_preflight_recorded", "blocked"]
    blockers: tuple[BlockerV1, ...]
    recognized_v046_binding_count: int
    preflight_record_build_allowed: bool
    evaluation_fingerprint: FingerprintV1
    worker_binding_activation_preflight_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightEvaluationV1:
        _ordered(self.blockers)
        allowed = self.preflight_state == "readiness_gated"
        if (
            self.eligibility == "worker_binding_activation_preflight_recorded"
        ) != allowed:
            raise ValueError("v0.47 eligibility mismatch")
        if self.recognized_v046_binding_count != (1 if allowed else 0):
            raise ValueError("v0.46 binding recognition count mismatch")
        if self.preflight_record_build_allowed != allowed:
            raise ValueError("v0.47 build flag mismatch")
        if allowed and (
            self.blockers != SUCCESS_BLOCKERS
            or not self.worker_binding_activation_preflight_recorded
        ):
            raise ValueError("recordable v0.47 preflight shape mismatch")
        if not allowed and self.worker_binding_activation_preflight_recorded:
            raise ValueError("blocked v0.47 preflight shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("v0.47 evaluation fingerprint mismatch")
        _bounded(self)
        return self


class WorkerBindingActivationPreflightV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-v1"] = (
        "worker-binding-activation-preflight-v1"
    )
    preflight_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    preflight_state: Literal["readiness_gated"] = "readiness_gated"
    eligibility: Literal["worker_binding_activation_preflight_recorded"] = (
        "worker_binding_activation_preflight_recorded"
    )
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    one_shot_dequeue_worker_binding: OneShotDequeueWorkerBindingV1
    one_shot_dequeue_worker_binding_status: OneShotDequeueWorkerBindingStatusV1
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    preflight_record_fingerprint: FingerprintV1
    worker_binding_activation_preflight_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("v0.47 preflight blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("v0.47 preflight expiry exceeds freshness bound")
        binding, status = (
            self.one_shot_dequeue_worker_binding,
            self.one_shot_dequeue_worker_binding_status,
        )
        if (
            self.operator_id != binding.operator_id
            or self.operator_id != status.operator_id
            or self.candidate_record_id != binding.candidate_record_id
            or self.candidate_record_id != status.candidate_record_id
            or status.binding_id != binding.binding_id
            or status.binding_record_fingerprint != binding.binding_record_fingerprint
            or self.valid_until > binding.valid_until
            or self.valid_until > status.valid_until
        ):
            raise ValueError("v0.47 preflight ownership or linkage mismatch")
        if (
            self.binding_subject_fingerprint != binding.subject_fingerprint
            or self.worker_subject_fingerprint != binding.worker_subject_fingerprint
            or self.queue_item_reference_fingerprint
            != binding.queue_item_reference_fingerprint
            or self.inherited_limits_fingerprint != binding.inherited_limits_fingerprint
        ):
            raise ValueError("v0.47 preflight subject or limits mismatch")
        if self.subject_fingerprint != preflight_subject_fingerprint(self):
            raise ValueError("v0.47 preflight subject fingerprint mismatch")
        if self.preflight_id != derived_preflight_id(self.subject_fingerprint):
            raise ValueError("v0.47 preflight id mismatch")
        if self.preflight_record_fingerprint != preflight_record_fingerprint(self):
            raise ValueError("v0.47 preflight record fingerprint mismatch")
        _bounded(self)
        return self


class WorkerBindingActivationPreflightStatusV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-status-v1"] = (
        "worker-binding-activation-preflight-status-v1"
    )
    preflight_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    lifecycle: Literal["active", "expired"]
    preflight_state: Literal["worker_binding_activation_preflight_recorded"]
    eligibility: Literal["worker_binding_activation_preflight_recorded"]
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    preflight_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    worker_binding_activation_preflight_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightStatusV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("v0.47 preflight status blockers are fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("v0.47 preflight status fingerprint mismatch")
        _bounded(self)
        return self


class WorkerBindingActivationPreflightIdempotencyReservationV1(ContractModel):
    schema: Literal["worker-binding-activation-preflight-idempotency-reservation-v1"] = (
        "worker-binding-activation-preflight-idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    preflight_id: CanonicalUuid5
    preflight_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    permanent: Literal[True] = True


class WorkerBindingActivationPreflightSubjectReservationV1(ContractModel):
    schema: Literal["worker-binding-activation-preflight-subject-reservation-v1"] = (
        "worker-binding-activation-preflight-subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    preflight_id: CanonicalUuid5
    preflight_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightSubjectReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("v0.47 preflight reservation fingerprint mismatch")
        return self


class WorkerBindingActivationPreflightAuditEvidenceV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-audit-v1"] = (
        "worker-binding-activation-preflight-audit-v1"
    )
    event: Literal[
        "worker_binding_activation_preflight_recorded",
        "worker_binding_activation_preflight_read",
        "worker_binding_activation_preflight_indeterminate",
    ]
    audit_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    preflight_id: CanonicalUuid5 | None
    occurred_at: UtcSecond
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"]
    correlation_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1 | None
    preflight_record_fingerprint: FingerprintV1 | None
    audit_fingerprint: FingerprintV1
    worker_binding_activation_preflight_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("v0.47 preflight audit fingerprint mismatch")
        return self


class WorkerBindingActivationPreflightRedactedErrorV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-error-v1"] = (
        "worker-binding-activation-preflight-error-v1"
    )
    error_code: Literal[
        "installation_capability_unsupported",
        "evidence_not_found",
        "ownership_mismatch",
        "permission_scope_missing",
        "v046_binding_not_active",
        "v046_binding_not_recorded",
        "linkage_mismatch",
        "fingerprint_mismatch",
        "inherited_limits_mismatch",
        "evidence_stale",
        "evidence_expired",
        "ambiguous_state",
        "caller_supplied_credential",
        "caller_supplied_endpoint",
        "caller_supplied_command",
        "unsupported_authority",
        "reservation_before_effect_failed",
        "permanent_subject_reserved",
        "idempotency_conflict",
        "append_indeterminate",
        "unauthenticated",
        "forbidden",
        "not_found",
        "invalid_request",
        "rate_limited",
        "quota_exceeded",
        "conflict",
        "record_too_large",
        "store_corrupt",
        "internal_error",
    ]
    message: Literal[SAFE_MESSAGE] = SAFE_MESSAGE
    retryable: Literal[False] = False
    correlation_fingerprint: FingerprintV1
    redacted: Literal[True] = True
    worker_binding_activation_preflight_recorded: Literal[False] = False


class WorkerBindingActivationPreflightResultV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-result-v1"] = (
        "worker-binding-activation-preflight-result-v1"
    )
    ok: bool
    outcome: Literal["success", "failure", "indeterminate"]
    record: WorkerBindingActivationPreflightV1 | None
    status: WorkerBindingActivationPreflightStatusV1 | None
    error: WorkerBindingActivationPreflightRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1
    worker_binding_activation_preflight_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightResultV1:
        if self.outcome == "success":
            good = (
                self.ok
                and self.record is not None
                and self.status is not None
                and self.error is None
                and self.worker_binding_activation_preflight_recorded
            )
        else:
            good = (
                not self.ok
                and self.record is None
                and self.status is None
                and self.error is not None
                and not self.worker_binding_activation_preflight_recorded
            )
        if not good:
            raise ValueError("v0.47 preflight result shape mismatch")
        if self.record is not None and self.status.preflight_id != self.record.preflight_id:
            raise ValueError("v0.47 preflight result status mismatch")
        _bounded(self)
        return self


class WorkerBindingActivationPreflightCollectionV1(ClosedAuthorityV1):
    schema: Literal["worker-binding-activation-preflight-collection-v1"] = (
        "worker-binding-activation-preflight-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[WorkerBindingActivationPreflightV1, ...]
    count: int
    collection_fingerprint: FingerprintV1
    worker_binding_activation_preflight_recorded: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("v0.47 preflight collection exceeds bound")
        ordered = tuple(
            sorted(self.items, key=lambda item: (item.recorded_at, item.preflight_id))
        )
        if ordered != self.items:
            raise ValueError("v0.47 preflight collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("v0.47 preflight collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("v0.47 preflight collection fingerprint mismatch")
        _bounded(self)
        return self


class WorkerBindingActivationPreflightValidationInputV1(ContractModel):
    """Injected facts only; no store, runtime, queue, worker, endpoint, or I/O."""

    operator_id: OperatorId
    authority: WorkerBindingActivationPreflightAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: WorkerBindingActivationPreflightCreateV1
    one_shot_dequeue_worker_binding: OneShotDequeueWorkerBindingV1
    one_shot_dequeue_worker_binding_status: OneShotDequeueWorkerBindingStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    ambiguous_binding_count: int = 0
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerBindingActivationPreflightValidationInputV1:
        binding = self.one_shot_dequeue_worker_binding
        status = self.one_shot_dequeue_worker_binding_status
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if self.ambiguous_binding_count != 0:
            raise ValueError("ambiguous v0.46 binding")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or binding.operator_id != self.operator_id
            or status.operator_id != self.operator_id
        ):
            raise ValueError("v0.47 ownership mismatch")
        if (
            binding.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("v0.47 candidate linkage mismatch")
        if (
            self.create.binding_id != binding.binding_id
            or self.create.binding_valid_until != binding.valid_until
            or status.binding_id != binding.binding_id
            or status.binding_record_fingerprint != binding.binding_record_fingerprint
        ):
            raise ValueError("v0.46 binding linkage mismatch")
        if (
            self.create.binding_record_fingerprint
            != binding.binding_record_fingerprint
            or self.create.binding_status_fingerprint != status.status_fingerprint
            or binding.binding_record_fingerprint
            != v046_binding_record_fingerprint(binding)
            or status.status_fingerprint != v046_status_fingerprint(status)
        ):
            raise ValueError("v0.46 binding fingerprint mismatch")
        if status.lifecycle != "active":
            raise ValueError("v0.46 binding is not active")
        if (
            binding.lifecycle != "active"
            or binding.binding_state != "readiness_gated"
            or binding.eligibility != "one_shot_dequeue_worker_binding_recorded"
            or status.binding_state != "one_shot_dequeue_worker_binding_recorded"
            or status.eligibility != "one_shot_dequeue_worker_binding_recorded"
            or binding.blockers != V046_SUCCESS_BLOCKERS
            or status.blockers != V046_SUCCESS_BLOCKERS
            or not binding.one_shot_dequeue_worker_binding_recorded
            or not status.one_shot_dequeue_worker_binding_recorded
        ):
            raise ValueError("v0.46 binding is not recorded")
        if (
            self.create.binding_subject_fingerprint != binding.subject_fingerprint
            or self.create.worker_subject_fingerprint
            != binding.worker_subject_fingerprint
            or self.create.queue_item_reference_fingerprint
            != binding.queue_item_reference_fingerprint
        ):
            raise ValueError("v0.46 binding fingerprint mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != binding.inherited_limits_fingerprint
        ):
            raise ValueError("v0.46 binding inherited limits mismatch")
        if (
            self.authority.credential_material_present
            or self.create.credential_material_present
        ):
            raise ValueError("caller supplied credential")
        if (
            self.authority.endpoint_material_present
            or self.create.endpoint_material_present
        ):
            raise ValueError("caller supplied endpoint")
        if self.authority.command_material_present or self.create.command_material_present:
            raise ValueError("caller supplied command")
        if self.authority.payload_material_present or self.create.payload_material_present:
            raise ValueError("caller supplied command")
        if any(getattr(self.authority, flag) for flag in _AUTHORITY_FLAGS):
            raise ValueError("unsupported authority")
        now = _instant(self.authority.request_received_at)
        starts = (_instant(binding.recorded_at), _instant(status.evaluated_at))
        if any(
            value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS)
            for value in starts
        ):
            raise ValueError("v0.46 binding evidence is stale or from the future")
        expiries = (_instant(binding.valid_until), _instant(status.valid_until))
        if any(now >= expiry for expiry in expiries):
            raise ValueError("v0.46 binding evidence is expired")
        return self


def build_create(
    *,
    binding: OneShotDequeueWorkerBindingV1,
    binding_status: OneShotDequeueWorkerBindingStatusV1,
) -> WorkerBindingActivationPreflightCreateV1:
    return WorkerBindingActivationPreflightCreateV1(
        binding_id=binding.binding_id,
        binding_record_fingerprint=binding.binding_record_fingerprint,
        binding_status_fingerprint=binding_status.status_fingerprint,
        binding_valid_until=binding.valid_until,
        binding_subject_fingerprint=binding.subject_fingerprint,
        worker_subject_fingerprint=binding.worker_subject_fingerprint,
        queue_item_reference_fingerprint=binding.queue_item_reference_fingerprint,
        inherited_limits_fingerprint=binding.inherited_limits_fingerprint,
    )


def evaluate_worker_binding_activation_preflight(
    value: WorkerBindingActivationPreflightValidationInputV1 | dict[str, Any],
) -> WorkerBindingActivationPreflightEvaluationV1:
    preflight_blocker = _preflight_blocker(value)
    if preflight_blocker is not None:
        return _blocked_evaluation(value, preflight_blocker)
    try:
        validation = (
            value
            if isinstance(value, WorkerBindingActivationPreflightValidationInputV1)
            else WorkerBindingActivationPreflightValidationInputV1.model_validate(value)
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    earliest = min(
        _instant(validation.one_shot_dequeue_worker_binding.valid_until),
        _instant(validation.one_shot_dequeue_worker_binding_status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest,
        preflight_state="readiness_gated",
        eligibility="worker_binding_activation_preflight_recorded",
        blockers=SUCCESS_BLOCKERS,
    )


def _preflight_blocker(
    value: WorkerBindingActivationPreflightValidationInputV1 | dict[str, Any],
) -> BlockerV1 | None:
    if isinstance(value, BaseModel) or not isinstance(value, dict):
        return None
    if value.get("ambiguous_binding_count", 0):
        return "ambiguous_state"
    for section_name in ("create", "authority"):
        section = value.get(section_name)
        if not isinstance(section, dict):
            continue
        keys = set(section)
        if keys & _CREDENTIAL_KEYS or section.get("credential_material_present"):
            return "caller_supplied_credential"
        if keys & _ENDPOINT_KEYS or section.get("endpoint_material_present"):
            return "caller_supplied_endpoint"
        if (
            keys & _COMMAND_KEYS
            or section.get("command_material_present")
            or section.get("payload_material_present")
        ):
            return "caller_supplied_command"
        if any(section.get(flag) for flag in _AUTHORITY_FLAGS):
            return "unsupported_authority"
    binding = value.get("one_shot_dequeue_worker_binding")
    status = value.get("one_shot_dequeue_worker_binding_status")
    if isinstance(binding, dict) and binding.get("lifecycle", "active") != "active":
        return "v046_binding_not_active"
    if isinstance(status, dict) and status.get("lifecycle", "active") != "active":
        return "v046_binding_not_active"
    if isinstance(binding, dict) and (
        binding.get("binding_state", "readiness_gated") != "readiness_gated"
        or binding.get("eligibility", "one_shot_dequeue_worker_binding_recorded")
        != "one_shot_dequeue_worker_binding_recorded"
        or binding.get("one_shot_dequeue_worker_binding_recorded", True) is not True
    ):
        return "v046_binding_not_recorded"
    if isinstance(status, dict) and (
        status.get("binding_state", "one_shot_dequeue_worker_binding_recorded")
        != "one_shot_dequeue_worker_binding_recorded"
        or status.get("eligibility", "one_shot_dequeue_worker_binding_recorded")
        != "one_shot_dequeue_worker_binding_recorded"
        or status.get("one_shot_dequeue_worker_binding_recorded", True) is not True
    ):
        return "v046_binding_not_recorded"
    keys = set(value)
    if keys & _CREDENTIAL_KEYS:
        return "caller_supplied_credential"
    if keys & _ENDPOINT_KEYS:
        return "caller_supplied_endpoint"
    if keys & _COMMAND_KEYS:
        return "caller_supplied_command"
    return None


def _evaluation(
    *,
    operator_id: str,
    candidate_record_id: str,
    evaluated_at: str,
    earliest_expiry: str | None,
    preflight_state: Literal["readiness_gated", "blocked"],
    eligibility: Literal["worker_binding_activation_preflight_recorded", "blocked"],
    blockers: tuple[BlockerV1, ...],
) -> WorkerBindingActivationPreflightEvaluationV1:
    allowed = preflight_state == "readiness_gated"
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "preflight_state": preflight_state,
        "eligibility": eligibility,
        "blockers": blockers,
        "recognized_v046_binding_count": 1 if allowed else 0,
        "preflight_record_build_allowed": allowed,
        "worker_binding_activation_preflight_recorded": allowed,
    }
    seed = WorkerBindingActivationPreflightEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return WorkerBindingActivationPreflightEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: WorkerBindingActivationPreflightValidationInputV1 | dict[str, Any],
    reason: str,
) -> WorkerBindingActivationPreflightEvaluationV1:
    if isinstance(value, BaseModel):
        raw = value.model_dump(mode="python")
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        raw = {}
    authority = raw.get("authority") if isinstance(raw.get("authority"), dict) else {}
    operator_id = raw.get("operator_id") or authority.get("authenticated_operator_id")
    candidate_record_id = raw.get("candidate_record_id")
    return _evaluation(
        operator_id=operator_id or _BLOCKED_OPERATOR_ID,
        candidate_record_id=candidate_record_id or _BLOCKED_CANDIDATE_ID,
        evaluated_at=authority.get("request_received_at") or "1970-01-01T00:00:00Z",
        earliest_expiry=None,
        preflight_state="blocked",
        eligibility="blocked",
        blockers=(_blocker_from_reason(reason),),
    )


def _blocker_from_reason(reason: str) -> BlockerV1:
    lowered = reason.lower()
    if lowered in BLOCKER_ORDER:
        return lowered  # type: ignore[return-value]
    if "home assistant" in lowered or "unsupported capability" in lowered:
        return "installation_capability_unsupported"
    if "ownership" in lowered:
        return "ownership_mismatch"
    if "permission" in lowered:
        return "permission_scope_missing"
    if "not active" in lowered and "v0.46" in lowered:
        return "v046_binding_not_active"
    if "not recorded" in lowered and "v0.46" in lowered:
        return "v046_binding_not_recorded"
    if "linkage" in lowered:
        return "linkage_mismatch"
    if "limits" in lowered:
        return "inherited_limits_mismatch"
    if "fingerprint" in lowered:
        return "fingerprint_mismatch"
    if "stale" in lowered or "future" in lowered:
        return "evidence_stale"
    if "expired" in lowered:
        return "evidence_expired"
    if "ambiguous" in lowered:
        return "ambiguous_state"
    if "credential" in lowered:
        return "caller_supplied_credential"
    if "endpoint" in lowered:
        return "caller_supplied_endpoint"
    if "command" in lowered or "payload" in lowered:
        return "caller_supplied_command"
    if "unsupported authority" in lowered:
        return "unsupported_authority"
    return "evidence_not_found"


def evaluation_fingerprint(
    value: WorkerBindingActivationPreflightEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def derived_uuid5(domain: str, value: Any) -> str:
    seed = fingerprint(domain, value).value
    return str(uuid.uuid5(_UUID5_NAMESPACE, f"{domain}:{seed}"))


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:worker-binding-activation-preflight-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerBindingActivationPreflightCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def preflight_subject_fingerprint(
    value: WorkerBindingActivationPreflightV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    binding = raw["one_shot_dequeue_worker_binding"]
    status = raw["one_shot_dequeue_worker_binding_status"]
    return fingerprint(
        "atlas:worker-binding-activation-preflight-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "binding_id": binding["binding_id"],
            "binding_record_fingerprint": binding["binding_record_fingerprint"],
            "binding_status_fingerprint": status["status_fingerprint"],
            "binding_subject_fingerprint": binding["subject_fingerprint"],
            "worker_subject_fingerprint": binding["worker_subject_fingerprint"],
            "queue_item_reference_fingerprint": binding[
                "queue_item_reference_fingerprint"
            ],
            "inherited_limits_fingerprint": binding["inherited_limits_fingerprint"],
        },
    )


def reservation_subject_fingerprint(
    validation: WorkerBindingActivationPreflightValidationInputV1 | dict[str, Any],
) -> FingerprintV1:
    raw = validation.model_dump(mode="json") if isinstance(validation, BaseModel) else dict(validation)
    binding = raw["one_shot_dequeue_worker_binding"]
    return fingerprint(
        "atlas:worker-binding-activation-preflight-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "binding_id": binding["binding_id"],
            "binding_record_fingerprint": raw["create"]["binding_record_fingerprint"],
            "binding_status_fingerprint": raw["create"]["binding_status_fingerprint"],
            "binding_subject_fingerprint": raw["create"]["binding_subject_fingerprint"],
            "worker_subject_fingerprint": raw["create"]["worker_subject_fingerprint"],
            "queue_item_reference_fingerprint": raw["create"][
                "queue_item_reference_fingerprint"
            ],
            "inherited_limits_fingerprint": raw["create"][
                "inherited_limits_fingerprint"
            ],
        },
    )


def derived_preflight_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5(
        "atlas:worker-binding-activation-preflight-id:v1", subject_fingerprint
    )


def preflight_record_fingerprint(
    value: WorkerBindingActivationPreflightV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-record:v1",
        _without(value, "preflight_record_fingerprint"),
    )


def status_fingerprint(
    value: WorkerBindingActivationPreflightStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-status:v1",
        _without(value, "status_fingerprint"),
    )


def reservation_fingerprint(
    value: WorkerBindingActivationPreflightSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def audit_fingerprint(
    value: WorkerBindingActivationPreflightAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: WorkerBindingActivationPreflightCollectionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-binding-activation-preflight-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def build_preflight(
    validation: WorkerBindingActivationPreflightValidationInputV1,
) -> WorkerBindingActivationPreflightV1:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.one_shot_dequeue_worker_binding.valid_until),
        _instant(validation.one_shot_dequeue_worker_binding_status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = reservation_subject_fingerprint(validation)
    raw = {
        "preflight_id": derived_preflight_id(subject),
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "one_shot_dequeue_worker_binding": validation.one_shot_dequeue_worker_binding,
        "one_shot_dequeue_worker_binding_status": (
            validation.one_shot_dequeue_worker_binding_status
        ),
        "binding_subject_fingerprint": validation.create.binding_subject_fingerprint,
        "worker_subject_fingerprint": validation.create.worker_subject_fingerprint,
        "queue_item_reference_fingerprint": (
            validation.create.queue_item_reference_fingerprint
        ),
        "inherited_limits_fingerprint": validation.create.inherited_limits_fingerprint,
        "subject_fingerprint": subject,
        "idempotency_key_fingerprint": idempotency_key_fingerprint(
            validation.operator_id, validation.idempotency_key
        ),
    }
    seed = WorkerBindingActivationPreflightV1.model_construct(
        **raw,
        preflight_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    return WorkerBindingActivationPreflightV1.model_validate(
        {**raw, "preflight_record_fingerprint": preflight_record_fingerprint(seed)}
    )


def build_reservations(
    validation: WorkerBindingActivationPreflightValidationInputV1,
    record: WorkerBindingActivationPreflightV1,
) -> tuple[
    WorkerBindingActivationPreflightIdempotencyReservationV1,
    WorkerBindingActivationPreflightSubjectReservationV1,
]:
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request_fp = request_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        create=validation.create,
        request_received_at=validation.authority.request_received_at,
        idempotency_fingerprint=idem,
    )
    raw = {
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request_fp,
        "subject_fingerprint": record.subject_fingerprint,
        "preflight_id": record.preflight_id,
        "preflight_record_fingerprint": record.preflight_record_fingerprint,
        "reserved_at": validation.authority.request_received_at,
    }
    idempotency = WorkerBindingActivationPreflightIdempotencyReservationV1.model_validate(
        raw
    )
    reservation_seed = (
        WorkerBindingActivationPreflightSubjectReservationV1.model_construct(
            **raw,
            reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
        )
    )
    reservation = WorkerBindingActivationPreflightSubjectReservationV1.model_validate(
        {**raw, "reservation_fingerprint": reservation_fingerprint(reservation_seed)}
    )
    return idempotency, reservation


def build_audit(
    record: WorkerBindingActivationPreflightV1,
    *,
    event: Literal[
        "worker_binding_activation_preflight_recorded",
        "worker_binding_activation_preflight_read",
        "worker_binding_activation_preflight_indeterminate",
    ],
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> WorkerBindingActivationPreflightAuditEvidenceV1:
    raw = {
        "event": event,
        "audit_id": derived_uuid5(
            "atlas:worker-binding-activation-preflight-audit-id:v1",
            {
                "operator_id": record.operator_id,
                "candidate_record_id": record.candidate_record_id,
                "preflight_id": record.preflight_id,
                "event": event,
                "outcome": outcome,
                "correlation_fingerprint": correlation_fingerprint,
                "occurred_at": occurred_at,
            },
        ),
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "preflight_id": record.preflight_id,
        "occurred_at": occurred_at,
        "outcome": outcome,
        "correlation_fingerprint": correlation_fingerprint,
        "subject_fingerprint": record.subject_fingerprint,
        "preflight_record_fingerprint": record.preflight_record_fingerprint,
        "worker_binding_activation_preflight_recorded": outcome == "recorded",
    }
    seed = WorkerBindingActivationPreflightAuditEvidenceV1.model_construct(
        **raw,
        audit_fingerprint=fingerprint("atlas:seed:v1", "audit"),
    )
    return WorkerBindingActivationPreflightAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_fingerprint(seed)}
    )


def derive_status(
    record: WorkerBindingActivationPreflightV1,
    *,
    evaluated_at: str,
) -> WorkerBindingActivationPreflightStatusV1:
    raw = {
        "preflight_id": record.preflight_id,
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "lifecycle": (
            "expired" if _instant(evaluated_at) >= _instant(record.valid_until) else "active"
        ),
        "preflight_state": "worker_binding_activation_preflight_recorded",
        "eligibility": record.eligibility,
        "blockers": record.blockers,
        "evaluated_at": evaluated_at,
        "valid_until": record.valid_until,
        "preflight_record_fingerprint": record.preflight_record_fingerprint,
    }
    seed = WorkerBindingActivationPreflightStatusV1.model_construct(
        **raw,
        status_fingerprint=fingerprint("atlas:seed:v1", "status"),
    )
    return WorkerBindingActivationPreflightStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[WorkerBindingActivationPreflightV1, ...],
) -> WorkerBindingActivationPreflightCollectionV1:
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": items,
        "count": len(items),
    }
    seed = WorkerBindingActivationPreflightCollectionV1.model_construct(
        **raw,
        collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
    )
    return WorkerBindingActivationPreflightCollectionV1.model_validate(
        {**raw, "collection_fingerprint": collection_fingerprint(seed)}
    )


def parse_create_json(raw: bytes | str) -> WorkerBindingActivationPreflightCreateV1:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 16 KiB")
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise StrictContractError("create request must be UTF-8") from error
    if unicodedata.normalize("NFC", decoded) != decoded:
        raise StrictContractError("create request must be NFC normalized")
    try:
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as error:
        raise StrictContractError("invalid strict create JSON") from error
    if not isinstance(parsed, dict):
        raise StrictContractError("create request must be an object")
    return WorkerBindingActivationPreflightCreateV1.model_validate(parsed)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictContractError(f"duplicate key: {key}")
        result[key] = value
    return result
