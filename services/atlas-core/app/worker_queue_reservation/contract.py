"""Closed immutable v0.39 worker queue reservation models and validation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
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
from app.worker_admission_stub.contract import (
    WorkerAdmissionStubLinkageV1,
    WorkerAdmissionStubStatusV1,
    WorkerAdmissionStubV1,
)
from app.worker_admission_stub.contract import (
    status_fingerprint as v038_status_fingerprint,
)
from app.worker_admission_stub.contract import stub_fingerprint as v038_stub_fingerprint

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 128 * 1024
MAX_COLLECTION_RECORDS = 100
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.worker_queue_reservation.record"
READ_PERMISSION = "installation.execution.worker_queue_reservation.read"
SCOPE = "installation_worker_queue_reservation_only"
SAFE_MESSAGE = "worker queue reservation request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")

BlockerV1 = Literal[
    "installation_capability_unsupported", "evidence_not_found",
    "ownership_mismatch", "permission_scope_missing", "linkage_mismatch",
    "fingerprint_mismatch", "evidence_stale", "evidence_expired",
    "worker_admission_not_active", "worker_reference_ineligible",
    "queue_intake_reference_ineligible", "queue_item_reference_invalid",
    "inherited_limits_mismatch", "permanent_subject_reserved",
    "live_enqueue_not_defined", "dequeue_not_defined",
    "worker_start_not_defined", "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported", "evidence_not_found",
    "ownership_mismatch", "permission_scope_missing", "linkage_mismatch",
    "fingerprint_mismatch", "evidence_stale", "evidence_expired",
    "worker_admission_not_active", "worker_reference_ineligible",
    "queue_intake_reference_ineligible", "queue_item_reference_invalid",
    "inherited_limits_mismatch", "permanent_subject_reserved",
    "live_enqueue_not_defined", "dequeue_not_defined",
    "worker_start_not_defined", "execution_start_boundary_not_defined",
)
RESERVATION_BLOCKERS: tuple[BlockerV1, ...] = (
    "live_enqueue_not_defined", "dequeue_not_defined",
    "worker_start_not_defined", "execution_start_boundary_not_defined",
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


class NoAuthorityV1(ContractModel):
    default_enabled: Literal[False] = False
    evidence_only: Literal[True] = True
    live_enqueue_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
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


class WorkerQueueReservationCreateV1(ContractModel):
    schema: Literal["worker-queue-reservation-create-v1"] = "worker-queue-reservation-create-v1"
    worker_admission_stub_id: CanonicalUuid4
    worker_admission_stub_fingerprint: FingerprintV1
    worker_admission_stub_valid_until: UtcSecond
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE
    evidence_only: Literal[True] = True
    live_enqueue_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class WorkerQueueReservationAuthorityContextV1(NoAuthorityV1):
    schema: Literal["worker-queue-reservation-authority-context-v1"] = (
        "worker-queue-reservation-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class QueueIntakeReferenceV1(ContractModel):
    schema: Literal["worker-queue-intake-reference-v1"] = "worker-queue-intake-reference-v1"
    queue_intake_reference_id: CanonicalUuid4
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_admission_stub_id: CanonicalUuid4
    worker_admission_stub_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    queue_kind: Literal["abstract_installation_queue"] = "abstract_installation_queue"
    trust_domain: Literal["atlas-installation"] = "atlas-installation"
    scope: Literal[SCOPE] = SCOPE
    eligibility: Literal["eligible_for_reservation_evidence_only"] = (
        "eligible_for_reservation_evidence_only"
    )
    identity_fingerprint: FingerprintV1
    capability_fingerprint: FingerprintV1
    inherited_limits: RunnerBindingLimitsV1
    inherited_limits_fingerprint: FingerprintV1
    valid_from: UtcSecond
    valid_until: UtcSecond
    reference_fingerprint: FingerprintV1
    queue_exists: Literal[False] = False
    queue_reachable: Literal[False] = False
    queue_authenticated: Literal[False] = False
    queue_contacted: Literal[False] = False
    reservation_endpoint_known: Literal[False] = False
    live_enqueue_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> QueueIntakeReferenceV1:
        start, expiry = _instant(self.valid_from), _instant(self.valid_until)
        if not start < expiry <= start + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("queue intake reference expiry exceeds freshness bound")
        if self.inherited_limits_fingerprint != self.inherited_limits.limits_fingerprint:
            raise ValueError("queue intake inherited limits mismatch")
        if self.reference_fingerprint != queue_intake_reference_fingerprint(self):
            raise ValueError("queue intake reference fingerprint mismatch")
        _bounded(self)
        return self


class QueueItemReferenceV1(ContractModel):
    schema: Literal["worker-queue-item-reference-v1"] = "worker-queue-item-reference-v1"
    queue_item_reference_id: CanonicalUuid5
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_admission_stub_id: CanonicalUuid4
    worker_admission_stub_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    item_kind: Literal["installation_evidence_reference_only"] = (
        "installation_evidence_reference_only"
    )
    scope: Literal[SCOPE] = SCOPE
    inherited_limits_fingerprint: FingerprintV1
    created_at: UtcSecond
    item_fingerprint: FingerprintV1
    payload_defined: Literal[False] = False
    serialized: Literal[False] = False
    enqueued: Literal[False] = False
    dequeued: Literal[False] = False
    claimed: Literal[False] = False
    executable: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> QueueItemReferenceV1:
        if self.item_fingerprint != queue_item_reference_fingerprint(self):
            raise ValueError("queue item reference fingerprint mismatch")
        _bounded(self)
        return self


class WorkerQueueReservationLinkageV1(ContractModel):
    schema: Literal["worker-queue-reservation-linkage-v1"] = (
        "worker-queue-reservation-linkage-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_admission_stub_linkage: WorkerAdmissionStubLinkageV1
    v020_v037_chain_fingerprint: FingerprintV1
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
    worker_admission_intent_fingerprint: FingerprintV1
    worker_intake_stub_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationLinkageV1:
        source = self.worker_admission_stub_linkage
        if (
            self.operator_id != source.operator_id
            or self.candidate_record_id != source.candidate_record_id
            or self.readiness_review_fingerprint
            != source.readiness_review_fingerprint
            or self.permission_grant_fingerprint
            != source.permission_grant_fingerprint
            or self.execution_admission_id != source.execution_admission_id
            or self.execution_admission_fingerprint
            != source.execution_admission_fingerprint
            or self.runner_binding_plan_id != source.runner_binding_plan_id
            or self.runner_binding_plan_fingerprint
            != source.runner_binding_plan_fingerprint
            or self.runner_binding_plan_status_fingerprint
            != source.runner_binding_plan_status_fingerprint
            or self.runner_reference_id != source.runner_reference_id
            or self.runner_reference_fingerprint
            != source.runner_reference_fingerprint
            or self.worker_reference_id != source.worker_reference_id
            or self.worker_reference_fingerprint
            != source.worker_reference_fingerprint
            or self.worker_admission_intent_fingerprint
            != source.worker_admission_intent_fingerprint
            or self.worker_intake_stub_fingerprint
            != source.worker_admission_intake_fingerprint
            or self.inherited_limits_fingerprint != source.inherited_limits_fingerprint
            or self.v020_v037_chain_fingerprint != v020_v037_chain_fingerprint(source)
        ):
            raise ValueError("embedded worker admission stub linkage mismatch")
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("worker queue reservation linkage fingerprint mismatch")
        _bounded(self)
        return self


class WorkerQueueReservationV1(NoAuthorityV1):
    schema: Literal["worker-queue-reservation-v1"] = "worker-queue-reservation-v1"
    reservation_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    lifecycle: Literal["active"] = "active"
    eligibility: Literal["worker_queue_reservation_recorded"] = (
        "worker_queue_reservation_recorded"
    )
    blockers: tuple[BlockerV1, ...] = RESERVATION_BLOCKERS
    linkage: WorkerQueueReservationLinkageV1
    queue_intake_reference: QueueIntakeReferenceV1
    queue_item_reference: QueueItemReferenceV1
    inherited_limits: RunnerBindingLimitsV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationV1:
        if self.blockers != RESERVATION_BLOCKERS:
            raise ValueError("worker queue reservation blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("worker queue reservation expiry exceeds freshness bound")
        intake, item, link = self.queue_intake_reference, self.queue_item_reference, self.linkage
        if (
            self.operator_id != link.operator_id
            or self.operator_id != intake.owner_operator_id
            or self.operator_id != item.owner_operator_id
            or self.candidate_record_id != link.candidate_record_id
            or self.candidate_record_id != intake.candidate_record_id
            or self.candidate_record_id != item.candidate_record_id
            or intake.queue_intake_reference_id != item.queue_intake_reference_id
            or intake.reference_fingerprint != item.queue_intake_reference_fingerprint
            or intake.reference_fingerprint != link.queue_intake_reference_fingerprint
            or item.item_fingerprint != link.queue_item_reference_fingerprint
            or self.inherited_limits != intake.inherited_limits
            or self.inherited_limits.limits_fingerprint != link.inherited_limits_fingerprint
        ):
            raise ValueError("worker queue reservation ownership or linkage mismatch")
        if self.subject_fingerprint != record_subject_fingerprint(self):
            raise ValueError("worker queue reservation subject fingerprint mismatch")
        if self.record_fingerprint != record_fingerprint(self):
            raise ValueError("worker queue reservation record fingerprint mismatch")
        _bounded(self)
        return self


class WorkerQueueReservationStatusV1(NoAuthorityV1):
    schema: Literal["worker-queue-reservation-status-v1"] = (
        "worker-queue-reservation-status-v1"
    )
    reservation_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    observed_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal["worker_queue_reservation_recorded", "readiness_gated", "blocked"]
    blockers: tuple[BlockerV1, ...]
    record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationStatusV1:
        if tuple(sorted(self.blockers, key=BLOCKER_ORDER.index)) != self.blockers:
            raise ValueError("worker queue reservation blockers are not ordered")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("worker queue reservation blockers contain duplicates")
        if self.eligibility == "worker_queue_reservation_recorded" and self.blockers != RESERVATION_BLOCKERS:
            raise ValueError("recorded status blockers must remain fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("worker queue reservation status fingerprint mismatch")
        return self


class WorkerQueueIdempotencyReservationV1(ContractModel):
    schema: Literal["worker-queue-idempotency-reservation-v1"] = (
        "worker-queue-idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    reservation_id: CanonicalUuid4
    record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    permanent: Literal[True] = True
    raw_key_persisted: Literal[False] = False
    consumed: Literal[False] = False
    released: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False


class WorkerQueueSubjectReservationV1(ContractModel):
    schema: Literal["worker-queue-subject-reservation-v1"] = (
        "worker-queue-subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_admission_stub_fingerprint: FingerprintV1
    worker_reference_fingerprint: FingerprintV1
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    reservation_id: CanonicalUuid4
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
    def exact(self) -> WorkerQueueSubjectReservationV1:
        if self.subject_fingerprint != reservation_subject_fingerprint(self):
            raise ValueError("worker queue subject fingerprint mismatch")
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("worker queue subject reservation fingerprint mismatch")
        return self


class WorkerQueueReservationAuditEvidenceV1(ContractModel):
    schema: Literal["worker-queue-reservation-audit-v1"] = "worker-queue-reservation-audit-v1"
    event: Literal["reservation_recorded", "reservation_read"]
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"]
    operator_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    reservation_id: CanonicalUuid4 | None
    subject_fingerprint: FingerprintV1 | None
    record_fingerprint: FingerprintV1 | None
    correlation_fingerprint: FingerprintV1
    occurred_at: UtcSecond
    audit_fingerprint: FingerprintV1
    evidence_only: Literal[True] = True
    queue_contact_attempted: Literal[False] = False
    enqueue_attempted: Literal[False] = False
    dequeue_attempted: Literal[False] = False
    worker_start_attempted: Literal[False] = False
    dispatch_attempted: Literal[False] = False
    execution_start_attempted: Literal[False] = False
    agent_invocation_attempted: Literal[False] = False
    process_execution_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False
    replay_attempted: Literal[False] = False
    effect_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("worker queue reservation audit fingerprint mismatch")
        return self


class WorkerQueueReservationRedactedErrorV1(NoAuthorityV1):
    schema: Literal["worker-queue-reservation-error-v1"] = "worker-queue-reservation-error-v1"
    error_code: Literal[
        "malformed", "unauthenticated", "forbidden", "not_found", "invalid_request",
        "not_eligible", "expired", "rate_limited", "quota_exceeded", "conflict",
        "record_too_large", "store_corrupt", "internal_error",
    ]
    message: Literal[SAFE_MESSAGE] = SAFE_MESSAGE
    retryable: Literal[False] = False
    correlation_fingerprint: FingerprintV1
    redacted: Literal[True] = True


class WorkerQueueReservationResultV1(NoAuthorityV1):
    schema: Literal["worker-queue-reservation-result-v1"] = "worker-queue-reservation-result-v1"
    disposition: Literal["recorded", "exact_duplicate", "read", "blocked"]
    reservation: WorkerQueueReservationV1 | None
    status: WorkerQueueReservationStatusV1 | None
    audit_evidence: WorkerQueueReservationAuditEvidenceV1 | None
    error: WorkerQueueReservationRedactedErrorV1 | None

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationResultV1:
        success = self.disposition in {"recorded", "exact_duplicate", "read"}
        if success != (
            self.reservation is not None
            and self.status is not None
            and self.audit_evidence is not None
            and self.error is None
        ):
            raise ValueError("result shape does not match disposition")
        if success and self.audit_evidence.outcome != self.disposition:
            raise ValueError("result audit disposition mismatch")
        _bounded(self)
        return self


class WorkerQueueReservationCollectionV1(NoAuthorityV1):
    schema: Literal["worker-queue-reservation-collection-v1"] = (
        "worker-queue-reservation-collection-v1"
    )
    items: tuple[WorkerQueueReservationResultV1, ...]
    count: int

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("worker queue reservation collection exceeds bound")
        _bounded(self)
        return self


class WorkerQueueReservationValidationInputV1(ContractModel):
    """Injected P1 facts only; no reader, store, queue, worker, or I/O."""

    operator_id: OperatorId
    authority: WorkerQueueReservationAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: WorkerQueueReservationCreateV1
    worker_admission_stub: WorkerAdmissionStubV1
    worker_admission_stub_status: WorkerAdmissionStubStatusV1
    queue_intake_reference: QueueIntakeReferenceV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerQueueReservationValidationInputV1:
        stub, status, intake = (
            self.worker_admission_stub, self.worker_admission_stub_status,
            self.queue_intake_reference,
        )
        now = _instant(self.authority.request_received_at)
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or stub.operator_id != self.operator_id
            or intake.owner_operator_id != self.operator_id
        ):
            raise ValueError("worker queue reservation ownership mismatch")
        if (
            stub.candidate_record_id != self.candidate_record_id
            or intake.candidate_record_id != self.candidate_record_id
            or self.create.worker_admission_stub_id != stub.stub_id
            or self.create.worker_admission_stub_fingerprint != stub.stub_fingerprint
            or self.create.worker_admission_stub_valid_until != stub.valid_until
            or intake.worker_admission_stub_id != stub.stub_id
            or intake.worker_admission_stub_fingerprint != stub.stub_fingerprint
        ):
            raise ValueError("worker admission stub linkage mismatch")
        if (
            status.stub_id != stub.stub_id
            or status.status_fingerprint != v038_status_fingerprint(status)
            or status.lifecycle != "active"
            or status.eligibility != "worker_admission_stubbed"
        ):
            raise ValueError("worker admission stub is not active")
        worker = stub.worker_reference
        if (
            intake.worker_reference_id != worker.worker_reference_id
            or intake.worker_reference_fingerprint != worker.reference_fingerprint
            or self.create.queue_intake_reference_id != intake.queue_intake_reference_id
            or self.create.queue_intake_reference_fingerprint != intake.reference_fingerprint
        ):
            raise ValueError("queue intake reference linkage mismatch")
        if (
            self.create.inherited_limits_fingerprint != stub.inherited_limits.limits_fingerprint
            or intake.inherited_limits != stub.inherited_limits
            or intake.inherited_limits_fingerprint != stub.inherited_limits.limits_fingerprint
        ):
            raise ValueError("inherited limits mismatch")
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        starts = (_instant(stub.recorded_at), _instant(status.observed_at), _instant(intake.valid_from))
        if any(value > now or now - value > timedelta(seconds=30) for value in starts):
            raise ValueError("worker queue evidence is stale or from the future")
        if now >= _instant(stub.valid_until) or now >= _instant(intake.valid_until):
            raise ValueError("worker queue evidence is expired")
        return self


def queue_intake_reference_fingerprint(value: QueueIntakeReferenceV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-intake-reference:v1", _without(value, "reference_fingerprint"))


def queue_item_reference_fingerprint(value: QueueItemReferenceV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-item-reference:v1", _without(value, "item_fingerprint"))


def v020_v037_chain_fingerprint(value: WorkerAdmissionStubLinkageV1) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-queue-reservation-v020-v037-chain:v1",
        {
            "runner_binding_plan_linkage": value.runner_binding_plan_linkage,
            "runner_binding_plan_id": value.runner_binding_plan_id,
            "runner_binding_plan_fingerprint": value.runner_binding_plan_fingerprint,
        },
    )


def linkage_fingerprint(value: WorkerQueueReservationLinkageV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-reservation-linkage:v1", _without(value, "linkage_fingerprint"))


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:worker-queue-reservation-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *, operator_id: str, candidate_record_id: str,
    create: WorkerQueueReservationCreateV1, request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-queue-reservation-request:v1",
        {
            "operator_id": operator_id, "candidate_record_id": candidate_record_id,
            "create": create, "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def _subject_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        key: raw[key] for key in (
            "operator_id", "candidate_record_id", "worker_admission_stub_fingerprint",
            "worker_reference_fingerprint", "queue_intake_reference_fingerprint",
            "queue_item_reference_fingerprint", "inherited_limits_fingerprint",
        )
    }


def record_subject_fingerprint(value: WorkerQueueReservationV1 | dict[str, Any]) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    link = raw["linkage"]
    stub_link = link["worker_admission_stub_linkage"]
    return fingerprint(
        "atlas:worker-queue-reservation-subject:v1",
        _subject_fields(
            {
                "operator_id": raw["operator_id"],
                "candidate_record_id": raw["candidate_record_id"],
                "worker_admission_stub_fingerprint": link[
                    "worker_admission_stub_fingerprint"
                ],
                "worker_reference_fingerprint": stub_link[
                    "worker_reference_fingerprint"
                ],
                "queue_intake_reference_fingerprint": link[
                    "queue_intake_reference_fingerprint"
                ],
                "queue_item_reference_fingerprint": link[
                    "queue_item_reference_fingerprint"
                ],
                "inherited_limits_fingerprint": link[
                    "inherited_limits_fingerprint"
                ],
            }
        ),
    )


def record_fingerprint(value: WorkerQueueReservationV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-reservation-record:v1", _without(value, "record_fingerprint"))


def status_fingerprint(value: WorkerQueueReservationStatusV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-reservation-status:v1", _without(value, "status_fingerprint"))


def reservation_subject_fingerprint(value: WorkerQueueSubjectReservationV1 | dict[str, Any]) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint("atlas:worker-queue-reservation-subject:v1", _subject_fields(raw))


def reservation_fingerprint(value: WorkerQueueSubjectReservationV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-reservation-reservation:v1", _without(value, "reservation_fingerprint"))


def audit_fingerprint(value: WorkerQueueReservationAuditEvidenceV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:worker-queue-reservation-audit:v1", _without(value, "audit_fingerprint"))


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def build_queue_intake_reference(
    *, queue_intake_reference_id: str, owner_operator_id: str,
    candidate_record_id: str, worker_admission_stub: WorkerAdmissionStubV1,
    identity_fingerprint: FingerprintV1, capability_fingerprint: FingerprintV1,
    valid_from: str, valid_until: str,
) -> QueueIntakeReferenceV1:
    worker = worker_admission_stub.worker_reference
    raw = {
        "queue_intake_reference_id": queue_intake_reference_id,
        "owner_operator_id": owner_operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_admission_stub_id": worker_admission_stub.stub_id,
        "worker_admission_stub_fingerprint": worker_admission_stub.stub_fingerprint,
        "worker_reference_id": worker.worker_reference_id,
        "worker_reference_fingerprint": worker.reference_fingerprint,
        "identity_fingerprint": identity_fingerprint,
        "capability_fingerprint": capability_fingerprint,
        "inherited_limits": worker_admission_stub.inherited_limits,
        "inherited_limits_fingerprint": worker_admission_stub.inherited_limits.limits_fingerprint,
        "valid_from": valid_from, "valid_until": valid_until,
    }
    seed = QueueIntakeReferenceV1.model_construct(
        **raw, reference_fingerprint=fingerprint("atlas:seed:v1", "intake")
    )
    return QueueIntakeReferenceV1.model_validate(
        {**raw, "reference_fingerprint": queue_intake_reference_fingerprint(seed)}
    )


def build_queue_item_reference(
    *, queue_item_reference_id: str, operator_id: str, candidate_record_id: str,
    worker_admission_stub: WorkerAdmissionStubV1,
    queue_intake_reference: QueueIntakeReferenceV1, created_at: str,
) -> QueueItemReferenceV1:
    stub, intake = worker_admission_stub, queue_intake_reference
    raw = {
        "queue_item_reference_id": queue_item_reference_id,
        "owner_operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_admission_stub_id": stub.stub_id,
        "worker_admission_stub_fingerprint": stub.stub_fingerprint,
        "queue_intake_reference_id": intake.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": intake.reference_fingerprint,
        "worker_reference_id": stub.worker_reference.worker_reference_id,
        "worker_reference_fingerprint": stub.worker_reference.reference_fingerprint,
        "inherited_limits_fingerprint": stub.inherited_limits.limits_fingerprint,
        "created_at": created_at,
    }
    seed = QueueItemReferenceV1.model_construct(
        **raw, item_fingerprint=fingerprint("atlas:seed:v1", "item")
    )
    return QueueItemReferenceV1.model_validate(
        {**raw, "item_fingerprint": queue_item_reference_fingerprint(seed)}
    )


def build_linkage(
    stub: WorkerAdmissionStubV1, status: WorkerAdmissionStubStatusV1,
    intake: QueueIntakeReferenceV1, item: QueueItemReferenceV1,
) -> WorkerQueueReservationLinkageV1:
    source = stub.linkage
    raw = {
        "operator_id": stub.operator_id, "candidate_record_id": stub.candidate_record_id,
        "worker_admission_stub_linkage": source,
        "v020_v037_chain_fingerprint": v020_v037_chain_fingerprint(source),
        "readiness_review_fingerprint": source.readiness_review_fingerprint,
        "permission_grant_fingerprint": source.permission_grant_fingerprint,
        "execution_admission_id": source.execution_admission_id,
        "execution_admission_fingerprint": source.execution_admission_fingerprint,
        "runner_binding_plan_id": source.runner_binding_plan_id,
        "runner_binding_plan_fingerprint": source.runner_binding_plan_fingerprint,
        "runner_binding_plan_status_fingerprint": source.runner_binding_plan_status_fingerprint,
        "runner_reference_id": source.runner_reference_id,
        "runner_reference_fingerprint": source.runner_reference_fingerprint,
        "worker_admission_stub_id": stub.stub_id,
        "worker_admission_stub_fingerprint": v038_stub_fingerprint(stub),
        "worker_admission_stub_status_fingerprint": v038_status_fingerprint(status),
        "worker_reference_id": source.worker_reference_id,
        "worker_reference_fingerprint": source.worker_reference_fingerprint,
        "worker_admission_intent_fingerprint": source.worker_admission_intent_fingerprint,
        "worker_intake_stub_fingerprint": source.worker_admission_intake_fingerprint,
        "queue_intake_reference_id": intake.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": intake.reference_fingerprint,
        "queue_item_reference_id": item.queue_item_reference_id,
        "queue_item_reference_fingerprint": item.item_fingerprint,
        "inherited_limits_fingerprint": source.inherited_limits_fingerprint,
    }
    seed = WorkerQueueReservationLinkageV1.model_construct(
        **raw, linkage_fingerprint=fingerprint("atlas:seed:v1", "linkage")
    )
    return WorkerQueueReservationLinkageV1.model_validate(
        {**raw, "linkage_fingerprint": linkage_fingerprint(seed)}
    )


def build_reservation(
    validation: WorkerQueueReservationValidationInputV1, *, reservation_id: str,
) -> tuple[
    WorkerQueueReservationV1,
    WorkerQueueIdempotencyReservationV1,
    WorkerQueueSubjectReservationV1,
]:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.worker_admission_stub.valid_until),
        _instant(validation.queue_intake_reference.valid_until),
    )
    item = build_queue_item_reference(
        queue_item_reference_id=validation.create.queue_item_reference_id,
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        worker_admission_stub=validation.worker_admission_stub,
        queue_intake_reference=validation.queue_intake_reference,
        created_at=validation.authority.request_received_at,
    )
    if item.item_fingerprint != validation.create.queue_item_reference_fingerprint:
        raise ValueError("queue item reference linkage mismatch")
    link = build_linkage(
        validation.worker_admission_stub,
        validation.worker_admission_stub_status,
        validation.queue_intake_reference,
        item,
    )
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request = request_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        create=validation.create,
        request_received_at=validation.authority.request_received_at,
        idempotency_fingerprint=idem,
    )
    raw = {
        "reservation_id": reservation_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "linkage": link,
        "queue_intake_reference": validation.queue_intake_reference,
        "queue_item_reference": item,
        "inherited_limits": validation.worker_admission_stub.inherited_limits,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
    }
    seed = WorkerQueueReservationV1.model_construct(
        **raw,
        subject_fingerprint=fingerprint("atlas:seed:v1", "subject"),
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    subject = record_subject_fingerprint(seed)
    seed = WorkerQueueReservationV1.model_construct(
        **raw, subject_fingerprint=subject,
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    record = WorkerQueueReservationV1.model_validate(
        {**raw, "subject_fingerprint": subject,
         "record_fingerprint": record_fingerprint(seed)}
    )
    common = {
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
        "subject_fingerprint": subject,
        "reservation_id": record.reservation_id,
        "record_fingerprint": record.record_fingerprint,
        "reserved_at": record.recorded_at,
    }
    idempotency = WorkerQueueIdempotencyReservationV1(**common)
    reservation_raw = {
        **common,
        "worker_admission_stub_fingerprint": link.worker_admission_stub_fingerprint,
        "worker_reference_fingerprint": link.worker_admission_stub_linkage.worker_reference_fingerprint,
        "queue_intake_reference_fingerprint": link.queue_intake_reference_fingerprint,
        "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
        "inherited_limits_fingerprint": link.inherited_limits_fingerprint,
    }
    reservation_seed = WorkerQueueSubjectReservationV1.model_construct(
        **reservation_raw,
        reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
    )
    permanent = WorkerQueueSubjectReservationV1.model_validate(
        {**reservation_raw,
         "reservation_fingerprint": reservation_fingerprint(reservation_seed)}
    )
    return record, idempotency, permanent


def derive_status(
    reservation: WorkerQueueReservationV1, *, observed_at: str,
) -> WorkerQueueReservationStatusV1:
    raw = {
        "reservation_id": reservation.reservation_id,
        "operator_id": reservation.operator_id,
        "candidate_record_id": reservation.candidate_record_id,
        "observed_at": observed_at,
        "valid_until": reservation.valid_until,
        "lifecycle": "active" if _instant(observed_at) < _instant(reservation.valid_until) else "expired",
        "eligibility": reservation.eligibility,
        "blockers": reservation.blockers,
        "record_fingerprint": reservation.record_fingerprint,
    }
    seed = WorkerQueueReservationStatusV1.model_construct(
        **raw, status_fingerprint=fingerprint("atlas:seed:v1", "status")
    )
    return WorkerQueueReservationStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def parse_create_json(payload: bytes | str) -> WorkerQueueReservationCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("worker queue reservation request exceeds 16 KiB")
    try:
        decoded = raw.decode()
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
        return WorkerQueueReservationCreateV1.model_validate(parsed)
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid worker queue reservation request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
