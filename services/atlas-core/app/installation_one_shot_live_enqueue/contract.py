"""Closed immutable v0.42 one-shot live enqueue models and pure validation."""

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
from app.installation_live_enqueue_admission.contract import (
    ADMISSION_BLOCKERS as LIVE_ADMISSION_BLOCKERS,
)
from app.installation_live_enqueue_admission.contract import (
    LiveEnqueueAdmissionLinkageV1,
    LiveEnqueueAdmissionStatusV1,
    LiveEnqueueAdmissionV1,
    v020_v039_chain_fingerprint,
)
from app.installation_live_enqueue_admission.contract import (
    record_fingerprint as v041_record_fingerprint,
)
from app.installation_live_enqueue_admission.contract import (
    status_fingerprint as v041_status_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.runner_binding_plan.contract import RunnerBindingLimitsV1
from app.worker_intake_admission.contract import (
    ADMISSION_BLOCKERS as WORKER_INTAKE_BLOCKERS,
)
from app.worker_intake_admission.contract import (
    WorkerIntakeAdmissionStatusV1,
    WorkerIntakeAdmissionV1,
)
from app.worker_intake_admission.contract import (
    record_fingerprint as v040_record_fingerprint,
)
from app.worker_intake_admission.contract import (
    status_fingerprint as v040_status_fingerprint,
)
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
PERMISSION = "installation.execution.one_shot_live_enqueue.record"
READ_PERMISSION = "installation.execution.one_shot_live_enqueue.read"
SCOPE = "installation_one_shot_live_enqueue_only"
SAFE_MESSAGE = "one-shot live enqueue request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{12}"
)
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
    "live_enqueue_admission_not_active",
    "live_enqueue_admission_not_recorded",
    "queue_reservation_not_active",
    "worker_intake_admission_not_active",
    "worker_identity_ineligible",
    "worker_intake_reference_ineligible",
    "queue_intake_reference_ineligible",
    "queue_item_reference_ineligible",
    "inherited_limits_mismatch",
    "reservation_before_effect_failed",
    "permanent_subject_reserved",
    "idempotency_conflict",
    "append_indeterminate",
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
    "live_enqueue_admission_not_active",
    "live_enqueue_admission_not_recorded",
    "queue_reservation_not_active",
    "worker_intake_admission_not_active",
    "worker_identity_ineligible",
    "worker_intake_reference_ineligible",
    "queue_intake_reference_ineligible",
    "queue_item_reference_ineligible",
    "inherited_limits_mismatch",
    "reservation_before_effect_failed",
    "permanent_subject_reserved",
    "idempotency_conflict",
    "append_indeterminate",
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


def _bounded(value: BaseModel, maximum: int = MAX_MODEL_BYTES) -> None:
    if len(canonical_json(value)) > maximum:
        raise ValueError("contract envelope exceeds bound")


