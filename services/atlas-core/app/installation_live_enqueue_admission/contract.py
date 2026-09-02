"""Closed immutable v0.41 live enqueue admission models and pure validation."""

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
from app.runner_binding_plan.contract import RunnerBindingLimitsV1
from app.worker_intake_admission.contract import (
    ADMISSION_BLOCKERS as WORKER_INTAKE_BLOCKERS,
)
from app.worker_intake_admission.contract import (
    WorkerIntakeAdmissionLinkageV1,
    WorkerIntakeAdmissionStatusV1,
    WorkerIntakeAdmissionV1,
)
from app.worker_intake_admission.contract import (
    record_fingerprint as v040_record_fingerprint,
)
from app.worker_intake_admission.contract import (
    status_fingerprint as v040_status_fingerprint,
)
from app.worker_intake_admission.contract import v020_v038_chain_fingerprint
from app.worker_queue_reservation.contract import (
    RESERVATION_BLOCKERS as QUEUE_RESERVATION_BLOCKERS,
)
from app.worker_queue_reservation.contract import (
    WorkerQueueReservationStatusV1,
    WorkerQueueReservationV1,
)
from app.worker_queue_reservation.contract import (
    record_fingerprint as v039_record_fingerprint,
)
from app.worker_queue_reservation.contract import (
    status_fingerprint as v039_status_fingerprint,
)

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 128 * 1024
MAX_RESULT_BYTES = 256 * 1024
MAX_COLLECTION_RECORDS = 100
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.live_enqueue_admission.record"
READ_PERMISSION = "installation.execution.live_enqueue_admission.read"
SCOPE = "installation_live_enqueue_admission_only"
SAFE_MESSAGE = "live enqueue admission request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{12}"
)
_UUID5_NAMESPACE = uuid.UUID("3d5cb80f-20e1-5c45-86c4-3ca0d1212474")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "evidence_stale",
    "evidence_expired",
    "worker_intake_admission_not_active",
    "queue_reservation_not_active",
    "queue_item_reference_invalid",
    "worker_identity_ineligible",
    "worker_intake_reference_ineligible",
    "inherited_limits_mismatch",
    "permanent_subject_reserved",
    "enqueue_operation_not_defined",
    "dequeue_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "evidence_stale",
    "evidence_expired",
    "worker_intake_admission_not_active",
    "queue_reservation_not_active",
    "queue_item_reference_invalid",
    "worker_identity_ineligible",
    "worker_intake_reference_ineligible",
    "inherited_limits_mismatch",
    "permanent_subject_reserved",
    "enqueue_operation_not_defined",
    "dequeue_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
)
ADMISSION_BLOCKERS: tuple[BlockerV1, ...] = (
    "enqueue_operation_not_defined",
    "dequeue_not_defined",
    "worker_start_not_defined",
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


def _bounded(value: BaseModel, maximum: int = MAX_MODEL_BYTES) -> None:
    if len(canonical_json(value)) > maximum:
        raise ValueError("contract envelope exceeds bound")


def _ordered(blockers: tuple[BlockerV1, ...]) -> None:
    if len(blockers) != len(set(blockers)):
        raise ValueError("live enqueue admission blockers contain duplicates")
    if [BLOCKER_ORDER.index(item) for item in blockers] != sorted(
        BLOCKER_ORDER.index(item) for item in blockers
    ):
        raise ValueError("live enqueue admission blockers are not ordered")


class NoAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    live_enqueue_allowed: Literal[False] = False
    enqueue_operation_defined: Literal[False] = False
    queue_item_payload_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    queue_publish_allowed: Literal[False] = False
    queue_send_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_authentication_allowed: Literal[False] = False
    worker_binding_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    runner_binding_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    workflow_start_allowed: Literal[False] = False
    docker_execution_allowed: Literal[False] = False
    podman_execution_allowed: Literal[False] = False
    shell_execution_allowed: Literal[False] = False
    process_execution_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False


class LiveEnqueueAdmissionCreateV1(ContractModel):
    schema: Literal["live-enqueue-admission-create-v1"] = (
        "live-enqueue-admission-create-v1"
    )
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_intake_admission_valid_until: UtcSecond
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE
    evidence_only: Literal[True] = True
    enqueue_operation_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    live_enqueue_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class LiveEnqueueAdmissionAuthorityContextV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-authority-context-v1"] = (
        "live-enqueue-admission-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class LiveEnqueueAdmissionDecisionV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-decision-v1"] = (
        "live-enqueue-admission-decision-v1"
    )
    decision_id: CanonicalUuid5
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    scope: Literal[SCOPE] = SCOPE
    decision: Literal[
        "preserve_non_enqueueing_live_enqueue_admission_evidence_only"
    ] = "preserve_non_enqueueing_live_enqueue_admission_evidence_only"
    evaluated_at: UtcSecond
    eligibility: Literal["live_enqueue_admission_recorded"] = (
        "live_enqueue_admission_recorded"
    )
    blockers: tuple[BlockerV1, ...] = ADMISSION_BLOCKERS
    inherited_limits_fingerprint: FingerprintV1
    decision_fingerprint: FingerprintV1
    queue_item_constructed: Literal[False] = False
    payload_constructed: Literal[False] = False
    request_serialized: Literal[False] = False
    request_sent: Literal[False] = False
    queue_enqueued: Literal[False] = False
    queue_dequeued: Literal[False] = False
    worker_contacted: Literal[False] = False
    worker_started: Literal[False] = False
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionDecisionV1:
        if self.blockers != ADMISSION_BLOCKERS:
            raise ValueError("live enqueue admission blockers must remain fixed")
        if self.decision_fingerprint != decision_fingerprint(self):
            raise ValueError("live enqueue admission decision fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueAdmissionLinkageV1(ContractModel):
    schema: Literal["live-enqueue-admission-linkage-v1"] = (
        "live-enqueue-admission-linkage-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_intake_admission_linkage: WorkerIntakeAdmissionLinkageV1
    v020_v039_chain_fingerprint: FingerprintV1
    readiness_review_fingerprint: FingerprintV1
    permission_grant_fingerprint: FingerprintV1
    execution_admission_id: CanonicalUuid4
    execution_admission_fingerprint: FingerprintV1
    runner_binding_plan_id: CanonicalUuid4
    runner_binding_plan_fingerprint: FingerprintV1
    runner_binding_plan_status_fingerprint: FingerprintV1
    runner_reference_id: CanonicalUuid4
    runner_reference_fingerprint: FingerprintV1
    worker_admission_stub_id: CanonicalUuid4
    worker_admission_stub_fingerprint: FingerprintV1
    worker_admission_stub_status_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    queue_reservation_id: CanonicalUuid4
    queue_reservation_fingerprint: FingerprintV1
    queue_reservation_status_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_intake_admission_status_fingerprint: FingerprintV1
    live_enqueue_admission_decision_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionLinkageV1:
        source = self.worker_intake_admission_linkage
        if (
            self.operator_id != source.operator_id
            or self.candidate_record_id != source.candidate_record_id
            or self.readiness_review_fingerprint != source.readiness_review_fingerprint
            or self.permission_grant_fingerprint != source.permission_grant_fingerprint
            or self.execution_admission_id != source.execution_admission_id
            or self.execution_admission_fingerprint
            != source.execution_admission_fingerprint
            or self.runner_binding_plan_id != source.runner_binding_plan_id
            or self.runner_binding_plan_fingerprint
            != source.runner_binding_plan_fingerprint
            or self.runner_binding_plan_status_fingerprint
            != source.runner_binding_plan_status_fingerprint
            or self.runner_reference_id != source.runner_reference_id
            or self.runner_reference_fingerprint != source.runner_reference_fingerprint
            or self.worker_admission_stub_id != source.worker_admission_stub_id
            or self.worker_admission_stub_fingerprint
            != source.worker_admission_stub_fingerprint
            or self.worker_admission_stub_status_fingerprint
            != source.worker_admission_stub_status_fingerprint
            or self.worker_reference_id != source.worker_reference_id
            or self.worker_reference_fingerprint != source.worker_reference_fingerprint
            or self.queue_reservation_id != source.queue_reservation_id
            or self.queue_reservation_fingerprint != source.queue_reservation_fingerprint
            or self.queue_reservation_status_fingerprint
            != source.queue_reservation_status_fingerprint
            or self.queue_intake_reference_id != source.queue_intake_reference_id
            or self.queue_intake_reference_fingerprint
            != source.queue_intake_reference_fingerprint
            or self.queue_item_reference_id != source.queue_item_reference_id
            or self.queue_item_reference_fingerprint
            != source.queue_item_reference_fingerprint
            or self.worker_identity_id != source.worker_identity_id
            or self.worker_identity_fingerprint != source.worker_identity_fingerprint
            or self.worker_intake_reference_id != source.worker_intake_reference_id
            or self.worker_intake_reference_fingerprint
            != source.worker_intake_reference_fingerprint
            or self.inherited_limits_fingerprint != source.inherited_limits_fingerprint
            or self.v020_v039_chain_fingerprint != v020_v039_chain_fingerprint(source)
        ):
            raise ValueError("embedded worker intake admission linkage mismatch")
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("live enqueue admission linkage fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueAdmissionV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-v1"] = "live-enqueue-admission-v1"
    admission_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    lifecycle: Literal["active"] = "active"
    eligibility: Literal["live_enqueue_admission_recorded"] = (
        "live_enqueue_admission_recorded"
    )
    blockers: tuple[BlockerV1, ...] = ADMISSION_BLOCKERS
    scope: Literal[SCOPE] = SCOPE
    linkage: LiveEnqueueAdmissionLinkageV1
    admission_decision: LiveEnqueueAdmissionDecisionV1
    inherited_limits: RunnerBindingLimitsV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionV1:
        if self.blockers != ADMISSION_BLOCKERS:
            raise ValueError("live enqueue admission blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("live enqueue admission expiry exceeds freshness bound")
        link, decision = self.linkage, self.admission_decision
        if (
            self.operator_id != link.operator_id
            or self.operator_id != decision.owner_operator_id
            or self.candidate_record_id != link.candidate_record_id
            or self.candidate_record_id != decision.candidate_record_id
            or self.admission_id != derived_admission_id(self.subject_fingerprint)
            or decision.worker_intake_admission_id
            != link.worker_intake_admission_id
            or decision.worker_intake_admission_fingerprint
            != link.worker_intake_admission_fingerprint
            or decision.worker_queue_reservation_id != link.queue_reservation_id
            or decision.worker_queue_reservation_fingerprint
            != link.queue_reservation_fingerprint
            or decision.queue_item_reference_id != link.queue_item_reference_id
            or decision.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
            or decision.worker_identity_id != link.worker_identity_id
            or decision.worker_identity_fingerprint != link.worker_identity_fingerprint
            or decision.worker_intake_reference_id != link.worker_intake_reference_id
            or decision.worker_intake_reference_fingerprint
            != link.worker_intake_reference_fingerprint
            or decision.decision_fingerprint
            != link.live_enqueue_admission_decision_fingerprint
            or self.inherited_limits.limits_fingerprint
            != link.inherited_limits_fingerprint
            or decision.inherited_limits_fingerprint != link.inherited_limits_fingerprint
        ):
            raise ValueError("live enqueue admission ownership or linkage mismatch")
        if self.subject_fingerprint != record_subject_fingerprint(self):
            raise ValueError("live enqueue admission subject fingerprint mismatch")
        if self.record_fingerprint != record_fingerprint(self):
            raise ValueError("live enqueue admission record fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueAdmissionStatusV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-status-v1"] = (
        "live-enqueue-admission-status-v1"
    )
    admission_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal["live_enqueue_admission_recorded", "readiness_gated", "blocked"]
    blockers: tuple[BlockerV1, ...]
    record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionStatusV1:
        _ordered(self.blockers)
        if (
            self.eligibility == "live_enqueue_admission_recorded"
            and self.blockers != ADMISSION_BLOCKERS
        ):
            raise ValueError("recorded status blockers must remain fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("live enqueue admission status fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueAdmissionIdempotencyReservationV1(ContractModel):
    schema: Literal["live-enqueue-admission-idempotency-reservation-v1"] = (
        "live-enqueue-admission-idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    admission_id: CanonicalUuid5
    record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    permanent: Literal[True] = True
    raw_key_persisted: Literal[False] = False
    consumed: Literal[False] = False
    released: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False


class LiveEnqueueAdmissionSubjectReservationV1(ContractModel):
    schema: Literal["live-enqueue-admission-subject-reservation-v1"] = (
        "live-enqueue-admission-subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_queue_reservation_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_fingerprint: FingerprintV1
    live_enqueue_admission_decision_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    admission_id: CanonicalUuid5
    record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True
    consumed: Literal[False] = False
    released: Literal[False] = False
    replaceable: Literal[False] = False
    supersedable: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionSubjectReservationV1:
        if self.subject_fingerprint != reservation_subject_fingerprint(self):
            raise ValueError("live enqueue admission subject fingerprint mismatch")
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("live enqueue admission reservation fingerprint mismatch")
        return self


class LiveEnqueueAdmissionAuditEvidenceV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-audit-v1"] = (
        "live-enqueue-admission-audit-v1"
    )
    event: Literal["live_enqueue_admission_recorded", "live_enqueue_admission_read"]
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"]
    operator_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    admission_id: CanonicalUuid5 | None
    subject_fingerprint: FingerprintV1 | None
    record_fingerprint: FingerprintV1 | None
    correlation_fingerprint: FingerprintV1
    occurred_at: UtcSecond
    audit_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("live enqueue admission audit fingerprint mismatch")
        return self


class LiveEnqueueAdmissionRedactedErrorV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-error-v1"] = (
        "live-enqueue-admission-error-v1"
    )
    error_code: Literal[
        "installation_capability_unsupported",
        "evidence_not_found",
        "ownership_mismatch",
        "permission_scope_missing",
        "linkage_mismatch",
        "fingerprint_mismatch",
        "evidence_stale",
        "evidence_expired",
        "worker_intake_admission_not_active",
        "queue_reservation_not_active",
        "queue_item_reference_invalid",
        "worker_identity_ineligible",
        "worker_intake_reference_ineligible",
        "inherited_limits_mismatch",
        "permanent_subject_reserved",
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


class LiveEnqueueAdmissionResultV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-result-v1"] = (
        "live-enqueue-admission-result-v1"
    )
    ok: bool
    admission: LiveEnqueueAdmissionV1 | None
    status: LiveEnqueueAdmissionStatusV1 | None
    error: LiveEnqueueAdmissionRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionResultV1:
        if self.ok != (
            self.admission is not None and self.status is not None and self.error is None
        ):
            raise ValueError("result shape does not match ok flag")
        if self.ok and self.status.admission_id != self.admission.admission_id:
            raise ValueError("result status binding mismatch")
        if not self.ok and (
            self.admission is not None or self.status is not None or self.error is None
        ):
            raise ValueError("failed result requires one redacted error")
        _bounded(self, MAX_RESULT_BYTES)
        return self


class LiveEnqueueAdmissionCollectionV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-collection-v1"] = (
        "live-enqueue-admission-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[LiveEnqueueAdmissionV1, ...]
    count: int
    collection_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("live enqueue admission collection exceeds bound")
        if tuple(sorted(self.items, key=lambda item: (item.recorded_at, item.admission_id))) != self.items:
            raise ValueError("live enqueue admission collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("live enqueue admission collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("live enqueue admission collection fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueWorkerIntakeEvidenceV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-worker-intake-evidence-v1"] = (
        "live-enqueue-admission-worker-intake-evidence-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_intake_admissions: tuple[WorkerIntakeAdmissionV1, ...]
    worker_intake_statuses: tuple[WorkerIntakeAdmissionStatusV1, ...]
    queue_reservations: tuple[WorkerQueueReservationV1, ...]
    queue_reservation_statuses: tuple[WorkerQueueReservationStatusV1, ...]
    count: int
    recognized_as_inert_evidence: Literal[True] = True
    live_enqueue_defined: Literal[False] = False
    payload_schema_defined: Literal[False] = False
    dequeue_defined: Literal[False] = False
    worker_start_defined: Literal[False] = False
    execution_start_defined: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueWorkerIntakeEvidenceV1:
        if (
            self.count != 1
            or len(self.worker_intake_admissions) != 1
            or len(self.worker_intake_statuses) != 1
            or len(self.queue_reservations) != 1
            or len(self.queue_reservation_statuses) != 1
        ):
            raise ValueError("exactly one v0.40 and v0.39 record must be recognized")
        admission = self.worker_intake_admissions[0]
        status = self.worker_intake_statuses[0]
        queue = self.queue_reservations[0]
        queue_status = self.queue_reservation_statuses[0]
        if (
            admission.operator_id != self.operator_id
            or status.operator_id != self.operator_id
            or queue.operator_id != self.operator_id
            or queue_status.operator_id != self.operator_id
            or admission.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
            or queue.candidate_record_id != self.candidate_record_id
            or queue_status.candidate_record_id != self.candidate_record_id
            or status.admission_id != admission.admission_id
            or status.record_fingerprint != admission.record_fingerprint
            or status.status_fingerprint != v040_status_fingerprint(status)
            or admission.record_fingerprint != v040_record_fingerprint(admission)
            or queue_status.reservation_id != queue.reservation_id
            or queue_status.record_fingerprint != queue.record_fingerprint
            or queue_status.status_fingerprint != v039_status_fingerprint(queue_status)
            or queue.record_fingerprint != v039_record_fingerprint(queue)
            or admission.linkage.queue_reservation_id != queue.reservation_id
            or admission.linkage.queue_reservation_fingerprint != queue.record_fingerprint
            or admission.linkage.queue_reservation_status_fingerprint
            != queue_status.status_fingerprint
            or status.lifecycle != "active"
            or status.eligibility != "worker_intake_admission_recorded"
            or status.blockers != WORKER_INTAKE_BLOCKERS
            or queue_status.lifecycle != "active"
            or queue_status.eligibility != "worker_queue_reservation_recorded"
            or queue_status.blockers != QUEUE_RESERVATION_BLOCKERS
        ):
            raise ValueError("v0.40 worker intake admission is not active inert evidence")
        if self.evidence_fingerprint != worker_intake_evidence_fingerprint(self):
            raise ValueError("live enqueue worker intake evidence fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueAdmissionEvaluationV1(NoAuthorityV1):
    schema: Literal["live-enqueue-admission-evaluation-v1"] = (
        "live-enqueue-admission-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    eligibility: Literal["live_enqueue_admission_recorded", "readiness_gated", "blocked"]
    blockers: tuple[BlockerV1, ...]
    worker_intake_evidence: LiveEnqueueWorkerIntakeEvidenceV1 | None
    recognized_active_v040_worker_intake_count: int
    recognized_active_v040_worker_intake_as_inert_evidence: bool
    admission_record_build_allowed: bool
    evaluation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionEvaluationV1:
        _ordered(self.blockers)
        has_evidence = self.worker_intake_evidence is not None
        if self.recognized_active_v040_worker_intake_count != (1 if has_evidence else 0):
            raise ValueError("active v0.40 worker intake recognition count mismatch")
        if self.recognized_active_v040_worker_intake_as_inert_evidence != has_evidence:
            raise ValueError("active v0.40 worker intake recognition flag mismatch")
        if self.admission_record_build_allowed != (
            self.eligibility == "live_enqueue_admission_recorded"
        ):
            raise ValueError("live enqueue admission record build flag mismatch")
        if (
            self.eligibility == "live_enqueue_admission_recorded"
            and (self.blockers != ADMISSION_BLOCKERS or not has_evidence)
        ):
            raise ValueError("recordable live enqueue admission requires active v0.40 evidence")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("live enqueue admission evaluation fingerprint mismatch")
        _bounded(self)
        return self


class LiveEnqueueAdmissionValidationInputV1(ContractModel):
    """Injected P1 facts only; no reader, store, queue, worker, Agent, or I/O."""

    operator_id: OperatorId
    authority: LiveEnqueueAdmissionAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: LiveEnqueueAdmissionCreateV1
    worker_intake_admission: WorkerIntakeAdmissionV1
    worker_intake_admission_status: WorkerIntakeAdmissionStatusV1
    worker_queue_reservation: WorkerQueueReservationV1
    worker_queue_reservation_status: WorkerQueueReservationStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> LiveEnqueueAdmissionValidationInputV1:
        admission, status = self.worker_intake_admission, self.worker_intake_admission_status
        queue = self.worker_queue_reservation
        queue_status = self.worker_queue_reservation_status
        now = _instant(self.authority.request_received_at)
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or admission.operator_id != self.operator_id
            or queue.operator_id != self.operator_id
        ):
            raise ValueError("live enqueue admission ownership mismatch")
        if (
            admission.candidate_record_id != self.candidate_record_id
            or queue.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("live enqueue admission candidate linkage mismatch")
        if (
            self.create.worker_intake_admission_id != admission.admission_id
            or self.create.worker_intake_admission_fingerprint
            != admission.record_fingerprint
            or self.create.worker_intake_admission_valid_until != admission.valid_until
        ):
            raise ValueError("worker intake admission binding mismatch")
        if (
            status.admission_id != admission.admission_id
            or status.record_fingerprint != admission.record_fingerprint
            or status.status_fingerprint != v040_status_fingerprint(status)
            or status.lifecycle != "active"
            or status.eligibility != "worker_intake_admission_recorded"
            or status.blockers != WORKER_INTAKE_BLOCKERS
        ):
            raise ValueError("worker intake admission is not active")
        if (
            queue_status.reservation_id != queue.reservation_id
            or queue_status.record_fingerprint != queue.record_fingerprint
            or queue_status.status_fingerprint != v039_status_fingerprint(queue_status)
            or queue_status.lifecycle != "active"
            or queue_status.eligibility != "worker_queue_reservation_recorded"
            or queue_status.blockers != QUEUE_RESERVATION_BLOCKERS
            or queue.record_fingerprint != v039_record_fingerprint(queue)
        ):
            raise ValueError("queue reservation is not active")
        link = admission.linkage
        queue_link = link.worker_queue_reservation_linkage
        if (
            self.create.worker_queue_reservation_id != link.queue_reservation_id
            or self.create.worker_queue_reservation_fingerprint
            != link.queue_reservation_fingerprint
            or queue.reservation_id != link.queue_reservation_id
            or queue.record_fingerprint != link.queue_reservation_fingerprint
            or queue_status.status_fingerprint
            != link.queue_reservation_status_fingerprint
            or self.create.queue_item_reference_id != link.queue_item_reference_id
            or self.create.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
            or self.create.worker_identity_id != link.worker_identity_id
            or self.create.worker_identity_fingerprint != link.worker_identity_fingerprint
            or self.create.worker_intake_reference_id != link.worker_intake_reference_id
            or self.create.worker_intake_reference_fingerprint
            != link.worker_intake_reference_fingerprint
            or self.create.inherited_limits_fingerprint
            != admission.inherited_limits.limits_fingerprint
            or admission.inherited_limits.limits_fingerprint
            != link.inherited_limits_fingerprint
            or admission.worker_identity.inherited_limits != admission.inherited_limits
            or admission.worker_identity.inherited_limits_fingerprint
            != admission.inherited_limits.limits_fingerprint
        ):
            raise ValueError("live enqueue inherited v0.40 linkage mismatch")
        if (
            queue_link.queue_item_reference_id != link.queue_item_reference_id
            or queue_link.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
            or queue_link.inherited_limits_fingerprint != link.inherited_limits_fingerprint
        ):
            raise ValueError("queue reservation linkage mismatch")
        if admission.worker_identity.eligibility != "eligible_for_intake_admission_evidence_only":
            raise ValueError("worker identity ineligible")
        if admission.worker_intake_reference.eligibility != "eligible_for_intake_admission_evidence_only":
            raise ValueError("worker intake reference ineligible")
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        starts = (
            _instant(admission.recorded_at),
            _instant(status.evaluated_at),
            _instant(queue.recorded_at),
            _instant(queue_status.observed_at),
            _instant(admission.worker_identity.valid_from),
            _instant(admission.worker_intake_reference.valid_from),
        )
        if any(value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS) for value in starts):
            raise ValueError("live enqueue admission evidence is stale or from the future")
        expiries = (
            _instant(admission.valid_until),
            _instant(queue.valid_until),
            _instant(admission.worker_identity.valid_until),
            _instant(admission.worker_intake_reference.valid_until),
        )
        if any(now >= expiry for expiry in expiries):
            raise ValueError("live enqueue admission evidence is expired")
        return self


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:live-enqueue-admission-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: LiveEnqueueAdmissionCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def v020_v039_chain_fingerprint(value: WorkerIntakeAdmissionLinkageV1) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-v020-v039-chain:v1",
        {
            "worker_queue_reservation_linkage": value.worker_queue_reservation_linkage,
            "queue_reservation_id": value.queue_reservation_id,
            "queue_reservation_fingerprint": value.queue_reservation_fingerprint,
            "v020_v038_chain_fingerprint": v020_v038_chain_fingerprint(
                value.worker_queue_reservation_linkage
            ),
        },
    )


def decision_fingerprint(
    value: LiveEnqueueAdmissionDecisionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-decision:v1",
        _without(value, "decision_fingerprint"),
    )


def linkage_fingerprint(value: LiveEnqueueAdmissionLinkageV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-linkage:v1",
        _without(value, "linkage_fingerprint"),
    )


def _subject_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        key: raw[key]
        for key in (
            "operator_id",
            "candidate_record_id",
            "worker_intake_admission_fingerprint",
            "worker_queue_reservation_fingerprint",
            "queue_item_reference_fingerprint",
            "worker_identity_fingerprint",
            "worker_intake_reference_fingerprint",
            "inherited_limits_fingerprint",
        )
    }


def record_subject_fingerprint(
    value: LiveEnqueueAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    link = raw["linkage"]
    return fingerprint(
        "atlas:live-enqueue-admission-subject:v1",
        _subject_fields(
            {
                "operator_id": raw["operator_id"],
                "candidate_record_id": raw["candidate_record_id"],
                "worker_intake_admission_fingerprint": link[
                    "worker_intake_admission_fingerprint"
                ],
                "worker_queue_reservation_fingerprint": link[
                    "queue_reservation_fingerprint"
                ],
                "queue_item_reference_fingerprint": link[
                    "queue_item_reference_fingerprint"
                ],
                "worker_identity_fingerprint": link["worker_identity_fingerprint"],
                "worker_intake_reference_fingerprint": link[
                    "worker_intake_reference_fingerprint"
                ],
                "live_enqueue_admission_decision_fingerprint": link[
                    "live_enqueue_admission_decision_fingerprint"
                ],
                "inherited_limits_fingerprint": link["inherited_limits_fingerprint"],
            }
        ),
    )


def record_fingerprint(value: LiveEnqueueAdmissionV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-record:v1",
        _without(value, "record_fingerprint"),
    )


def status_fingerprint(value: LiveEnqueueAdmissionStatusV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-status:v1",
        _without(value, "status_fingerprint"),
    )


def reservation_subject_fingerprint(
    value: LiveEnqueueAdmissionSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint("atlas:live-enqueue-admission-subject:v1", _subject_fields(raw))


def reservation_fingerprint(
    value: LiveEnqueueAdmissionSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def audit_fingerprint(
    value: LiveEnqueueAdmissionAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: LiveEnqueueAdmissionCollectionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def worker_intake_evidence_fingerprint(
    value: LiveEnqueueWorkerIntakeEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-worker-intake-evidence:v1",
        _without(value, "evidence_fingerprint"),
    )


def evaluation_fingerprint(
    value: LiveEnqueueAdmissionEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:live-enqueue-admission-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def derived_uuid5(domain: str, value: Any) -> str:
    seed = fingerprint(domain, value).value
    return str(uuid.uuid5(_UUID5_NAMESPACE, f"{domain}:{seed}"))


def derived_admission_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5("atlas:live-enqueue-admission-id:v1", subject_fingerprint)


def derived_decision_id(
    *,
    operator_id: str,
    candidate_record_id: str,
    worker_intake_admission_fingerprint: FingerprintV1,
    idempotency_fingerprint: FingerprintV1,
) -> str:
    return derived_uuid5(
        "atlas:live-enqueue-admission-decision-id:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "worker_intake_admission_fingerprint": worker_intake_admission_fingerprint,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def build_worker_intake_evidence(
    *,
    operator_id: str,
    candidate_record_id: str,
    admission: WorkerIntakeAdmissionV1,
    status: WorkerIntakeAdmissionStatusV1,
    queue_reservation: WorkerQueueReservationV1,
    queue_reservation_status: WorkerQueueReservationStatusV1,
) -> LiveEnqueueWorkerIntakeEvidenceV1:
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_intake_admissions": (admission,),
        "worker_intake_statuses": (status,),
        "queue_reservations": (queue_reservation,),
        "queue_reservation_statuses": (queue_reservation_status,),
        "count": 1,
    }
    seed = LiveEnqueueWorkerIntakeEvidenceV1.model_construct(
        **raw,
        evidence_fingerprint=fingerprint("atlas:seed:v1", "worker-intake-evidence"),
    )
    return LiveEnqueueWorkerIntakeEvidenceV1.model_validate(
        {**raw, "evidence_fingerprint": worker_intake_evidence_fingerprint(seed)}
    )


def build_decision(
    *,
    decision_id: str,
    operator_id: str,
    candidate_record_id: str,
    worker_intake_admission: WorkerIntakeAdmissionV1,
    evaluated_at: str,
) -> LiveEnqueueAdmissionDecisionV1:
    link = worker_intake_admission.linkage
    raw = {
        "decision_id": decision_id,
        "owner_operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_intake_admission_id": worker_intake_admission.admission_id,
        "worker_intake_admission_fingerprint": worker_intake_admission.record_fingerprint,
        "worker_queue_reservation_id": link.queue_reservation_id,
        "worker_queue_reservation_fingerprint": link.queue_reservation_fingerprint,
        "queue_item_reference_id": link.queue_item_reference_id,
        "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
        "worker_identity_id": link.worker_identity_id,
        "worker_identity_fingerprint": link.worker_identity_fingerprint,
        "worker_intake_reference_id": link.worker_intake_reference_id,
        "worker_intake_reference_fingerprint": link.worker_intake_reference_fingerprint,
        "evaluated_at": evaluated_at,
        "inherited_limits_fingerprint": link.inherited_limits_fingerprint,
    }
    seed = LiveEnqueueAdmissionDecisionV1.model_construct(
        **raw,
        decision_fingerprint=fingerprint("atlas:seed:v1", "decision"),
    )
    return LiveEnqueueAdmissionDecisionV1.model_validate(
        {**raw, "decision_fingerprint": decision_fingerprint(seed)}
    )


def build_linkage(
    admission: WorkerIntakeAdmissionV1,
    status: WorkerIntakeAdmissionStatusV1,
    decision: LiveEnqueueAdmissionDecisionV1,
) -> LiveEnqueueAdmissionLinkageV1:
    source = admission.linkage
    raw = {
        "operator_id": admission.operator_id,
        "candidate_record_id": admission.candidate_record_id,
        "worker_intake_admission_linkage": source,
        "v020_v039_chain_fingerprint": v020_v039_chain_fingerprint(source),
        "readiness_review_fingerprint": source.readiness_review_fingerprint,
        "permission_grant_fingerprint": source.permission_grant_fingerprint,
        "execution_admission_id": source.execution_admission_id,
        "execution_admission_fingerprint": source.execution_admission_fingerprint,
        "runner_binding_plan_id": source.runner_binding_plan_id,
        "runner_binding_plan_fingerprint": source.runner_binding_plan_fingerprint,
        "runner_binding_plan_status_fingerprint": (
            source.runner_binding_plan_status_fingerprint
        ),
        "runner_reference_id": source.runner_reference_id,
        "runner_reference_fingerprint": source.runner_reference_fingerprint,
        "worker_admission_stub_id": source.worker_admission_stub_id,
        "worker_admission_stub_fingerprint": source.worker_admission_stub_fingerprint,
        "worker_admission_stub_status_fingerprint": (
            source.worker_admission_stub_status_fingerprint
        ),
        "worker_reference_id": source.worker_reference_id,
        "worker_reference_fingerprint": source.worker_reference_fingerprint,
        "queue_reservation_id": source.queue_reservation_id,
        "queue_reservation_fingerprint": source.queue_reservation_fingerprint,
        "queue_reservation_status_fingerprint": source.queue_reservation_status_fingerprint,
        "queue_intake_reference_id": source.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": source.queue_intake_reference_fingerprint,
        "queue_item_reference_id": source.queue_item_reference_id,
        "queue_item_reference_fingerprint": source.queue_item_reference_fingerprint,
        "worker_identity_id": source.worker_identity_id,
        "worker_identity_fingerprint": source.worker_identity_fingerprint,
        "worker_intake_reference_id": source.worker_intake_reference_id,
        "worker_intake_reference_fingerprint": source.worker_intake_reference_fingerprint,
        "worker_intake_admission_id": admission.admission_id,
        "worker_intake_admission_fingerprint": v040_record_fingerprint(admission),
        "worker_intake_admission_status_fingerprint": v040_status_fingerprint(status),
        "live_enqueue_admission_decision_fingerprint": decision.decision_fingerprint,
        "inherited_limits_fingerprint": source.inherited_limits_fingerprint,
    }
    seed = LiveEnqueueAdmissionLinkageV1.model_construct(
        **raw,
        linkage_fingerprint=fingerprint("atlas:seed:v1", "linkage"),
    )
    return LiveEnqueueAdmissionLinkageV1.model_validate(
        {**raw, "linkage_fingerprint": linkage_fingerprint(seed)}
    )


def build_admission(
    validation: LiveEnqueueAdmissionValidationInputV1,
) -> tuple[
    LiveEnqueueAdmissionV1,
    LiveEnqueueAdmissionIdempotencyReservationV1,
    LiveEnqueueAdmissionSubjectReservationV1,
]:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.worker_intake_admission.valid_until),
        _instant(validation.worker_intake_admission.worker_identity.valid_until),
        _instant(validation.worker_intake_admission.worker_intake_reference.valid_until),
    )
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request = request_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        create=validation.create,
        request_received_at=validation.authority.request_received_at,
        idempotency_fingerprint=idem,
    )
    decision_id = derived_decision_id(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        worker_intake_admission_fingerprint=validation.worker_intake_admission.record_fingerprint,
        idempotency_fingerprint=idem,
    )
    decision = build_decision(
        decision_id=decision_id,
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        worker_intake_admission=validation.worker_intake_admission,
        evaluated_at=validation.authority.request_received_at,
    )
    link = build_linkage(
        validation.worker_intake_admission,
        validation.worker_intake_admission_status,
        decision,
    )
    raw_without_id = {
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "linkage": link,
        "admission_decision": decision,
        "inherited_limits": validation.worker_intake_admission.inherited_limits,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
    }
    subject_seed = LiveEnqueueAdmissionV1.model_construct(
        admission_id=derived_uuid5("atlas:live-enqueue-admission-seed-id:v1", request),
        **raw_without_id,
        subject_fingerprint=fingerprint("atlas:seed:v1", "subject"),
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    subject = record_subject_fingerprint(subject_seed)
    admission_id = derived_admission_id(subject)
    record_seed = LiveEnqueueAdmissionV1.model_construct(
        admission_id=admission_id,
        **raw_without_id,
        subject_fingerprint=subject,
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    record = LiveEnqueueAdmissionV1.model_validate(
        {
            "admission_id": admission_id,
            **raw_without_id,
            "subject_fingerprint": subject,
            "record_fingerprint": record_fingerprint(record_seed),
        }
    )
    common = {
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
        "subject_fingerprint": subject,
        "admission_id": record.admission_id,
        "record_fingerprint": record.record_fingerprint,
        "reserved_at": record.recorded_at,
    }
    idempotency = LiveEnqueueAdmissionIdempotencyReservationV1(**common)
    reservation_raw = {
        **common,
        "worker_intake_admission_fingerprint": link.worker_intake_admission_fingerprint,
        "worker_queue_reservation_fingerprint": link.queue_reservation_fingerprint,
        "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
        "worker_identity_fingerprint": link.worker_identity_fingerprint,
        "worker_intake_reference_fingerprint": link.worker_intake_reference_fingerprint,
        "live_enqueue_admission_decision_fingerprint": (
            link.live_enqueue_admission_decision_fingerprint
        ),
        "inherited_limits_fingerprint": link.inherited_limits_fingerprint,
    }
    reservation_seed = LiveEnqueueAdmissionSubjectReservationV1.model_construct(
        **reservation_raw,
        reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
    )
    permanent = LiveEnqueueAdmissionSubjectReservationV1.model_validate(
        {
            **reservation_raw,
            "reservation_fingerprint": reservation_fingerprint(reservation_seed),
        }
    )
    return record, idempotency, permanent


def build_audit(
    admission: LiveEnqueueAdmissionV1,
    *,
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> LiveEnqueueAdmissionAuditEvidenceV1:
    raw = {
        "event": "live_enqueue_admission_recorded"
        if outcome in {"recorded", "exact_duplicate", "blocked"}
        else "live_enqueue_admission_read",
        "outcome": outcome,
        "operator_fingerprint": opaque_fingerprint(
            "atlas:live-enqueue-admission-operator:v1",
            admission.operator_id,
        ),
        "candidate_record_fingerprint": opaque_fingerprint(
            "atlas:live-enqueue-admission-candidate:v1",
            admission.candidate_record_id,
        ),
        "admission_id": admission.admission_id,
        "subject_fingerprint": admission.subject_fingerprint,
        "record_fingerprint": admission.record_fingerprint,
        "correlation_fingerprint": correlation_fingerprint,
        "occurred_at": occurred_at,
    }
    seed = LiveEnqueueAdmissionAuditEvidenceV1.model_construct(
        **raw,
        audit_fingerprint=fingerprint("atlas:seed:v1", "audit"),
    )
    return LiveEnqueueAdmissionAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_fingerprint(seed)}
    )


def derive_status(
    admission: LiveEnqueueAdmissionV1,
    *,
    evaluated_at: str,
) -> LiveEnqueueAdmissionStatusV1:
    raw = {
        "admission_id": admission.admission_id,
        "operator_id": admission.operator_id,
        "candidate_record_id": admission.candidate_record_id,
        "evaluated_at": evaluated_at,
        "valid_until": admission.valid_until,
        "lifecycle": (
            "active"
            if _instant(evaluated_at) < _instant(admission.valid_until)
            else "expired"
        ),
        "eligibility": admission.eligibility,
        "blockers": admission.blockers,
        "record_fingerprint": admission.record_fingerprint,
    }
    seed = LiveEnqueueAdmissionStatusV1.model_construct(
        **raw,
        status_fingerprint=fingerprint("atlas:seed:v1", "status"),
    )
    return LiveEnqueueAdmissionStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[LiveEnqueueAdmissionV1, ...],
) -> LiveEnqueueAdmissionCollectionV1:
    ordered = tuple(sorted(items, key=lambda item: (item.recorded_at, item.admission_id)))
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": ordered,
        "count": len(ordered),
    }
    seed = LiveEnqueueAdmissionCollectionV1.model_construct(
        **raw,
        collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
    )
    return LiveEnqueueAdmissionCollectionV1.model_validate(
        {**raw, "collection_fingerprint": collection_fingerprint(seed)}
    )


def evaluate_live_enqueue_admission(
    value: LiveEnqueueAdmissionValidationInputV1 | dict[str, Any],
) -> LiveEnqueueAdmissionEvaluationV1:
    try:
        validation = (
            value
            if isinstance(value, LiveEnqueueAdmissionValidationInputV1)
            else LiveEnqueueAdmissionValidationInputV1.model_validate(value)
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    evidence = build_worker_intake_evidence(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        admission=validation.worker_intake_admission,
        status=validation.worker_intake_admission_status,
        queue_reservation=validation.worker_queue_reservation,
        queue_reservation_status=validation.worker_queue_reservation_status,
    )
    earliest = min(
        _instant(validation.worker_intake_admission.valid_until),
        _instant(validation.worker_queue_reservation.valid_until),
        _instant(validation.worker_intake_admission.worker_identity.valid_until),
        _instant(validation.worker_intake_admission.worker_intake_reference.valid_until),
    )
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest.strftime("%Y-%m-%dT%H:%M:%SZ"),
        eligibility="live_enqueue_admission_recorded",
        blockers=ADMISSION_BLOCKERS,
        worker_intake_evidence=evidence,
    )


def _evaluation(
    *,
    operator_id: str,
    candidate_record_id: str,
    evaluated_at: str,
    earliest_expiry: str | None,
    eligibility: Literal["live_enqueue_admission_recorded", "readiness_gated", "blocked"],
    blockers: tuple[BlockerV1, ...],
    worker_intake_evidence: LiveEnqueueWorkerIntakeEvidenceV1 | None,
) -> LiveEnqueueAdmissionEvaluationV1:
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "eligibility": eligibility,
        "blockers": blockers,
        "worker_intake_evidence": worker_intake_evidence,
        "recognized_active_v040_worker_intake_count": (
            1 if worker_intake_evidence is not None else 0
        ),
        "recognized_active_v040_worker_intake_as_inert_evidence": (
            worker_intake_evidence is not None
        ),
        "admission_record_build_allowed": (
            eligibility == "live_enqueue_admission_recorded"
        ),
    }
    seed = LiveEnqueueAdmissionEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return LiveEnqueueAdmissionEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: LiveEnqueueAdmissionValidationInputV1 | dict[str, Any],
    reason: str,
) -> LiveEnqueueAdmissionEvaluationV1:
    raw = value.model_dump(mode="python") if isinstance(value, BaseModel) else dict(value)
    authority = raw.get("authority") if isinstance(raw.get("authority"), dict) else {}
    operator_id = _safe_operator_id(
        raw.get("operator_id") or authority.get("authenticated_operator_id")
    )
    candidate_record_id = _safe_candidate_id(raw.get("candidate_record_id"))
    evaluated_at = _safe_utc_second(
        authority.get("request_received_at") or "1970-01-01T00:00:00Z"
    )
    blocker = _blocker_from_reason(reason)
    eligibility: Literal["readiness_gated", "blocked"] = (
        "readiness_gated"
        if blocker
        in {
            "evidence_stale",
            "evidence_expired",
            "worker_intake_admission_not_active",
            "queue_reservation_not_active",
            "worker_identity_ineligible",
            "worker_intake_reference_ineligible",
        }
        else "blocked"
    )
    return _evaluation(
        operator_id=operator_id,
        candidate_record_id=candidate_record_id,
        evaluated_at=evaluated_at,
        earliest_expiry=None,
        eligibility=eligibility,
        blockers=(blocker,),
        worker_intake_evidence=None,
    )


def _blocker_from_reason(reason: str) -> BlockerV1:
    lowered = reason.lower()
    if "home assistant" in lowered or "unsupported" in lowered:
        return "installation_capability_unsupported"
    if "ownership" in lowered:
        return "ownership_mismatch"
    if "permission" in lowered:
        return "permission_scope_missing"
    if "linkage" in lowered:
        return "linkage_mismatch"
    if "fingerprint" in lowered:
        return "fingerprint_mismatch"
    if "stale" in lowered or "future" in lowered:
        return "evidence_stale"
    if "expired" in lowered:
        return "evidence_expired"
    if "worker intake admission is not active" in lowered:
        return "worker_intake_admission_not_active"
    if "queue reservation" in lowered:
        return "queue_reservation_not_active"
    if "queue item" in lowered:
        return "queue_item_reference_invalid"
    if "worker identity" in lowered:
        return "worker_identity_ineligible"
    if "intake reference" in lowered:
        return "worker_intake_reference_ineligible"
    if "limits" in lowered:
        return "inherited_limits_mismatch"
    return "evidence_not_found"


def _safe_operator_id(value: Any) -> str:
    if isinstance(value, str) and value.isascii() and _IDENTITY.fullmatch(value):
        return value
    return _BLOCKED_OPERATOR_ID


def _safe_candidate_id(value: Any) -> str:
    if isinstance(value, str) and _UUID4.fullmatch(value):
        return value
    return _BLOCKED_CANDIDATE_ID


def _safe_utc_second(value: Any) -> str:
    if isinstance(value, str):
        try:
            _instant(value)
        except ValueError:
            pass
        else:
            return value
    return "1970-01-01T00:00:00Z"


def parse_create_json(payload: bytes | str) -> LiveEnqueueAdmissionCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("live enqueue admission request exceeds 16 KiB")
    try:
        decoded = raw.decode("utf-8")
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        parsed = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
        return LiveEnqueueAdmissionCreateV1.model_validate(parsed)
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid live enqueue admission request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")
