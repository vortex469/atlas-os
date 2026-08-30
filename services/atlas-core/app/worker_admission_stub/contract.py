"""Closed immutable v0.38 worker admission stub models and pure validation."""

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
from app.runner_binding_plan.contract import (
    RunnerBindingLimitsV1,
    RunnerBindingPlanLinkageV1,
    RunnerBindingPlanStatusV1,
    RunnerBindingPlanV1,
)
from app.runner_binding_plan.contract import (
    plan_fingerprint as v037_plan_fingerprint,
)
from app.runner_binding_plan.contract import (
    status_fingerprint as v037_status_fingerprint,
)

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 128 * 1024
MAX_RESULT_BYTES = 128 * 1024
MAX_COLLECTION_RECORDS = 100
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.worker_admission_stub.record"
READ_PERMISSION = "installation.execution.worker_admission_stub.read"
SCOPE = "installation_worker_admission_stub_only"
SAFE_MESSAGE = "worker admission stub request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")

BlockerV1 = Literal[
    "missing_evidence",
    "ownership_mismatch",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "invalid_evidence",
    "stale_evidence",
    "expired_evidence",
    "runner_binding_plan_not_active",
    "runner_binding_scope_mismatch",
    "worker_reference_unavailable",
    "worker_reference_ineligible",
    "worker_scope_mismatch",
    "inherited_limits_mismatch",
    "permission_denied",
    "subject_reserved",
    "installation_capability_unsupported",
    "worker_not_started",
    "queue_boundary_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "missing_evidence",
    "ownership_mismatch",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "invalid_evidence",
    "stale_evidence",
    "expired_evidence",
    "runner_binding_plan_not_active",
    "runner_binding_scope_mismatch",
    "worker_reference_unavailable",
    "worker_reference_ineligible",
    "worker_scope_mismatch",
    "inherited_limits_mismatch",
    "permission_denied",
    "subject_reserved",
    "installation_capability_unsupported",
    "worker_not_started",
    "queue_boundary_not_defined",
    "execution_start_boundary_not_defined",
)
STUB_BLOCKERS: tuple[BlockerV1, ...] = (
    "worker_not_started",
    "queue_boundary_not_defined",
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


def _fp(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(
        domain.encode() + b"\0" + canonical_json(value)
    ).hexdigest()
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


class WorkerAdmissionStubCreateV1(ContractModel):
    schema: Literal["worker-admission-stub-create-v1"] = (
        "worker-admission-stub-create-v1"
    )
    runner_binding_plan_id: CanonicalUuid4
    runner_binding_plan_fingerprint: FingerprintV1
    runner_binding_plan_valid_until: UtcSecond
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE
    evidence_only: Literal[True] = True
    worker_start_allowed: Literal[False] = False
    queue_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class WorkerAdmissionAuthorityContextV1(ContractModel):
    schema: Literal["worker-admission-stub-authority-context-v1"] = (
        "worker-admission-stub-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )
    evidence_only: Literal[True] = True
    worker_registration_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_reservation_allowed: Literal[False] = False
    worker_binding_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    queue_allowed: Literal[False] = False
    enqueue_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    docker_allowed: Literal[False] = False
    podman_allowed: Literal[False] = False
    shell_allowed: Literal[False] = False
    process_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class WorkerAdmissionIntentV1(ContractModel):
    schema: Literal["worker-admission-intent-v1"] = "worker-admission-intent-v1"
    intent_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runner_binding_plan_id: CanonicalUuid4
    runner_binding_plan_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    scope: Literal[SCOPE] = SCOPE
    intent: Literal["preserve_non_executing_worker_admission_evidence_only"] = (
        "preserve_non_executing_worker_admission_evidence_only"
    )
    requested_at: UtcSecond
    intent_fingerprint: FingerprintV1
    queue_requested: Literal[False] = False
    dispatch_requested: Literal[False] = False
    worker_start_requested: Literal[False] = False
    execution_requested: Literal[False] = False
    agent_invocation_requested: Literal[False] = False
    mutation_requested: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionIntentV1:
        if self.intent_fingerprint != intent_fingerprint(self):
            raise ValueError("worker admission intent fingerprint mismatch")
        _bounded(self)
        return self


class WorkerAdmissionIntakeStubV1(ContractModel):
    schema: Literal["worker-admission-intake-stub-v1"] = (
        "worker-admission-intake-stub-v1"
    )
    intent_id: CanonicalUuid5
    intent_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    scope: Literal[SCOPE] = SCOPE
    intake_state: Literal["undefined"] = "undefined"
    intake_protocol: Literal["none"] = "none"
    intake_fingerprint: FingerprintV1
    queue_selected: Literal[False] = False
    queue_created: Literal[False] = False
    intake_open: Literal[False] = False
    payload_constructed: Literal[False] = False
    request_serialized: Literal[False] = False
    request_sent: Literal[False] = False
    worker_contacted: Literal[False] = False
    worker_started: Literal[False] = False
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionIntakeStubV1:
        if self.intake_fingerprint != intake_fingerprint(self):
            raise ValueError("worker admission intake fingerprint mismatch")
        _bounded(self)
        return self


class WorkerReferenceV1(ContractModel):
    schema: Literal["installation-worker-reference-v1"] = (
        "installation-worker-reference-v1"
    )
    worker_reference_id: CanonicalUuid4
    owner_operator_id: OperatorId
    worker_kind: Literal["isolated_installation_worker"] = (
        "isolated_installation_worker"
    )
    trust_domain: Literal["atlas-installation"] = "atlas-installation"
    scope: Literal[SCOPE] = SCOPE
    eligibility: Literal["eligible_for_admission_stub_only"] = (
        "eligible_for_admission_stub_only"
    )
    runner_reference_id: CanonicalUuid4
    runner_reference_fingerprint: FingerprintV1
    identity_fingerprint: FingerprintV1
    capability_profile_fingerprint: FingerprintV1
    inherited_limits: RunnerBindingLimitsV1
    inherited_limits_fingerprint: FingerprintV1
    valid_from: UtcSecond
    valid_until: UtcSecond
    reference_fingerprint: FingerprintV1
    registered: Literal[False] = False
    available: Literal[False] = False
    reachable: Literal[False] = False
    authenticated: Literal[False] = False
    contacted: Literal[False] = False
    reserved: Literal[False] = False
    bound: Literal[False] = False
    queue_known: Literal[False] = False
    intake_open: Literal[False] = False
    invocation_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerReferenceV1:
        start, expiry = _instant(self.valid_from), _instant(self.valid_until)
        if not start < expiry <= start + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("worker reference expiry exceeds freshness bound")
        if self.inherited_limits_fingerprint != self.inherited_limits.limits_fingerprint:
            raise ValueError("worker reference inherited limits mismatch")
        if self.reference_fingerprint != worker_reference_fingerprint(self):
            raise ValueError("worker reference fingerprint mismatch")
        _bounded(self)
        return self


class WorkerAdmissionStubLinkageV1(ContractModel):
    schema: Literal["worker-admission-stub-linkage-v1"] = (
        "worker-admission-stub-linkage-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runner_binding_plan_linkage: RunnerBindingPlanLinkageV1
    v020_v036_chain_fingerprint: FingerprintV1
    readiness_review_fingerprint: FingerprintV1
    permission_grant_fingerprint: FingerprintV1
    execution_admission_id: CanonicalUuid4
    execution_admission_fingerprint: FingerprintV1
    runner_binding_plan_id: CanonicalUuid4
    runner_binding_plan_fingerprint: FingerprintV1
    runner_binding_plan_status_fingerprint: FingerprintV1
    runner_reference_id: CanonicalUuid4
    runner_reference_fingerprint: FingerprintV1
    worker_reference_id: CanonicalUuid4
    worker_reference_fingerprint: FingerprintV1
    worker_identity_fingerprint: FingerprintV1
    worker_capability_profile_fingerprint: FingerprintV1
    worker_admission_intent_fingerprint: FingerprintV1
    worker_admission_intake_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubLinkageV1:
        source = self.runner_binding_plan_linkage
        if (
            self.readiness_review_fingerprint != source.readiness_review_fingerprint
            or self.permission_grant_fingerprint != source.permission_grant_fingerprint
            or self.execution_admission_id != source.execution_admission_id
            or self.execution_admission_fingerprint
            != source.execution_admission_fingerprint
            or self.runner_reference_id != source.runner_reference_id
            or self.runner_reference_fingerprint != source.runner_reference_fingerprint
            or self.inherited_limits_fingerprint != source.limits_fingerprint
            or self.v020_v036_chain_fingerprint
            != v020_v036_chain_fingerprint(source)
        ):
            raise ValueError("embedded runner binding plan linkage mismatch")
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("worker admission stub linkage fingerprint mismatch")
        _bounded(self)
        return self


class _NoAuthority(ContractModel):
    evidence_only: Literal[True] = True
    runner_binding_allowed: Literal[False] = False
    worker_registered: Literal[False] = False
    worker_contacted: Literal[False] = False
    worker_reserved: Literal[False] = False
    worker_bound: Literal[False] = False
    worker_started: Literal[False] = False
    queue_created: Literal[False] = False
    queue_allowed: Literal[False] = False
    work_enqueued: Literal[False] = False
    enqueue_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    docker_allowed: Literal[False] = False
    podman_allowed: Literal[False] = False
    shell_allowed: Literal[False] = False
    process_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class WorkerAdmissionStubV1(_NoAuthority):
    schema: Literal["worker-admission-stub-v1"] = "worker-admission-stub-v1"
    stub_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    lifecycle: Literal["active"] = "active"
    eligibility: Literal["worker_admission_stubbed"] = "worker_admission_stubbed"
    blockers: tuple[BlockerV1, ...] = STUB_BLOCKERS
    linkage: WorkerAdmissionStubLinkageV1
    worker_admission_intent: WorkerAdmissionIntentV1
    worker_admission_intake: WorkerAdmissionIntakeStubV1
    worker_reference: WorkerReferenceV1
    inherited_limits: RunnerBindingLimitsV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    stub_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubV1:
        if self.blockers != STUB_BLOCKERS:
            raise ValueError("worker admission stub blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=30):
            raise ValueError("worker admission stub expiry exceeds freshness bound")
        intent, intake, reference = (
            self.worker_admission_intent,
            self.worker_admission_intake,
            self.worker_reference,
        )
        if (
            self.operator_id != self.linkage.operator_id
            or self.operator_id != intent.operator_id
            or self.operator_id != reference.owner_operator_id
            or self.candidate_record_id != self.linkage.candidate_record_id
            or self.candidate_record_id != intent.candidate_record_id
            or intent.intent_id != intake.intent_id
            or intent.intent_fingerprint != intake.intent_fingerprint
            or reference.worker_reference_id != intake.worker_reference_id
            or reference.worker_reference_id != self.linkage.worker_reference_id
            or reference.reference_fingerprint
            != self.linkage.worker_reference_fingerprint
            or self.inherited_limits != reference.inherited_limits
            or self.inherited_limits.limits_fingerprint
            != self.linkage.inherited_limits_fingerprint
            or intent.intent_fingerprint
            != self.linkage.worker_admission_intent_fingerprint
            or intake.intake_fingerprint
            != self.linkage.worker_admission_intake_fingerprint
        ):
            raise ValueError("worker admission stub ownership or linkage mismatch")
        if self.stub_fingerprint != stub_fingerprint(self):
            raise ValueError("worker admission stub fingerprint mismatch")
        _bounded(self)
        return self


class WorkerAdmissionStubStatusV1(ContractModel):
    schema: Literal["worker-admission-stub-status-v1"] = (
        "worker-admission-stub-status-v1"
    )
    stub_id: CanonicalUuid4
    observed_at: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal["worker_admission_stubbed"] = "worker_admission_stubbed"
    blockers: tuple[BlockerV1, ...] = STUB_BLOCKERS
    status_fingerprint: FingerprintV1
    evidence_only: Literal[True] = True
    worker_started: Literal[False] = False
    work_enqueued: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubStatusV1:
        if self.blockers != STUB_BLOCKERS:
            raise ValueError("worker admission status blockers must remain fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("worker admission stub status fingerprint mismatch")
        _bounded(self)
        return self


class WorkerAdmissionStubIdempotencyV1(ContractModel):
    schema: Literal["worker-admission-stub-idempotency-v1"] = (
        "worker-admission-stub-idempotency-v1"
    )
    operator_id: OperatorId
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    stub_id: CanonicalUuid4
    stub_fingerprint: FingerprintV1
    reservation_state: Literal["permanently_reserved"] = "permanently_reserved"
    exact_duplicate: bool = False
    raw_key_persisted: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class WorkerAdmissionStubReservationV1(ContractModel):
    schema: Literal["worker-admission-stub-reservation-v1"] = (
        "worker-admission-stub-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runner_binding_plan_fingerprint: FingerprintV1
    worker_reference_fingerprint: FingerprintV1
    worker_admission_intent_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    stub_id: CanonicalUuid4
    stub_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["permanent"] = "permanent"
    reservation_fingerprint: FingerprintV1
    consumed: Literal[False] = False
    released: Literal[False] = False
    replaceable: Literal[False] = False
    supersedable: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubReservationV1:
        if self.subject_fingerprint != subject_fingerprint(self):
            raise ValueError("worker admission stub subject fingerprint mismatch")
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("worker admission stub reservation fingerprint mismatch")
        _bounded(self)
        return self


class WorkerAdmissionStubAuditEvidenceV1(ContractModel):
    schema: Literal["worker-admission-stub-audit-evidence-v1"] = (
        "worker-admission-stub-audit-evidence-v1"
    )
    event: Literal["worker_admission_stub_recorded", "worker_admission_stub_read"]
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"]
    operator_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    stub_fingerprint: FingerprintV1 | None
    correlation_fingerprint: FingerprintV1
    occurred_at: UtcSecond
    audit_fingerprint: FingerprintV1
    evidence_only: Literal[True] = True
    worker_contact_attempted: Literal[False] = False
    worker_start_attempted: Literal[False] = False
    enqueue_attempted: Literal[False] = False
    dispatch_attempted: Literal[False] = False
    execution_start_attempted: Literal[False] = False
    agent_invocation_attempted: Literal[False] = False
    workflow_start_attempted: Literal[False] = False
    process_execution_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False
    replay_attempted: Literal[False] = False
    effect_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubAuditEvidenceV1:
        if self.audit_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("worker admission stub audit fingerprint mismatch")
        _bounded(self)
        return self


class WorkerAdmissionStubRedactedErrorV1(ContractModel):
    schema: Literal["worker-admission-stub-redacted-error-v1"] = (
        "worker-admission-stub-redacted-error-v1"
    )
    error_code: Literal[
        "malformed",
        "unauthenticated",
        "unauthorized",
        "not_found",
        "not_eligible",
        "expired",
        "conflict",
        "quota_exceeded",
        "unavailable",
    ]
    message: Literal[SAFE_MESSAGE] = SAFE_MESSAGE
    correlation_fingerprint: FingerprintV1
    retryable: Literal[False] = False
    redacted: Literal[True] = True
    evidence_only: Literal[True] = True
    worker_start_allowed: Literal[False] = False
    enqueue_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class WorkerAdmissionStubResultV1(ContractModel):
    schema: Literal["worker-admission-stub-result-v1"] = (
        "worker-admission-stub-result-v1"
    )
    disposition: Literal["recorded", "exact_duplicate", "read", "blocked"]
    stub: WorkerAdmissionStubV1 | None
    status: WorkerAdmissionStubStatusV1 | None
    audit_evidence: WorkerAdmissionStubAuditEvidenceV1 | None
    error: WorkerAdmissionStubRedactedErrorV1 | None
    evidence_only: Literal[True] = True
    worker_registration_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_reservation_allowed: Literal[False] = False
    worker_binding_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    queue_allowed: Literal[False] = False
    enqueue_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubResultV1:
        success = self.disposition in {"recorded", "exact_duplicate", "read"}
        if success and (
            self.stub is None
            or self.status is None
            or self.audit_evidence is None
            or self.error is not None
        ):
            raise ValueError("successful result requires stub, status, and audit")
        if not success and (
            self.stub is not None or self.status is not None or self.error is None
        ):
            raise ValueError("blocked result requires one redacted error")
        if success and self.audit_evidence.outcome != self.disposition:
            raise ValueError("result audit disposition mismatch")
        _bounded(self, MAX_RESULT_BYTES)
        return self


class WorkerAdmissionStubCollectionV1(ContractModel):
    schema: Literal["worker-admission-stub-collection-v1"] = (
        "worker-admission-stub-collection-v1"
    )
    stubs: tuple[WorkerAdmissionStubResultV1, ...]
    evidence_only: Literal[True] = True
    worker_start_allowed: Literal[False] = False
    enqueue_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bounded(self) -> WorkerAdmissionStubCollectionV1:
        if len(self.stubs) > MAX_COLLECTION_RECORDS:
            raise ValueError("worker admission stub collection exceeds bound")
        _bounded(self)
        return self


class WorkerAdmissionStubValidationInputV1(ContractModel):
    """Injected P1 facts only; no reader, store, worker, queue, or I/O."""

    operator_id: OperatorId
    authority: WorkerAdmissionAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: WorkerAdmissionStubCreateV1
    runner_binding_plan: RunnerBindingPlanV1
    runner_binding_plan_status: RunnerBindingPlanStatusV1
    worker_reference: WorkerReferenceV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False

    @model_validator(mode="after")
    def exact(self) -> WorkerAdmissionStubValidationInputV1:
        plan, status, worker = (
            self.runner_binding_plan,
            self.runner_binding_plan_status,
            self.worker_reference,
        )
        now = _instant(self.authority.request_received_at)
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or plan.operator_id != self.operator_id
            or worker.owner_operator_id != self.operator_id
        ):
            raise ValueError("worker admission stub ownership mismatch")
        if (
            plan.candidate_record_id != self.candidate_record_id
            or self.create.runner_binding_plan_id != plan.plan_id
            or self.create.runner_binding_plan_fingerprint != plan.plan_fingerprint
            or self.create.runner_binding_plan_valid_until != plan.valid_until
        ):
            raise ValueError("runner binding plan linkage mismatch")
        if (
            status.plan_id != plan.plan_id
            or status.status_fingerprint != v037_status_fingerprint(status)
            or status.lifecycle != "active"
            or status.eligibility != "binding_planned"
        ):
            raise ValueError("runner binding plan is not active")
        if (
            self.create.worker_reference_id != worker.worker_reference_id
            or self.create.worker_reference_fingerprint != worker.reference_fingerprint
            or worker.runner_reference_id != plan.runner_reference.runner_reference_id
            or worker.runner_reference_fingerprint
            != plan.runner_reference.reference_fingerprint
        ):
            raise ValueError("worker reference linkage mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != plan.limits.limits_fingerprint
            or worker.inherited_limits != plan.limits
            or worker.inherited_limits_fingerprint != plan.limits.limits_fingerprint
        ):
            raise ValueError("inherited limits mismatch")
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        instants = (
            _instant(plan.recorded_at),
            _instant(status.observed_at),
            _instant(worker.valid_from),
        )
        if any(value > now or now - value > timedelta(seconds=30) for value in instants):
            raise ValueError("worker admission evidence is stale or from the future")
        if now >= _instant(plan.valid_until) or now >= _instant(worker.valid_until):
            raise ValueError("worker admission evidence is expired")
        return self


def intent_fingerprint(value: WorkerAdmissionIntentV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-intent:v1", _without(value, "intent_fingerprint"))


def intake_fingerprint(
    value: WorkerAdmissionIntakeStubV1 | dict[str, Any],
) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-intake:v1", _without(value, "intake_fingerprint"))


def worker_reference_fingerprint(
    value: WorkerReferenceV1 | dict[str, Any],
) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-reference:v1", _without(value, "reference_fingerprint"))


def v020_v036_chain_fingerprint(value: RunnerBindingPlanLinkageV1) -> FingerprintV1:
    return _fp(
        "atlas:worker-admission-stub-v020-v036-chain:v1",
        {
            "execution_admission_linkage": value.execution_admission_linkage,
            "execution_admission_id": value.execution_admission_id,
            "execution_admission_fingerprint": value.execution_admission_fingerprint,
        },
    )


def linkage_fingerprint(
    value: WorkerAdmissionStubLinkageV1 | dict[str, Any],
) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-linkage:v1", _without(value, "linkage_fingerprint"))


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    digest = hashlib.sha256(
        b"atlas:worker-admission-stub-idempotency:v1\0"
        + operator_id.encode()
        + b"\0"
        + key.encode()
    ).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerAdmissionStubCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return _fp(
        "atlas:worker-admission-stub-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def stub_fingerprint(value: WorkerAdmissionStubV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-record:v1", _without(value, "stub_fingerprint"))


def status_fingerprint(
    value: WorkerAdmissionStubStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-status:v1", _without(value, "status_fingerprint"))


def subject_fingerprint(
    value: WorkerAdmissionStubReservationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    keys = (
        "operator_id",
        "candidate_record_id",
        "runner_binding_plan_fingerprint",
        "worker_reference_fingerprint",
        "worker_admission_intent_fingerprint",
        "inherited_limits_fingerprint",
    )
    return _fp("atlas:worker-admission-stub-subject:v1", {key: raw[key] for key in keys})


def reservation_fingerprint(
    value: WorkerAdmissionStubReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-reservation:v1", _without(value, "reservation_fingerprint"))


def audit_evidence_fingerprint(
    value: WorkerAdmissionStubAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return _fp("atlas:worker-admission-stub-audit:v1", _without(value, "audit_fingerprint"))


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return _fp(domain, value)


def build_worker_reference(
    *,
    worker_reference_id: str,
    owner_operator_id: str,
    runner_reference_id: str,
    runner_reference_fingerprint_value: FingerprintV1,
    identity_fingerprint: FingerprintV1,
    capability_profile_fingerprint: FingerprintV1,
    inherited_limits: RunnerBindingLimitsV1,
    valid_from: str,
    valid_until: str,
) -> WorkerReferenceV1:
    raw = {
        "worker_reference_id": worker_reference_id,
        "owner_operator_id": owner_operator_id,
        "runner_reference_id": runner_reference_id,
        "runner_reference_fingerprint": runner_reference_fingerprint_value,
        "identity_fingerprint": identity_fingerprint,
        "capability_profile_fingerprint": capability_profile_fingerprint,
        "inherited_limits": inherited_limits,
        "inherited_limits_fingerprint": inherited_limits.limits_fingerprint,
        "valid_from": valid_from,
        "valid_until": valid_until,
    }
    seed = WorkerReferenceV1.model_construct(
        **raw, reference_fingerprint=_fp("atlas:seed:v1", "worker-reference")
    )
    return WorkerReferenceV1.model_validate(
        {**raw, "reference_fingerprint": worker_reference_fingerprint(seed)}
    )


def build_intent(
    validation: WorkerAdmissionStubValidationInputV1, *, intent_id: str
) -> WorkerAdmissionIntentV1:
    raw = {
        "intent_id": intent_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "runner_binding_plan_id": validation.runner_binding_plan.plan_id,
        "runner_binding_plan_fingerprint": validation.runner_binding_plan.plan_fingerprint,
        "worker_reference_id": validation.worker_reference.worker_reference_id,
        "worker_reference_fingerprint": validation.worker_reference.reference_fingerprint,
        "inherited_limits_fingerprint": validation.worker_reference.inherited_limits_fingerprint,
        "requested_at": validation.authority.request_received_at,
    }
    seed = WorkerAdmissionIntentV1.model_construct(
        **raw, intent_fingerprint=_fp("atlas:seed:v1", "intent")
    )
    return WorkerAdmissionIntentV1.model_validate(
        {**raw, "intent_fingerprint": intent_fingerprint(seed)}
    )


def build_intake(intent: WorkerAdmissionIntentV1) -> WorkerAdmissionIntakeStubV1:
    raw = {
        "intent_id": intent.intent_id,
        "intent_fingerprint": intent.intent_fingerprint,
        "worker_reference_id": intent.worker_reference_id,
        "worker_reference_fingerprint": intent.worker_reference_fingerprint,
    }
    seed = WorkerAdmissionIntakeStubV1.model_construct(
        **raw, intake_fingerprint=_fp("atlas:seed:v1", "intake")
    )
    return WorkerAdmissionIntakeStubV1.model_validate(
        {**raw, "intake_fingerprint": intake_fingerprint(seed)}
    )


def build_linkage(
    plan: RunnerBindingPlanV1,
    status: RunnerBindingPlanStatusV1,
    worker: WorkerReferenceV1,
    intent: WorkerAdmissionIntentV1,
    intake: WorkerAdmissionIntakeStubV1,
) -> WorkerAdmissionStubLinkageV1:
    source = plan.linkage
    raw = {
        "operator_id": plan.operator_id,
        "candidate_record_id": plan.candidate_record_id,
        "runner_binding_plan_linkage": source,
        "v020_v036_chain_fingerprint": v020_v036_chain_fingerprint(source),
        "readiness_review_fingerprint": source.readiness_review_fingerprint,
        "permission_grant_fingerprint": source.permission_grant_fingerprint,
        "execution_admission_id": source.execution_admission_id,
        "execution_admission_fingerprint": source.execution_admission_fingerprint,
        "runner_binding_plan_id": plan.plan_id,
        "runner_binding_plan_fingerprint": v037_plan_fingerprint(plan),
        "runner_binding_plan_status_fingerprint": v037_status_fingerprint(status),
        "runner_reference_id": source.runner_reference_id,
        "runner_reference_fingerprint": source.runner_reference_fingerprint,
        "worker_reference_id": worker.worker_reference_id,
        "worker_reference_fingerprint": worker.reference_fingerprint,
        "worker_identity_fingerprint": worker.identity_fingerprint,
        "worker_capability_profile_fingerprint": worker.capability_profile_fingerprint,
        "worker_admission_intent_fingerprint": intent.intent_fingerprint,
        "worker_admission_intake_fingerprint": intake.intake_fingerprint,
        "inherited_limits_fingerprint": worker.inherited_limits_fingerprint,
    }
    seed = WorkerAdmissionStubLinkageV1.model_construct(
        **raw, linkage_fingerprint=_fp("atlas:seed:v1", "linkage")
    )
    return WorkerAdmissionStubLinkageV1.model_validate(
        {**raw, "linkage_fingerprint": linkage_fingerprint(seed)}
    )


def build_stub(
    validation: WorkerAdmissionStubValidationInputV1,
    *,
    stub_id: str,
    intent_id: str,
) -> tuple[
    WorkerAdmissionStubV1,
    WorkerAdmissionStubIdempotencyV1,
    WorkerAdmissionStubReservationV1,
]:
    recorded = _instant(validation.authority.request_received_at)
    valid_until = min(
        recorded + timedelta(seconds=30),
        _instant(validation.runner_binding_plan.valid_until),
        _instant(validation.worker_reference.valid_until),
    )
    if recorded >= valid_until:
        raise ValueError("worker admission evidence is expired")
    idem = idempotency_key_fingerprint(
        validation.operator_id, validation.idempotency_key
    )
    request = request_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        create=validation.create,
        request_received_at=validation.authority.request_received_at,
        idempotency_fingerprint=idem,
    )
    intent = build_intent(validation, intent_id=intent_id)
    intake = build_intake(intent)
    linkage = build_linkage(
        validation.runner_binding_plan,
        validation.runner_binding_plan_status,
        validation.worker_reference,
        intent,
        intake,
    )
    raw = {
        "stub_id": stub_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "linkage": linkage,
        "worker_admission_intent": intent,
        "worker_admission_intake": intake,
        "worker_reference": validation.worker_reference,
        "inherited_limits": validation.runner_binding_plan.limits,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
    }
    seed = WorkerAdmissionStubV1.model_construct(
        **raw, stub_fingerprint=_fp("atlas:seed:v1", "stub")
    )
    stub = WorkerAdmissionStubV1.model_validate(
        {**raw, "stub_fingerprint": stub_fingerprint(seed)}
    )
    reservation_raw = {
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "runner_binding_plan_fingerprint": stub.linkage.runner_binding_plan_fingerprint,
        "worker_reference_fingerprint": stub.linkage.worker_reference_fingerprint,
        "worker_admission_intent_fingerprint": intent.intent_fingerprint,
        "inherited_limits_fingerprint": stub.linkage.inherited_limits_fingerprint,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
        "stub_id": stub_id,
        "stub_fingerprint": stub.stub_fingerprint,
        "reserved_at": validation.authority.request_received_at,
    }
    reservation_seed = WorkerAdmissionStubReservationV1.model_construct(
        **reservation_raw,
        subject_fingerprint=_fp("atlas:seed:v1", "subject"),
        reservation_fingerprint=_fp("atlas:seed:v1", "reservation"),
    )
    subject = subject_fingerprint(reservation_seed)
    reservation_seed = WorkerAdmissionStubReservationV1.model_construct(
        **reservation_raw,
        subject_fingerprint=subject,
        reservation_fingerprint=_fp("atlas:seed:v1", "reservation"),
    )
    reservation = WorkerAdmissionStubReservationV1.model_validate(
        {
            **reservation_raw,
            "subject_fingerprint": subject,
            "reservation_fingerprint": reservation_fingerprint(reservation_seed),
        }
    )
    idempotency = WorkerAdmissionStubIdempotencyV1(
        operator_id=validation.operator_id,
        idempotency_key_fingerprint=idem,
        request_fingerprint=request,
        subject_fingerprint=subject,
        stub_id=stub_id,
        stub_fingerprint=stub.stub_fingerprint,
    )
    return stub, idempotency, reservation


def derive_status(
    stub: WorkerAdmissionStubV1, *, observed_at: str
) -> WorkerAdmissionStubStatusV1:
    raw = {
        "stub_id": stub.stub_id,
        "observed_at": observed_at,
        "lifecycle": (
            "active" if _instant(observed_at) < _instant(stub.valid_until) else "expired"
        ),
    }
    seed = WorkerAdmissionStubStatusV1.model_construct(
        **raw, status_fingerprint=_fp("atlas:seed:v1", "status")
    )
    return WorkerAdmissionStubStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def parse_create_json(payload: bytes | str) -> WorkerAdmissionStubCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("worker admission stub request exceeds 16 KiB")
    try:
        decoded = raw.decode()
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
        return WorkerAdmissionStubCreateV1.model_validate(parsed)
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid worker admission stub request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