def _ordered(blockers: tuple[BlockerV1, ...]) -> None:
    if len(blockers) != len(set(blockers)):
        raise ValueError("one-shot live enqueue blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("one-shot live enqueue blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    reference_only: Literal[True] = True
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    dequeue_defined: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
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
    scheduler_allowed: Literal[False] = False
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


class OneShotLiveEnqueueCreateV1(ContractModel):
    schema: Literal["one-shot-live-enqueue-create-v1"] = (
        "one-shot-live-enqueue-create-v1"
    )
    live_enqueue_admission_id: CanonicalUuid5
    live_enqueue_admission_fingerprint: FingerprintV1
    live_enqueue_admission_status_fingerprint: FingerprintV1
    live_enqueue_admission_valid_until: UtcSecond
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE
    reference_only: Literal[True] = True
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    dequeue_allowed: Literal[False] = False
    queue_polling_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class OneShotLiveEnqueueAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-authority-context-v1"] = (
        "one-shot-live-enqueue-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class OneShotLiveEnqueueQueueItemV1(ContractModel):
    schema: Literal["one-shot-live-enqueue-item-v1"] = (
        "one-shot-live-enqueue-item-v1"
    )
    queue_item_id: CanonicalUuid5
    owner_operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    live_enqueue_admission_id: CanonicalUuid5
    live_enqueue_admission_fingerprint: FingerprintV1
    live_enqueue_admission_status_fingerprint: FingerprintV1
    worker_queue_reservation_id: CanonicalUuid4
    worker_queue_reservation_fingerprint: FingerprintV1
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    item_kind: Literal["inert_reference_only_queue_item"] = (
        "inert_reference_only_queue_item"
    )
    trust_domain: Literal["atlas-installation"] = "atlas-installation"
    scope: Literal[SCOPE] = SCOPE
    reference_only: Literal[True] = True
    item_state: Literal["recorded"] = "recorded"
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lineage_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    item_fingerprint: FingerprintV1
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    dequeue_defined: Literal[False] = False
    dequeued: Literal[False] = False
    queue_polled: Literal[False] = False
    queue_claimed: Literal[False] = False
    queue_leased: Literal[False] = False
    worker_contacted: Literal[False] = False
    worker_started: Literal[False] = False
    execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueQueueItemV1:
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("one-shot queue item expiry exceeds freshness bound")
        if self.queue_item_id != derived_queue_item_id(item_subject_fingerprint(self)):
            raise ValueError("one-shot queue item id mismatch")
        if self.item_fingerprint != item_fingerprint(self):
            raise ValueError("one-shot queue item fingerprint mismatch")
        _bounded(self)
        return self


class OneShotLiveEnqueueLineageV1(ContractModel):
    schema: Literal["one-shot-live-enqueue-lineage-v1"] = (
        "one-shot-live-enqueue-lineage-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    live_enqueue_admission_linkage: LiveEnqueueAdmissionLinkageV1
    v020_v040_chain_fingerprint: FingerprintV1
    v020_v041_chain_fingerprint: FingerprintV1
    readiness_review_fingerprint: FingerprintV1
    permission_grant_fingerprint: FingerprintV1
    execution_admission_id: CanonicalUuid4
    execution_admission_fingerprint: FingerprintV1
    runner_binding_plan_id: CanonicalUuid4
    runner_binding_plan_fingerprint: FingerprintV1
    worker_admission_stub_id: CanonicalUuid4
    worker_admission_stub_fingerprint: FingerprintV1
    queue_reservation_id: CanonicalUuid4
    queue_reservation_fingerprint: FingerprintV1
    queue_reservation_status_fingerprint: FingerprintV1
    queue_intake_reference_id: CanonicalUuid4
    queue_intake_reference_fingerprint: FingerprintV1
    queue_item_reference_id: CanonicalUuid5
    queue_item_reference_fingerprint: FingerprintV1
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_intake_admission_status_fingerprint: FingerprintV1
    worker_identity_id: CanonicalUuid4
    worker_identity_fingerprint: FingerprintV1
    worker_intake_reference_id: CanonicalUuid4
    worker_intake_reference_fingerprint: FingerprintV1
    live_enqueue_admission_id: CanonicalUuid5
    live_enqueue_admission_fingerprint: FingerprintV1
    live_enqueue_admission_status_fingerprint: FingerprintV1
    live_enqueue_admission_subject_fingerprint: FingerprintV1
    live_enqueue_admission_decision_fingerprint: FingerprintV1
    one_shot_queue_item_id: CanonicalUuid5
    one_shot_queue_item_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    lineage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueLineageV1:
        source = self.live_enqueue_admission_linkage
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
            or self.worker_admission_stub_id != source.worker_admission_stub_id
            or self.worker_admission_stub_fingerprint
            != source.worker_admission_stub_fingerprint
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
            or self.worker_intake_admission_id != source.worker_intake_admission_id
            or self.worker_intake_admission_fingerprint
            != source.worker_intake_admission_fingerprint
            or self.worker_intake_admission_status_fingerprint
            != source.worker_intake_admission_status_fingerprint
            or self.worker_identity_id != source.worker_identity_id
            or self.worker_identity_fingerprint != source.worker_identity_fingerprint
            or self.worker_intake_reference_id != source.worker_intake_reference_id
            or self.worker_intake_reference_fingerprint
            != source.worker_intake_reference_fingerprint
            or self.live_enqueue_admission_decision_fingerprint
            != source.live_enqueue_admission_decision_fingerprint
            or self.inherited_limits_fingerprint != source.inherited_limits_fingerprint
            or self.v020_v040_chain_fingerprint != v020_v040_chain_fingerprint(source)
            or self.v020_v041_chain_fingerprint
            != fingerprint(
                "atlas:one-shot-live-enqueue-v020-v041-chain:v1",
                {
                    "live_enqueue_admission_linkage": source,
                    "live_enqueue_admission_id": self.live_enqueue_admission_id,
                    "live_enqueue_admission_fingerprint": (
                        self.live_enqueue_admission_fingerprint
                    ),
                    "live_enqueue_admission_status_fingerprint": (
                        self.live_enqueue_admission_status_fingerprint
                    ),
                    "live_enqueue_admission_subject_fingerprint": (
                        self.live_enqueue_admission_subject_fingerprint
                    ),
                    "live_enqueue_admission_decision_fingerprint": (
                        self.live_enqueue_admission_decision_fingerprint
                    ),
                    "v020_v040_chain_fingerprint": self.v020_v040_chain_fingerprint,
                },
            )
        ):
            raise ValueError("embedded live enqueue admission lineage mismatch")
        if self.lineage_fingerprint != lineage_fingerprint(self):
            raise ValueError("one-shot live enqueue lineage fingerprint mismatch")
        _bounded(self)
        return self


class OneShotLiveEnqueueV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-v1"] = "one-shot-live-enqueue-v1"
    enqueue_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    lifecycle: Literal["active"] = "active"
    outcome: Literal["one_shot_live_enqueue_recorded"] = (
        "one_shot_live_enqueue_recorded"
    )
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    lineage: OneShotLiveEnqueueLineageV1
    queue_item: OneShotLiveEnqueueQueueItemV1
    inherited_limits: RunnerBindingLimitsV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    item_subject_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1
    one_shot_live_enqueue_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("one-shot live enqueue blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("one-shot live enqueue expiry exceeds freshness bound")
        link, item = self.lineage, self.queue_item
        if (
            self.enqueue_id != item.queue_item_id
            or self.enqueue_id != link.one_shot_queue_item_id
            or self.operator_id != link.operator_id
            or self.operator_id != item.owner_operator_id
            or self.candidate_record_id != link.candidate_record_id
            or self.candidate_record_id != item.candidate_record_id
            or self.valid_until != item.valid_until
            or self.recorded_at != item.recorded_at
            or self.inherited_limits.limits_fingerprint
            != link.inherited_limits_fingerprint
            or item.inherited_limits_fingerprint != link.inherited_limits_fingerprint
            or self.item_subject_fingerprint != item_subject_fingerprint(item)
            or item.item_fingerprint != link.one_shot_queue_item_fingerprint
            or item.lineage_fingerprint != link.lineage_fingerprint
        ):
            raise ValueError("one-shot live enqueue ownership or lineage mismatch")
        if self.record_fingerprint != record_fingerprint(self):
            raise ValueError("one-shot live enqueue record fingerprint mismatch")
        _bounded(self)
        return self


class OneShotLiveEnqueueStatusV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-status-v1"] = (
        "one-shot-live-enqueue-status-v1"
    )
    enqueue_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    lifecycle: Literal["active", "expired"]
    outcome: Literal[
        "one_shot_live_enqueue_recorded", "readiness_gated", "blocked", "indeterminate"
    ]
    blockers: tuple[BlockerV1, ...]
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    one_shot_live_enqueue_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueStatusV1:
        _ordered(self.blockers)
        if (
            self.outcome == "one_shot_live_enqueue_recorded"
            and (self.blockers != SUCCESS_BLOCKERS or not self.one_shot_live_enqueue_recorded)
        ):
            raise ValueError("recorded status blockers and authority are fixed")
        if self.outcome != "one_shot_live_enqueue_recorded" and self.one_shot_live_enqueue_recorded:
            raise ValueError("failed status cannot record one-shot live enqueue")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("one-shot live enqueue status fingerprint mismatch")
        _bounded(self)
        return self


class OneShotLiveEnqueueIdempotencyReservationV1(ContractModel):
    schema: Literal["one-shot-live-enqueue-idempotency-reservation-v1"] = (
        "one-shot-live-enqueue-idempotency-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    item_subject_fingerprint: FingerprintV1
    enqueue_id: CanonicalUuid5
    record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    permanent: Literal[True] = True


class OneShotLiveEnqueueSubjectReservationV1(ContractModel):
    schema: Literal["one-shot-live-enqueue-subject-reservation-v1"] = (
        "one-shot-live-enqueue-subject-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    item_subject_fingerprint: FingerprintV1
    enqueue_id: CanonicalUuid5
    record_fingerprint: FingerprintV1
    reserved_at: UtcSecond
    reservation_state: Literal["reserved"] = "reserved"
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueSubjectReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("one-shot live enqueue reservation fingerprint mismatch")
        return self


class OneShotLiveEnqueueAuditEvidenceV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-audit-v1"] = (
        "one-shot-live-enqueue-audit-v1"
    )
    event: Literal[
        "one_shot_live_enqueue_recorded",
        "one_shot_live_enqueue_read",
        "one_shot_live_enqueue_indeterminate",
    ]
    audit_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    enqueue_id: CanonicalUuid5 | None
    occurred_at: UtcSecond
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked", "indeterminate"]
    correlation_fingerprint: FingerprintV1
    item_subject_fingerprint: FingerprintV1 | None
    record_fingerprint: FingerprintV1 | None
    audit_fingerprint: FingerprintV1
    one_shot_live_enqueue_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueAuditEvidenceV1:
        if self.audit_fingerprint != audit_fingerprint(self):
            raise ValueError("one-shot live enqueue audit fingerprint mismatch")
        return self


class OneShotLiveEnqueueRedactedErrorV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-error-v1"] = (
        "one-shot-live-enqueue-error-v1"
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
        "live_enqueue_admission_not_active",
        "live_enqueue_admission_not_recorded",
        "queue_reservation_not_active",
        "worker_intake_admission_not_active",
        "worker_identity_ineligible",
        "worker_intake_reference_ineligible",
        "queue_intake_reference_ineligible",
        "queue_item_reference_ineligible",
        "inherited_limits_mismatch",
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
    one_shot_live_enqueue_recorded: Literal[False] = False


class OneShotLiveEnqueueResultV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-result-v1"] = (
        "one-shot-live-enqueue-result-v1"
    )
    ok: bool
    outcome: Literal["success", "failure", "indeterminate"]
    record: OneShotLiveEnqueueV1 | None
    status: OneShotLiveEnqueueStatusV1 | None
    error: OneShotLiveEnqueueRedactedErrorV1 | None
    correlation_fingerprint: FingerprintV1
    one_shot_live_enqueue_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueResultV1:
        if self.outcome == "success":
            good = (
                self.ok
                and self.record is not None
                and self.status is not None
                and self.error is None
                and self.one_shot_live_enqueue_recorded
            )
        else:
            good = (
                not self.ok
                and self.record is None
                and self.status is None
                and self.error is not None
                and not self.one_shot_live_enqueue_recorded
            )
        if not good:
            raise ValueError("result shape does not match outcome")
        if self.record is not None and self.status.enqueue_id != self.record.enqueue_id:
            raise ValueError("result status binding mismatch")
        _bounded(self, MAX_RESULT_BYTES)
        return self


class OneShotLiveEnqueueCollectionV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-collection-v1"] = (
        "one-shot-live-enqueue-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[OneShotLiveEnqueueV1, ...]
    count: int
    collection_fingerprint: FingerprintV1
    one_shot_live_enqueue_recorded: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueCollectionV1:
        if self.count != len(self.items) or self.count > MAX_COLLECTION_RECORDS:
            raise ValueError("one-shot live enqueue collection exceeds bound")
        ordered = tuple(sorted(self.items, key=lambda item: (item.recorded_at, item.enqueue_id)))
        if ordered != self.items:
            raise ValueError("one-shot live enqueue collection is not ordered")
        if any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("one-shot live enqueue collection ownership mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("one-shot live enqueue collection fingerprint mismatch")
        _bounded(self)
        return self


class OneShotLiveEnqueueEvaluationV1(ClosedAuthorityV1):
    schema: Literal["one-shot-live-enqueue-evaluation-v1"] = (
        "one-shot-live-enqueue-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    outcome: Literal[
        "one_shot_live_enqueue_recorded", "readiness_gated", "blocked", "indeterminate"
    ]
    blockers: tuple[BlockerV1, ...]
    recognized_active_v041_live_enqueue_count: int
    recognized_active_v041_live_enqueue_as_inert_evidence: bool
    queue_item_record_build_allowed: bool
    evaluation_fingerprint: FingerprintV1
    one_shot_live_enqueue_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueEvaluationV1:
        _ordered(self.blockers)
        allowed = self.outcome == "one_shot_live_enqueue_recorded"
        if self.recognized_active_v041_live_enqueue_count != (1 if allowed else 0):
            raise ValueError("active v0.41 live enqueue recognition count mismatch")
        if self.recognized_active_v041_live_enqueue_as_inert_evidence != allowed:
            raise ValueError("active v0.41 live enqueue recognition flag mismatch")
        if self.queue_item_record_build_allowed != allowed:
            raise ValueError("one-shot queue item build flag mismatch")
        if allowed and (
            self.blockers != SUCCESS_BLOCKERS or not self.one_shot_live_enqueue_recorded
        ):
            raise ValueError("recordable one-shot enqueue requires fixed blockers")
        if not allowed and self.one_shot_live_enqueue_recorded:
            raise ValueError("blocked one-shot enqueue cannot be recorded")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("one-shot live enqueue evaluation fingerprint mismatch")
        _bounded(self)
        return self


class OneShotLiveEnqueueValidationInputV1(ContractModel):
    """Injected P1 facts only; no store, queue, worker, Agent, network, or I/O."""

    operator_id: OperatorId
    authority: OneShotLiveEnqueueAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: OneShotLiveEnqueueCreateV1
    live_enqueue_admission: LiveEnqueueAdmissionV1
    live_enqueue_admission_status: LiveEnqueueAdmissionStatusV1
    worker_intake_admission: WorkerIntakeAdmissionV1
    worker_intake_admission_status: WorkerIntakeAdmissionStatusV1
    worker_queue_reservation: WorkerQueueReservationV1
    worker_queue_reservation_status: WorkerQueueReservationStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> OneShotLiveEnqueueValidationInputV1:
        live, live_status = self.live_enqueue_admission, self.live_enqueue_admission_status
        intake, intake_status = self.worker_intake_admission, self.worker_intake_admission_status
        queue, queue_status = self.worker_queue_reservation, self.worker_queue_reservation_status
        now = _instant(self.authority.request_received_at)
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or live.operator_id != self.operator_id
            or intake.operator_id != self.operator_id
            or queue.operator_id != self.operator_id
        ):
            raise ValueError("one-shot live enqueue ownership mismatch")
        if (
            live.candidate_record_id != self.candidate_record_id
            or intake.candidate_record_id != self.candidate_record_id
            or queue.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("one-shot live enqueue candidate linkage mismatch")
        if (
            self.create.live_enqueue_admission_id != live.admission_id
            or self.create.live_enqueue_admission_fingerprint != live.record_fingerprint
            or self.create.live_enqueue_admission_status_fingerprint
            != live_status.status_fingerprint
            or self.create.live_enqueue_admission_valid_until != live.valid_until
            or live.record_fingerprint != v041_record_fingerprint(live)
        ):
            raise ValueError("live enqueue admission binding mismatch")
        if (
            live_status.admission_id != live.admission_id
            or live_status.record_fingerprint != live.record_fingerprint
            or live_status.status_fingerprint != v041_status_fingerprint(live_status)
            or live_status.lifecycle != "active"
            or live_status.eligibility != "live_enqueue_admission_recorded"
            or live_status.blockers != LIVE_ADMISSION_BLOCKERS
        ):
            raise ValueError("live enqueue admission is not active")
        if live.eligibility != "live_enqueue_admission_recorded":
            raise ValueError("live enqueue admission is not recorded")
        if (
            intake_status.admission_id != intake.admission_id
            or intake_status.record_fingerprint != intake.record_fingerprint
            or intake_status.status_fingerprint != v040_status_fingerprint(intake_status)
            or intake_status.lifecycle != "active"
            or intake_status.eligibility != "worker_intake_admission_recorded"
            or intake_status.blockers != WORKER_INTAKE_BLOCKERS
            or intake.record_fingerprint != v040_record_fingerprint(intake)
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
        link = live.linkage
        if (
            intake.admission_id != link.worker_intake_admission_id
            or intake.record_fingerprint != link.worker_intake_admission_fingerprint
            or intake_status.status_fingerprint
            != link.worker_intake_admission_status_fingerprint
            or queue.reservation_id != link.queue_reservation_id
            or queue.record_fingerprint != link.queue_reservation_fingerprint
            or queue_status.status_fingerprint != link.queue_reservation_status_fingerprint
            or self.create.worker_intake_admission_id != link.worker_intake_admission_id
            or self.create.worker_intake_admission_fingerprint
            != link.worker_intake_admission_fingerprint
            or self.create.worker_queue_reservation_id != link.queue_reservation_id
            or self.create.worker_queue_reservation_fingerprint
            != link.queue_reservation_fingerprint
            or self.create.worker_identity_id != link.worker_identity_id
            or self.create.worker_identity_fingerprint != link.worker_identity_fingerprint
            or self.create.worker_intake_reference_id != link.worker_intake_reference_id
            or self.create.worker_intake_reference_fingerprint
            != link.worker_intake_reference_fingerprint
            or self.create.queue_intake_reference_id != link.queue_intake_reference_id
            or self.create.queue_intake_reference_fingerprint
            != link.queue_intake_reference_fingerprint
            or self.create.queue_item_reference_id != link.queue_item_reference_id
            or self.create.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
            or self.create.inherited_limits_fingerprint != link.inherited_limits_fingerprint
            or live.inherited_limits.limits_fingerprint != link.inherited_limits_fingerprint
            or intake.inherited_limits.limits_fingerprint != link.inherited_limits_fingerprint
            or queue.inherited_limits.limits_fingerprint != link.inherited_limits_fingerprint
        ):
            raise ValueError("one-shot v0.39-v0.41 linkage mismatch")
        if (
            queue.queue_intake_reference.reference_fingerprint
            != link.queue_intake_reference_fingerprint
            or queue.queue_item_reference.item_fingerprint
            != link.queue_item_reference_fingerprint
        ):
            raise ValueError("queue reference linkage mismatch")
        if intake.worker_identity.eligibility != "eligible_for_intake_admission_evidence_only":
            raise ValueError("worker identity ineligible")
        if intake.worker_intake_reference.eligibility != "eligible_for_intake_admission_evidence_only":
            raise ValueError("worker intake reference ineligible")
        if queue.queue_intake_reference.eligibility != "eligible_for_reservation_evidence_only":
            raise ValueError("queue intake reference ineligible")
        if queue.queue_item_reference.item_kind != "installation_evidence_reference_only":
            raise ValueError("queue item reference ineligible")
        starts = (
            _instant(live.recorded_at),
            _instant(live_status.evaluated_at),
            _instant(intake.recorded_at),
            _instant(intake_status.evaluated_at),
            _instant(queue.recorded_at),
            _instant(queue_status.observed_at),
            _instant(intake.worker_identity.valid_from),
            _instant(intake.worker_intake_reference.valid_from),
            _instant(queue.queue_intake_reference.valid_from),
            _instant(queue.queue_item_reference.created_at),
        )
        if any(value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS) for value in starts):
            raise ValueError("one-shot live enqueue evidence is stale or from the future")
        expiries = (
            _instant(live.valid_until),
            _instant(intake.valid_until),
            _instant(queue.valid_until),
            _instant(intake.worker_identity.valid_until),
            _instant(intake.worker_intake_reference.valid_until),
            _instant(queue.queue_intake_reference.valid_until),
        )
        if any(now >= expiry for expiry in expiries):
            raise ValueError("one-shot live enqueue evidence is expired")
        return self


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:one-shot-live-enqueue-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: OneShotLiveEnqueueCreateV1,
    request_received_at: str,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "request_received_at": request_received_at,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def v020_v040_chain_fingerprint(value: LiveEnqueueAdmissionLinkageV1) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-v020-v040-chain:v1",
        {
            "live_enqueue_admission_linkage": value,
            "worker_intake_admission_id": value.worker_intake_admission_id,
            "worker_intake_admission_fingerprint": value.worker_intake_admission_fingerprint,
            "v020_v039_chain_fingerprint": v020_v039_chain_fingerprint(
                value.worker_intake_admission_linkage
            ),
        },
    )


def v020_v041_chain_fingerprint(
    live: LiveEnqueueAdmissionV1,
    status: LiveEnqueueAdmissionStatusV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-v020-v041-chain:v1",
        {
            "live_enqueue_admission_linkage": live.linkage,
            "live_enqueue_admission_id": live.admission_id,
            "live_enqueue_admission_fingerprint": live.record_fingerprint,
            "live_enqueue_admission_status_fingerprint": status.status_fingerprint,
            "live_enqueue_admission_subject_fingerprint": live.subject_fingerprint,
            "live_enqueue_admission_decision_fingerprint": (
                live.admission_decision.decision_fingerprint
            ),
            "v020_v040_chain_fingerprint": v020_v040_chain_fingerprint(live.linkage),
        },
    )


def item_subject_fingerprint(
    value: OneShotLiveEnqueueQueueItemV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint(
        "atlas:one-shot-live-enqueue-item-subject:v1",
        {
            "owner_operator_id": raw["owner_operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "live_enqueue_admission_fingerprint": raw[
                "live_enqueue_admission_fingerprint"
            ],
            "live_enqueue_admission_status_fingerprint": raw[
                "live_enqueue_admission_status_fingerprint"
            ],
            "worker_queue_reservation_fingerprint": raw[
                "worker_queue_reservation_fingerprint"
            ],
            "worker_intake_admission_fingerprint": raw[
                "worker_intake_admission_fingerprint"
            ],
            "worker_identity_fingerprint": raw["worker_identity_fingerprint"],
            "worker_intake_reference_fingerprint": raw[
                "worker_intake_reference_fingerprint"
            ],
            "queue_intake_reference_fingerprint": raw[
                "queue_intake_reference_fingerprint"
            ],
            "queue_item_reference_fingerprint": raw[
                "queue_item_reference_fingerprint"
            ],
            "inherited_limits_fingerprint": raw["inherited_limits_fingerprint"],
        },
    )


def item_fingerprint(
    value: OneShotLiveEnqueueQueueItemV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _without(value, "item_fingerprint")
    raw.pop("lineage_fingerprint", None)
    return fingerprint(
        "atlas:one-shot-live-enqueue-item:v1",
        raw,
    )


def lineage_fingerprint(
    value: OneShotLiveEnqueueLineageV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _without(value, "lineage_fingerprint")
    raw.pop("one_shot_queue_item_fingerprint", None)
    return fingerprint(
        "atlas:one-shot-live-enqueue-lineage:v1",
        raw,
    )


def record_fingerprint(value: OneShotLiveEnqueueV1 | dict[str, Any]) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-record:v1",
        _without(value, "record_fingerprint"),
    )


def status_fingerprint(
    value: OneShotLiveEnqueueStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-status:v1",
        _without(value, "status_fingerprint"),
    )


def reservation_fingerprint(
    value: OneShotLiveEnqueueSubjectReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def audit_fingerprint(
    value: OneShotLiveEnqueueAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-audit:v1",
        _without(value, "audit_fingerprint"),
    )


def collection_fingerprint(
    value: OneShotLiveEnqueueCollectionV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-collection:v1",
        _without(value, "collection_fingerprint"),
    )


def evaluation_fingerprint(
    value: OneShotLiveEnqueueEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-live-enqueue-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def derived_uuid5(domain: str, value: Any) -> str:
    seed = fingerprint(domain, value).value
    return str(uuid.uuid5(_UUID5_NAMESPACE, f"{domain}:{seed}"))


def derived_queue_item_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5("atlas:one-shot-live-enqueue-item-id:v1", subject_fingerprint)


def build_queue_item(
    *,
    queue_item_id: str,
    operator_id: str,
    candidate_record_id: str,
    live_enqueue_admission: LiveEnqueueAdmissionV1,
    live_enqueue_admission_status: LiveEnqueueAdmissionStatusV1,
    lineage_fingerprint_value: FingerprintV1,
    recorded_at: str,
    valid_until: str,
) -> OneShotLiveEnqueueQueueItemV1:
    link = live_enqueue_admission.linkage
    raw = {
        "queue_item_id": queue_item_id,
        "owner_operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "live_enqueue_admission_id": live_enqueue_admission.admission_id,
        "live_enqueue_admission_fingerprint": live_enqueue_admission.record_fingerprint,
        "live_enqueue_admission_status_fingerprint": (
            live_enqueue_admission_status.status_fingerprint
        ),
        "worker_queue_reservation_id": link.queue_reservation_id,
        "worker_queue_reservation_fingerprint": link.queue_reservation_fingerprint,
        "worker_intake_admission_id": link.worker_intake_admission_id,
        "worker_intake_admission_fingerprint": link.worker_intake_admission_fingerprint,
        "worker_identity_id": link.worker_identity_id,
        "worker_identity_fingerprint": link.worker_identity_fingerprint,
        "worker_intake_reference_id": link.worker_intake_reference_id,
        "worker_intake_reference_fingerprint": link.worker_intake_reference_fingerprint,
        "queue_intake_reference_id": link.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": link.queue_intake_reference_fingerprint,
        "queue_item_reference_id": link.queue_item_reference_id,
        "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
        "recorded_at": recorded_at,
        "valid_until": valid_until,
        "lineage_fingerprint": lineage_fingerprint_value,
        "inherited_limits_fingerprint": link.inherited_limits_fingerprint,
    }
    seed = OneShotLiveEnqueueQueueItemV1.model_construct(
        **raw,
        item_fingerprint=fingerprint("atlas:seed:v1", "item"),
    )
    return OneShotLiveEnqueueQueueItemV1.model_validate(
        {**raw, "item_fingerprint": item_fingerprint(seed)}
    )


def build_lineage(
    live: LiveEnqueueAdmissionV1,
    status: LiveEnqueueAdmissionStatusV1,
    *,
    one_shot_queue_item_id: str,
    one_shot_queue_item_fingerprint: FingerprintV1,
    lineage_fingerprint_value: FingerprintV1 | None = None,
) -> OneShotLiveEnqueueLineageV1:
    source = live.linkage
    raw = {
        "operator_id": live.operator_id,
        "candidate_record_id": live.candidate_record_id,
        "live_enqueue_admission_linkage": source,
        "v020_v040_chain_fingerprint": v020_v040_chain_fingerprint(source),
        "v020_v041_chain_fingerprint": v020_v041_chain_fingerprint(live, status),
        "readiness_review_fingerprint": source.readiness_review_fingerprint,
        "permission_grant_fingerprint": source.permission_grant_fingerprint,
        "execution_admission_id": source.execution_admission_id,
        "execution_admission_fingerprint": source.execution_admission_fingerprint,
        "runner_binding_plan_id": source.runner_binding_plan_id,
        "runner_binding_plan_fingerprint": source.runner_binding_plan_fingerprint,
        "worker_admission_stub_id": source.worker_admission_stub_id,
        "worker_admission_stub_fingerprint": source.worker_admission_stub_fingerprint,
        "queue_reservation_id": source.queue_reservation_id,
        "queue_reservation_fingerprint": source.queue_reservation_fingerprint,
        "queue_reservation_status_fingerprint": (
            source.queue_reservation_status_fingerprint
        ),
        "queue_intake_reference_id": source.queue_intake_reference_id,
        "queue_intake_reference_fingerprint": source.queue_intake_reference_fingerprint,
        "queue_item_reference_id": source.queue_item_reference_id,
        "queue_item_reference_fingerprint": source.queue_item_reference_fingerprint,
        "worker_intake_admission_id": source.worker_intake_admission_id,
        "worker_intake_admission_fingerprint": (
            source.worker_intake_admission_fingerprint
        ),
        "worker_intake_admission_status_fingerprint": (
            source.worker_intake_admission_status_fingerprint
        ),
        "worker_identity_id": source.worker_identity_id,
        "worker_identity_fingerprint": source.worker_identity_fingerprint,
        "worker_intake_reference_id": source.worker_intake_reference_id,
        "worker_intake_reference_fingerprint": source.worker_intake_reference_fingerprint,
        "live_enqueue_admission_id": live.admission_id,
        "live_enqueue_admission_fingerprint": live.record_fingerprint,
        "live_enqueue_admission_status_fingerprint": status.status_fingerprint,
        "live_enqueue_admission_subject_fingerprint": live.subject_fingerprint,
        "live_enqueue_admission_decision_fingerprint": (
            source.live_enqueue_admission_decision_fingerprint
        ),
        "one_shot_queue_item_id": one_shot_queue_item_id,
        "one_shot_queue_item_fingerprint": one_shot_queue_item_fingerprint,
        "inherited_limits_fingerprint": source.inherited_limits_fingerprint,
    }
    if lineage_fingerprint_value is not None:
        return OneShotLiveEnqueueLineageV1.model_validate(
            {**raw, "lineage_fingerprint": lineage_fingerprint_value}
        )
    seed = OneShotLiveEnqueueLineageV1.model_construct(
        **raw,
        lineage_fingerprint=fingerprint("atlas:seed:v1", "lineage"),
    )
    return OneShotLiveEnqueueLineageV1.model_validate(
        {**raw, "lineage_fingerprint": lineage_fingerprint(seed)}
    )


def build_enqueue(
    validation: OneShotLiveEnqueueValidationInputV1,
) -> tuple[
    OneShotLiveEnqueueV1,
    OneShotLiveEnqueueIdempotencyReservationV1,
    OneShotLiveEnqueueSubjectReservationV1,
]:
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(validation.live_enqueue_admission.valid_until),
        _instant(validation.worker_intake_admission.valid_until),
        _instant(validation.worker_queue_reservation.valid_until),
        _instant(validation.worker_intake_admission.worker_identity.valid_until),
        _instant(validation.worker_intake_admission.worker_intake_reference.valid_until),
        _instant(validation.worker_queue_reservation.queue_intake_reference.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request = request_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        create=validation.create,
        request_received_at=validation.authority.request_received_at,
        idempotency_fingerprint=idem,
    )
    link = validation.live_enqueue_admission.linkage
    subject = item_subject_fingerprint(
        {
            "owner_operator_id": validation.operator_id,
            "candidate_record_id": validation.candidate_record_id,
            "live_enqueue_admission_fingerprint": (
                validation.live_enqueue_admission.record_fingerprint
            ),
            "live_enqueue_admission_status_fingerprint": (
                validation.live_enqueue_admission_status.status_fingerprint
            ),
            "worker_queue_reservation_fingerprint": link.queue_reservation_fingerprint,
            "worker_intake_admission_fingerprint": (
                link.worker_intake_admission_fingerprint
            ),
            "worker_identity_fingerprint": link.worker_identity_fingerprint,
            "worker_intake_reference_fingerprint": (
                link.worker_intake_reference_fingerprint
            ),
            "queue_intake_reference_fingerprint": (
                link.queue_intake_reference_fingerprint
            ),
            "queue_item_reference_fingerprint": link.queue_item_reference_fingerprint,
            "inherited_limits_fingerprint": link.inherited_limits_fingerprint,
        }
    )
    enqueue_id = derived_queue_item_id(subject)
    seed_lineage = build_lineage(
        validation.live_enqueue_admission,
        validation.live_enqueue_admission_status,
        one_shot_queue_item_id=enqueue_id,
        one_shot_queue_item_fingerprint=fingerprint("atlas:seed:v1", "item"),
    )
    item = build_queue_item(
        queue_item_id=enqueue_id,
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        live_enqueue_admission=validation.live_enqueue_admission,
        live_enqueue_admission_status=validation.live_enqueue_admission_status,
        lineage_fingerprint_value=seed_lineage.lineage_fingerprint,
        recorded_at=validation.authority.request_received_at,
        valid_until=valid_until,
    )
    lineage = build_lineage(
        validation.live_enqueue_admission,
        validation.live_enqueue_admission_status,
        one_shot_queue_item_id=enqueue_id,
        one_shot_queue_item_fingerprint=item.item_fingerprint,
    )
    item = build_queue_item(
        queue_item_id=enqueue_id,
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        live_enqueue_admission=validation.live_enqueue_admission,
        live_enqueue_admission_status=validation.live_enqueue_admission_status,
        lineage_fingerprint_value=lineage.lineage_fingerprint,
        recorded_at=validation.authority.request_received_at,
        valid_until=valid_until,
    )
    lineage = build_lineage(
        validation.live_enqueue_admission,
        validation.live_enqueue_admission_status,
        one_shot_queue_item_id=enqueue_id,
        one_shot_queue_item_fingerprint=item.item_fingerprint,
    )
    raw = {
        "enqueue_id": enqueue_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "lineage": lineage,
        "queue_item": item,
        "inherited_limits": validation.live_enqueue_admission.inherited_limits,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
        "item_subject_fingerprint": subject,
    }
    seed = OneShotLiveEnqueueV1.model_construct(
        **raw,
        record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    record = OneShotLiveEnqueueV1.model_validate(
        {**raw, "record_fingerprint": record_fingerprint(seed)}
    )
    common = {
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
        "item_subject_fingerprint": subject,
        "enqueue_id": record.enqueue_id,
        "record_fingerprint": record.record_fingerprint,
        "reserved_at": record.recorded_at,
    }
    idempotency = OneShotLiveEnqueueIdempotencyReservationV1(**common)
    reservation_seed = OneShotLiveEnqueueSubjectReservationV1.model_construct(
        **common,
        reservation_fingerprint=fingerprint("atlas:seed:v1", "reservation"),
    )
    permanent = OneShotLiveEnqueueSubjectReservationV1.model_validate(
        {**common, "reservation_fingerprint": reservation_fingerprint(reservation_seed)}
    )
    return record, idempotency, permanent


def derive_status(
    record: OneShotLiveEnqueueV1,
    *,
    evaluated_at: str,
) -> OneShotLiveEnqueueStatusV1:
    raw = {
        "enqueue_id": record.enqueue_id,
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "lifecycle": (
            "active" if _instant(evaluated_at) < _instant(record.valid_until) else "expired"
        ),
        "outcome": record.outcome,
        "blockers": record.blockers,
        "evaluated_at": evaluated_at,
        "valid_until": record.valid_until,
        "record_fingerprint": record.record_fingerprint,
        "one_shot_live_enqueue_recorded": True,
    }
    seed = OneShotLiveEnqueueStatusV1.model_construct(
        **raw,
        status_fingerprint=fingerprint("atlas:seed:v1", "status"),
    )
    return OneShotLiveEnqueueStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def build_collection(
    *,
    operator_id: str,
    candidate_record_id: str,
    items: tuple[OneShotLiveEnqueueV1, ...],
) -> OneShotLiveEnqueueCollectionV1:
    ordered = tuple(sorted(items, key=lambda item: (item.recorded_at, item.enqueue_id)))
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "items": ordered,
        "count": len(ordered),
    }
    seed = OneShotLiveEnqueueCollectionV1.model_construct(
        **raw,
        collection_fingerprint=fingerprint("atlas:seed:v1", "collection"),
    )
    return OneShotLiveEnqueueCollectionV1.model_validate(
        {**raw, "collection_fingerprint": collection_fingerprint(seed)}
    )


def evaluate_one_shot_live_enqueue(
    value: OneShotLiveEnqueueValidationInputV1 | dict[str, Any],
) -> OneShotLiveEnqueueEvaluationV1:
    try:
        validation = (
            value
            if isinstance(value, OneShotLiveEnqueueValidationInputV1)
            else OneShotLiveEnqueueValidationInputV1.model_validate(value)
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    earliest = min(
        _instant(validation.live_enqueue_admission.valid_until),
        _instant(validation.worker_intake_admission.valid_until),
        _instant(validation.worker_queue_reservation.valid_until),
        _instant(validation.worker_intake_admission.worker_identity.valid_until),
        _instant(validation.worker_intake_admission.worker_intake_reference.valid_until),
        _instant(validation.worker_queue_reservation.queue_intake_reference.valid_until),
    )
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest.strftime("%Y-%m-%dT%H:%M:%SZ"),
        outcome="one_shot_live_enqueue_recorded",
        blockers=SUCCESS_BLOCKERS,
    )


def _evaluation(
    *,
    operator_id: str,
    candidate_record_id: str,
    evaluated_at: str,
    earliest_expiry: str | None,
    outcome: Literal[
        "one_shot_live_enqueue_recorded", "readiness_gated", "blocked", "indeterminate"
    ],
    blockers: tuple[BlockerV1, ...],
) -> OneShotLiveEnqueueEvaluationV1:
    recorded = outcome == "one_shot_live_enqueue_recorded"
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "outcome": outcome,
        "blockers": blockers,
        "recognized_active_v041_live_enqueue_count": 1 if recorded else 0,
        "recognized_active_v041_live_enqueue_as_inert_evidence": recorded,
        "queue_item_record_build_allowed": recorded,
        "one_shot_live_enqueue_recorded": recorded,
    }
    seed = OneShotLiveEnqueueEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return OneShotLiveEnqueueEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: OneShotLiveEnqueueValidationInputV1 | dict[str, Any],
    reason: str,
) -> OneShotLiveEnqueueEvaluationV1:
    raw = value.model_dump(mode="python") if isinstance(value, BaseModel) else dict(value)
    authority = raw.get("authority") if isinstance(raw.get("authority"), dict) else {}
    operator_id = _safe_operator_id(
        raw.get("operator_id") or authority.get("authenticated_operator_id")
    )
    candidate_record_id = _safe_candidate_id(raw.get("candidate_record_id"))
    evaluated_at = _safe_utc_second(
        authority.get("request_received_at") or "1970-01-01T00:00:00Z"
    )
    blocker = _blocker_from_raw(raw) or _blocker_from_reason(reason)
    outcome: Literal["readiness_gated", "blocked", "indeterminate"] = (
        "readiness_gated"
        if blocker
        in {
            "evidence_stale",
            "evidence_expired",
            "live_enqueue_admission_not_active",
            "live_enqueue_admission_not_recorded",
            "worker_intake_admission_not_active",
            "queue_reservation_not_active",
            "worker_identity_ineligible",
            "worker_intake_reference_ineligible",
            "queue_intake_reference_ineligible",
            "queue_item_reference_ineligible",
        }
        else "blocked"
    )
    return _evaluation(
        operator_id=operator_id,
        candidate_record_id=candidate_record_id,
        evaluated_at=evaluated_at,
        earliest_expiry=None,
        outcome=outcome,
        blockers=(blocker,),
    )


def _blocker_from_raw(raw: dict[str, Any]) -> BlockerV1 | None:
    live_status = raw.get("live_enqueue_admission_status")
    if isinstance(live_status, dict) and live_status.get("lifecycle") not in {
        None,
        "active",
    }:
        return "live_enqueue_admission_not_active"
    intake_status = raw.get("worker_intake_admission_status")
    if isinstance(intake_status, dict) and intake_status.get("lifecycle") not in {
        None,
        "active",
    }:
        return "worker_intake_admission_not_active"
    queue_status = raw.get("worker_queue_reservation_status")
    if isinstance(queue_status, dict) and queue_status.get("lifecycle") not in {
        None,
        "active",
    }:
        return "queue_reservation_not_active"
    return None


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
    if "live enqueue admission is not active" in lowered:
        return "live_enqueue_admission_not_active"
    if "live enqueue admission is not recorded" in lowered:
        return "live_enqueue_admission_not_recorded"
    if "worker intake admission is not active" in lowered:
        return "worker_intake_admission_not_active"
    if "queue reservation" in lowered:
        return "queue_reservation_not_active"
    if "queue intake reference" in lowered:
        return "queue_intake_reference_ineligible"
    if "queue item reference" in lowered:
        return "queue_item_reference_ineligible"
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


def parse_create_json(payload: bytes | str) -> OneShotLiveEnqueueCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("one-shot live enqueue request exceeds 16 KiB")
    try:
        decoded = raw.decode("utf-8")
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        parsed = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
        return OneShotLiveEnqueueCreateV1.model_validate(parsed)
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid one-shot live enqueue request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")
