"""Closed immutable v0.44 controlled dequeue admission models.

This module is pure contract validation. It has no store, queue I/O, route,
polling, dequeue, claim, lease, ack, worker, Agent, execution, installation,
deployment, rollback, or mutation behavior.
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
from app.installation_one_shot_live_enqueue.contract import (
    SUCCESS_BLOCKERS as V042_SUCCESS_BLOCKERS,
)
from app.installation_one_shot_live_enqueue.contract import (
    record_fingerprint as v042_record_fingerprint,
)
from app.installation_one_shot_live_enqueue.contract import (
    status_fingerprint as v042_status_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.queue_observation_receipt.contract import (
    SUCCESS_BLOCKERS as V043_SUCCESS_BLOCKERS,
)
from app.queue_observation_receipt.contract import (
    QueueObservationReceiptStatusV1,
    QueueObservationReceiptV1,
)
from app.queue_observation_receipt.contract import (
    lineage_fingerprint as v043_lineage_fingerprint,
)
from app.queue_observation_receipt.contract import (
    observation_fingerprint as v043_observation_fingerprint,
)
from app.queue_observation_receipt.contract import (
    receipt_fingerprint as v043_receipt_fingerprint,
)
from app.queue_observation_receipt.contract import (
    receipt_record_fingerprint as v043_receipt_record_fingerprint,
)
from app.queue_observation_receipt.contract import (
    status_fingerprint as v043_status_fingerprint,
)
from app.runner_binding_plan.contract import RunnerBindingLimitsV1

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 192 * 1024
MAX_COLLECTION_RECORDS = 16
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.controlled_dequeue_admission.record"
SCOPE = "installation_controlled_dequeue_admission_only"
SAFE_MESSAGE = "controlled dequeue admission request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UUID5_NAMESPACE = uuid.UUID("8c132d1a-23a0-5fb2-997d-764076b4a997")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v043_observation_not_active",
    "v043_observation_not_recorded",
    "v043_receipt_not_contract_eligible",
    "v042_enqueue_not_active",
    "v042_enqueue_not_recorded",
    "linkage_mismatch",
    "queue_identity_mismatch",
    "item_identity_mismatch",
    "observation_receipt_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "executable_payload",
    "unsupported_authority",
    "reservation_before_effect_failed",
    "permanent_subject_reserved",
    "idempotency_conflict",
    "append_indeterminate",
    "dequeue_not_defined",
    "queue_polling_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v043_observation_not_active",
    "v043_observation_not_recorded",
    "v043_receipt_not_contract_eligible",
    "v042_enqueue_not_active",
    "v042_enqueue_not_recorded",
    "linkage_mismatch",
    "queue_identity_mismatch",
    "item_identity_mismatch",
    "observation_receipt_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "executable_payload",
    "unsupported_authority",
    "reservation_before_effect_failed",
    "permanent_subject_reserved",
    "idempotency_conflict",
    "append_indeterminate",
    "dequeue_not_defined",
    "queue_polling_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
    "dequeue_not_defined",
    "queue_polling_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
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


def _ordered(blockers: tuple[BlockerV1, ...]) -> None:
    if len(blockers) != len(set(blockers)):
        raise ValueError("controlled dequeue admission blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("controlled dequeue admission blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    executable_payload_allowed: Literal[False] = False
    dequeue_defined: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    dequeue_attempted: Literal[False] = False
    dequeued: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    queue_polled: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_claimed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
    queue_leased: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    queue_acked: Literal[False] = False
    queue_consumed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_contacted: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    worker_started: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    process_execution_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    scheduler_allowed: Literal[False] = False
    workflow_start_allowed: Literal[False] = False
    docker_execution_allowed: Literal[False] = False
    podman_execution_allowed: Literal[False] = False
    container_execution_allowed: Literal[False] = False
    shell_execution_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False


class ControlledDequeueAdmissionCreateV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-create-v1"] = (
        "controlled-dequeue-admission-create-v1"
    )
    queue_observation_receipt_id: CanonicalUuid5
    queue_observation_receipt_fingerprint: FingerprintV1
    queue_observation_receipt_status_fingerprint: FingerprintV1
    queue_observation_receipt_valid_until: UtcSecond
    enqueue_id: CanonicalUuid5
    inert_queue_item_id: CanonicalUuid5
    inert_queue_item_fingerprint: FingerprintV1
    queue_identity: Literal["abstract_installation_queue"] = (
        "abstract_installation_queue"
    )
    item_identity: Literal["inert_reference_only_queue_item"] = (
        "inert_reference_only_queue_item"
    )
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        if self.enqueue_id != self.inert_queue_item_id:
            raise ValueError("controlled dequeue admission item identity mismatch")
        return self


class ControlledDequeueAdmissionAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-authority-context-v1"] = (
        "controlled-dequeue-admission-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class ControlledDequeueAdmissionDecisionV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-decision-v1"] = (
        "controlled-dequeue-admission-decision-v1"
    )
    decision: Literal["eligible_for_later_dequeue_consideration"] = (
        "eligible_for_later_dequeue_consideration"
    )
    admission_state: Literal["readiness_gated"] = "readiness_gated"
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    queue_identity_fingerprint: FingerprintV1
    item_identity_fingerprint: FingerprintV1
    lineage_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    decision_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionDecisionV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("controlled dequeue decision blockers must remain fixed")
        if self.decision_fingerprint != decision_fingerprint(self):
            raise ValueError("controlled dequeue decision fingerprint mismatch")
        _bounded(self)
        return self


class ControlledDequeueAdmissionV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-v1"] = (
        "controlled-dequeue-admission-v1"
    )
    admission_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    admission_state: Literal["readiness_gated"] = "readiness_gated"
    disposition: Literal["controlled_dequeue_admission_recorded"] = (
        "controlled_dequeue_admission_recorded"
    )
    eligibility: Literal["eligible_for_later_dequeue_consideration"] = (
        "eligible_for_later_dequeue_consideration"
    )
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    queue_observation_receipt: QueueObservationReceiptV1
    queue_observation_receipt_status: QueueObservationReceiptStatusV1
    inherited_limits: RunnerBindingLimitsV1
    admission_decision: ControlledDequeueAdmissionDecisionV1
    queue_identity_fingerprint: FingerprintV1
    item_identity_fingerprint: FingerprintV1
    lineage_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    admission_record_fingerprint: FingerprintV1
    controlled_dequeue_admission_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("controlled dequeue admission blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("controlled dequeue admission expiry exceeds freshness bound")
        receipt, status = (
            self.queue_observation_receipt,
            self.queue_observation_receipt_status,
        )
        enqueue = receipt.v042_enqueue
        item = enqueue.queue_item
        if (
            self.operator_id != receipt.operator_id
            or self.operator_id != status.operator_id
            or self.candidate_record_id != receipt.candidate_record_id
            or self.candidate_record_id != status.candidate_record_id
            or status.receipt_id != receipt.receipt_id
            or status.receipt_record_fingerprint != receipt.receipt_record_fingerprint
            or self.valid_until > receipt.valid_until
            or self.inherited_limits.limits_fingerprint
            != enqueue.inherited_limits.limits_fingerprint
            or item.inherited_limits_fingerprint
            != enqueue.inherited_limits.limits_fingerprint
        ):
            raise ValueError("controlled dequeue admission ownership or linkage mismatch")
        if (
            self.queue_identity_fingerprint
            != queue_identity_fingerprint(receipt, status)
            or self.item_identity_fingerprint != item_identity_fingerprint(receipt)
            or self.lineage_fingerprint != lineage_fingerprint(receipt, status)
            or self.admission_decision.queue_identity_fingerprint
            != self.queue_identity_fingerprint
            or self.admission_decision.item_identity_fingerprint
            != self.item_identity_fingerprint
            or self.admission_decision.lineage_fingerprint != self.lineage_fingerprint
            or self.admission_decision.inherited_limits_fingerprint
            != self.inherited_limits.limits_fingerprint
        ):
            raise ValueError("controlled dequeue admission fingerprint linkage mismatch")
        if self.subject_fingerprint != admission_subject_fingerprint(self):
            raise ValueError("controlled dequeue admission subject fingerprint mismatch")
        if self.admission_id != derived_admission_id(self.subject_fingerprint):
            raise ValueError("controlled dequeue admission id mismatch")
        if self.admission_record_fingerprint != admission_record_fingerprint(self):
            raise ValueError("controlled dequeue admission record fingerprint mismatch")
        _bounded(self)
        return self


class ControlledDequeueAdmissionStatusV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-status-v1"] = (
        "controlled-dequeue-admission-status-v1"
    )
    admission_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    lifecycle: Literal["active", "expired"]
    admission_state: Literal["controlled_dequeue_admission_recorded", "readiness_gated"]
    eligibility: Literal["eligible_for_later_dequeue_consideration"]
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    admission_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    controlled_dequeue_admission_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionStatusV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("controlled dequeue admission status blockers are fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("controlled dequeue admission status fingerprint mismatch")
        _bounded(self)
        return self


class ControlledDequeueAdmissionIdempotencyReservationV1(ContractModel):
    schema: Literal["controlled-dequeue-admission-idempotency-reservation-v1"] = (
        "controlled-dequeue-admission-idempotency-reservation-v1"
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


class ControlledDequeueAdmissionSubjectReservationV1(ContractModel):
    schema: Literal["controlled-dequeue-admission-subject-reservation-v1"] = (
        "controlled-dequeue-admission-subject-reservation-v1"
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
    def exact(self) -> ControlledDequeueAdmissionSubjectReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("controlled dequeue admission reservation fingerprint mismatch")
        return self


class ControlledDequeueAdmissionAuditEvidenceV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-audit-v1"] = (
        "controlled-dequeue-admission-audit-v1"
    )
    event: Literal[
        "controlled_dequeue_admission_recorded",
        "controlled_dequeue_admission_read",
        "controlled_dequeue_admission_indeterminate",
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
    controlled_dequeue_admission_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("controlled dequeue admission audit fingerprint mismatch")
        return self


class ControlledDequeueAdmissionEvaluationV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-evaluation-v1"] = (
        "controlled-dequeue-admission-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    admission_state: Literal["readiness_gated", "blocked", "indeterminate"]
    eligibility: Literal[
        "eligible_for_later_dequeue_consideration",
        "not_eligible_for_later_dequeue_consideration",
    ]
    blockers: tuple[BlockerV1, ...]
    recognized_active_v043_observation_count: int
    recognized_exact_v042_inert_queue_item_count: int
    controlled_dequeue_admission_build_allowed: bool
    evaluation_fingerprint: FingerprintV1
    controlled_dequeue_admission_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionEvaluationV1:
        _ordered(self.blockers)
        allowed = self.admission_state == "readiness_gated"
        if self.recognized_active_v043_observation_count != (1 if allowed else 0):
            raise ValueError("v0.43 observation recognition count mismatch")
        if self.recognized_exact_v042_inert_queue_item_count != (1 if allowed else 0):
            raise ValueError("v0.42 inert item recognition count mismatch")
        if self.controlled_dequeue_admission_build_allowed != allowed:
            raise ValueError("controlled dequeue admission build flag mismatch")
        if allowed and (
            self.blockers != SUCCESS_BLOCKERS
            or self.eligibility != "eligible_for_later_dequeue_consideration"
            or not self.controlled_dequeue_admission_recorded
        ):
            raise ValueError("recordable controlled dequeue admission shape mismatch")
        if not allowed and (
            self.eligibility != "not_eligible_for_later_dequeue_consideration"
            or self.controlled_dequeue_admission_recorded
        ):
            raise ValueError("blocked controlled dequeue admission shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("controlled dequeue evaluation fingerprint mismatch")
        _bounded(self)
        return self


class ControlledDequeueAdmissionRedactedErrorV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-error-v1"] = (
        "controlled-dequeue-admission-error-v1"
    )
    error_code: Literal[
        "installation_capability_unsupported",
        "evidence_not_found",
        "ownership_mismatch",
        "permission_scope_missing",
        "v043_observation_not_active",
        "v043_observation_not_recorded",
        "v043_receipt_not_contract_eligible",
        "v042_enqueue_not_active",
        "v042_enqueue_not_recorded",
        "linkage_mismatch",
        "queue_identity_mismatch",
        "item_identity_mismatch",
        "observation_receipt_mismatch",
        "fingerprint_mismatch",
        "inherited_limits_mismatch",
        "evidence_stale",
        "evidence_expired",
        "ambiguous_state",
        "executable_payload",
        "unsupported_authority",
        "permanent_subject_reserved",
        "idempotency_conflict",
        "append_indeterminate",
        "reservation_before_effect_failed",
        "unauthenticated",
        "forbidden",
        "not_found",
        "invalid_request",
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
    controlled_dequeue_admission_recorded: Literal[False] = False


class ControlledDequeueAdmissionResultV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-result-v1"] = (
        "controlled-dequeue-admission-result-v1"
    )
    ok: bool
    outcome: Literal["success", "failure", "indeterminate"]
    record: ControlledDequeueAdmissionV1 | None
    status: ControlledDequeueAdmissionStatusV1 | None
    error: ControlledDequeueAdmissionRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1
    controlled_dequeue_admission_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionResultV1:
        if self.outcome == "success":
            good = (
                self.ok
                and self.record is not None
                and self.status is not None
                and self.error is None
                and self.controlled_dequeue_admission_recorded
            )
        else:
            good = (
                not self.ok
                and self.record is None
                and self.status is None
                and self.error is not None
                and not self.controlled_dequeue_admission_recorded
            )
        if not good:
            raise ValueError("controlled dequeue admission result shape mismatch")
        if self.record is not None and self.status.admission_id != self.record.admission_id:
            raise ValueError("controlled dequeue admission result status binding mismatch")
        _bounded(self)
        return self


class ControlledDequeueAdmissionCollectionV1(ClosedAuthorityV1):
    schema: Literal["controlled-dequeue-admission-collection-v1"] = (
        "controlled-dequeue-admission-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[ControlledDequeueAdmissionV1, ...]
    count: int
    collection_fingerprint: FingerprintV1
    controlled_dequeue_admission_recorded: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("controlled dequeue admission collection exceeds bound")
        ordered = tuple(sorted(self.items, key=lambda item: (item.recorded_at, item.admission_id)))
        if ordered != self.items:
            raise ValueError("controlled dequeue admission collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("controlled dequeue admission collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("controlled dequeue admission collection fingerprint mismatch")
        _bounded(self)
        return self


class ControlledDequeueAdmissionValidationInputV1(ContractModel):
    """Injected facts only; no queue, worker, Agent, network, store, or I/O."""

    operator_id: OperatorId
    authority: ControlledDequeueAdmissionAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: ControlledDequeueAdmissionCreateV1
    queue_observation_receipt: QueueObservationReceiptV1
    queue_observation_receipt_status: QueueObservationReceiptStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> ControlledDequeueAdmissionValidationInputV1:
        receipt, status = (
            self.queue_observation_receipt,
            self.queue_observation_receipt_status,
        )
        enqueue = receipt.v042_enqueue
        enqueue_status = receipt.v042_enqueue_status
        item = enqueue.queue_item
        evidence = receipt.receipt_evidence
        observation = receipt.queue_observation
        now = _instant(self.authority.request_received_at)
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or receipt.operator_id != self.operator_id
            or status.operator_id != self.operator_id
            or enqueue.operator_id != self.operator_id
            or evidence.operator_id != self.operator_id
            or observation.operator_id != self.operator_id
        ):
            raise ValueError("controlled dequeue admission ownership mismatch")
        if (
            receipt.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
            or enqueue.candidate_record_id != self.candidate_record_id
            or evidence.candidate_record_id != self.candidate_record_id
            or observation.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("controlled dequeue admission candidate linkage mismatch")
        if (
            self.create.queue_observation_receipt_id != receipt.receipt_id
            or self.create.queue_observation_receipt_fingerprint
            != receipt.receipt_record_fingerprint
            or self.create.queue_observation_receipt_status_fingerprint
            != status.status_fingerprint
            or self.create.queue_observation_receipt_valid_until != receipt.valid_until
            or status.receipt_id != receipt.receipt_id
            or status.receipt_record_fingerprint != receipt.receipt_record_fingerprint
        ):
            raise ValueError("v0.43 observation receipt linkage mismatch")
        if (
            receipt.receipt_record_fingerprint != v043_receipt_record_fingerprint(receipt)
            or status.status_fingerprint != v043_status_fingerprint(status)
            or receipt.lineage_fingerprint
            != v043_lineage_fingerprint(enqueue, enqueue_status)
            or evidence.receipt_fingerprint != v043_receipt_fingerprint(evidence)
            or observation.observation_fingerprint
            != v043_observation_fingerprint(observation)
            or enqueue.record_fingerprint != v042_record_fingerprint(enqueue)
            or enqueue_status.status_fingerprint
            != v042_status_fingerprint(enqueue_status)
        ):
            raise ValueError("controlled dequeue prerequisite fingerprint mismatch")
        if status.lifecycle != "active":
            raise ValueError("v0.43 observation is not active")
        if (
            receipt.lifecycle != "active"
            or status.disposition != "observation_recorded"
            or not status.queue_observation_recorded
            or receipt.disposition != "observation_recorded"
            or receipt.blockers != V043_SUCCESS_BLOCKERS
            or status.blockers != V043_SUCCESS_BLOCKERS
            or observation.observation_state != "observed_recorded_not_consumable"
            or observation.lifecycle != "active"
        ):
            raise ValueError("v0.43 observation is not recorded")
        if (
            evidence.receipt_state != "receipt_recorded_for_contract_eligible_enqueue"
            or evidence.receipt_disposition != "contract_eligible"
            or evidence.payload_present
            or evidence.effect_attempted
        ):
            raise ValueError("v0.43 receipt is not contract eligible")
        if enqueue_status.lifecycle != "active":
            raise ValueError("v0.42 enqueue is not active")
        if (
            enqueue.lifecycle != "active"
            or enqueue.outcome != "one_shot_live_enqueue_recorded"
            or not enqueue.one_shot_live_enqueue_recorded
            or enqueue_status.outcome != "one_shot_live_enqueue_recorded"
            or not enqueue_status.one_shot_live_enqueue_recorded
            or enqueue.blockers != V042_SUCCESS_BLOCKERS
            or enqueue_status.blockers != V042_SUCCESS_BLOCKERS
        ):
            raise ValueError("v0.42 enqueue is not recorded")
        if (
            self.create.queue_identity != "abstract_installation_queue"
            or observation.queue_identity != "abstract_installation_queue"
        ):
            raise ValueError("queue identity mismatch")
        if (
            self.create.item_identity != "inert_reference_only_queue_item"
            or observation.item_identity != "inert_reference_only_queue_item"
            or item.item_kind != "inert_reference_only_queue_item"
        ):
            raise ValueError("item identity mismatch")
        if (
            self.create.enqueue_id != enqueue.enqueue_id
            or self.create.enqueue_id != item.queue_item_id
            or self.create.enqueue_id != evidence.inert_queue_item_id
            or self.create.enqueue_id != observation.enqueue_id
            or self.create.inert_queue_item_id != item.queue_item_id
            or self.create.inert_queue_item_fingerprint != item.item_fingerprint
            or evidence.inert_queue_item_fingerprint != item.item_fingerprint
        ):
            raise ValueError("observation receipt item mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != enqueue.inherited_limits.limits_fingerprint
            or item.inherited_limits_fingerprint
            != enqueue.inherited_limits.limits_fingerprint
        ):
            raise ValueError("inherited limits mismatch")
        if (
            item.payload_schema_defined
            or item.payload_constructed
            or item.payload_serialized
            or item.payload_bytes != 0
            or item.execution_allowed
            or evidence.executable
        ):
            raise ValueError("executable payload is not supported")
        if (
            self.authority.dequeue_allowed
            or self.authority.dequeue_attempted
            or self.authority.dequeued
            or self.authority.queue_polling_allowed
            or self.authority.queue_claim_allowed
            or self.authority.queue_lease_allowed
            or self.authority.queue_ack_allowed
            or self.authority.worker_contact_allowed
            or self.authority.worker_start_allowed
            or self.authority.agent_invocation_allowed
            or self.authority.execution_start_allowed
            or self.authority.process_execution_allowed
        ):
            raise ValueError("unsupported authority")
        starts = (
            _instant(receipt.recorded_at),
            _instant(status.evaluated_at),
            _instant(observation.observed_at),
            _instant(evidence.recorded_at),
            _instant(enqueue.recorded_at),
            _instant(enqueue_status.evaluated_at),
            _instant(item.recorded_at),
        )
        if any(
            value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS)
            for value in starts
        ):
            raise ValueError("controlled dequeue admission evidence is stale")
        expiries = (
            _instant(receipt.valid_until),
            _instant(status.valid_until),
            _instant(observation.valid_until),
            _instant(evidence.valid_until),
            _instant(enqueue.valid_until),
            _instant(item.valid_until),
        )
        if any(now >= expiry for expiry in expiries):
            raise ValueError("controlled dequeue admission evidence is expired")
        return self


def queue_identity_fingerprint(
    receipt: QueueObservationReceiptV1 | dict[str, Any],
    receipt_status: QueueObservationReceiptStatusV1 | dict[str, Any],
) -> FingerprintV1:
    raw = receipt.model_dump(mode="json") if isinstance(receipt, BaseModel) else dict(receipt)
    receipt_status_raw = (
        receipt_status.model_dump(mode="json")
        if isinstance(receipt_status, BaseModel)
        else dict(receipt_status)
    )
    enqueue = raw["v042_enqueue"]
    enqueue_status = raw["v042_enqueue_status"]
    item = enqueue["queue_item"]
    observation = raw["queue_observation"]
    return fingerprint(
        "atlas:controlled-dequeue-admission-queue-identity:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "queue_identity": observation["queue_identity"],
            "queue_intake_reference_id": item["queue_intake_reference_id"],
            "queue_intake_reference_fingerprint": item[
                "queue_intake_reference_fingerprint"
            ],
            "queue_item_reference_id": item["queue_item_reference_id"],
            "queue_item_reference_fingerprint": item[
                "queue_item_reference_fingerprint"
            ],
            "enqueue_id": enqueue["enqueue_id"],
            "enqueue_record_fingerprint": enqueue["record_fingerprint"],
            "enqueue_status_fingerprint": enqueue_status["status_fingerprint"],
            "receipt_id": raw["receipt_id"],
            "receipt_record_fingerprint": raw["receipt_record_fingerprint"],
            "receipt_status_fingerprint": receipt_status_raw["status_fingerprint"],
            "observation_fingerprint": observation["observation_fingerprint"],
            "lineage_fingerprint": raw["lineage_fingerprint"],
            "inherited_limits_fingerprint": item["inherited_limits_fingerprint"],
        },
    )


def item_identity_fingerprint(
    receipt: QueueObservationReceiptV1 | dict[str, Any],
) -> FingerprintV1:
    raw = receipt.model_dump(mode="json") if isinstance(receipt, BaseModel) else dict(receipt)
    enqueue = raw["v042_enqueue"]
    item = enqueue["queue_item"]
    evidence = raw["receipt_evidence"]
    observation = raw["queue_observation"]
    return fingerprint(
        "atlas:controlled-dequeue-admission-item-identity:v1",
        {
            "enqueue_id": enqueue["enqueue_id"],
            "queue_item_id": item["queue_item_id"],
            "inert_queue_item_id": evidence["inert_queue_item_id"],
            "observation_enqueue_id": observation["enqueue_id"],
            "item_identity": observation["item_identity"],
            "item_fingerprint": item["item_fingerprint"],
            "receipt_item_fingerprint": evidence["inert_queue_item_fingerprint"],
            "reference_only": item["reference_only"],
            "payload_bytes": item["payload_bytes"],
        },
    )


def lineage_fingerprint(
    receipt: QueueObservationReceiptV1,
    status: QueueObservationReceiptStatusV1,
) -> FingerprintV1:
    enqueue = receipt.v042_enqueue
    enqueue_status = receipt.v042_enqueue_status
    return fingerprint(
        "atlas:controlled-dequeue-admission-v020-v043-chain:v1",
        {
            "v043_receipt_id": receipt.receipt_id,
            "v043_receipt_record_fingerprint": receipt.receipt_record_fingerprint,
            "v043_receipt_status_fingerprint": status.status_fingerprint,
            "v043_receipt_subject_fingerprint": receipt.subject_fingerprint,
            "v043_observation_fingerprint": (
                receipt.queue_observation.observation_fingerprint
            ),
            "v043_enqueue_receipt_fingerprint": (
                receipt.receipt_evidence.receipt_fingerprint
            ),
            "v043_lineage_fingerprint": receipt.lineage_fingerprint,
            "v042_enqueue_id": enqueue.enqueue_id,
            "v042_enqueue_record_fingerprint": enqueue.record_fingerprint,
            "v042_enqueue_status_fingerprint": enqueue_status.status_fingerprint,
            "v042_queue_item_fingerprint": enqueue.queue_item.item_fingerprint,
            "v042_lineage_fingerprint": enqueue.lineage.lineage_fingerprint,
        },
    )


def decision_fingerprint(
    value: ControlledDequeueAdmissionDecisionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-decision:v1",
        _without(value, "decision_fingerprint"),
    )


def admission_subject_fingerprint(
    value: ControlledDequeueAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint(
        "atlas:controlled-dequeue-admission-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "queue_observation_receipt_fingerprint": raw[
                "queue_observation_receipt"
            ]["receipt_record_fingerprint"],
            "queue_observation_receipt_status_fingerprint": raw[
                "queue_observation_receipt_status"
            ]["status_fingerprint"],
            "queue_identity_fingerprint": raw["queue_identity_fingerprint"],
            "item_identity_fingerprint": raw["item_identity_fingerprint"],
            "lineage_fingerprint": raw["lineage_fingerprint"],
            "decision_fingerprint": raw["admission_decision"]["decision_fingerprint"],
        },
    )


def admission_record_fingerprint(
    value: ControlledDequeueAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-record:v1",
        _without(value, "admission_record_fingerprint"),
    )


def status_fingerprint(
    value: ControlledDequeueAdmissionStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-status:v1",
        _without(value, "status_fingerprint"),
    )


def evaluation_fingerprint(
    value: ControlledDequeueAdmissionEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:controlled-dequeue-admission-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: ControlledDequeueAdmissionCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def reservation_fingerprint(
    value: ControlledDequeueAdmissionSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def derived_uuid5(domain: str, value: Any) -> str:
    seed = fingerprint(domain, value).value
    return str(uuid.uuid5(_UUID5_NAMESPACE, f"{domain}:{seed}"))


def derived_admission_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5(
        "atlas:controlled-dequeue-admission-id:v1", subject_fingerprint
    )


def audit_fingerprint(
    value: ControlledDequeueAdmissionAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: ControlledDequeueAdmissionCollectionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-dequeue-admission-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def build_admission(
    validation: ControlledDequeueAdmissionValidationInputV1,
) -> ControlledDequeueAdmissionV1:
    receipt, status = (
        validation.queue_observation_receipt,
        validation.queue_observation_receipt_status,
    )
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(receipt.valid_until),
        _instant(status.valid_until),
        _instant(receipt.v042_enqueue.valid_until),
        _instant(receipt.v042_enqueue.queue_item.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    queue_fp = queue_identity_fingerprint(receipt, status)
    item_fp = item_identity_fingerprint(receipt)
    line_fp = lineage_fingerprint(receipt, status)
    decision_raw = {
        "queue_identity_fingerprint": queue_fp,
        "item_identity_fingerprint": item_fp,
        "lineage_fingerprint": line_fp,
        "inherited_limits_fingerprint": receipt.v042_enqueue.inherited_limits.limits_fingerprint,
    }
    decision_seed = ControlledDequeueAdmissionDecisionV1.model_construct(
        **decision_raw,
        decision_fingerprint=fingerprint("atlas:seed:v1", "decision"),
    )
    decision = ControlledDequeueAdmissionDecisionV1.model_validate(
        {**decision_raw, "decision_fingerprint": decision_fingerprint(decision_seed)}
    )
    raw = {
        "admission_id": derived_admission_id(
            fingerprint(
                "atlas:controlled-dequeue-admission-subject:v1",
                {
                    "operator_id": validation.operator_id,
                    "candidate_record_id": validation.candidate_record_id,
                    "queue_observation_receipt_fingerprint": (
                        receipt.receipt_record_fingerprint
                    ),
                    "queue_observation_receipt_status_fingerprint": (
                        status.status_fingerprint
                    ),
                    "queue_identity_fingerprint": queue_fp,
                    "item_identity_fingerprint": item_fp,
                    "lineage_fingerprint": line_fp,
                    "decision_fingerprint": decision.decision_fingerprint,
                },
            )
        ),
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "queue_observation_receipt": receipt,
        "queue_observation_receipt_status": status,
        "inherited_limits": receipt.v042_enqueue.inherited_limits,
        "admission_decision": decision,
        "queue_identity_fingerprint": queue_fp,
        "item_identity_fingerprint": item_fp,
        "lineage_fingerprint": line_fp,
    }
    subject_seed = ControlledDequeueAdmissionV1.model_construct(
        **raw,
        subject_fingerprint=fingerprint("atlas:seed:v1", "subject"),
        admission_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    subject = admission_subject_fingerprint(subject_seed)
    record_seed = ControlledDequeueAdmissionV1.model_construct(
        **{**raw, "admission_id": derived_admission_id(subject)},
        subject_fingerprint=subject,
        admission_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    return ControlledDequeueAdmissionV1.model_validate(
        {
            **raw,
            "admission_id": derived_admission_id(subject),
            "subject_fingerprint": subject,
            "admission_record_fingerprint": admission_record_fingerprint(record_seed),
        }
    )


def build_reservations(
    validation: ControlledDequeueAdmissionValidationInputV1,
    admission: ControlledDequeueAdmissionV1,
) -> tuple[
    ControlledDequeueAdmissionIdempotencyReservationV1,
    ControlledDequeueAdmissionSubjectReservationV1,
]:
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request = request_fingerprint(
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
        "request_fingerprint": request,
        "subject_fingerprint": admission.subject_fingerprint,
        "admission_id": admission.admission_id,
        "admission_record_fingerprint": admission.admission_record_fingerprint,
        "reserved_at": validation.authority.request_received_at,
    }
    idempotency = ControlledDequeueAdmissionIdempotencyReservationV1.model_validate(raw)
    seed = ControlledDequeueAdmissionSubjectReservationV1.model_construct(
        **raw,
        reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
    )
    subject = ControlledDequeueAdmissionSubjectReservationV1.model_validate(
        {**raw, "reservation_fingerprint": reservation_fingerprint(seed)}
    )
    return idempotency, subject


def derive_status(
    record: ControlledDequeueAdmissionV1,
    *,
    evaluated_at: str,
) -> ControlledDequeueAdmissionStatusV1:
    lifecycle = "active" if _instant(evaluated_at) < _instant(record.valid_until) else "expired"
    raw = {
        "admission_id": record.admission_id,
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "lifecycle": lifecycle,
        "admission_state": "readiness_gated",
        "eligibility": record.eligibility,
        "blockers": record.blockers,
        "evaluated_at": evaluated_at,
        "valid_until": record.valid_until,
        "admission_record_fingerprint": record.admission_record_fingerprint,
    }
    seed = ControlledDequeueAdmissionStatusV1.model_construct(
        **raw,
        status_fingerprint=fingerprint("atlas:seed:v1", "status"),
    )
    return ControlledDequeueAdmissionStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[ControlledDequeueAdmissionV1, ...],
) -> ControlledDequeueAdmissionCollectionV1:
    ordered = tuple(sorted(items, key=lambda item: (item.recorded_at, item.admission_id)))
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": ordered,
        "count": len(ordered),
    }
    seed = ControlledDequeueAdmissionCollectionV1.model_construct(
        **raw,
        collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
    )
    return ControlledDequeueAdmissionCollectionV1.model_validate(
        {**raw, "collection_fingerprint": collection_fingerprint(seed)}
    )


def build_audit(
    record: ControlledDequeueAdmissionV1,
    *,
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"],
    event: Literal[
        "controlled_dequeue_admission_recorded",
        "controlled_dequeue_admission_read",
        "controlled_dequeue_admission_indeterminate",
    ],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> ControlledDequeueAdmissionAuditEvidenceV1:
    raw = {
        "event": event,
        "audit_id": derived_uuid5(
            "atlas:controlled-dequeue-admission-audit-id:v1",
            {
                "admission_id": record.admission_id,
                "admission_record_fingerprint": record.admission_record_fingerprint,
                "event": event,
                "outcome": outcome,
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
        "controlled_dequeue_admission_recorded": outcome == "recorded",
    }
    seed = ControlledDequeueAdmissionAuditEvidenceV1.model_construct(
        **raw,
        audit_fingerprint=fingerprint("atlas:seed:v1", "audit"),
    )
    return ControlledDequeueAdmissionAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_fingerprint(seed)}
    )


def evaluate_controlled_dequeue_admission(
    value: ControlledDequeueAdmissionValidationInputV1 | dict[str, Any],
) -> ControlledDequeueAdmissionEvaluationV1:
    now = _evaluation_time(value)
    try:
        validation = (
            value
            if isinstance(value, ControlledDequeueAdmissionValidationInputV1)
            else ControlledDequeueAdmissionValidationInputV1.model_validate(value)
        )
        blocker: BlockerV1 | None = None
        operator_id = validation.operator_id
        candidate_record_id = validation.candidate_record_id
        expiries = (
            validation.queue_observation_receipt.valid_until,
            validation.queue_observation_receipt_status.valid_until,
            validation.queue_observation_receipt.v042_enqueue.valid_until,
            validation.queue_observation_receipt.v042_enqueue.queue_item.valid_until,
        )
        earliest_expiry = min(expiries, key=_instant)
    except Exception as exc:  # noqa: BLE001 - closed redaction for hostile input
        blocker = _classify_validation_error(str(exc))
        operator_id = _blocked_operator(value)
        candidate_record_id = _blocked_candidate(value)
        earliest_expiry = None
    allowed = blocker is None
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": now,
        "earliest_expiry": earliest_expiry,
        "admission_state": "readiness_gated" if allowed else "blocked",
        "eligibility": (
            "eligible_for_later_dequeue_consideration"
            if allowed
            else "not_eligible_for_later_dequeue_consideration"
        ),
        "blockers": SUCCESS_BLOCKERS if allowed else (blocker,),
        "recognized_active_v043_observation_count": 1 if allowed else 0,
        "recognized_exact_v042_inert_queue_item_count": 1 if allowed else 0,
        "controlled_dequeue_admission_build_allowed": allowed,
        "controlled_dequeue_admission_recorded": allowed,
    }
    seed = ControlledDequeueAdmissionEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return ControlledDequeueAdmissionEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def parse_create_json(raw: str | bytes) -> ControlledDequeueAdmissionCreateV1:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 16 KiB")
    try:
        text = data.decode("utf-8")
        if unicodedata.normalize("NFC", text) != text:
            raise StrictContractError("create request must be NFC")
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except StrictContractError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictContractError("malformed create request") from exc
    except ValueError as exc:
        raise StrictContractError("malformed create request") from exc
    return ControlledDequeueAdmissionCreateV1.model_validate(parsed)


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictContractError("duplicate key in create request")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise StrictContractError(f"unsupported JSON constant {value}")


def _evaluation_time(
    value: ControlledDequeueAdmissionValidationInputV1 | dict[str, Any],
) -> str:
    if isinstance(value, ControlledDequeueAdmissionValidationInputV1):
        return value.authority.request_received_at
    authority = value.get("authority") if isinstance(value, dict) else None
    if isinstance(authority, dict) and isinstance(authority.get("request_received_at"), str):
        return authority["request_received_at"]
    return "1970-01-01T00:00:00Z"


def _blocked_operator(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("operator_id"), str):
        raw = value["operator_id"]
        if raw.isascii() and _IDENTITY.fullmatch(raw) is not None:
            return raw
    return _BLOCKED_OPERATOR_ID


def _blocked_candidate(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("candidate_record_id"), str):
        raw = value["candidate_record_id"]
        if re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{12}", raw
        ):
            return raw
    return _BLOCKED_CANDIDATE_ID


def _classify_validation_error(message: str) -> BlockerV1:
    lowered = message.lower()
    if "field required" in lowered or "missing" in lowered:
        return "evidence_not_found"
    if "home assistant" in lowered or "capability" in lowered:
        return "installation_capability_unsupported"
    if "ownership" in lowered:
        return "ownership_mismatch"
    if "permission" in lowered or "scope" in lowered:
        return "permission_scope_missing"
    if "not active" in lowered and "v0.43" in lowered:
        return "v043_observation_not_active"
    if "not recorded" in lowered and "v0.43" in lowered:
        return "v043_observation_not_recorded"
    if "contract eligible" in lowered:
        return "v043_receipt_not_contract_eligible"
    if "not active" in lowered and "v0.42" in lowered:
        return "v042_enqueue_not_active"
    if "not recorded" in lowered and "v0.42" in lowered:
        return "v042_enqueue_not_recorded"
    if "queue identity" in lowered:
        return "queue_identity_mismatch"
    if "item identity" in lowered:
        return "item_identity_mismatch"
    if "observation_state" in lowered or "receipt_disposition" in lowered:
        return "ambiguous_state"
    if "fingerprint" in lowered:
        return "fingerprint_mismatch"
    if "inherited limits" in lowered:
        return "inherited_limits_mismatch"
    if "stale" in lowered or "future" in lowered:
        return "evidence_stale"
    if "expired" in lowered:
        return "evidence_expired"
    if "ambiguous" in lowered:
        return "ambiguous_state"
    if "executable" in lowered or "payload" in lowered:
        return "executable_payload"
    if "authority" in lowered:
        return "unsupported_authority"
    if "observation receipt" in lowered or "item mismatch" in lowered:
        return "observation_receipt_mismatch"
    if "linkage" in lowered or "binding" in lowered:
        return "linkage_mismatch"
    return "evidence_not_found"
