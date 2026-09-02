"""Closed immutable v0.40 worker intake admission models and pure validation."""

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
from app.worker_queue_reservation.contract import (
    RESERVATION_BLOCKERS as QUEUE_RESERVATION_BLOCKERS,
)
from app.worker_queue_reservation.contract import (
    WorkerQueueReservationLinkageV1,
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
MAX_COLLECTION_RECORDS = 100
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.worker_intake_admission.record"
READ_PERMISSION = "installation.execution.worker_intake_admission.read"
SCOPE = "installation_worker_intake_admission_only"
SAFE_MESSAGE = "worker intake admission request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "evidence_stale",
    "evidence_expired",
    "worker_queue_reservation_not_active",
    "worker_identity_ineligible",
    "worker_intake_reference_ineligible",
    "queue_reservation_binding_mismatch",
    "inherited_limits_mismatch",
    "permanent_subject_reserved",
    "live_enqueue_not_defined",
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
    "worker_queue_reservation_not_active",
    "worker_identity_ineligible",
    "worker_intake_reference_ineligible",
    "queue_reservation_binding_mismatch",
    "inherited_limits_mismatch",
    "permanent_subject_reserved",
    "live_enqueue_not_defined",
    "dequeue_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
)
ADMISSION_BLOCKERS: tuple[BlockerV1, ...] = (
    "live_enqueue_not_defined",
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


def _bounded(value: BaseModel) -> None:
    if len(canonical_json(value)) > MAX_MODEL_BYTES:
        raise ValueError("contract envelope exceeds bound")


class NoAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    live_enqueue_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
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


class WorkerIntakeAdmissionCreateV1(ContractModel):
    schema: Literal["worker-intake-admission-create-v1"] = (
        "worker-intake-admission-create-v1"
    )
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_queue_reservation_valid_until: UtcSecond
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE
    evidence_only: Literal[True] = True
    live_enqueue_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class WorkerIntakeAdmissionAuthorityContextV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-authority-context-v1"] = (
        "worker-intake-admission-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class WorkerIntakeWorkerIdentityV1(ContractModel):
    schema: Literal["worker-intake-worker-identity-v1"] = (
        "worker-intake-worker-identity-v1"
    )
    worker_identity_id: CanonicalUuid4
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    worker_kind: Literal["isolated_installation_worker"] = "isolated_installation_worker"
    trust_domain: Literal["atlas-installation"] = "atlas-installation"
    scope: Literal[SCOPE] = SCOPE
    eligibility: Literal["eligible_for_intake_admission_evidence_only"] = (
        "eligible_for_intake_admission_evidence_only"
    )
    identity_fingerprint: FingerprintV1
    capability_profile_fingerprint: FingerprintV1
    inherited_limits: RunnerBindingLimitsV1
    inherited_limits_fingerprint: FingerprintV1
    valid_from: UtcSecond
    valid_until: UtcSecond
    registered: Literal[False] = False
    available: Literal[False] = False
    reachable: Literal[False] = False
    authenticated: Literal[False] = False
    contacted: Literal[False] = False
    reserved: Literal[False] = False
    started: Literal[False] = False
    execution_allowed: Literal[False] = False
    worker_identity_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeWorkerIdentityV1:
        start, expiry = _instant(self.valid_from), _instant(self.valid_until)
        if not start < expiry <= start + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("worker identity expiry exceeds freshness bound")
        if self.inherited_limits_fingerprint != self.inherited_limits.limits_fingerprint:
            raise ValueError("worker identity inherited limits mismatch")
        if self.worker_identity_fingerprint != worker_identity_fingerprint(self):
            raise ValueError("worker identity fingerprint mismatch")
        _bounded(self)
        return self


class WorkerIntakeReferenceV1(ContractModel):
    schema: Literal["worker-intake-reference-v1"] = "worker-intake-reference-v1"
    worker_intake_reference_id: CanonicalUuid4
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    intake_kind: Literal["abstract_worker_intake"] = "abstract_worker_intake"
    trust_domain: Literal["atlas-installation"] = "atlas-installation"
    scope: Literal[SCOPE] = SCOPE
    eligibility: Literal["eligible_for_intake_admission_evidence_only"] = (
        "eligible_for_intake_admission_evidence_only"
    )
    valid_from: UtcSecond
    valid_until: UtcSecond
    intake_reference_fingerprint: FingerprintV1
    intake_protocol: Literal["none"] = "none"
    intake_exists: Literal[False] = False
    intake_open: Literal[False] = False
    endpoint_known: Literal[False] = False
    credential_known: Literal[False] = False
    payload_schema_defined: Literal[False] = False
    serialization_allowed: Literal[False] = False
    live_enqueue_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeReferenceV1:
        start, expiry = _instant(self.valid_from), _instant(self.valid_until)
        if not start < expiry <= start + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("worker intake reference expiry exceeds freshness bound")
        if self.intake_reference_fingerprint != intake_reference_fingerprint(self):
            raise ValueError("worker intake reference fingerprint mismatch")
        _bounded(self)
        return self


class WorkerIntakeAdmissionDecisionV1(ContractModel):
    schema: Literal["worker-intake-admission-decision-v1"] = (
        "worker-intake-admission-decision-v1"
    )
    decision_id: CanonicalUuid5
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    scope: Literal[SCOPE] = SCOPE
    decision: Literal[
        "preserve_non_executing_worker_intake_admission_evidence_only"
    ] = "preserve_non_executing_worker_intake_admission_evidence_only"
    evaluated_at: UtcSecond
    eligibility: Literal["worker_intake_admission_recorded"] = (
        "worker_intake_admission_recorded"
    )
    blockers: tuple[BlockerV1, ...] = ADMISSION_BLOCKERS
    inherited_limits_fingerprint: FingerprintV1
    decision_fingerprint: FingerprintV1
    payload_constructed: Literal[False] = False
    request_serialized: Literal[False] = False
    request_sent: Literal[False] = False
    queue_enqueued: Literal[False] = False
    queue_dequeued: Literal[False] = False
    worker_contacted: Literal[False] = False
    worker_started: Literal[False] = False
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionDecisionV1:
        if self.blockers != ADMISSION_BLOCKERS:
            raise ValueError("worker intake admission blockers must remain fixed")
        if self.decision_fingerprint != decision_fingerprint(self):
            raise ValueError("worker intake admission decision fingerprint mismatch")
        _bounded(self)
        return self


class WorkerIntakeAdmissionLinkageV1(ContractModel):
    schema: Literal["worker-intake-admission-linkage-v1"] = (
        "worker-intake-admission-linkage-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_queue_reservation_linkage: WorkerQueueReservationLinkageV1
    v020_v038_chain_fingerprint: FingerprintV1
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
    worker_intake_admission_decision_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionLinkageV1:
        source = self.worker_queue_reservation_linkage
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
            or self.queue_intake_reference_id != source.queue_intake_reference_id
            or self.queue_intake_reference_fingerprint
            != source.queue_intake_reference_fingerprint
            or self.queue_item_reference_id != source.queue_item_reference_id
            or self.queue_item_reference_fingerprint
            != source.queue_item_reference_fingerprint
            or self.inherited_limits_fingerprint != source.inherited_limits_fingerprint
            or self.v020_v038_chain_fingerprint != v020_v038_chain_fingerprint(source)
        ):
            raise ValueError("embedded worker queue reservation linkage mismatch")
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("worker intake admission linkage fingerprint mismatch")
        _bounded(self)
        return self


class WorkerIntakeAdmissionV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-v1"] = "worker-intake-admission-v1"
    admission_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    lifecycle: Literal["active"] = "active"
    eligibility: Literal["worker_intake_admission_recorded"] = (
        "worker_intake_admission_recorded"
    )
    blockers: tuple[BlockerV1, ...] = ADMISSION_BLOCKERS
    linkage: WorkerIntakeAdmissionLinkageV1
    worker_identity: WorkerIntakeWorkerIdentityV1
    worker_intake_reference: WorkerIntakeReferenceV1
    admission_decision: WorkerIntakeAdmissionDecisionV1
    inherited_limits: RunnerBindingLimitsV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionV1:
        if self.blockers != ADMISSION_BLOCKERS:
            raise ValueError("worker intake admission blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("worker intake admission expiry exceeds freshness bound")
        link, identity, intake, decision = (
            self.linkage,
            self.worker_identity,
            self.worker_intake_reference,
            self.admission_decision,
        )
        if (
            self.operator_id != link.operator_id
            or self.operator_id != identity.owner_operator_id
            or self.operator_id != intake.owner_operator_id
            or self.operator_id != decision.owner_operator_id
            or self.candidate_record_id != link.candidate_record_id
            or self.candidate_record_id != identity.candidate_record_id
            or self.candidate_record_id != intake.candidate_record_id
            or self.candidate_record_id != decision.candidate_record_id
            or identity.worker_queue_reservation_id != link.queue_reservation_id
            or identity.worker_queue_reservation_fingerprint
            != link.queue_reservation_fingerprint
            or intake.worker_queue_reservation_id != link.queue_reservation_id
            or intake.worker_queue_reservation_fingerprint
            != link.queue_reservation_fingerprint
            or decision.worker_queue_reservation_id != link.queue_reservation_id
            or decision.worker_queue_reservation_fingerprint
            != link.queue_reservation_fingerprint
            or identity.worker_identity_id != intake.worker_identity_id
            or identity.worker_identity_fingerprint != intake.worker_identity_fingerprint
            or identity.worker_identity_id != decision.worker_identity_id
            or identity.worker_identity_fingerprint != decision.worker_identity_fingerprint
            or identity.worker_identity_id != link.worker_identity_id
            or identity.worker_identity_fingerprint != link.worker_identity_fingerprint
            or intake.worker_intake_reference_id != link.worker_intake_reference_id
            or intake.intake_reference_fingerprint
            != link.worker_intake_reference_fingerprint
            or intake.worker_intake_reference_id != decision.worker_intake_reference_id
            or intake.intake_reference_fingerprint
            != decision.worker_intake_reference_fingerprint
            or decision.decision_fingerprint
            != link.worker_intake_admission_decision_fingerprint
            or self.inherited_limits != identity.inherited_limits
            or self.inherited_limits.limits_fingerprint
            != link.inherited_limits_fingerprint
        ):
            raise ValueError("worker intake admission ownership or linkage mismatch")
        if self.subject_fingerprint != record_subject_fingerprint(self):
            raise ValueError("worker intake admission subject fingerprint mismatch")
        if self.record_fingerprint != record_fingerprint(self):
            raise ValueError("worker intake admission record fingerprint mismatch")
        _bounded(self)
        return self


class WorkerIntakeAdmissionStatusV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-status-v1"] = (
        "worker-intake-admission-status-v1"
    )
    admission_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal["worker_intake_admission_recorded", "readiness_gated", "blocked"]
    blockers: tuple[BlockerV1, ...]
    record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionStatusV1:
        if tuple(sorted(self.blockers, key=BLOCKER_ORDER.index)) != self.blockers:
            raise ValueError("worker intake admission blockers are not ordered")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("worker intake admission blockers contain duplicates")
        if (
            self.eligibility == "worker_intake_admission_recorded"
            and self.blockers != ADMISSION_BLOCKERS
        ):
            raise ValueError("recorded status blockers must remain fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("worker intake admission status fingerprint mismatch")
        return self


class WorkerIntakeAdmissionIdempotencyReservationV1(ContractModel):
    schema: Literal["worker-intake-admission-idempotency-reservation-v1"] = (
        "worker-intake-admission-idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    admission_id: CanonicalUuid4
    record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    permanent: Literal[True] = True
    raw_key_persisted: Literal[False] = False
    consumed: Literal[False] = False
    released: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False


class WorkerIntakeAdmissionSubjectReservationV1(ContractModel):
    schema: Literal["worker-intake-admission-subject-reservation-v1"] = (
        "worker-intake-admission-subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_fingerprint: FingerprintV1
    worker_intake_admission_decision_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    admission_id: CanonicalUuid4
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
    def exact(self) -> WorkerIntakeAdmissionSubjectReservationV1:
        if self.subject_fingerprint != reservation_subject_fingerprint(self):
            raise ValueError("worker intake admission subject fingerprint mismatch")
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("worker intake admission reservation fingerprint mismatch")
        return self


class WorkerIntakeAdmissionAuditEvidenceV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-audit-v1"] = (
        "worker-intake-admission-audit-v1"
    )
    event: Literal["intake_admission_recorded", "intake_admission_read"]
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"]
    operator_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    admission_id: CanonicalUuid4 | None
    subject_fingerprint: FingerprintV1 | None
    record_fingerprint: FingerprintV1 | None
    correlation_fingerprint: FingerprintV1
    occurred_at: UtcSecond
    audit_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("worker intake admission audit fingerprint mismatch")
        return self


class WorkerIntakeAdmissionRedactedErrorV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-error-v1"] = (
        "worker-intake-admission-error-v1"
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
        "worker_queue_reservation_not_active",
        "worker_identity_ineligible",
        "worker_intake_reference_ineligible",
        "queue_reservation_binding_mismatch",
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


class WorkerIntakeAdmissionResultV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-result-v1"] = (
        "worker-intake-admission-result-v1"
    )
    ok: bool
    admission: WorkerIntakeAdmissionV1 | None
    error: WorkerIntakeAdmissionRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionResultV1:
        if self.ok != (self.admission is not None and self.error is None):
            raise ValueError("result shape does not match ok flag")
        if (self.admission is None) == (self.error is None):
            raise ValueError("exactly one of admission or error is required")
        _bounded(self)
        return self


class WorkerIntakeAdmissionCollectionV1(NoAuthorityV1):
    schema: Literal["worker-intake-admission-collection-v1"] = (
        "worker-intake-admission-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[WorkerIntakeAdmissionV1, ...]
    count: int
    collection_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("worker intake admission collection exceeds bound")
        if tuple(sorted(self.items, key=lambda item: (item.recorded_at, item.admission_id))) != self.items:
            raise ValueError("worker intake admission collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("worker intake admission collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("worker intake admission collection fingerprint mismatch")
        _bounded(self)
        return self


class WorkerIntakeAdmissionValidationInputV1(ContractModel):
    """Injected P1 facts only; no reader, store, queue, worker, or I/O."""

    operator_id: OperatorId
    authority: WorkerIntakeAdmissionAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: WorkerIntakeAdmissionCreateV1
    worker_queue_reservation: WorkerQueueReservationV1
    worker_queue_reservation_status: WorkerQueueReservationStatusV1
    worker_identity: WorkerIntakeWorkerIdentityV1
    worker_intake_reference: WorkerIntakeReferenceV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerIntakeAdmissionValidationInputV1:
        reservation, status, identity, intake = (
            self.worker_queue_reservation,
            self.worker_queue_reservation_status,
            self.worker_identity,
            self.worker_intake_reference,
        )
        now = _instant(self.authority.request_received_at)
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or reservation.operator_id != self.operator_id
            or identity.owner_operator_id != self.operator_id
            or intake.owner_operator_id != self.operator_id
        ):
            raise ValueError("worker intake admission ownership mismatch")
        if (
            reservation.candidate_record_id != self.candidate_record_id
            or identity.candidate_record_id != self.candidate_record_id
            or intake.candidate_record_id != self.candidate_record_id
            or self.create.worker_queue_reservation_id != reservation.reservation_id
            or self.create.worker_queue_reservation_fingerprint
            != reservation.record_fingerprint
            or self.create.worker_queue_reservation_valid_until != reservation.valid_until
            or identity.worker_queue_reservation_id != reservation.reservation_id
            or identity.worker_queue_reservation_fingerprint
            != reservation.record_fingerprint
            or intake.worker_queue_reservation_id != reservation.reservation_id
            or intake.worker_queue_reservation_fingerprint
            != reservation.record_fingerprint
        ):
            raise ValueError("queue reservation binding mismatch")
        if (
            status.reservation_id != reservation.reservation_id
            or status.record_fingerprint != reservation.record_fingerprint
            or status.status_fingerprint != v039_status_fingerprint(status)
            or status.lifecycle != "active"
            or status.eligibility != "worker_queue_reservation_recorded"
            or status.blockers != QUEUE_RESERVATION_BLOCKERS
        ):
            raise ValueError("worker queue reservation is not active")
        link = reservation.linkage
        if (
            identity.worker_reference_id != link.worker_reference_id
            or identity.worker_reference_fingerprint != link.worker_reference_fingerprint
            or identity.queue_intake_reference_id != link.queue_intake_reference_id
            or identity.queue_intake_reference_fingerprint
            != link.queue_intake_reference_fingerprint
            or identity.queue_item_reference_id != link.queue_item_reference_id
            or identity.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
            or intake.queue_intake_reference_id != link.queue_intake_reference_id
            or intake.queue_intake_reference_fingerprint
            != link.queue_intake_reference_fingerprint
            or intake.queue_item_reference_id != link.queue_item_reference_id
            or intake.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
        ):
            raise ValueError("queue reservation binding mismatch")
        if (
            self.create.worker_identity_id != identity.worker_identity_id
            or self.create.worker_identity_fingerprint
            != identity.worker_identity_fingerprint
            or self.create.worker_intake_reference_id
            != intake.worker_intake_reference_id
            or self.create.worker_intake_reference_fingerprint
            != intake.intake_reference_fingerprint
            or intake.worker_identity_id != identity.worker_identity_id
            or intake.worker_identity_fingerprint != identity.worker_identity_fingerprint
        ):
            raise ValueError("worker identity or intake reference mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != reservation.inherited_limits.limits_fingerprint
            or identity.inherited_limits != reservation.inherited_limits
            or identity.inherited_limits_fingerprint
            != reservation.inherited_limits.limits_fingerprint
        ):
            raise ValueError("inherited limits mismatch")
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        starts = (
            _instant(reservation.recorded_at),
            _instant(status.observed_at),
            _instant(identity.valid_from),
            _instant(intake.valid_from),
        )
        if any(value > now or now - value > timedelta(seconds=30) for value in starts):
            raise ValueError("worker intake admission evidence is stale or from the future")
        if (
            now >= _instant(reservation.valid_until)
            or now >= _instant(identity.valid_until)
            or now >= _instant(intake.valid_until)
        ):
            raise ValueError("worker intake admission evidence is expired")
        return self


def worker_identity_fingerprint(
    value: WorkerIntakeWorkerIdentityV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-worker-identity:v1",
        _without(value, "worker_identity_fingerprint"),
    )


def intake_reference_fingerprint(
    value: WorkerIntakeReferenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-intake-reference:v1",
        _without(value, "intake_reference_fingerprint"),
    )


def decision_fingerprint(
    value: WorkerIntakeAdmissionDecisionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-decision:v1",
        _without(value, "decision_fingerprint"),
    )


def v020_v038_chain_fingerprint(value: WorkerQueueReservationLinkageV1) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-v020-v038-chain:v1",
        {
            "worker_admission_stub_linkage": value.worker_admission_stub_linkage,
            "worker_admission_stub_id": value.worker_admission_stub_id,
            "worker_admission_stub_fingerprint": value.worker_admission_stub_fingerprint,
        },
    )


def linkage_fingerprint(
    value: WorkerIntakeAdmissionLinkageV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-linkage:v1",
        _without(value, "linkage_fingerprint"),
    )


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:worker-intake-admission-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerIntakeAdmissionCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def _subject_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        key: raw[key]
        for key in (
            "operator_id",
            "candidate_record_id",
            "worker_queue_reservation_fingerprint",
            "worker_identity_fingerprint",
            "worker_intake_reference_fingerprint",
            "worker_intake_admission_decision_fingerprint",
            "inherited_limits_fingerprint",
        )
    }


def record_subject_fingerprint(
    value: WorkerIntakeAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    link = raw["linkage"]
    return fingerprint(
        "atlas:worker-intake-admission-subject:v1",
        _subject_fields(
            {
                "operator_id": raw["operator_id"],
                "candidate_record_id": raw["candidate_record_id"],
                "worker_queue_reservation_fingerprint": link[
                    "queue_reservation_fingerprint"
                ],
                "worker_identity_fingerprint": link["worker_identity_fingerprint"],
                "worker_intake_reference_fingerprint": link[
                    "worker_intake_reference_fingerprint"
                ],
                "worker_intake_admission_decision_fingerprint": link[
                    "worker_intake_admission_decision_fingerprint"
                ],
                "inherited_limits_fingerprint": link["inherited_limits_fingerprint"],
            }
        ),
    )


def record_fingerprint(value: WorkerIntakeAdmissionV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-record:v1",
        _without(value, "record_fingerprint"),
    )


def status_fingerprint(
    value: WorkerIntakeAdmissionStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-status:v1",
        _without(value, "status_fingerprint"),
    )


def reservation_subject_fingerprint(
    value: WorkerIntakeAdmissionSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint("atlas:worker-intake-admission-subject:v1", _subject_fields(raw))


def reservation_fingerprint(
    value: WorkerIntakeAdmissionSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def audit_fingerprint(
    value: WorkerIntakeAdmissionAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: WorkerIntakeAdmissionCollectionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:worker-intake-admission-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def build_worker_identity(
    *,
    worker_identity_id: str,
    owner_operator_id: str,
    candidate_record_id: str,
    worker_queue_reservation: WorkerQueueReservationV1,
    identity_fingerprint: FingerprintV1,
    capability_profile_fingerprint: FingerprintV1,
    valid_from: str,
    valid_until: str,
) -> WorkerIntakeWorkerIdentityV1:
    link = worker_queue_reservation.linkage
    raw = {
        "worker_identity_id": worker_identity_id,
        "owner_operator_id": owner_operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_queue_reservation_id": worker_queue_reservation.reservation_id,
        "worker_queue_reservation_fingerprint": worker_queue_reservation.record_fingerprint,
        "worker_reference_id": link.worker_reference_id,
        "worker_reference_fingerprint": link.worker_reference_fingerprint,
        "queue_intake_reference_id": link.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": link.queue_intake_reference_fingerprint,
        "queue_item_reference_id": link.queue_item_reference_id,
        "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
        "identity_fingerprint": identity_fingerprint,
        "capability_profile_fingerprint": capability_profile_fingerprint,
        "inherited_limits": worker_queue_reservation.inherited_limits,
        "inherited_limits_fingerprint": worker_queue_reservation.inherited_limits.limits_fingerprint,
        "valid_from": valid_from,
        "valid_until": valid_until,
    }
    seed = WorkerIntakeWorkerIdentityV1.model_construct(
        **raw,
        worker_identity_fingerprint=fingerprint("atlas:seed:v1", "identity"),
    )
    return WorkerIntakeWorkerIdentityV1.model_validate(
        {**raw, "worker_identity_fingerprint": worker_identity_fingerprint(seed)}
    )


def build_worker_intake_reference(
    *,
    worker_intake_reference_id: str,
    owner_operator_id: str,
    candidate_record_id: str,
    worker_queue_reservation: WorkerQueueReservationV1,
    worker_identity: WorkerIntakeWorkerIdentityV1,
    valid_from: str,
    valid_until: str,
) -> WorkerIntakeReferenceV1:
    link = worker_queue_reservation.linkage
    raw = {
        "worker_intake_reference_id": worker_intake_reference_id,
        "owner_operator_id": owner_operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_queue_reservation_id": worker_queue_reservation.reservation_id,
        "worker_queue_reservation_fingerprint": worker_queue_reservation.record_fingerprint,
        "worker_identity_id": worker_identity.worker_identity_id,
        "worker_identity_fingerprint": worker_identity.worker_identity_fingerprint,
        "queue_intake_reference_id": link.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": link.queue_intake_reference_fingerprint,
        "queue_item_reference_id": link.queue_item_reference_id,
        "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
        "valid_from": valid_from,
        "valid_until": valid_until,
    }
    seed = WorkerIntakeReferenceV1.model_construct(
        **raw,
        intake_reference_fingerprint=fingerprint("atlas:seed:v1", "intake-reference"),
    )
    return WorkerIntakeReferenceV1.model_validate(
        {**raw, "intake_reference_fingerprint": intake_reference_fingerprint(seed)}
    )


def build_decision(
    *,
    decision_id: str,
    operator_id: str,
    candidate_record_id: str,
    worker_queue_reservation: WorkerQueueReservationV1,
    worker_identity: WorkerIntakeWorkerIdentityV1,
    worker_intake_reference: WorkerIntakeReferenceV1,
    evaluated_at: str,
) -> WorkerIntakeAdmissionDecisionV1:
    raw = {
        "decision_id": decision_id,
        "owner_operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "worker_queue_reservation_id": worker_queue_reservation.reservation_id,
        "worker_queue_reservation_fingerprint": worker_queue_reservation.record_fingerprint,
        "worker_identity_id": worker_identity.worker_identity_id,
        "worker_identity_fingerprint": worker_identity.worker_identity_fingerprint,
        "worker_intake_reference_id": worker_intake_reference.worker_intake_reference_id,
        "worker_intake_reference_fingerprint": (
            worker_intake_reference.intake_reference_fingerprint
        ),
        "evaluated_at": evaluated_at,
        "inherited_limits_fingerprint": worker_queue_reservation.inherited_limits.limits_fingerprint,
    }
    seed = WorkerIntakeAdmissionDecisionV1.model_construct(
        **raw,
        decision_fingerprint=fingerprint("atlas:seed:v1", "decision"),
    )
    return WorkerIntakeAdmissionDecisionV1.model_validate(
        {**raw, "decision_fingerprint": decision_fingerprint(seed)}
    )


def build_linkage(
    reservation: WorkerQueueReservationV1,
    status: WorkerQueueReservationStatusV1,
    identity: WorkerIntakeWorkerIdentityV1,
    intake: WorkerIntakeReferenceV1,
    decision: WorkerIntakeAdmissionDecisionV1,
) -> WorkerIntakeAdmissionLinkageV1:
    source = reservation.linkage
    raw = {
        "operator_id": reservation.operator_id,
        "candidate_record_id": reservation.candidate_record_id,
        "worker_queue_reservation_linkage": source,
        "v020_v038_chain_fingerprint": v020_v038_chain_fingerprint(source),
        "readiness_review_fingerprint": source.readiness_review_fingerprint,
        "permission_grant_fingerprint": source.permission_grant_fingerprint,
        "execution_admission_id": source.execution_admission_id,
        "execution_admission_fingerprint": source.execution_admission_fingerprint,
        "runner_binding_plan_id": source.runner_binding_plan_id,
        "runner_binding_plan_fingerprint": source.runner_binding_plan_fingerprint,
        "runner_binding_plan_status_fingerprint": source.runner_binding_plan_status_fingerprint,
        "runner_reference_id": source.runner_reference_id,
        "runner_reference_fingerprint": source.runner_reference_fingerprint,
        "worker_admission_stub_id": source.worker_admission_stub_id,
        "worker_admission_stub_fingerprint": source.worker_admission_stub_fingerprint,
        "worker_admission_stub_status_fingerprint": source.worker_admission_stub_status_fingerprint,
        "worker_reference_id": source.worker_reference_id,
        "worker_reference_fingerprint": source.worker_reference_fingerprint,
        "queue_reservation_id": reservation.reservation_id,
        "queue_reservation_fingerprint": v039_record_fingerprint(reservation),
        "queue_reservation_status_fingerprint": v039_status_fingerprint(status),
        "queue_intake_reference_id": source.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": source.queue_intake_reference_fingerprint,
        "queue_item_reference_id": source.queue_item_reference_id,
        "queue_item_reference_fingerprint": source.queue_item_reference_fingerprint,
        "worker_identity_id": identity.worker_identity_id,
        "worker_identity_fingerprint": identity.worker_identity_fingerprint,
        "worker_intake_reference_id": intake.worker_intake_reference_id,
        "worker_intake_reference_fingerprint": intake.intake_reference_fingerprint,
        "worker_intake_admission_decision_fingerprint": decision.decision_fingerprint,
        "inherited_limits_fingerprint": source.inherited_limits_fingerprint,
    }
    seed = WorkerIntakeAdmissionLinkageV1.model_construct(
        **raw,
        linkage_fingerprint=fingerprint("atlas:seed:v1", "linkage"),
    )
    return WorkerIntakeAdmissionLinkageV1.model_validate(
        {**raw, "linkage_fingerprint": linkage_fingerprint(seed)}
    )


def build_admission(
    validation: WorkerIntakeAdmissionValidationInputV1,
    *,
    admission_id: str,
    decision_id: str,
) -> tuple[
    WorkerIntakeAdmissionV1,
    WorkerIntakeAdmissionIdempotencyReservationV1,
    WorkerIntakeAdmissionSubjectReservationV1,
]:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.worker_queue_reservation.valid_until),
        _instant(validation.worker_identity.valid_until),
        _instant(validation.worker_intake_reference.valid_until),
    )
    decision = build_decision(
        decision_id=decision_id,
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        worker_queue_reservation=validation.worker_queue_reservation,
        worker_identity=validation.worker_identity,
        worker_intake_reference=validation.worker_intake_reference,
        evaluated_at=validation.authority.request_received_at,
    )
    link = build_linkage(
        validation.worker_queue_reservation,
        validation.worker_queue_reservation_status,
        validation.worker_identity,
        validation.worker_intake_reference,
        decision,
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
        "admission_id": admission_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "linkage": link,
        "worker_identity": validation.worker_identity,
        "worker_intake_reference": validation.worker_intake_reference,
        "admission_decision": decision,
        "inherited_limits": validation.worker_queue_reservation.inherited_limits,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
    }
    seed = WorkerIntakeAdmissionV1.model_construct(
        **raw,
        subject_fingerprint=fingerprint("atlas:seed:v1", "subject"),
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    subject = record_subject_fingerprint(seed)
    seed = WorkerIntakeAdmissionV1.model_construct(
        **raw,
        subject_fingerprint=subject,
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    record = WorkerIntakeAdmissionV1.model_validate(
        {
            **raw,
            "subject_fingerprint": subject,
            "record_fingerprint": record_fingerprint(seed),
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
    idempotency = WorkerIntakeAdmissionIdempotencyReservationV1(**common)
    reservation_raw = {
        **common,
        "worker_queue_reservation_fingerprint": link.queue_reservation_fingerprint,
        "worker_identity_fingerprint": link.worker_identity_fingerprint,
        "worker_intake_reference_fingerprint": link.worker_intake_reference_fingerprint,
        "worker_intake_admission_decision_fingerprint": (
            link.worker_intake_admission_decision_fingerprint
        ),
        "inherited_limits_fingerprint": link.inherited_limits_fingerprint,
    }
    reservation_seed = WorkerIntakeAdmissionSubjectReservationV1.model_construct(
        **reservation_raw,
        reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
    )
    permanent = WorkerIntakeAdmissionSubjectReservationV1.model_validate(
        {
            **reservation_raw,
            "reservation_fingerprint": reservation_fingerprint(reservation_seed),
        }
    )
    return record, idempotency, permanent


def derive_status(
    admission: WorkerIntakeAdmissionV1,
    *,
    evaluated_at: str,
) -> WorkerIntakeAdmissionStatusV1:
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
    seed = WorkerIntakeAdmissionStatusV1.model_construct(
        **raw,
        status_fingerprint=fingerprint("atlas:seed:v1", "status"),
    )
    return WorkerIntakeAdmissionStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_audit(
    admission: WorkerIntakeAdmissionV1,
    *,
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> WorkerIntakeAdmissionAuditEvidenceV1:
    raw = {
        "event": "intake_admission_recorded"
        if outcome == "recorded"
        else "intake_admission_read",
        "outcome": outcome,
        "operator_fingerprint": opaque_fingerprint(
            "atlas:worker-intake-admission-operator:v1",
            admission.operator_id,
        ),
        "candidate_record_fingerprint": opaque_fingerprint(
            "atlas:worker-intake-admission-candidate:v1",
            admission.candidate_record_id,
        ),
        "admission_id": admission.admission_id,
        "subject_fingerprint": admission.subject_fingerprint,
        "record_fingerprint": admission.record_fingerprint,
        "correlation_fingerprint": correlation_fingerprint,
        "occurred_at": occurred_at,
    }
    seed = WorkerIntakeAdmissionAuditEvidenceV1.model_construct(
        **raw,
        audit_fingerprint=admission.record_fingerprint,
    )
    return WorkerIntakeAdmissionAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[WorkerIntakeAdmissionV1, ...],
) -> WorkerIntakeAdmissionCollectionV1:
    ordered = tuple(sorted(items, key=lambda item: (item.recorded_at, item.admission_id)))
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": ordered,
        "count": len(ordered),
    }
    seed = WorkerIntakeAdmissionCollectionV1.model_construct(
        **raw,
        collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
    )
    return WorkerIntakeAdmissionCollectionV1.model_validate(
        {**raw, "collection_fingerprint": collection_fingerprint(seed)}
    )


def parse_create_json(payload: bytes | str) -> WorkerIntakeAdmissionCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("worker intake admission request exceeds 16 KiB")
    try:
        decoded = raw.decode()
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
        return WorkerIntakeAdmissionCreateV1.model_validate(parsed)
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid worker intake admission request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
