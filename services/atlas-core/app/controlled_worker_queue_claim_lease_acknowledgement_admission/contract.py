"""Closed immutable v0.51 queue claim/lease/ack admission models.

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

from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    SUCCESS_BLOCKERS as V050_SUCCESS_BLOCKERS,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    prerequisite_record_fingerprint as v050_record_fingerprint,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.contract import (
    prerequisite_status_fingerprint as v050_status_fingerprint,
)
from app.execution_permission_grant.contract import (
    CanonicalUuid5,
    OperatorId,
    canonical_json,
)
from app.installation_execution_admission.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 192 * 1024
MAX_COLLECTION_RECORDS = 100
MAX_FRESHNESS_SECONDS = 30
PERMISSION = (
    "installation.execution."
    "controlled_worker_queue_claim_lease_acknowledgement_admission.evaluate"
)
SCOPE = "controlled_worker_queue_claim_lease_acknowledgement_admission_only"
SAFE_MESSAGE = (
    "controlled worker queue claim lease acknowledgement admission request "
    "could not be completed"
)
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"
_UUID5_NAMESPACE = uuid.UUID("1f397d2d-6b71-4bba-9f70-9d4f0d1f7a51")
_CREDENTIAL_KEYS = frozenset(
    {"credential", "credentials", "secret", "token", "claim_token", "lease_token"}
)
_ENDPOINT_KEYS = frozenset({"endpoint", "endpoints", "url", "uri"})
_COMMAND_KEYS = frozenset(
    {"command", "commands", "cmd", "shell", "payload", "ack_handle"}
)
_AUTHORITY_FLAGS = frozenset(
    {
        "caller_supplied_credentials_allowed",
        "caller_supplied_endpoint_allowed",
        "caller_supplied_command_allowed",
        "caller_supplied_payload_allowed",
        "caller_supplied_queue_selector_allowed",
        "caller_supplied_claim_token_allowed",
        "caller_supplied_lease_token_allowed",
        "caller_supplied_acknowledgement_handle_allowed",
        "payload_schema_defined",
        "payload_constructed",
        "payload_serialized",
        "queue_adapter_defined",
        "queue_polling_allowed",
        "queue_claim_allowed",
        "queue_lease_allowed",
        "queue_ack_allowed",
        "queue_consume_allowed",
        "queue_requeue_allowed",
        "queue_mutation_allowed",
        "worker_activation_runtime_allowed",
        "worker_store_contact_allowed",
        "worker_runtime_contact_allowed",
        "worker_contact_allowed",
        "worker_start_admission_allowed",
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
        "queue_claimed",
        "queue_leased",
        "queue_acknowledged",
        "worker_start_admitted",
        "worker_started",
        "agent_invoked",
        "execution_started",
        "later_queue_claim_lease_acknowledgement_allowed",
        "worker_start_admission_build_allowed",
        "execution_start_admission_build_allowed",
        "runtime_effect_allowed",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
    }
)

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v050_prerequisite_not_active",
    "v050_prerequisite_not_frozen",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "caller_supplied_queue_selector",
    "caller_supplied_claim_token",
    "caller_supplied_lease_token",
    "caller_supplied_acknowledgement_handle",
    "unsupported_authority",
    "queue_adapter_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_activation_runtime_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_admission_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v050_prerequisite_not_active",
    "v050_prerequisite_not_frozen",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "caller_supplied_queue_selector",
    "caller_supplied_claim_token",
    "caller_supplied_lease_token",
    "caller_supplied_acknowledgement_handle",
    "unsupported_authority",
    "queue_adapter_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_activation_runtime_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_admission_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
    "queue_adapter_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_activation_runtime_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_admission_not_defined",
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
        raise ValueError("v0.51 blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("v0.51 blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    caller_supplied_credentials_allowed: Literal[False] = False
    caller_supplied_endpoint_allowed: Literal[False] = False
    caller_supplied_command_allowed: Literal[False] = False
    caller_supplied_payload_allowed: Literal[False] = False
    caller_supplied_queue_selector_allowed: Literal[False] = False
    caller_supplied_claim_token_allowed: Literal[False] = False
    caller_supplied_lease_token_allowed: Literal[False] = False
    caller_supplied_acknowledgement_handle_allowed: Literal[False] = False
    credential_material_present: bool = False
    endpoint_material_present: bool = False
    command_material_present: bool = False
    payload_material_present: bool = False
    queue_selector_material_present: bool = False
    claim_token_material_present: bool = False
    lease_token_material_present: bool = False
    acknowledgement_handle_material_present: bool = False
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    queue_adapter_defined: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    queue_consume_allowed: Literal[False] = False
    queue_requeue_allowed: Literal[False] = False
    queue_mutation_allowed: Literal[False] = False
    worker_activation_runtime_allowed: Literal[False] = False
    worker_store_contact_allowed: Literal[False] = False
    worker_runtime_contact_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_start_admission_allowed: Literal[False] = False
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
    queue_claimed: Literal[False] = False
    queue_leased: Literal[False] = False
    queue_acknowledged: Literal[False] = False
    worker_start_admitted: Literal[False] = False
    worker_started: Literal[False] = False
    agent_invoked: Literal[False] = False
    execution_started: Literal[False] = False


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-create-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-create-v1"
    prerequisite_id: CanonicalUuid5
    prerequisite_record_fingerprint: FingerprintV1
    prerequisite_status_fingerprint: FingerprintV1
    prerequisite_valid_until: UtcSecond
    v049_admission_record_fingerprint: FingerprintV1
    v049_admission_status_fingerprint: FingerprintV1
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def exact(self) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityContextV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-authority-context-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-admission-"
        "authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-evaluation-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-evaluation-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    admission_state: Literal["recorded", "blocked"]
    eligibility: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        "blocked",
    ]
    blockers: tuple[BlockerV1, ...]
    recognized_v050_prerequisite_count: int
    later_queue_claim_lease_acknowledgement_allowed: Literal[False] = False
    worker_start_admission_build_allowed: Literal[False] = False
    execution_start_admission_build_allowed: Literal[False] = False
    runtime_effect_allowed: Literal[False] = False
    evaluation_fingerprint: FingerprintV1
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: bool = (
        False
    )

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1:
        _ordered(self.blockers)
        recorded = self.admission_state == "recorded"
        if (
            self.eligibility
            == "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
        ) != recorded:
            raise ValueError("v0.51 eligibility mismatch")
        if self.recognized_v050_prerequisite_count != (1 if recorded else 0):
            raise ValueError("v0.50 prerequisite recognition count mismatch")
        if recorded and (
            self.blockers != SUCCESS_BLOCKERS
            or not self.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
        ):
            raise ValueError("recorded v0.51 admission shape mismatch")
        if (
            not recorded
            and self.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
        ):
            raise ValueError("blocked v0.51 admission shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("v0.51 evaluation fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1(ClosedAuthorityV1):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-v1"
    admission_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    admission_state: Literal["recorded"] = "recorded"
    eligibility: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
    ] = "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1
    )
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1
    )
    prerequisite_id: CanonicalUuid5
    prerequisite_record_fingerprint: FingerprintV1
    prerequisite_status_fingerprint: FingerprintV1
    v049_admission_record_fingerprint: FingerprintV1
    v049_admission_status_fingerprint: FingerprintV1
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    admission_record_fingerprint: FingerprintV1
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: (
        Literal[True]
    ) = True

    @model_validator(mode="after")
    def exact(self) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("v0.51 admission blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("v0.51 admission expiry exceeds freshness bound")
        prerequisite = (
            self.controlled_worker_queue_claim_lease_acknowledgement_prerequisite
        )
        status = (
            self.controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status
        )
        if (
            self.operator_id != prerequisite.operator_id
            or self.operator_id != status.operator_id
            or self.candidate_record_id != prerequisite.candidate_record_id
            or self.candidate_record_id != status.candidate_record_id
            or self.prerequisite_id != prerequisite.prerequisite_id
            or status.prerequisite_id != prerequisite.prerequisite_id
            or status.prerequisite_record_fingerprint
            != prerequisite.prerequisite_record_fingerprint
            or self.valid_until > prerequisite.valid_until
            or self.valid_until > status.valid_until
        ):
            raise ValueError("v0.51 admission ownership or linkage mismatch")
        if (
            self.prerequisite_record_fingerprint
            != prerequisite.prerequisite_record_fingerprint
            or self.prerequisite_status_fingerprint != status.status_fingerprint
            or self.v049_admission_record_fingerprint
            != prerequisite.admission_record_fingerprint
            or self.v049_admission_status_fingerprint
            != prerequisite.admission_status_fingerprint
            or self.binding_subject_fingerprint
            != prerequisite.binding_subject_fingerprint
            or self.worker_subject_fingerprint != prerequisite.worker_subject_fingerprint
            or self.queue_item_reference_fingerprint
            != prerequisite.queue_item_reference_fingerprint
            or self.inherited_limits_fingerprint
            != prerequisite.inherited_limits_fingerprint
        ):
            raise ValueError("v0.51 admission subject or limits mismatch")
        if self.subject_fingerprint != admission_subject_fingerprint(self):
            raise ValueError("v0.51 admission subject fingerprint mismatch")
        if self.admission_id != derived_admission_id(self.subject_fingerprint):
            raise ValueError("v0.51 admission id mismatch")
        if self.admission_record_fingerprint != admission_record_fingerprint(self):
            raise ValueError("v0.51 admission record fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-status-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-status-v1"
    admission_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    lifecycle: Literal["active", "expired"]
    admission_state: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
    ]
    eligibility: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
    ]
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    admission_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: (
        Literal[True]
    ) = True

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("v0.51 admission status blockers are fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("v0.51 admission status fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionIdempotencyReservationV1(
    ContractModel
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-idempotency-reservation-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-admission-"
        "idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    admission_id: CanonicalUuid5
    admission_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    permanent: Literal[True] = True


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionSubjectReservationV1(
    ContractModel
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-subject-reservation-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-admission-"
        "subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    admission_id: CanonicalUuid5
    admission_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionSubjectReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("v0.51 admission reservation fingerprint mismatch")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuditEvidenceV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-audit-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-audit-v1"
    event: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_read",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_indeterminate",
    ]
    audit_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    admission_id: CanonicalUuid5 | None
    occurred_at: UtcSecond
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"]
    correlation_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1 | None
    admission_record_fingerprint: FingerprintV1 | None
    audit_fingerprint: FingerprintV1
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: bool = (
        False
    )

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("v0.51 admission audit fingerprint mismatch")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionRedactedErrorV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-error-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-error-v1"
    error_code: Literal[
        "installation_capability_unsupported",
        "evidence_not_found",
        "ownership_mismatch",
        "permission_scope_missing",
        "v050_prerequisite_not_active",
        "v050_prerequisite_not_frozen",
        "linkage_mismatch",
        "fingerprint_mismatch",
        "inherited_limits_mismatch",
        "evidence_stale",
        "evidence_expired",
        "ambiguous_state",
        "caller_supplied_credential",
        "caller_supplied_endpoint",
        "caller_supplied_command",
        "caller_supplied_queue_selector",
        "caller_supplied_claim_token",
        "caller_supplied_lease_token",
        "caller_supplied_acknowledgement_handle",
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
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: (
        Literal[False]
    ) = False


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-result-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-result-v1"
    ok: bool
    outcome: Literal["success", "failure", "indeterminate"]
    record: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 | None
    status: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1 | None
    error: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: bool = (
        False
    )

    @model_validator(mode="after")
    def exact(self) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultV1:
        if self.outcome == "success":
            good = (
                self.ok
                and self.record is not None
                and self.status is not None
                and self.error is None
                and self.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
            )
        else:
            good = (
                not self.ok
                and self.record is None
                and self.status is None
                and self.error is not None
                and not self.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
            )
        if not good:
            raise ValueError("v0.51 admission result shape mismatch")
        if self.record is not None and self.status.admission_id != self.record.admission_id:
            raise ValueError("v0.51 admission result status mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-admission-collection-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-admission-collection-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1, ...]
    count: int
    collection_fingerprint: FingerprintV1
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: (
        Literal[False]
    ) = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("v0.51 admission collection exceeds bound")
        ordered = tuple(
            sorted(self.items, key=lambda item: (item.recorded_at, item.admission_id))
        )
        if ordered != self.items:
            raise ValueError("v0.51 admission collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("v0.51 admission collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("v0.51 admission collection fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1(
    ContractModel
):
    """Injected facts only; no store, runtime, queue, worker, endpoint, or I/O."""

    operator_id: OperatorId
    authority: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1
    )
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1
    )
    idempotency_key: VisibleIdempotencyKey | None = None
    home_assistant: bool = False
    ambiguous_prerequisite_count: int = 0
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1:
        prerequisite = (
            self.controlled_worker_queue_claim_lease_acknowledgement_prerequisite
        )
        status = (
            self.controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status
        )
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if self.ambiguous_prerequisite_count != 0:
            raise ValueError("ambiguous v0.50 prerequisite")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or prerequisite.operator_id != self.operator_id
            or status.operator_id != self.operator_id
        ):
            raise ValueError("v0.51 ownership mismatch")
        if (
            prerequisite.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("v0.51 candidate linkage mismatch")
        if (
            self.create.prerequisite_id != prerequisite.prerequisite_id
            or self.create.prerequisite_valid_until != prerequisite.valid_until
            or status.prerequisite_id != prerequisite.prerequisite_id
            or status.prerequisite_record_fingerprint
            != prerequisite.prerequisite_record_fingerprint
        ):
            raise ValueError("v0.50 prerequisite linkage mismatch")
        if (
            self.create.prerequisite_record_fingerprint
            != prerequisite.prerequisite_record_fingerprint
            or self.create.prerequisite_status_fingerprint != status.status_fingerprint
            or prerequisite.prerequisite_record_fingerprint
            != v050_record_fingerprint(prerequisite)
            or status.status_fingerprint != v050_status_fingerprint(status)
        ):
            raise ValueError("v0.50 prerequisite fingerprint mismatch")
        if status.lifecycle != "active":
            raise ValueError("v0.50 prerequisite is not active")
        if (
            prerequisite.lifecycle != "active"
            or prerequisite.prerequisite_state != "frozen"
            or prerequisite.eligibility != "v0.50_prerequisite_frozen"
            or status.prerequisite_state != "v0.50_prerequisite_frozen"
            or status.eligibility != "v0.50_prerequisite_frozen"
            or prerequisite.blockers != V050_SUCCESS_BLOCKERS
            or status.blockers != V050_SUCCESS_BLOCKERS
            or not prerequisite.v0_50_prerequisite_frozen
            or not status.v0_50_prerequisite_frozen
        ):
            raise ValueError("v0.50 prerequisite is not frozen")
        if (
            self.create.v049_admission_record_fingerprint
            != prerequisite.admission_record_fingerprint
            or self.create.v049_admission_status_fingerprint
            != prerequisite.admission_status_fingerprint
            or self.create.binding_subject_fingerprint
            != prerequisite.binding_subject_fingerprint
            or self.create.worker_subject_fingerprint
            != prerequisite.worker_subject_fingerprint
            or self.create.queue_item_reference_fingerprint
            != prerequisite.queue_item_reference_fingerprint
        ):
            raise ValueError("v0.50 prerequisite lineage fingerprint mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != prerequisite.inherited_limits_fingerprint
        ):
            raise ValueError("v0.50 prerequisite inherited limits mismatch")
        if (
            self.authority.credential_material_present
            or self.create.credential_material_present
            or self.authority.claim_token_material_present
            or self.create.claim_token_material_present
            or self.authority.lease_token_material_present
            or self.create.lease_token_material_present
        ):
            raise ValueError("caller supplied credential")
        if (
            self.authority.endpoint_material_present
            or self.create.endpoint_material_present
        ):
            raise ValueError("caller supplied endpoint")
        if (
            self.authority.command_material_present
            or self.create.command_material_present
            or self.authority.payload_material_present
            or self.create.payload_material_present
        ):
            raise ValueError("caller supplied command")
        if (
            self.authority.queue_selector_material_present
            or self.create.queue_selector_material_present
        ):
            raise ValueError("caller supplied queue selector")
        if (
            self.authority.acknowledgement_handle_material_present
            or self.create.acknowledgement_handle_material_present
        ):
            raise ValueError("caller supplied acknowledgement handle")
        if any(getattr(self.authority, flag, False) for flag in _AUTHORITY_FLAGS):
            raise ValueError("unsupported authority")
        now = _instant(self.authority.request_received_at)
        starts = (_instant(prerequisite.recorded_at), _instant(status.evaluated_at))
        if any(
            value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS)
            for value in starts
        ):
            raise ValueError("v0.50 prerequisite is stale or from the future")
        expiries = (_instant(prerequisite.valid_until), _instant(status.valid_until))
        if any(now >= expiry for expiry in expiries):
            raise ValueError("v0.50 prerequisite is expired")
        return self


def build_create(
    *,
    prerequisite: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1,
    prerequisite_status: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1:
    return ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1(
        prerequisite_id=prerequisite.prerequisite_id,
        prerequisite_record_fingerprint=prerequisite.prerequisite_record_fingerprint,
        prerequisite_status_fingerprint=prerequisite_status.status_fingerprint,
        prerequisite_valid_until=prerequisite.valid_until,
        v049_admission_record_fingerprint=prerequisite.admission_record_fingerprint,
        v049_admission_status_fingerprint=prerequisite.admission_status_fingerprint,
        binding_subject_fingerprint=prerequisite.binding_subject_fingerprint,
        worker_subject_fingerprint=prerequisite.worker_subject_fingerprint,
        queue_item_reference_fingerprint=prerequisite.queue_item_reference_fingerprint,
        inherited_limits_fingerprint=prerequisite.inherited_limits_fingerprint,
    )


def evaluate_controlled_worker_queue_claim_lease_acknowledgement_admission(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1
        | dict[str, Any]
    ),
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1:
    preflight_blocker = _preflight_blocker(value)
    if preflight_blocker is not None:
        return _blocked_evaluation(value, preflight_blocker)
    try:
        validation = (
            value
            if isinstance(
                value,
                ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1,
            )
            else ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1.model_validate(
                value
            )
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    prerequisite = (
        validation.controlled_worker_queue_claim_lease_acknowledgement_prerequisite
    )
    status = (
        validation.controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status
    )
    earliest = min(
        _instant(prerequisite.valid_until),
        _instant(status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest,
        admission_state="recorded",
        eligibility=(
            "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
        ),
        blockers=SUCCESS_BLOCKERS,
    )


def _preflight_blocker(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1
        | dict[str, Any]
    ),
) -> BlockerV1 | None:
    if isinstance(value, BaseModel) or not isinstance(value, dict):
        return None
    if value.get("boundary_enabled"):
        return "unsupported_authority"
    if value.get("ambiguous_prerequisite_count", 0):
        return "ambiguous_state"
    for section_name in ("create", "authority"):
        section = value.get(section_name)
        if not isinstance(section, dict):
            continue
        keys = set(section)
        if "queue_selector" in keys or section.get("queue_selector_material_present"):
            return "caller_supplied_queue_selector"
        if "claim_token" in keys or section.get("claim_token_material_present"):
            return "caller_supplied_claim_token"
        if "lease_token" in keys or section.get("lease_token_material_present"):
            return "caller_supplied_lease_token"
        if "acknowledgement_handle" in keys or section.get(
            "acknowledgement_handle_material_present"
        ):
            return "caller_supplied_acknowledgement_handle"
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
    prerequisite = value.get(
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite"
    )
    status = value.get(
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status"
    )
    if (
        isinstance(prerequisite, dict)
        and prerequisite.get("lifecycle", "active") != "active"
    ):
        return "v050_prerequisite_not_active"
    if isinstance(status, dict) and status.get("lifecycle", "active") != "active":
        return "v050_prerequisite_not_active"
    if isinstance(prerequisite, dict) and (
        prerequisite.get("prerequisite_state", "frozen") != "frozen"
        or prerequisite.get("eligibility", "v0.50_prerequisite_frozen")
        != "v0.50_prerequisite_frozen"
        or prerequisite.get("v0_50_prerequisite_frozen", True) is not True
    ):
        return "v050_prerequisite_not_frozen"
    if isinstance(status, dict) and (
        status.get("prerequisite_state", "v0.50_prerequisite_frozen")
        != "v0.50_prerequisite_frozen"
        or status.get("eligibility", "v0.50_prerequisite_frozen")
        != "v0.50_prerequisite_frozen"
        or status.get("v0_50_prerequisite_frozen", True) is not True
    ):
        return "v050_prerequisite_not_frozen"
    keys = set(value)
    if "queue_selector" in keys:
        return "caller_supplied_queue_selector"
    if "claim_token" in keys:
        return "caller_supplied_claim_token"
    if "lease_token" in keys:
        return "caller_supplied_lease_token"
    if "acknowledgement_handle" in keys:
        return "caller_supplied_acknowledgement_handle"
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
    admission_state: Literal["recorded", "blocked"],
    eligibility: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        "blocked",
    ],
    blockers: tuple[BlockerV1, ...],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1:
    recorded = admission_state == "recorded"
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "admission_state": admission_state,
        "eligibility": eligibility,
        "blockers": blockers,
        "recognized_v050_prerequisite_count": 1 if recorded else 0,
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded": recorded,
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1.model_construct(
            **raw,
            evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1
        | dict[str, Any]
    ),
    reason: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1:
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
        admission_state="blocked",
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
    if "not active" in lowered and "v0.50" in lowered:
        return "v050_prerequisite_not_active"
    if "not frozen" in lowered and "v0.50" in lowered:
        return "v050_prerequisite_not_frozen"
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
    if "queue selector" in lowered:
        return "caller_supplied_queue_selector"
    if "claim token" in lowered:
        return "caller_supplied_claim_token"
    if "lease token" in lowered:
        return "caller_supplied_lease_token"
    if "acknowledgement handle" in lowered:
        return "caller_supplied_acknowledgement_handle"
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
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionEvaluationV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-evaluation:v1",
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
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def admission_subject_fingerprint(
    value: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    prerequisite = raw[
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite"
    ]
    status = raw[
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status"
    ]
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "prerequisite_id": prerequisite["prerequisite_id"],
            "prerequisite_record_fingerprint": prerequisite[
                "prerequisite_record_fingerprint"
            ],
            "prerequisite_status_fingerprint": status["status_fingerprint"],
            "v049_admission_record_fingerprint": prerequisite[
                "admission_record_fingerprint"
            ],
            "v049_admission_status_fingerprint": prerequisite[
                "admission_status_fingerprint"
            ],
            "binding_subject_fingerprint": prerequisite[
                "binding_subject_fingerprint"
            ],
            "worker_subject_fingerprint": prerequisite["worker_subject_fingerprint"],
            "queue_item_reference_fingerprint": prerequisite[
                "queue_item_reference_fingerprint"
            ],
            "inherited_limits_fingerprint": prerequisite["inherited_limits_fingerprint"],
        },
    )


def reservation_subject_fingerprint(
    validation: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    raw = (
        validation.model_dump(mode="json")
        if isinstance(validation, BaseModel)
        else dict(validation)
    )
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "prerequisite_id": raw["create"]["prerequisite_id"],
            "prerequisite_record_fingerprint": raw["create"][
                "prerequisite_record_fingerprint"
            ],
            "prerequisite_status_fingerprint": raw["create"][
                "prerequisite_status_fingerprint"
            ],
            "v049_admission_record_fingerprint": raw["create"][
                "v049_admission_record_fingerprint"
            ],
            "v049_admission_status_fingerprint": raw["create"][
                "v049_admission_status_fingerprint"
            ],
            "binding_subject_fingerprint": raw["create"][
                "binding_subject_fingerprint"
            ],
            "worker_subject_fingerprint": raw["create"]["worker_subject_fingerprint"],
            "queue_item_reference_fingerprint": raw["create"][
                "queue_item_reference_fingerprint"
            ],
            "inherited_limits_fingerprint": raw["create"][
                "inherited_limits_fingerprint"
            ],
        },
    )


def derived_admission_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-id:v1",
        subject_fingerprint,
    )


def admission_record_fingerprint(
    value: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-record:v1",
        _without(value, "admission_record_fingerprint"),
    )


def status_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-status:v1",
        _without(value, "status_fingerprint"),
    )


def reservation_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionSubjectReservationV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def audit_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuditEvidenceV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def build_admission(
    validation: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1:
    now = _instant(validation.authority.request_received_at)
    prerequisite = (
        validation.controlled_worker_queue_claim_lease_acknowledgement_prerequisite
    )
    status = (
        validation.controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status
    )
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(prerequisite.valid_until),
        _instant(status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = reservation_subject_fingerprint(validation)
    raw = {
        "admission_id": derived_admission_id(subject),
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite": prerequisite,
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status": (
            status
        ),
        "prerequisite_id": validation.create.prerequisite_id,
        "prerequisite_record_fingerprint": (
            validation.create.prerequisite_record_fingerprint
        ),
        "prerequisite_status_fingerprint": (
            validation.create.prerequisite_status_fingerprint
        ),
        "v049_admission_record_fingerprint": (
            validation.create.v049_admission_record_fingerprint
        ),
        "v049_admission_status_fingerprint": (
            validation.create.v049_admission_status_fingerprint
        ),
        "binding_subject_fingerprint": validation.create.binding_subject_fingerprint,
        "worker_subject_fingerprint": validation.create.worker_subject_fingerprint,
        "queue_item_reference_fingerprint": (
            validation.create.queue_item_reference_fingerprint
        ),
        "inherited_limits_fingerprint": validation.create.inherited_limits_fingerprint,
        "subject_fingerprint": subject,
        "idempotency_key_fingerprint": idempotency_key_fingerprint(
            validation.operator_id, validation.idempotency_key or ""
        ),
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1.model_construct(
            **raw,
            admission_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1.model_validate(
        {**raw, "admission_record_fingerprint": admission_record_fingerprint(seed)}
    )


def build_reservations(
    validation: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionValidationInputV1,
    record: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
) -> tuple[
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionIdempotencyReservationV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionSubjectReservationV1,
]:
    idem = idempotency_key_fingerprint(
        validation.operator_id, validation.idempotency_key or ""
    )
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
        "admission_id": record.admission_id,
        "admission_record_fingerprint": record.admission_record_fingerprint,
        "reserved_at": validation.authority.request_received_at,
    }
    idempotency = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionIdempotencyReservationV1.model_validate(
            raw
        )
    )
    reservation_seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionSubjectReservationV1.model_construct(
            **raw,
            reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
        )
    )
    reservation = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionSubjectReservationV1.model_validate(
            {**raw, "reservation_fingerprint": reservation_fingerprint(reservation_seed)}
        )
    )
    return idempotency, reservation


def build_audit(
    record: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
    *,
    event: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_read",
        "controlled_worker_queue_claim_lease_acknowledgement_admission_indeterminate",
    ],
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuditEvidenceV1:
    raw = {
        "event": event,
        "audit_id": derived_uuid5(
            "atlas:controlled-worker-queue-claim-lease-acknowledgement-admission-audit-id:v1",
            {
                "operator_id": record.operator_id,
                "candidate_record_id": record.candidate_record_id,
                "admission_id": record.admission_id,
                "event": event,
                "outcome": outcome,
                "correlation_fingerprint": correlation_fingerprint,
                "occurred_at": occurred_at,
            },
        ),
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "admission_id": record.admission_id,
        "occurred_at": occurred_at,
        "outcome": outcome,
        "correlation_fingerprint": correlation_fingerprint,
        "subject_fingerprint": record.subject_fingerprint,
        "admission_record_fingerprint": record.admission_record_fingerprint,
        "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded": (
            outcome == "recorded"
        ),
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuditEvidenceV1.model_construct(
            **raw,
            audit_fingerprint=fingerprint("atlas:seed:v1", "audit"),
        )
    )
    return (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuditEvidenceV1.model_validate(
            {**raw, "audit_fingerprint": audit_fingerprint(seed)}
        )
    )


def derive_status(
    record: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
    *,
    evaluated_at: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1:
    raw = {
        "admission_id": record.admission_id,
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "lifecycle": (
            "expired"
            if _instant(evaluated_at) >= _instant(record.valid_until)
            else "active"
        ),
        "admission_state": (
            "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
        ),
        "eligibility": record.eligibility,
        "blockers": record.blockers,
        "evaluated_at": evaluated_at,
        "valid_until": record.valid_until,
        "admission_record_fingerprint": record.admission_record_fingerprint,
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1.model_construct(
            **raw,
            status_fingerprint=fingerprint("atlas:seed:v1", "status"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1, ...],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1:
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": items,
        "count": len(items),
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1.model_construct(
            **raw,
            collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
        )
    )
    return (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1.model_validate(
            {**raw, "collection_fingerprint": collection_fingerprint(seed)}
        )
    )


def parse_create_json(
    data: str | bytes,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1:
    if isinstance(data, bytes):
        if len(data) > MAX_CREATE_BYTES:
            raise StrictContractError("create request exceeds 16 KiB")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise StrictContractError("create request must be utf-8") from error
    else:
        text = data
    if len(text.encode("utf-8")) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 16 KiB")
    if unicodedata.normalize("NFC", text) != text:
        raise StrictContractError("create request must be NFC normalized")
    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as error:
        raise StrictContractError("create request must be strict json") from error
    try:
        return ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCreateV1.model_validate(
            raw
        )
    except ValueError as error:
        raise StrictContractError("create request failed closed validation") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key}")
        seen.add(key)
        result[key] = value
    return result
