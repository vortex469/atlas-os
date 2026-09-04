"""Closed immutable v0.43 queue observation and enqueue receipt models.

This module is pure contract validation. It has no store, queue, worker,
network, Agent, execution, installation, deployment, or rollback behavior.
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
    OneShotLiveEnqueueStatusV1,
    OneShotLiveEnqueueV1,
)
from app.installation_one_shot_live_enqueue.contract import (
    record_fingerprint as v042_record_fingerprint,
)
from app.installation_one_shot_live_enqueue.contract import (
    status_fingerprint as v042_status_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 128 * 1024
MAX_COLLECTION_RECORDS = 16
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.queue_observation_receipt.record"
SCOPE = "installation_queue_observation_receipt_only"
SAFE_MESSAGE = "queue observation receipt request could not be completed"
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
    "linkage_mismatch",
    "fingerprint_mismatch",
    "evidence_stale",
    "evidence_expired",
    "v042_enqueue_not_active",
    "v042_enqueue_not_recorded",
    "queue_identity_mismatch",
    "item_identity_mismatch",
    "receipt_evidence_invalid",
    "observation_malformed",
    "ambiguous_state",
    "executable_payload",
    "unsupported_authority",
    "dequeue_not_defined",
    "queue_polling_not_defined",
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
    "v042_enqueue_not_active",
    "v042_enqueue_not_recorded",
    "queue_identity_mismatch",
    "item_identity_mismatch",
    "receipt_evidence_invalid",
    "observation_malformed",
    "ambiguous_state",
    "executable_payload",
    "unsupported_authority",
    "dequeue_not_defined",
    "queue_polling_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
    "dequeue_not_defined",
    "queue_polling_not_defined",
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
        raise ValueError("queue observation receipt blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("queue observation receipt blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    observation_only: Literal[True] = True
    reference_only: Literal[True] = True
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    executable_payload_allowed: Literal[False] = False
    live_enqueue_allowed: Literal[False] = False
    dequeue_defined: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    workflow_start_allowed: Literal[False] = False
    docker_execution_allowed: Literal[False] = False
    podman_execution_allowed: Literal[False] = False
    container_execution_allowed: Literal[False] = False
    shell_execution_allowed: Literal[False] = False
    process_execution_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False


class QueueObservationReceiptCreateV1(ContractModel):
    schema: Literal["queue-observation-receipt-create-v1"] = (
        "queue-observation-receipt-create-v1"
    )
    enqueue_id: CanonicalUuid5
    enqueue_record_fingerprint: FingerprintV1
    enqueue_status_fingerprint: FingerprintV1
    enqueue_valid_until: UtcSecond
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    inert_queue_item_id: CanonicalUuid5
    inert_queue_item_fingerprint: FingerprintV1
    observed_queue_identity: Literal["abstract_installation_queue"] = (
        "abstract_installation_queue"
    )
    observed_item_identity: Literal["inert_reference_only_queue_item"] = (
        "inert_reference_only_queue_item"
    )
    observation_state: Literal["observed_recorded_not_consumable"] = (
        "observed_recorded_not_consumable"
    )
    receipt_disposition: Literal["contract_eligible"] = "contract_eligible"
    requested_scope: Literal[SCOPE] = SCOPE
    observation_only: Literal[True] = True
    reference_only: Literal[True] = True
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    executable_payload_allowed: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class QueueObservationReceiptAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-authority-context-v1"] = (
        "queue-observation-receipt-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class EnqueueReceiptEvidenceV1(ContractModel):
    schema: Literal["enqueue-receipt-evidence-v1"] = "enqueue-receipt-evidence-v1"
    enqueue_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    enqueue_record_fingerprint: FingerprintV1
    enqueue_status_fingerprint: FingerprintV1
    inert_queue_item_id: CanonicalUuid5
    inert_queue_item_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    receipt_state: Literal["receipt_recorded_for_contract_eligible_enqueue"] = (
        "receipt_recorded_for_contract_eligible_enqueue"
    )
    receipt_disposition: Literal["contract_eligible"] = "contract_eligible"
    recorded_at: UtcSecond
    valid_until: UtcSecond
    receipt_fingerprint: FingerprintV1
    payload_present: Literal[False] = False
    executable: Literal[False] = False
    effect_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> EnqueueReceiptEvidenceV1:
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("enqueue receipt evidence expiry exceeds freshness bound")
        if self.enqueue_id != self.inert_queue_item_id:
            raise ValueError("enqueue receipt item identity mismatch")
        if self.receipt_fingerprint != receipt_fingerprint(self):
            raise ValueError("enqueue receipt evidence fingerprint mismatch")
        _bounded(self)
        return self


class QueueObservationV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-v1"] = "queue-observation-v1"
    observation_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    enqueue_id: CanonicalUuid5
    queue_identity: Literal["abstract_installation_queue"] = "abstract_installation_queue"
    item_identity: Literal["inert_reference_only_queue_item"] = (
        "inert_reference_only_queue_item"
    )
    observation_state: Literal["observed_recorded_not_consumable"] = (
        "observed_recorded_not_consumable"
    )
    lifecycle: Literal["active"] = "active"
    disposition: Literal["observation_recorded"] = "observation_recorded"
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    receipt_evidence: EnqueueReceiptEvidenceV1
    observed_at: UtcSecond
    valid_until: UtcSecond
    observation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> QueueObservationV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("queue observation blockers must remain fixed")
        observed, expiry = _instant(self.observed_at), _instant(self.valid_until)
        if not observed < expiry <= observed + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("queue observation expiry exceeds freshness bound")
        receipt = self.receipt_evidence
        if (
            self.operator_id != receipt.operator_id
            or self.candidate_record_id != receipt.candidate_record_id
            or self.enqueue_id != receipt.enqueue_id
            or self.enqueue_id != receipt.inert_queue_item_id
            or self.observed_at != receipt.recorded_at
            or self.valid_until != receipt.valid_until
        ):
            raise ValueError("queue observation receipt linkage mismatch")
        if self.observation_id != derived_observation_id(observation_subject_fingerprint(self)):
            raise ValueError("queue observation id mismatch")
        if self.observation_fingerprint != observation_fingerprint(self):
            raise ValueError("queue observation fingerprint mismatch")
        _bounded(self)
        return self


class QueueObservationReceiptV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-v1"] = "queue-observation-receipt-v1"
    receipt_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    disposition: Literal["observation_recorded"] = "observation_recorded"
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    v042_enqueue: OneShotLiveEnqueueV1
    v042_enqueue_status: OneShotLiveEnqueueStatusV1
    receipt_evidence: EnqueueReceiptEvidenceV1
    queue_observation: QueueObservationV1
    lineage_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    receipt_record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("queue observation receipt blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("queue observation receipt expiry exceeds freshness bound")
        enqueue, status, evidence, observation = (
            self.v042_enqueue,
            self.v042_enqueue_status,
            self.receipt_evidence,
            self.queue_observation,
        )
        if (
            self.receipt_id != observation.observation_id
            or self.operator_id != enqueue.operator_id
            or self.operator_id != status.operator_id
            or self.operator_id != evidence.operator_id
            or self.operator_id != observation.operator_id
            or self.candidate_record_id != enqueue.candidate_record_id
            or self.candidate_record_id != status.candidate_record_id
            or self.candidate_record_id != evidence.candidate_record_id
            or self.candidate_record_id != observation.candidate_record_id
            or self.recorded_at != evidence.recorded_at
            or self.recorded_at != observation.observed_at
            or self.valid_until != evidence.valid_until
            or self.valid_until != observation.valid_until
        ):
            raise ValueError("queue observation receipt ownership or linkage mismatch")
        if (
            evidence.enqueue_id != enqueue.enqueue_id
            or status.enqueue_id != enqueue.enqueue_id
            or evidence.enqueue_record_fingerprint != enqueue.record_fingerprint
            or status.record_fingerprint != enqueue.record_fingerprint
            or evidence.enqueue_status_fingerprint != status.status_fingerprint
            or evidence.inert_queue_item_fingerprint != enqueue.queue_item.item_fingerprint
            or evidence.queue_intake_reference_id
            != enqueue.queue_item.queue_intake_reference_id
            or evidence.queue_intake_reference_fingerprint
            != enqueue.queue_item.queue_intake_reference_fingerprint
            or evidence.queue_item_reference_id != enqueue.queue_item.queue_item_reference_id
            or evidence.queue_item_reference_fingerprint
            != enqueue.queue_item.queue_item_reference_fingerprint
        ):
            raise ValueError("queue observation receipt queue/item identity mismatch")
        if self.lineage_fingerprint != lineage_fingerprint(enqueue, status):
            raise ValueError("queue observation receipt lineage fingerprint mismatch")
        if self.subject_fingerprint != receipt_subject_fingerprint(self):
            raise ValueError("queue observation receipt subject fingerprint mismatch")
        if self.receipt_record_fingerprint != receipt_record_fingerprint(self):
            raise ValueError("queue observation receipt record fingerprint mismatch")
        _bounded(self)
        return self


class QueueObservationReceiptEvaluationV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-evaluation-v1"] = (
        "queue-observation-receipt-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    disposition: Literal["observation_recorded", "blocked"]
    blockers: tuple[BlockerV1, ...]
    recognized_exact_v042_enqueue_count: int
    recognized_contract_eligible_enqueue: bool
    receipt_build_allowed: bool
    evaluation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptEvaluationV1:
        _ordered(self.blockers)
        allowed = self.disposition == "observation_recorded"
        if self.recognized_exact_v042_enqueue_count != (1 if allowed else 0):
            raise ValueError("v0.42 enqueue recognition count mismatch")
        if self.recognized_contract_eligible_enqueue != allowed:
            raise ValueError("v0.42 enqueue recognition flag mismatch")
        if self.receipt_build_allowed != allowed:
            raise ValueError("queue observation receipt build flag mismatch")
        if allowed and self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("recordable queue observation requires fixed blockers")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("queue observation receipt evaluation fingerprint mismatch")
        _bounded(self)
        return self


class QueueObservationReceiptStatusV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-status-v1"] = (
        "queue-observation-receipt-status-v1"
    )
    receipt_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    lifecycle: Literal["active", "expired"]
    disposition: Literal["observation_recorded"]
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    receipt_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    queue_observation_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptStatusV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("queue observation receipt status blockers must remain fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("queue observation receipt status fingerprint mismatch")
        _bounded(self)
        return self


class QueueObservationReceiptIdempotencyReservationV1(ContractModel):
    schema: Literal["queue-observation-receipt-idempotency-reservation-v1"] = (
        "queue-observation-receipt-idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    receipt_id: CanonicalUuid5
    receipt_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    permanent: Literal[True] = True


class QueueObservationReceiptSubjectReservationV1(ContractModel):
    schema: Literal["queue-observation-receipt-subject-reservation-v1"] = (
        "queue-observation-receipt-subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    receipt_id: CanonicalUuid5
    receipt_record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptSubjectReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("queue observation receipt reservation fingerprint mismatch")
        return self


class QueueObservationReceiptAuditEvidenceV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-audit-v1"] = (
        "queue-observation-receipt-audit-v1"
    )
    event: Literal[
        "queue_observation_receipt_recorded",
        "queue_observation_receipt_read",
        "queue_observation_receipt_indeterminate",
    ]
    audit_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    receipt_id: CanonicalUuid5 | None
    occurred_at: UtcSecond
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"]
    correlation_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1 | None
    receipt_record_fingerprint: FingerprintV1 | None
    audit_fingerprint: FingerprintV1
    queue_observation_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("queue observation receipt audit fingerprint mismatch")
        return self


class QueueObservationReceiptRedactedErrorV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-error-v1"] = (
        "queue-observation-receipt-error-v1"
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
        "v042_enqueue_not_active",
        "v042_enqueue_not_recorded",
        "queue_identity_mismatch",
        "item_identity_mismatch",
        "receipt_evidence_invalid",
        "observation_malformed",
        "ambiguous_state",
        "executable_payload",
        "unsupported_authority",
        "reservation_before_effect_failed",
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
    queue_observation_recorded: Literal[False] = False


class QueueObservationReceiptResultV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-result-v1"] = (
        "queue-observation-receipt-result-v1"
    )
    ok: bool
    outcome: Literal["success", "failure", "indeterminate"]
    record: QueueObservationReceiptV1 | None
    status: QueueObservationReceiptStatusV1 | None
    error: QueueObservationReceiptRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1
    queue_observation_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptResultV1:
        if self.outcome == "success":
            good = (
                self.ok
                and self.record is not None
                and self.status is not None
                and self.error is None
                and self.queue_observation_recorded
            )
        else:
            good = (
                not self.ok
                and self.record is None
                and self.status is None
                and self.error is not None
                and not self.queue_observation_recorded
            )
        if not good:
            raise ValueError("queue observation receipt result shape mismatch")
        if self.record is not None and self.status.receipt_id != self.record.receipt_id:
            raise ValueError("queue observation receipt result status binding mismatch")
        _bounded(self)
        return self


class QueueObservationReceiptCollectionV1(ClosedAuthorityV1):
    schema: Literal["queue-observation-receipt-collection-v1"] = (
        "queue-observation-receipt-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[QueueObservationReceiptV1, ...]
    count: int
    collection_fingerprint: FingerprintV1
    queue_observation_recorded: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("queue observation receipt collection exceeds bound")
        ordered = tuple(sorted(self.items, key=lambda item: (item.recorded_at, item.receipt_id)))
        if ordered != self.items:
            raise ValueError("queue observation receipt collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("queue observation receipt collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("queue observation receipt collection fingerprint mismatch")
        _bounded(self)
        return self


class QueueObservationReceiptValidationInputV1(ContractModel):
    """Injected facts only; no store, live queue operation, worker, network, or I/O."""

    operator_id: OperatorId
    authority: QueueObservationReceiptAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: QueueObservationReceiptCreateV1
    v042_enqueue: OneShotLiveEnqueueV1
    v042_enqueue_status: OneShotLiveEnqueueStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> QueueObservationReceiptValidationInputV1:
        enqueue, status = self.v042_enqueue, self.v042_enqueue_status
        now = _instant(self.authority.request_received_at)
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or enqueue.operator_id != self.operator_id
            or status.operator_id != self.operator_id
        ):
            raise ValueError("queue observation receipt ownership mismatch")
        if (
            enqueue.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("queue observation receipt candidate linkage mismatch")
        if (
            self.create.enqueue_id != enqueue.enqueue_id
            or self.create.enqueue_record_fingerprint != enqueue.record_fingerprint
            or self.create.enqueue_status_fingerprint != status.status_fingerprint
            or self.create.enqueue_valid_until != enqueue.valid_until
            or status.enqueue_id != enqueue.enqueue_id
            or status.record_fingerprint != enqueue.record_fingerprint
            or enqueue.record_fingerprint != v042_record_fingerprint(enqueue)
            or status.status_fingerprint != v042_status_fingerprint(status)
        ):
            raise ValueError("v0.42 enqueue evidence fingerprint mismatch")
        if (
            status.lifecycle != "active"
            or status.outcome != "one_shot_live_enqueue_recorded"
            or status.blockers != V042_SUCCESS_BLOCKERS
            or not status.one_shot_live_enqueue_recorded
        ):
            raise ValueError("v0.42 enqueue is not active")
        if enqueue.outcome != "one_shot_live_enqueue_recorded" or not enqueue.one_shot_live_enqueue_recorded:
            raise ValueError("v0.42 enqueue is not recorded")
        item = enqueue.queue_item
        if (
            self.create.inert_queue_item_id != enqueue.enqueue_id
            or self.create.inert_queue_item_id != item.queue_item_id
            or self.create.inert_queue_item_fingerprint != item.item_fingerprint
            or item.item_kind != "inert_reference_only_queue_item"
            or not item.reference_only
        ):
            raise ValueError("inert queue item identity mismatch")
        if (
            self.create.queue_intake_reference_id != item.queue_intake_reference_id
            or self.create.queue_intake_reference_fingerprint
            != item.queue_intake_reference_fingerprint
            or self.create.queue_item_reference_id != item.queue_item_reference_id
            or self.create.queue_item_reference_fingerprint
            != item.queue_item_reference_fingerprint
            or self.create.observed_queue_identity != "abstract_installation_queue"
        ):
            raise ValueError("queue identity mismatch")
        if self.create.observed_item_identity != "inert_reference_only_queue_item":
            raise ValueError("item identity mismatch")
        if self.create.observation_state != "observed_recorded_not_consumable":
            raise ValueError("queue observation state is malformed")
        if self.create.receipt_disposition != "contract_eligible":
            raise ValueError("queue observation state is ambiguous")
        if item.payload_schema_defined or item.payload_constructed or item.payload_serialized:
            raise ValueError("executable payload is not supported")
        if item.payload_bytes != 0 or item.execution_allowed:
            raise ValueError("executable payload is not supported")
        if (
            self.authority.live_enqueue_allowed
            or self.authority.dequeue_allowed
            or self.authority.queue_polling_allowed
            or self.authority.worker_start_allowed
            or self.authority.execution_start_allowed
            or self.authority.process_execution_allowed
        ):
            raise ValueError("unsupported authority")
        starts = (
            _instant(enqueue.recorded_at),
            _instant(status.evaluated_at),
            _instant(item.recorded_at),
        )
        if any(value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS) for value in starts):
            raise ValueError("queue observation receipt evidence is stale or from the future")
        expiries = (_instant(enqueue.valid_until), _instant(item.valid_until))
        if any(now >= expiry for expiry in expiries):
            raise ValueError("queue observation receipt evidence is expired")
        return self


def receipt_fingerprint(value: EnqueueReceiptEvidenceV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:enqueue-receipt-evidence:v1", _without(value, "receipt_fingerprint"))


def observation_subject_fingerprint(value: QueueObservationV1 | dict[str, Any]) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint(
        "atlas:queue-observation-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "enqueue_id": raw["enqueue_id"],
            "receipt_fingerprint": raw["receipt_evidence"]["receipt_fingerprint"],
            "observation_state": raw["observation_state"],
        },
    )


def observation_fingerprint(value: QueueObservationV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint("atlas:queue-observation:v1", _without(value, "observation_fingerprint"))


def receipt_subject_fingerprint(value: QueueObservationReceiptV1 | dict[str, Any]) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint(
        "atlas:queue-observation-receipt-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "enqueue_record_fingerprint": raw["v042_enqueue"]["record_fingerprint"],
            "enqueue_status_fingerprint": raw["v042_enqueue_status"]["status_fingerprint"],
            "receipt_fingerprint": raw["receipt_evidence"]["receipt_fingerprint"],
            "observation_fingerprint": raw["queue_observation"]["observation_fingerprint"],
        },
    )


def receipt_record_fingerprint(value: QueueObservationReceiptV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-record:v1",
        _without(value, "receipt_record_fingerprint"),
    )


def lineage_fingerprint(
    enqueue: OneShotLiveEnqueueV1,
    status: OneShotLiveEnqueueStatusV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-v020-v042-chain:v1",
        {
            "one_shot_live_enqueue_lineage": enqueue.lineage,
            "one_shot_live_enqueue_id": enqueue.enqueue_id,
            "one_shot_live_enqueue_record_fingerprint": enqueue.record_fingerprint,
            "one_shot_live_enqueue_status_fingerprint": status.status_fingerprint,
            "one_shot_live_enqueue_item_fingerprint": enqueue.queue_item.item_fingerprint,
            "one_shot_live_enqueue_subject_fingerprint": enqueue.item_subject_fingerprint,
        },
    )


def evaluation_fingerprint(value: QueueObservationReceiptEvaluationV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:queue-observation-receipt-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: QueueObservationReceiptCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def reservation_fingerprint(
    value: QueueObservationReceiptSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def status_fingerprint(
    value: QueueObservationReceiptStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-status:v1",
        _without(value, "status_fingerprint"),
    )


def audit_fingerprint(
    value: QueueObservationReceiptAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: QueueObservationReceiptCollectionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:queue-observation-receipt-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def derived_uuid5(domain: str, value: Any) -> str:
    seed = fingerprint(domain, value).value
    return str(uuid.uuid5(_UUID5_NAMESPACE, f"{domain}:{seed}"))


def derived_observation_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5("atlas:queue-observation-id:v1", subject_fingerprint)


def build_receipt(
    validation: QueueObservationReceiptValidationInputV1,
) -> QueueObservationReceiptV1:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.v042_enqueue.valid_until),
        _instant(validation.v042_enqueue.queue_item.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    enqueue, status, item = (
        validation.v042_enqueue,
        validation.v042_enqueue_status,
        validation.v042_enqueue.queue_item,
    )
    evidence_raw = {
        "enqueue_id": enqueue.enqueue_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "enqueue_record_fingerprint": enqueue.record_fingerprint,
        "enqueue_status_fingerprint": status.status_fingerprint,
        "inert_queue_item_id": item.queue_item_id,
        "inert_queue_item_fingerprint": item.item_fingerprint,
        "queue_intake_reference_id": item.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": item.queue_intake_reference_fingerprint,
        "queue_item_reference_id": item.queue_item_reference_id,
        "queue_item_reference_fingerprint": item.queue_item_reference_fingerprint,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
    }
    evidence_seed = EnqueueReceiptEvidenceV1.model_construct(
        **evidence_raw,
        receipt_fingerprint=fingerprint("atlas:seed:v1", "receipt"),
    )
    evidence = EnqueueReceiptEvidenceV1.model_validate(
        {**evidence_raw, "receipt_fingerprint": receipt_fingerprint(evidence_seed)}
    )
    observation_raw = {
        "observation_id": derived_observation_id(
            fingerprint(
                "atlas:queue-observation-subject:v1",
                {
                    "operator_id": validation.operator_id,
                    "candidate_record_id": validation.candidate_record_id,
                    "enqueue_id": enqueue.enqueue_id,
                    "receipt_fingerprint": evidence.receipt_fingerprint,
                    "observation_state": "observed_recorded_not_consumable",
                },
            )
        ),
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "enqueue_id": enqueue.enqueue_id,
        "receipt_evidence": evidence,
        "observed_at": validation.authority.request_received_at,
        "valid_until": valid_until,
    }
    observation_seed = QueueObservationV1.model_construct(
        **observation_raw,
        observation_fingerprint=fingerprint("atlas:seed:v1", "observation"),
    )
    observation = QueueObservationV1.model_validate(
        {
            **observation_raw,
            "observation_fingerprint": observation_fingerprint(observation_seed),
        }
    )
    raw = {
        "receipt_id": observation.observation_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "v042_enqueue": enqueue,
        "v042_enqueue_status": status,
        "receipt_evidence": evidence,
        "queue_observation": observation,
        "lineage_fingerprint": lineage_fingerprint(enqueue, status),
    }
    subject_seed = QueueObservationReceiptV1.model_construct(
        **raw,
        subject_fingerprint=fingerprint("atlas:seed:v1", "subject"),
        receipt_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    subject = receipt_subject_fingerprint(subject_seed)
    record_seed = QueueObservationReceiptV1.model_construct(
        **raw,
        subject_fingerprint=subject,
        receipt_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    return QueueObservationReceiptV1.model_validate(
        {
            **raw,
            "subject_fingerprint": subject,
            "receipt_record_fingerprint": receipt_record_fingerprint(record_seed),
        }
    )


def build_reservations(
    validation: QueueObservationReceiptValidationInputV1,
    receipt: QueueObservationReceiptV1,
) -> tuple[
    QueueObservationReceiptIdempotencyReservationV1,
    QueueObservationReceiptSubjectReservationV1,
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
        "subject_fingerprint": receipt.subject_fingerprint,
        "receipt_id": receipt.receipt_id,
        "receipt_record_fingerprint": receipt.receipt_record_fingerprint,
        "reserved_at": validation.authority.request_received_at,
    }
    idempotency = QueueObservationReceiptIdempotencyReservationV1.model_validate(raw)
    seed = QueueObservationReceiptSubjectReservationV1.model_construct(
        **raw,
        reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
    )
    subject = QueueObservationReceiptSubjectReservationV1.model_validate(
        {**raw, "reservation_fingerprint": reservation_fingerprint(seed)}
    )
    return idempotency, subject


def derive_status(
    record: QueueObservationReceiptV1,
    *,
    evaluated_at: str,
) -> QueueObservationReceiptStatusV1:
    lifecycle = "active" if _instant(evaluated_at) < _instant(record.valid_until) else "expired"
    raw = {
        "receipt_id": record.receipt_id,
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "lifecycle": lifecycle,
        "disposition": record.disposition,
        "blockers": record.blockers,
        "evaluated_at": evaluated_at,
        "valid_until": record.valid_until,
        "receipt_record_fingerprint": record.receipt_record_fingerprint,
    }
    seed = QueueObservationReceiptStatusV1.model_construct(
        **raw,
        status_fingerprint=fingerprint("atlas:seed:v1", "status"),
    )
    return QueueObservationReceiptStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[QueueObservationReceiptV1, ...],
) -> QueueObservationReceiptCollectionV1:
    ordered = tuple(sorted(items, key=lambda item: (item.recorded_at, item.receipt_id)))
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": ordered,
        "count": len(ordered),
    }
    seed = QueueObservationReceiptCollectionV1.model_construct(
        **raw,
        collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
    )
    return QueueObservationReceiptCollectionV1.model_validate(
        {**raw, "collection_fingerprint": collection_fingerprint(seed)}
    )


def build_audit(
    record: QueueObservationReceiptV1,
    *,
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"],
    event: Literal[
        "queue_observation_receipt_recorded",
        "queue_observation_receipt_read",
        "queue_observation_receipt_indeterminate",
    ],
    correlation_fingerprint: FingerprintV1,
    occurred_at: str,
) -> QueueObservationReceiptAuditEvidenceV1:
    raw = {
        "event": event,
        "audit_id": derived_uuid5(
            "atlas:queue-observation-receipt-audit-id:v1",
            {
                "receipt_id": record.receipt_id,
                "receipt_record_fingerprint": record.receipt_record_fingerprint,
                "event": event,
                "outcome": outcome,
                "occurred_at": occurred_at,
            },
        ),
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "receipt_id": record.receipt_id,
        "occurred_at": occurred_at,
        "outcome": outcome,
        "correlation_fingerprint": correlation_fingerprint,
        "subject_fingerprint": record.subject_fingerprint,
        "receipt_record_fingerprint": record.receipt_record_fingerprint,
        "queue_observation_recorded": outcome == "recorded",
    }
    seed = QueueObservationReceiptAuditEvidenceV1.model_construct(
        **raw,
        audit_fingerprint=fingerprint("atlas:seed:v1", "audit"),
    )
    return QueueObservationReceiptAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_fingerprint(seed)}
    )


def evaluate_queue_observation_receipt(
    value: QueueObservationReceiptValidationInputV1 | dict[str, Any],
) -> QueueObservationReceiptEvaluationV1:
    now = _evaluation_time(value)
    try:
        validation = (
            value
            if isinstance(value, QueueObservationReceiptValidationInputV1)
            else QueueObservationReceiptValidationInputV1.model_validate(value)
        )
        blocker: BlockerV1 | None = None
        operator_id = validation.operator_id
        candidate_record_id = validation.candidate_record_id
        earliest_expiry = validation.v042_enqueue.valid_until
    except Exception as exc:  # noqa: BLE001 - closed redaction for malformed hostile input
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
        "disposition": "observation_recorded" if allowed else "blocked",
        "blockers": SUCCESS_BLOCKERS if allowed else (blocker,),
        "recognized_exact_v042_enqueue_count": 1 if allowed else 0,
        "recognized_contract_eligible_enqueue": allowed,
        "receipt_build_allowed": allowed,
    }
    seed = QueueObservationReceiptEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return QueueObservationReceiptEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def parse_create_json(raw: str | bytes) -> QueueObservationReceiptCreateV1:
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
    return QueueObservationReceiptCreateV1.model_validate(parsed)


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictContractError("duplicate key in create request")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise StrictContractError(f"unsupported JSON constant {value}")


def _evaluation_time(value: QueueObservationReceiptValidationInputV1 | dict[str, Any]) -> str:
    if isinstance(value, QueueObservationReceiptValidationInputV1):
        return value.authority.request_received_at
    authority = value.get("authority")
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
        if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{12}", raw):
            return raw
    return _BLOCKED_CANDIDATE_ID


def _classify_validation_error(message: str) -> BlockerV1:
    lowered = message.lower()
    if "home assistant" in lowered or "capability" in lowered:
        return "installation_capability_unsupported"
    if "ownership" in lowered:
        return "ownership_mismatch"
    if "permission" in lowered or "scope" in lowered:
        return "permission_scope_missing"
    if "stale" in lowered or "future" in lowered:
        return "evidence_stale"
    if "expired" in lowered:
        return "evidence_expired"
    if "not active" in lowered:
        return "v042_enqueue_not_active"
    if "not recorded" in lowered or "one_shot_live_enqueue_recorded" in lowered:
        return "v042_enqueue_not_recorded"
    if "queue identity" in lowered:
        return "queue_identity_mismatch"
    if "item identity" in lowered or "inert queue item" in lowered:
        return "item_identity_mismatch"
    if "malformed" in lowered:
        return "observation_malformed"
    if "ambiguous" in lowered:
        return "ambiguous_state"
    if "executable" in lowered or "payload" in lowered:
        return "executable_payload"
    if "fingerprint" in lowered:
        return "fingerprint_mismatch"
    if "authority" in lowered:
        return "unsupported_authority"
    if "linkage" in lowered or "binding" in lowered:
        return "linkage_mismatch"
    if "receipt" in lowered:
        return "receipt_evidence_invalid"
    return "evidence_not_found"
