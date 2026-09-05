"""Closed immutable v0.45 one-shot controlled dequeue models.

This module is pure contract validation. It has no store, queue I/O, route,
polling, claim, lease, ack, worker, Agent, execution, installation,
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

from app.controlled_dequeue_admission.contract import (
    SUCCESS_BLOCKERS as V044_SUCCESS_BLOCKERS,
)
from app.controlled_dequeue_admission.contract import (
    ControlledDequeueAdmissionStatusV1,
    ControlledDequeueAdmissionV1,
)
from app.controlled_dequeue_admission.contract import (
    admission_record_fingerprint as v044_admission_record_fingerprint,
)
from app.controlled_dequeue_admission.contract import (
    status_fingerprint as v044_status_fingerprint,
)
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
MAX_MODEL_BYTES = 224 * 1024
MAX_COLLECTION_RECORDS = 16
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.one_shot_controlled_dequeue.record"
READ_PERMISSION = "installation.execution.one_shot_controlled_dequeue.read"
SCOPE = "installation_one_shot_controlled_dequeue_only"
SAFE_MESSAGE = "one-shot controlled dequeue request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UUID5_NAMESPACE = uuid.UUID("78ce5caf-44b9-5e34-b215-56f27e2a06c3")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v044_admission_not_active",
    "v044_admission_not_recorded",
    "v044_admission_not_eligible",
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
    "dequeue_adapter_unavailable",
    "dequeue_receipt_mismatch",
    "reservation_before_effect_failed",
    "permanent_subject_reserved",
    "idempotency_conflict",
    "append_indeterminate",
    "dequeue_indeterminate",
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
    "v044_admission_not_active",
    "v044_admission_not_recorded",
    "v044_admission_not_eligible",
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
    "dequeue_adapter_unavailable",
    "dequeue_receipt_mismatch",
    "reservation_before_effect_failed",
    "permanent_subject_reserved",
    "idempotency_conflict",
    "append_indeterminate",
    "dequeue_indeterminate",
    "queue_polling_not_defined",
    "queue_claim_not_defined",
    "queue_lease_not_defined",
    "queue_ack_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
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
        raise ValueError("one-shot controlled dequeue blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("one-shot controlled dequeue blockers are not ordered")


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


class OneShotControlledDequeueCreateV1(ClosedAuthorityV1):
    schema: Literal["one-shot-controlled-dequeue-create-v1"] = (
        "one-shot-controlled-dequeue-create-v1"
    )
    controlled_dequeue_admission_id: CanonicalUuid5
    controlled_dequeue_admission_fingerprint: FingerprintV1
    controlled_dequeue_admission_status_fingerprint: FingerprintV1
    controlled_dequeue_admission_valid_until: UtcSecond
    queue_observation_receipt_id: CanonicalUuid5
    queue_observation_receipt_fingerprint: FingerprintV1
    queue_observation_receipt_status_fingerprint: FingerprintV1
    enqueue_id: CanonicalUuid5
    inert_queue_item_id: CanonicalUuid5
    inert_queue_item_fingerprint: FingerprintV1
    queue_identity_fingerprint: FingerprintV1
    item_identity_fingerprint: FingerprintV1
    lineage_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    queue_identity: Literal["abstract_installation_queue"] = "abstract_installation_queue"
    item_identity: Literal["inert_reference_only_queue_item"] = (
        "inert_reference_only_queue_item"
    )
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def exact(self) -> OneShotControlledDequeueCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        if self.enqueue_id != self.inert_queue_item_id:
            raise ValueError("one-shot controlled dequeue item identity mismatch")
        return self


class OneShotControlledDequeueAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["one-shot-controlled-dequeue-authority-context-v1"] = (
        "one-shot-controlled-dequeue-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class BoundedDequeueReceiptEvidenceV1(ClosedAuthorityV1):
    schema: Literal["bounded-one-shot-controlled-dequeue-receipt-v1"] = (
        "bounded-one-shot-controlled-dequeue-receipt-v1"
    )
    outcome: Literal["success", "failure", "indeterminate"]
    disposition: Literal[
        "exact_inert_item_dequeued",
        "exact_inert_item_not_dequeued",
        "dequeue_completion_indeterminate",
    ]
    exact_admitted_item_only: Literal[True] = True
    adapter_receipt_redacted: Literal[True] = True
    adapter_receipt_fingerprint: FingerprintV1
    queue_identity_fingerprint: FingerprintV1
    item_identity_fingerprint: FingerprintV1
    receipt_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> BoundedDequeueReceiptEvidenceV1:
        expected = {
            "success": "exact_inert_item_dequeued",
            "failure": "exact_inert_item_not_dequeued",
            "indeterminate": "dequeue_completion_indeterminate",
        }[self.outcome]
        if self.disposition != expected:
            raise ValueError("one-shot controlled dequeue disposition mismatch")
        if self.receipt_fingerprint != bounded_receipt_fingerprint(self):
            raise ValueError("one-shot controlled dequeue receipt fingerprint mismatch")
        return self


class OneShotControlledDequeueReceiptV1(ClosedAuthorityV1):
    schema: Literal["one-shot-controlled-dequeue-v1"] = (
        "one-shot-controlled-dequeue-v1"
    )
    dequeue_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    dequeue_state: Literal["one_shot_controlled_dequeue_recorded"] = (
        "one_shot_controlled_dequeue_recorded"
    )
    outcome: Literal["success", "failure", "indeterminate"]
    disposition: Literal[
        "exact_inert_item_dequeued",
        "exact_inert_item_not_dequeued",
        "dequeue_completion_indeterminate",
    ]
    blockers: tuple[BlockerV1, ...] = SUCCESS_BLOCKERS
    controlled_dequeue_admission: ControlledDequeueAdmissionV1
    controlled_dequeue_admission_status: ControlledDequeueAdmissionStatusV1
    inherited_limits: RunnerBindingLimitsV1
    bounded_receipt: BoundedDequeueReceiptEvidenceV1
    queue_identity_fingerprint: FingerprintV1
    item_identity_fingerprint: FingerprintV1
    lineage_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    dequeue_record_fingerprint: FingerprintV1
    one_shot_controlled_dequeue_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> OneShotControlledDequeueReceiptV1:
        if self.blockers != SUCCESS_BLOCKERS:
            raise ValueError("one-shot controlled dequeue blockers must remain fixed")
        expected = {
            "success": "exact_inert_item_dequeued",
            "failure": "exact_inert_item_not_dequeued",
            "indeterminate": "dequeue_completion_indeterminate",
        }[self.outcome]
        if self.disposition != expected or self.bounded_receipt.outcome != self.outcome:
            raise ValueError("one-shot controlled dequeue outcome mismatch")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("one-shot controlled dequeue expiry exceeds freshness bound")
        admission = self.controlled_dequeue_admission
        status = self.controlled_dequeue_admission_status
        receipt = admission.queue_observation_receipt
        item = receipt.v042_enqueue.queue_item
        if (
            self.operator_id != admission.operator_id
            or self.operator_id != status.operator_id
            or self.candidate_record_id != admission.candidate_record_id
            or self.candidate_record_id != status.candidate_record_id
            or status.admission_id != admission.admission_id
            or status.admission_record_fingerprint
            != admission.admission_record_fingerprint
            or self.valid_until > admission.valid_until
            or self.inherited_limits.limits_fingerprint
            != admission.inherited_limits.limits_fingerprint
            or item.inherited_limits_fingerprint
            != admission.inherited_limits.limits_fingerprint
        ):
            raise ValueError("one-shot controlled dequeue ownership or linkage mismatch")
        if (
            self.queue_identity_fingerprint != queue_identity_fingerprint(admission, status)
            or self.item_identity_fingerprint != item_identity_fingerprint(admission)
            or self.lineage_fingerprint != lineage_fingerprint(admission, status)
            or self.bounded_receipt.queue_identity_fingerprint
            != self.queue_identity_fingerprint
            or self.bounded_receipt.item_identity_fingerprint != self.item_identity_fingerprint
        ):
            raise ValueError("one-shot controlled dequeue fingerprint linkage mismatch")
        if self.subject_fingerprint != dequeue_subject_fingerprint(self):
            raise ValueError("one-shot controlled dequeue subject fingerprint mismatch")
        if self.dequeue_id != derived_dequeue_id(self.subject_fingerprint):
            raise ValueError("one-shot controlled dequeue id mismatch")
        if self.dequeue_record_fingerprint != dequeue_record_fingerprint(self):
            raise ValueError("one-shot controlled dequeue record fingerprint mismatch")
        _bounded(self)
        return self


class OneShotControlledDequeueEvaluationV1(ClosedAuthorityV1):
    schema: Literal["one-shot-controlled-dequeue-evaluation-v1"] = (
        "one-shot-controlled-dequeue-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    dequeue_state: Literal["readiness_gated", "blocked", "indeterminate"]
    outcome: Literal["success", "failure", "indeterminate"]
    disposition: Literal[
        "exact_inert_item_dequeued",
        "exact_inert_item_not_dequeued",
        "dequeue_completion_indeterminate",
    ]
    blockers: tuple[BlockerV1, ...]
    recognized_active_v044_admission_count: int
    recognized_exact_v042_inert_queue_item_count: int
    one_shot_controlled_dequeue_build_allowed: bool
    evaluation_fingerprint: FingerprintV1
    one_shot_controlled_dequeue_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> OneShotControlledDequeueEvaluationV1:
        _ordered(self.blockers)
        allowed = self.dequeue_state == "readiness_gated"
        if self.recognized_active_v044_admission_count != (1 if allowed else 0):
            raise ValueError("v0.44 admission recognition count mismatch")
        if self.recognized_exact_v042_inert_queue_item_count != (1 if allowed else 0):
            raise ValueError("v0.42 inert item recognition count mismatch")
        if self.one_shot_controlled_dequeue_build_allowed != allowed:
            raise ValueError("one-shot controlled dequeue build flag mismatch")
        if allowed and (
            self.blockers != SUCCESS_BLOCKERS
            or self.outcome != "success"
            or self.disposition != "exact_inert_item_dequeued"
            or not self.one_shot_controlled_dequeue_recorded
        ):
            raise ValueError("recordable one-shot controlled dequeue shape mismatch")
        if not allowed and self.one_shot_controlled_dequeue_recorded:
            raise ValueError("blocked one-shot controlled dequeue shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("one-shot controlled dequeue evaluation fingerprint mismatch")
        _bounded(self)
        return self


class OneShotControlledDequeueValidationInputV1(ContractModel):
    """Injected facts only; no queue, worker, Agent, network, store, or I/O."""

    operator_id: OperatorId
    authority: OneShotControlledDequeueAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: OneShotControlledDequeueCreateV1
    controlled_dequeue_admission: ControlledDequeueAdmissionV1
    controlled_dequeue_admission_status: ControlledDequeueAdmissionStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> OneShotControlledDequeueValidationInputV1:
        admission = self.controlled_dequeue_admission
        status = self.controlled_dequeue_admission_status
        receipt = admission.queue_observation_receipt
        receipt_status = admission.queue_observation_receipt_status
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
            or admission.operator_id != self.operator_id
            or status.operator_id != self.operator_id
            or receipt.operator_id != self.operator_id
            or receipt_status.operator_id != self.operator_id
            or enqueue.operator_id != self.operator_id
            or evidence.operator_id != self.operator_id
            or observation.operator_id != self.operator_id
        ):
            raise ValueError("one-shot controlled dequeue ownership mismatch")
        if (
            admission.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
            or receipt.candidate_record_id != self.candidate_record_id
            or receipt_status.candidate_record_id != self.candidate_record_id
            or enqueue.candidate_record_id != self.candidate_record_id
            or evidence.candidate_record_id != self.candidate_record_id
            or observation.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("one-shot controlled dequeue candidate linkage mismatch")
        if (
            self.create.controlled_dequeue_admission_id != admission.admission_id
            or self.create.controlled_dequeue_admission_valid_until
            != admission.valid_until
            or status.admission_id != admission.admission_id
        ):
            raise ValueError("v0.44 admission linkage mismatch")
        if (
            self.create.controlled_dequeue_admission_fingerprint
            != admission.admission_record_fingerprint
            or self.create.controlled_dequeue_admission_status_fingerprint
            != status.status_fingerprint
            or status.admission_record_fingerprint != admission.admission_record_fingerprint
        ):
            raise ValueError("v0.44 admission fingerprint mismatch")
        if (
            self.create.queue_observation_receipt_id != receipt.receipt_id
            or receipt_status.receipt_id != receipt.receipt_id
        ):
            raise ValueError("v0.43 observation receipt linkage mismatch")
        if (
            self.create.queue_observation_receipt_fingerprint
            != receipt.receipt_record_fingerprint
            or self.create.queue_observation_receipt_status_fingerprint
            != receipt_status.status_fingerprint
            or receipt_status.receipt_record_fingerprint != receipt.receipt_record_fingerprint
        ):
            raise ValueError("v0.43 observation receipt fingerprint mismatch")
        if (
            admission.admission_record_fingerprint
            != v044_admission_record_fingerprint(admission)
            or status.status_fingerprint != v044_status_fingerprint(status)
            or receipt.receipt_record_fingerprint != v043_receipt_record_fingerprint(receipt)
            or receipt_status.status_fingerprint != v043_status_fingerprint(receipt_status)
            or receipt.lineage_fingerprint
            != v043_lineage_fingerprint(enqueue, enqueue_status)
            or evidence.receipt_fingerprint != v043_receipt_fingerprint(evidence)
            or observation.observation_fingerprint
            != v043_observation_fingerprint(observation)
            or enqueue.record_fingerprint != v042_record_fingerprint(enqueue)
            or enqueue_status.status_fingerprint
            != v042_status_fingerprint(enqueue_status)
        ):
            raise ValueError("one-shot controlled dequeue prerequisite fingerprint mismatch")
        if status.lifecycle != "active":
            raise ValueError("v0.44 admission is not active")
        if (
            admission.lifecycle != "active"
            or admission.disposition != "controlled_dequeue_admission_recorded"
            or not admission.controlled_dequeue_admission_recorded
            or status.admission_state != "readiness_gated"
            or not status.controlled_dequeue_admission_recorded
            or admission.blockers != V044_SUCCESS_BLOCKERS
            or status.blockers != V044_SUCCESS_BLOCKERS
        ):
            raise ValueError("v0.44 admission is not recorded")
        if admission.eligibility != "eligible_for_later_dequeue_consideration":
            raise ValueError("v0.44 admission is not eligible")
        if receipt_status.lifecycle != "active":
            raise ValueError("v0.43 observation is not active")
        if (
            receipt.lifecycle != "active"
            or receipt_status.disposition != "observation_recorded"
            or not receipt_status.queue_observation_recorded
            or receipt.disposition != "observation_recorded"
            or receipt.blockers != V043_SUCCESS_BLOCKERS
            or receipt_status.blockers != V043_SUCCESS_BLOCKERS
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
            self.create.queue_identity_fingerprint
            != queue_identity_fingerprint(admission, status)
        ):
            raise ValueError("queue identity mismatch")
        if self.create.item_identity_fingerprint != item_identity_fingerprint(admission):
            raise ValueError("item identity mismatch")
        if self.create.lineage_fingerprint != lineage_fingerprint(admission, status):
            raise ValueError("lineage fingerprint mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != admission.inherited_limits.limits_fingerprint
            or item.inherited_limits_fingerprint
            != admission.inherited_limits.limits_fingerprint
            or admission.inherited_limits.limits_fingerprint
            != enqueue.inherited_limits.limits_fingerprint
        ):
            raise ValueError("inherited limits mismatch")
        if (
            item.payload_schema_defined
            or item.payload_constructed
            or item.payload_serialized
            or item.payload_bytes != 0
            or item.dequeued
            or item.queue_polled
            or item.queue_claimed
            or item.queue_leased
            or item.worker_contacted
            or item.worker_started
            or item.execution_allowed
            or evidence.executable
        ):
            raise ValueError("executable payload or previously dequeued item")
        if (
            self.authority.dequeue_allowed
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
            _instant(admission.recorded_at),
            _instant(status.evaluated_at),
            _instant(receipt.recorded_at),
            _instant(receipt_status.evaluated_at),
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
            raise ValueError("one-shot controlled dequeue evidence is stale")
        expiries = (
            _instant(admission.valid_until),
            _instant(status.valid_until),
            _instant(receipt.valid_until),
            _instant(receipt_status.valid_until),
            _instant(observation.valid_until),
            _instant(evidence.valid_until),
            _instant(enqueue.valid_until),
            _instant(item.valid_until),
        )
        if any(now >= expiry for expiry in expiries):
            raise ValueError("one-shot controlled dequeue evidence is expired")
        return self


def queue_identity_fingerprint(
    admission: ControlledDequeueAdmissionV1 | dict[str, Any],
    status: ControlledDequeueAdmissionStatusV1 | dict[str, Any],
) -> FingerprintV1:
    raw = admission.model_dump(mode="json") if isinstance(admission, BaseModel) else dict(admission)
    status_raw = status.model_dump(mode="json") if isinstance(status, BaseModel) else dict(status)
    receipt = raw["queue_observation_receipt"]
    receipt_status = raw["queue_observation_receipt_status"]
    enqueue = receipt["v042_enqueue"]
    enqueue_status = receipt["v042_enqueue_status"]
    item = enqueue["queue_item"]
    observation = receipt["queue_observation"]
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-queue-identity:v1",
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
            "receipt_id": receipt["receipt_id"],
            "receipt_record_fingerprint": receipt["receipt_record_fingerprint"],
            "receipt_status_fingerprint": receipt_status["status_fingerprint"],
            "observation_fingerprint": observation["observation_fingerprint"],
            "v043_lineage_fingerprint": receipt["lineage_fingerprint"],
            "admission_id": raw["admission_id"],
            "admission_record_fingerprint": raw["admission_record_fingerprint"],
            "admission_status_fingerprint": status_raw["status_fingerprint"],
            "v044_queue_identity_fingerprint": raw["queue_identity_fingerprint"],
            "v044_subject_fingerprint": raw["subject_fingerprint"],
            "inherited_limits_fingerprint": item["inherited_limits_fingerprint"],
        },
    )


def item_identity_fingerprint(
    admission: ControlledDequeueAdmissionV1 | dict[str, Any],
) -> FingerprintV1:
    raw = admission.model_dump(mode="json") if isinstance(admission, BaseModel) else dict(admission)
    receipt = raw["queue_observation_receipt"]
    enqueue = receipt["v042_enqueue"]
    item = enqueue["queue_item"]
    evidence = receipt["receipt_evidence"]
    observation = receipt["queue_observation"]
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-item-identity:v1",
        {
            "enqueue_id": enqueue["enqueue_id"],
            "queue_item_id": item["queue_item_id"],
            "inert_queue_item_id": evidence["inert_queue_item_id"],
            "observation_enqueue_id": observation["enqueue_id"],
            "admission_item_identity_fingerprint": raw["item_identity_fingerprint"],
            "item_identity": observation["item_identity"],
            "item_fingerprint": item["item_fingerprint"],
            "receipt_item_fingerprint": evidence["inert_queue_item_fingerprint"],
            "reference_only": item["reference_only"],
            "payload_bytes": item["payload_bytes"],
            "dequeued": item["dequeued"],
        },
    )


def lineage_fingerprint(
    admission: ControlledDequeueAdmissionV1,
    status: ControlledDequeueAdmissionStatusV1,
) -> FingerprintV1:
    receipt = admission.queue_observation_receipt
    receipt_status = admission.queue_observation_receipt_status
    enqueue = receipt.v042_enqueue
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-v020-v044-chain:v1",
        {
            "v044_admission_id": admission.admission_id,
            "v044_admission_record_fingerprint": admission.admission_record_fingerprint,
            "v044_admission_status_fingerprint": status.status_fingerprint,
            "v044_decision_fingerprint": admission.admission_decision.decision_fingerprint,
            "v044_queue_identity_fingerprint": admission.queue_identity_fingerprint,
            "v044_item_identity_fingerprint": admission.item_identity_fingerprint,
            "v044_lineage_fingerprint": admission.lineage_fingerprint,
            "v044_subject_fingerprint": admission.subject_fingerprint,
            "v043_receipt_id": receipt.receipt_id,
            "v043_receipt_record_fingerprint": receipt.receipt_record_fingerprint,
            "v043_receipt_status_fingerprint": receipt_status.status_fingerprint,
            "v043_observation_fingerprint": (
                receipt.queue_observation.observation_fingerprint
            ),
            "v043_enqueue_receipt_fingerprint": (
                receipt.receipt_evidence.receipt_fingerprint
            ),
            "v043_lineage_fingerprint": receipt.lineage_fingerprint,
            "v042_enqueue_id": enqueue.enqueue_id,
            "v042_enqueue_record_fingerprint": enqueue.record_fingerprint,
            "v042_enqueue_status_fingerprint": receipt.v042_enqueue_status.status_fingerprint,
            "v042_queue_item_fingerprint": enqueue.queue_item.item_fingerprint,
            "v042_lineage_fingerprint": enqueue.lineage.lineage_fingerprint,
            "inherited_limits_fingerprint": enqueue.inherited_limits.limits_fingerprint,
        },
    )


def bounded_receipt_fingerprint(
    value: BoundedDequeueReceiptEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-bounded-receipt:v1",
        _without(value, "receipt_fingerprint"),
    )


def dequeue_subject_fingerprint(
    value: OneShotControlledDequeueReceiptV1 | dict[str, Any],
) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-subject:v1",
        {
            "operator_id": raw["operator_id"],
            "candidate_record_id": raw["candidate_record_id"],
            "controlled_dequeue_admission_fingerprint": raw[
                "controlled_dequeue_admission"
            ]["admission_record_fingerprint"],
            "controlled_dequeue_admission_status_fingerprint": raw[
                "controlled_dequeue_admission_status"
            ]["status_fingerprint"],
            "queue_identity_fingerprint": raw["queue_identity_fingerprint"],
            "item_identity_fingerprint": raw["item_identity_fingerprint"],
            "lineage_fingerprint": raw["lineage_fingerprint"],
            "bounded_receipt_fingerprint": raw["bounded_receipt"]["receipt_fingerprint"],
            "idempotency_key_fingerprint": raw["idempotency_key_fingerprint"],
        },
    )


def dequeue_record_fingerprint(
    value: OneShotControlledDequeueReceiptV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-record:v1",
        _without(value, "dequeue_record_fingerprint"),
    )


def evaluation_fingerprint(
    value: OneShotControlledDequeueEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:one-shot-controlled-dequeue-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return fingerprint(domain, value)


def derived_uuid5(domain: str, value: Any) -> str:
    seed = fingerprint(domain, value).value
    return str(uuid.uuid5(_UUID5_NAMESPACE, f"{domain}:{seed}"))


def derived_dequeue_id(subject_fingerprint: FingerprintV1) -> str:
    return derived_uuid5(
        "atlas:one-shot-controlled-dequeue-id:v1", subject_fingerprint
    )


def build_receipt(
    validation: OneShotControlledDequeueValidationInputV1,
    *,
    adapter_receipt_fingerprint: FingerprintV1 | None = None,
    outcome: Literal["success", "failure", "indeterminate"] = "success",
) -> OneShotControlledDequeueReceiptV1:
    admission, status = (
        validation.controlled_dequeue_admission,
        validation.controlled_dequeue_admission_status,
    )
    now = _instant(validation.authority.request_received_at)
    valid_until = min(
        now + timedelta(seconds=MAX_FRESHNESS_SECONDS),
        _instant(admission.valid_until),
        _instant(status.valid_until),
        _instant(admission.queue_observation_receipt.valid_until),
        _instant(admission.queue_observation_receipt_status.valid_until),
        _instant(admission.queue_observation_receipt.v042_enqueue.valid_until),
        _instant(admission.queue_observation_receipt.v042_enqueue.queue_item.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    queue_fp = queue_identity_fingerprint(admission, status)
    item_fp = item_identity_fingerprint(admission)
    line_fp = lineage_fingerprint(admission, status)
    adapter_fp = adapter_receipt_fingerprint or opaque_fingerprint(
        "atlas:one-shot-controlled-dequeue-adapter-receipt:v1",
        "pure-contract-success-receipt",
    )
    disposition = {
        "success": "exact_inert_item_dequeued",
        "failure": "exact_inert_item_not_dequeued",
        "indeterminate": "dequeue_completion_indeterminate",
    }[outcome]
    bounded_raw = {
        "outcome": outcome,
        "disposition": disposition,
        "adapter_receipt_fingerprint": adapter_fp,
        "queue_identity_fingerprint": queue_fp,
        "item_identity_fingerprint": item_fp,
    }
    bounded_seed = BoundedDequeueReceiptEvidenceV1.model_construct(
        **bounded_raw,
        receipt_fingerprint=fingerprint("atlas:seed:v1", "bounded-receipt"),
    )
    bounded = BoundedDequeueReceiptEvidenceV1.model_validate(
        {**bounded_raw, "receipt_fingerprint": bounded_receipt_fingerprint(bounded_seed)}
    )
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    raw = {
        "dequeue_id": derived_dequeue_id(
            fingerprint(
                "atlas:one-shot-controlled-dequeue-subject:v1",
                {
                    "operator_id": validation.operator_id,
                    "candidate_record_id": validation.candidate_record_id,
                    "controlled_dequeue_admission_fingerprint": (
                        admission.admission_record_fingerprint
                    ),
                    "controlled_dequeue_admission_status_fingerprint": (
                        status.status_fingerprint
                    ),
                    "queue_identity_fingerprint": queue_fp,
                    "item_identity_fingerprint": item_fp,
                    "lineage_fingerprint": line_fp,
                    "bounded_receipt_fingerprint": bounded.receipt_fingerprint,
                    "idempotency_key_fingerprint": idem,
                },
            )
        ),
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until,
        "outcome": outcome,
        "disposition": disposition,
        "controlled_dequeue_admission": admission,
        "controlled_dequeue_admission_status": status,
        "inherited_limits": admission.inherited_limits,
        "bounded_receipt": bounded,
        "queue_identity_fingerprint": queue_fp,
        "item_identity_fingerprint": item_fp,
        "lineage_fingerprint": line_fp,
        "idempotency_key_fingerprint": idem,
    }
    subject_seed = OneShotControlledDequeueReceiptV1.model_construct(
        **raw,
        subject_fingerprint=fingerprint("atlas:seed:v1", "subject"),
        dequeue_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    subject = dequeue_subject_fingerprint(subject_seed)
    record_seed = OneShotControlledDequeueReceiptV1.model_construct(
        **{**raw, "dequeue_id": derived_dequeue_id(subject)},
        subject_fingerprint=subject,
        dequeue_record_fingerprint=fingerprint("atlas:seed:v1", "record"),
    )
    return OneShotControlledDequeueReceiptV1.model_validate(
        {
            **raw,
            "dequeue_id": derived_dequeue_id(subject),
            "subject_fingerprint": subject,
            "dequeue_record_fingerprint": dequeue_record_fingerprint(record_seed),
        }
    )


def evaluate_one_shot_controlled_dequeue(
    value: OneShotControlledDequeueValidationInputV1 | dict[str, Any],
) -> OneShotControlledDequeueEvaluationV1:
    now = _evaluation_time(value)
    try:
        validation = (
            value
            if isinstance(value, OneShotControlledDequeueValidationInputV1)
            else OneShotControlledDequeueValidationInputV1.model_validate(value)
        )
        blocker: BlockerV1 | None = None
        operator_id = validation.operator_id
        candidate_record_id = validation.candidate_record_id
        admission = validation.controlled_dequeue_admission
        expiries = (
            admission.valid_until,
            validation.controlled_dequeue_admission_status.valid_until,
            admission.queue_observation_receipt.valid_until,
            admission.queue_observation_receipt_status.valid_until,
            admission.queue_observation_receipt.v042_enqueue.valid_until,
            admission.queue_observation_receipt.v042_enqueue.queue_item.valid_until,
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
        "dequeue_state": "readiness_gated" if allowed else "blocked",
        "outcome": "success" if allowed else "failure",
        "disposition": (
            "exact_inert_item_dequeued"
            if allowed
            else "exact_inert_item_not_dequeued"
        ),
        "blockers": SUCCESS_BLOCKERS if allowed else (blocker,),
        "recognized_active_v044_admission_count": 1 if allowed else 0,
        "recognized_exact_v042_inert_queue_item_count": 1 if allowed else 0,
        "one_shot_controlled_dequeue_build_allowed": allowed,
        "one_shot_controlled_dequeue_recorded": allowed,
    }
    seed = OneShotControlledDequeueEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return OneShotControlledDequeueEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def parse_create_json(raw: str | bytes) -> OneShotControlledDequeueCreateV1:
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
    return OneShotControlledDequeueCreateV1.model_validate(parsed)


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
    value: OneShotControlledDequeueValidationInputV1 | dict[str, Any],
) -> str:
    if isinstance(value, OneShotControlledDequeueValidationInputV1):
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
    if "not active" in lowered and "v0.44" in lowered:
        return "v044_admission_not_active"
    if "not recorded" in lowered and "v0.44" in lowered:
        return "v044_admission_not_recorded"
    if "not eligible" in lowered and "v0.44" in lowered:
        return "v044_admission_not_eligible"
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
    if "dequeued" in lowered or "executable" in lowered or "payload" in lowered:
        return "executable_payload"
    if "authority" in lowered:
        return "unsupported_authority"
    if "observation receipt" in lowered or "item mismatch" in lowered:
        return "observation_receipt_mismatch"
    if "linkage" in lowered or "binding" in lowered:
        return "linkage_mismatch"
    return "evidence_not_found"
