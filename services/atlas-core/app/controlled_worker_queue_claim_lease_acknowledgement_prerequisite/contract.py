"""Closed immutable v0.50 queue claim/lease/ack prerequisite models.

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

from app.controlled_worker_queue_claim_admission.contract import (
    SUCCESS_BLOCKERS as V049_SUCCESS_BLOCKERS,
)
from app.controlled_worker_queue_claim_admission.contract import (
    ControlledWorkerQueueClaimAdmissionStatusV1,
    ControlledWorkerQueueClaimAdmissionV1,
)
from app.controlled_worker_queue_claim_admission.contract import (
    admission_record_fingerprint as v049_record_fingerprint,
)
from app.controlled_worker_queue_claim_admission.contract import (
    status_fingerprint as v049_status_fingerprint,
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
MAX_COLLECTION_RECORDS = 100
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 192 * 1024
MAX_FRESHNESS_SECONDS = 30
PERMISSION = (
    "installation.execution."
    "controlled_worker_queue_claim_lease_acknowledgement_prerequisite.evaluate"
)
SCOPE = "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_only"
SAFE_MESSAGE = (
    "controlled worker queue claim lease acknowledgement prerequisite request "
    "could not be completed"
)
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"
_UUID5_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")
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
    }
)

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v049_admission_not_active",
    "v049_admission_not_recorded",
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
    "v049_admission_not_active",
    "v049_admission_not_recorded",
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
        raise ValueError("v0.50 blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("v0.50 blockers are not ordered")


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


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-create-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-create-v1"
    admission_id: CanonicalUuid5
    admission_record_fingerprint: FingerprintV1
    admission_status_fingerprint: FingerprintV1
    admission_valid_until: UtcSecond
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuthorityContextV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-authority-context-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-authority-context-v1"
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-evaluation-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-evaluation-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    prerequisite_state: Literal["frozen", "blocked"]
    eligibility: Literal["v0.50_prerequisite_frozen", "blocked"]
    blockers: tuple[BlockerV1, ...]
    recognized_v049_admission_count: int
    later_queue_claim_lease_acknowledgement_allowed: Literal[False] = False
    worker_start_admission_build_allowed: Literal[False] = False
    execution_start_admission_build_allowed: Literal[False] = False
    runtime_effect_allowed: Literal[False] = False
    evaluation_fingerprint: FingerprintV1
    v0_50_prerequisite_frozen: bool = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1:
        _ordered(self.blockers)
        frozen = self.prerequisite_state == "frozen"
        if (self.eligibility == "v0.50_prerequisite_frozen") != frozen:
            raise ValueError("v0.50 eligibility mismatch")
        if self.recognized_v049_admission_count != (1 if frozen else 0):
            raise ValueError("v0.49 admission recognition count mismatch")
        if frozen and (self.blockers != SUCCESS_BLOCKERS or not self.v0_50_prerequisite_frozen):
            raise ValueError("frozen v0.50 prerequisite shape mismatch")
        if not frozen and self.v0_50_prerequisite_frozen:
            raise ValueError("blocked v0.50 prerequisite shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("v0.50 evaluation fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1(ClosedAuthorityV1):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1"
    prerequisite_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    prerequisite_state: Literal["frozen"] = "frozen"
    eligibility: Literal["v0.50_prerequisite_frozen"] = "v0.50_prerequisite_frozen"
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    controlled_worker_queue_claim_admission: ControlledWorkerQueueClaimAdmissionV1
    controlled_worker_queue_claim_admission_status: (
        ControlledWorkerQueueClaimAdmissionStatusV1
    )
    admission_id: CanonicalUuid5
    admission_record_fingerprint: FingerprintV1
    admission_status_fingerprint: FingerprintV1
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    prerequisite_record_fingerprint: FingerprintV1
    v0_50_prerequisite_frozen: Literal[True] = True

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("v0.50 prerequisite blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("v0.50 prerequisite expiry exceeds freshness bound")
        admission = self.controlled_worker_queue_claim_admission
        status = self.controlled_worker_queue_claim_admission_status
        if (
            self.operator_id != admission.operator_id
            or self.operator_id != status.operator_id
            or self.candidate_record_id != admission.candidate_record_id
            or self.candidate_record_id != status.candidate_record_id
            or self.admission_id != admission.admission_id
            or status.admission_id != admission.admission_id
            or self.valid_until > admission.valid_until
            or self.valid_until > status.valid_until
        ):
            raise ValueError("v0.50 prerequisite ownership or linkage mismatch")
        if (
            self.admission_record_fingerprint != admission.admission_record_fingerprint
            or self.admission_status_fingerprint != status.status_fingerprint
            or self.binding_subject_fingerprint != admission.binding_subject_fingerprint
            or self.worker_subject_fingerprint != admission.worker_subject_fingerprint
            or self.queue_item_reference_fingerprint
            != admission.queue_item_reference_fingerprint
            or self.inherited_limits_fingerprint != admission.inherited_limits_fingerprint
        ):
            raise ValueError("v0.50 prerequisite subject or limits mismatch")
        if self.subject_fingerprint != prerequisite_subject_fingerprint(self):
            raise ValueError("v0.50 prerequisite subject fingerprint mismatch")
        if self.prerequisite_id != derived_prerequisite_id(self.subject_fingerprint):
            raise ValueError("v0.50 prerequisite id mismatch")
        if self.prerequisite_record_fingerprint != prerequisite_record_fingerprint(self):
            raise ValueError("v0.50 prerequisite record fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-status-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-status-v1"
    prerequisite_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    lifecycle: Literal["active", "expired"]
    prerequisite_state: Literal["v0.50_prerequisite_frozen"]
    eligibility: Literal["v0.50_prerequisite_frozen"]
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    prerequisite_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    v0_50_prerequisite_frozen: Literal[True] = True

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("v0.50 prerequisite status blockers are fixed")
        if self.status_fingerprint != prerequisite_status_fingerprint(self):
            raise ValueError("v0.50 prerequisite status fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteIdempotencyReservationV1(
    ContractModel
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-idempotency-reservation-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-"
        "idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    prerequisite_id: CanonicalUuid5
    prerequisite_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    permanent: Literal[True] = True


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteSubjectReservationV1(
    ContractModel
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-subject-reservation-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-"
        "subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    prerequisite_id: CanonicalUuid5
    prerequisite_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteSubjectReservationV1:
        if self.reservation_fingerprint != prerequisite_reservation_fingerprint(self):
            raise ValueError("v0.50 prerequisite reservation fingerprint mismatch")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuditEvidenceV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-audit-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-audit-v1"
    event: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_recorded",
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_read",
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_indeterminate",
    ]
    audit_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    prerequisite_id: CanonicalUuid5 | None
    occurred_at: UtcSecond
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"]
    correlation_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1 | None
    prerequisite_record_fingerprint: FingerprintV1 | None
    audit_fingerprint: FingerprintV1
    v0_50_prerequisite_frozen: bool = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuditEvidenceV1:
        if self.audit_fingerprint != prerequisite_audit_fingerprint(self):
            raise ValueError("v0.50 prerequisite audit fingerprint mismatch")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteRedactedErrorV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-error-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-error-v1"
    error_code: Literal[
        "installation_capability_unsupported",
        "evidence_not_found",
        "ownership_mismatch",
        "permission_scope_missing",
        "v049_admission_not_active",
        "v049_admission_not_recorded",
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
    v0_50_prerequisite_frozen: Literal[False] = False


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteResultV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-result-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-result-v1"
    ok: bool
    outcome: Literal["success", "failure", "indeterminate"]
    record: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1 | None
    status: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1 | None
    )
    error: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteRedactedErrorV1
        | None
    )
    correlation_fingerprint: FingerprintV1
    v0_50_prerequisite_frozen: bool = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteResultV1:
        if self.outcome == "success":
            good = (
                self.ok
                and self.record is not None
                and self.status is not None
                and self.error is None
                and self.v0_50_prerequisite_frozen
            )
        else:
            good = (
                not self.ok
                and self.record is None
                and self.status is None
                and self.error is not None
                and not self.v0_50_prerequisite_frozen
            )
        if not good:
            raise ValueError("v0.50 prerequisite result shape mismatch")
        if (
            self.record is not None
            and self.status.prerequisite_id != self.record.prerequisite_id
        ):
            raise ValueError("v0.50 prerequisite result status mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCollectionV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-collection-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-"
        "collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1, ...]
    count: int
    collection_fingerprint: FingerprintV1
    v0_50_prerequisite_frozen: Literal[False] = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("v0.50 prerequisite collection exceeds bound")
        ordered = tuple(
            sorted(self.items, key=lambda item: (item.recorded_at, item.prerequisite_id))
        )
        if ordered != self.items:
            raise ValueError("v0.50 prerequisite collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("v0.50 prerequisite collection ownership mismatch")
        if self.collection_fingerprint != prerequisite_collection_fingerprint(self):
            raise ValueError("v0.50 prerequisite collection fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1(
    ContractModel
):
    """Injected facts only; no store, runtime, queue, worker, endpoint, or I/O."""

    operator_id: OperatorId
    authority: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuthorityContextV1
    )
    candidate_record_id: CanonicalUuid4
    create: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1
    controlled_worker_queue_claim_admission: ControlledWorkerQueueClaimAdmissionV1
    controlled_worker_queue_claim_admission_status: (
        ControlledWorkerQueueClaimAdmissionStatusV1
    )
    idempotency_key: VisibleIdempotencyKey | None = None
    home_assistant: bool = False
    ambiguous_admission_count: int = 0
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(
        self,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1:
        admission = self.controlled_worker_queue_claim_admission
        status = self.controlled_worker_queue_claim_admission_status
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if self.ambiguous_admission_count != 0:
            raise ValueError("ambiguous v0.49 admission")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or admission.operator_id != self.operator_id
            or status.operator_id != self.operator_id
        ):
            raise ValueError("v0.50 ownership mismatch")
        if (
            admission.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("v0.50 candidate linkage mismatch")
        if (
            self.create.admission_id != admission.admission_id
            or self.create.admission_valid_until != admission.valid_until
            or status.admission_id != admission.admission_id
            or status.admission_record_fingerprint
            != admission.admission_record_fingerprint
        ):
            raise ValueError("v0.49 admission linkage mismatch")
        if (
            self.create.admission_record_fingerprint
            != admission.admission_record_fingerprint
            or self.create.admission_status_fingerprint != status.status_fingerprint
            or admission.admission_record_fingerprint
            != v049_record_fingerprint(admission)
            or status.status_fingerprint != v049_status_fingerprint(status)
        ):
            raise ValueError("v0.49 admission fingerprint mismatch")
        if status.lifecycle != "active":
            raise ValueError("v0.49 admission is not active")
        if (
            admission.lifecycle != "active"
            or admission.admission_state != "readiness_gated"
            or admission.eligibility
            != "controlled_worker_queue_claim_admission_recorded"
            or status.admission_state
            != "controlled_worker_queue_claim_admission_recorded"
            or status.eligibility != "controlled_worker_queue_claim_admission_recorded"
            or admission.blockers != V049_SUCCESS_BLOCKERS
            or status.blockers != V049_SUCCESS_BLOCKERS
            or not admission.controlled_worker_queue_claim_admission_recorded
            or not status.controlled_worker_queue_claim_admission_recorded
        ):
            raise ValueError("v0.49 admission is not recorded")
        if (
            self.create.binding_subject_fingerprint
            != admission.binding_subject_fingerprint
            or self.create.worker_subject_fingerprint
            != admission.worker_subject_fingerprint
            or self.create.queue_item_reference_fingerprint
            != admission.queue_item_reference_fingerprint
        ):
            raise ValueError("v0.49 admission fingerprint mismatch")
        if self.create.inherited_limits_fingerprint != admission.inherited_limits_fingerprint:
            raise ValueError("v0.49 admission inherited limits mismatch")
        if (
            self.authority.credential_material_present
            or self.create.credential_material_present
            or self.authority.claim_token_material_present
            or self.create.claim_token_material_present
            or self.authority.lease_token_material_present
            or self.create.lease_token_material_present
        ):
            raise ValueError("caller supplied credential")
        if self.authority.endpoint_material_present or self.create.endpoint_material_present:
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
        if any(getattr(self.authority, flag) for flag in _AUTHORITY_FLAGS):
            raise ValueError("unsupported authority")
        now = _instant(self.authority.request_received_at)
        starts = (_instant(admission.recorded_at), _instant(status.evaluated_at))
        if any(
            value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS)
            for value in starts
        ):
            raise ValueError("v0.49 admission is stale or from the future")
        expiries = (_instant(admission.valid_until), _instant(status.valid_until))
        if any(now >= expiry for expiry in expiries):
            raise ValueError("v0.49 admission is expired")
        return self


def build_create(
    *,
    admission: ControlledWorkerQueueClaimAdmissionV1,
    admission_status: ControlledWorkerQueueClaimAdmissionStatusV1,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1:
    return ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1(
        admission_id=admission.admission_id,
        admission_record_fingerprint=admission.admission_record_fingerprint,
        admission_status_fingerprint=admission_status.status_fingerprint,
        admission_valid_until=admission.valid_until,
        binding_subject_fingerprint=admission.binding_subject_fingerprint,
        worker_subject_fingerprint=admission.worker_subject_fingerprint,
        queue_item_reference_fingerprint=admission.queue_item_reference_fingerprint,
        inherited_limits_fingerprint=admission.inherited_limits_fingerprint,
    )


def evaluate_controlled_worker_queue_claim_lease_acknowledgement_prerequisite(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1
        | dict[str, Any]
    ),
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1:
    preflight_blocker = _preflight_blocker(value)
    if preflight_blocker is not None:
        return _blocked_evaluation(value, preflight_blocker)
    try:
        validation = (
            value
            if isinstance(
                value,
                ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1,
            )
            else ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1.model_validate(
                value
            )
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    earliest = min(
        _instant(validation.controlled_worker_queue_claim_admission.valid_until),
        _instant(
            validation.controlled_worker_queue_claim_admission_status.valid_until
        ),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest,
        prerequisite_state="frozen",
        eligibility="v0.50_prerequisite_frozen",
        blockers=SUCCESS_BLOCKERS,
    )


def _preflight_blocker(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1
        | dict[str, Any]
    ),
) -> BlockerV1 | None:
    if isinstance(value, BaseModel) or not isinstance(value, dict):
        return None
    if value.get("boundary_enabled"):
        return "unsupported_authority"
    if value.get("ambiguous_admission_count", 0):
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
    admission = value.get("controlled_worker_queue_claim_admission")
    status = value.get("controlled_worker_queue_claim_admission_status")
    if isinstance(admission, dict) and admission.get("lifecycle", "active") != "active":
        return "v049_admission_not_active"
    if isinstance(status, dict) and status.get("lifecycle", "active") != "active":
        return "v049_admission_not_active"
    if isinstance(admission, dict) and (
        admission.get("admission_state", "readiness_gated") != "readiness_gated"
        or admission.get(
            "eligibility",
            "controlled_worker_queue_claim_admission_recorded",
        )
        != "controlled_worker_queue_claim_admission_recorded"
        or admission.get("controlled_worker_queue_claim_admission_recorded", True)
        is not True
    ):
        return "v049_admission_not_recorded"
    if isinstance(status, dict) and (
        status.get(
            "admission_state",
            "controlled_worker_queue_claim_admission_recorded",
        )
        != "controlled_worker_queue_claim_admission_recorded"
        or status.get(
            "eligibility",
            "controlled_worker_queue_claim_admission_recorded",
        )
        != "controlled_worker_queue_claim_admission_recorded"
        or status.get("controlled_worker_queue_claim_admission_recorded", True)
        is not True
    ):
        return "v049_admission_not_recorded"
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
    prerequisite_state: Literal["frozen", "blocked"],
    eligibility: Literal["v0.50_prerequisite_frozen", "blocked"],
    blockers: tuple[BlockerV1, ...],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1:
    frozen = prerequisite_state == "frozen"
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "prerequisite_state": prerequisite_state,
        "eligibility": eligibility,
        "blockers": blockers,
        "recognized_v049_admission_count": 1 if frozen else 0,
        "v0_50_prerequisite_frozen": frozen,
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1.model_construct(
            **raw,
            evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1
        | dict[str, Any]
    ),
    reason: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1:
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
        prerequisite_state="blocked",
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
    if "not active" in lowered and "v0.49" in lowered:
        return "v049_admission_not_active"
    if "not recorded" in lowered and "v0.49" in lowered:
        return "v049_admission_not_recorded"
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
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteEvaluationV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-evaluation:v1",
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
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def prerequisite_subject_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1 | dict[str, Any]
    ),
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    admission = raw["controlled_worker_queue_claim_admission"]
    status = raw["controlled_worker_queue_claim_admission_status"]
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "admission_id": admission["admission_id"],
            "admission_record_fingerprint": admission[
                "admission_record_fingerprint"
            ],
            "admission_status_fingerprint": status["status_fingerprint"],
            "binding_subject_fingerprint": admission[
                "binding_subject_fingerprint"
            ],
            "worker_subject_fingerprint": admission["worker_subject_fingerprint"],
            "queue_item_reference_fingerprint": admission[
                "queue_item_reference_fingerprint"
            ],
            "inherited_limits_fingerprint": admission["inherited_limits_fingerprint"],
        },
    )


def reservation_subject_fingerprint(
    validation: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    raw = (
        validation.model_dump(mode="json")
        if isinstance(validation, BaseModel)
        else dict(validation)
    )
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "admission_id": raw["create"]["admission_id"],
            "admission_record_fingerprint": raw["create"][
                "admission_record_fingerprint"
            ],
            "admission_status_fingerprint": raw["create"][
                "admission_status_fingerprint"
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


def derived_prerequisite_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-id:v1",
        subject_fingerprint,
    )


def prerequisite_record_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1 | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-record:v1",
        _without(value, "prerequisite_record_fingerprint"),
    )


def prerequisite_status_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-status:v1",
        _without(value, "status_fingerprint"),
    )


def prerequisite_reservation_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteSubjectReservationV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def prerequisite_audit_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuditEvidenceV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def prerequisite_collection_fingerprint(
    value: (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCollectionV1
        | dict[str, Any]
    ),
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def build_prerequisite(
    validation: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.controlled_worker_queue_claim_admission.valid_until),
        _instant(validation.controlled_worker_queue_claim_admission_status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = reservation_subject_fingerprint(validation)
    raw = {
        "prerequisite_id": derived_prerequisite_id(subject),
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "controlled_worker_queue_claim_admission": (
            validation.controlled_worker_queue_claim_admission
        ),
        "controlled_worker_queue_claim_admission_status": (
            validation.controlled_worker_queue_claim_admission_status
        ),
        "admission_id": validation.create.admission_id,
        "admission_record_fingerprint": validation.create.admission_record_fingerprint,
        "admission_status_fingerprint": validation.create.admission_status_fingerprint,
        "binding_subject_fingerprint": validation.create.binding_subject_fingerprint,
        "worker_subject_fingerprint": validation.create.worker_subject_fingerprint,
        "queue_item_reference_fingerprint": (
            validation.create.queue_item_reference_fingerprint
        ),
        "inherited_limits_fingerprint": (
            validation.create.inherited_limits_fingerprint
        ),
        "subject_fingerprint": subject,
        "idempotency_key_fingerprint": idempotency_key_fingerprint(
            validation.operator_id, validation.idempotency_key or ""
        ),
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1.model_construct(
            **raw,
            prerequisite_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1.model_validate(
        {**raw, "prerequisite_record_fingerprint": prerequisite_record_fingerprint(seed)}
    )


def build_reservations(
    validation: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteValidationInputV1,
    record: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1,
) -> tuple[
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteIdempotencyReservationV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteSubjectReservationV1,
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
        "prerequisite_id": record.prerequisite_id,
        "prerequisite_record_fingerprint": record.prerequisite_record_fingerprint,
        "reserved_at": validation.authority.request_received_at,
    }
    idempotency = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteIdempotencyReservationV1.model_validate(
            raw
        )
    )
    reservation_seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteSubjectReservationV1.model_construct(
            **raw,
            reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
        )
    )
    reservation = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteSubjectReservationV1.model_validate(
            {
                **raw,
                "reservation_fingerprint": prerequisite_reservation_fingerprint(
                    reservation_seed
                ),
            }
        )
    )
    return idempotency, reservation


def build_audit(
    record: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1,
    *,
    event: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_recorded",
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_read",
        "controlled_worker_queue_claim_lease_acknowledgement_prerequisite_indeterminate",
    ],
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuditEvidenceV1:
    raw = {
        "event": event,
        "audit_id": derived_uuid5(
            "atlas:controlled-worker-queue-claim-lease-acknowledgement-prerequisite-audit-id:v1",
            {
                "operator_id": record.operator_id,
                "candidate_record_id": record.candidate_record_id,
                "prerequisite_id": record.prerequisite_id,
                "event": event,
                "outcome": outcome,
                "correlation_fingerprint": correlation_fingerprint,
                "occurred_at": occurred_at,
            },
        ),
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "prerequisite_id": record.prerequisite_id,
        "occurred_at": occurred_at,
        "outcome": outcome,
        "correlation_fingerprint": correlation_fingerprint,
        "subject_fingerprint": record.subject_fingerprint,
        "prerequisite_record_fingerprint": record.prerequisite_record_fingerprint,
        "v0_50_prerequisite_frozen": outcome == "recorded",
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuditEvidenceV1.model_construct(
            **raw,
            audit_fingerprint=fingerprint("atlas:seed:v1", "audit"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": prerequisite_audit_fingerprint(seed)}
    )


def derive_status(
    record: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1,
    *,
    evaluated_at: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1:
    raw = {
        "prerequisite_id": record.prerequisite_id,
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "lifecycle": (
            "expired"
            if _instant(evaluated_at) >= _instant(record.valid_until)
            else "active"
        ),
        "prerequisite_state": "v0.50_prerequisite_frozen",
        "eligibility": record.eligibility,
        "blockers": record.blockers,
        "evaluated_at": evaluated_at,
        "valid_until": record.valid_until,
        "prerequisite_record_fingerprint": record.prerequisite_record_fingerprint,
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1.model_construct(
            **raw,
            status_fingerprint=fingerprint("atlas:seed:v1", "status"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1.model_validate(
        {**raw, "status_fingerprint": prerequisite_status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1, ...],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCollectionV1:
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": items,
        "count": len(items),
    }
    seed = (
        ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCollectionV1.model_construct(
            **raw,
            collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
        )
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCollectionV1.model_validate(
        {**raw, "collection_fingerprint": prerequisite_collection_fingerprint(seed)}
    )


def parse_create_json(
    raw: bytes | str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1:
    payload = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(payload) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 16 KiB")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise StrictContractError("create request must be utf-8") from error
    if unicodedata.normalize("NFC", text) != text:
        raise StrictContractError("create request must be NFC normalized")
    try:
        decoded = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as error:
        raise StrictContractError("create request must be valid json") from error
    if not isinstance(decoded, dict):
        raise StrictContractError("create request must be an object")
    if len(decoded) != len(set(decoded)):
        raise StrictContractError("duplicate keys are not accepted")
    try:
        return (
            ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteCreateV1.model_validate(
                decoded
            )
        )
    except ValueError as error:
        raise StrictContractError("create request violates v0.50 contract") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictContractError(f"duplicate key: {key}")
        result[key] = value
    return result
