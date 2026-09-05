"""Closed immutable v0.46 one-shot dequeue to worker-subject binding models.

This module is pure contract validation. It has no store, queue I/O, route,
polling, claim, lease, ack, worker contact, Agent, execution, installation,
deployment, rollback, endpoint, credential, command, or mutation behavior.
"""

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
from app.one_shot_controlled_dequeue.contract import (
    SUCCESS_BLOCKERS as V045_SUCCESS_BLOCKERS,
)
from app.one_shot_controlled_dequeue.contract import (
    OneShotControlledDequeueReceiptV1,
    OneShotControlledDequeueStatusV1,
)
from app.one_shot_controlled_dequeue.contract import (
    dequeue_record_fingerprint as v045_dequeue_record_fingerprint,
)
from app.one_shot_controlled_dequeue.contract import (
    status_fingerprint as v045_status_fingerprint,
)
from app.worker_intake_admission.contract import (
    ADMISSION_BLOCKERS as V040_ADMISSION_BLOCKERS,
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

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 192 * 1024
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.one_shot_dequeue_worker_binding.record"
READ_PERMISSION = "installation.execution.one_shot_dequeue_worker_binding.read"
SCOPE = "installation_one_shot_dequeue_worker_binding_only"
SAFE_MESSAGE = "one-shot dequeue worker binding request could not be completed"
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"
_CREDENTIAL_KEYS = frozenset({"credential", "credentials", "secret", "token"})
_ENDPOINT_KEYS = frozenset({"endpoint", "endpoints", "url", "uri"})
_COMMAND_KEYS = frozenset({"command", "commands", "cmd", "shell"})
_AUTHORITY_FLAGS = frozenset(
    {
        "caller_supplied_credentials_allowed",
        "caller_supplied_endpoint_allowed",
        "caller_supplied_command_allowed",
        "payload_schema_defined",
        "payload_constructed",
        "payload_serialized",
        "queue_polling_allowed",
        "queue_claim_allowed",
        "queue_lease_allowed",
        "queue_ack_allowed",
        "queue_mutation_allowed",
        "worker_contact_allowed",
        "worker_start_allowed",
        "agent_invocation_allowed",
        "execution_start_allowed",
        "process_execution_allowed",
        "store_contact_allowed",
        "runtime_contact_allowed",
        "dispatch_allowed",
        "retry_allowed",
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
    }
)

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v045_dequeue_not_active",
    "v045_dequeue_not_recorded",
    "v045_dequeue_not_successful",
    "v040_worker_intake_not_active",
    "v040_worker_intake_not_recorded",
    "linkage_mismatch",
    "worker_subject_mismatch",
    "queue_item_reference_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "unsupported_authority",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v045_dequeue_not_active",
    "v045_dequeue_not_recorded",
    "v045_dequeue_not_successful",
    "v040_worker_intake_not_active",
    "v040_worker_intake_not_recorded",
    "linkage_mismatch",
    "worker_subject_mismatch",
    "queue_item_reference_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "unsupported_authority",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
    "store_contact_not_defined",
    "runtime_contact_not_defined",
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
        raise ValueError("v0.46 blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("v0.46 blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    caller_supplied_credentials_allowed: Literal[False] = False
    caller_supplied_endpoint_allowed: Literal[False] = False
    caller_supplied_command_allowed: Literal[False] = False
    credential_material_present: bool = False
    endpoint_material_present: bool = False
    command_material_present: bool = False
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    queue_polling_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    queue_mutation_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    process_execution_allowed: Literal[False] = False
    store_contact_allowed: Literal[False] = False
    runtime_contact_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
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


class OneShotDequeueWorkerBindingCreateV1(ClosedAuthorityV1):
    schema: Literal["one-shot-dequeue-worker-binding-create-v1"] = (
        "one-shot-dequeue-worker-binding-create-v1"
    )
    one_shot_controlled_dequeue_id: CanonicalUuid5
    one_shot_controlled_dequeue_fingerprint: FingerprintV1
    one_shot_controlled_dequeue_status_fingerprint: FingerprintV1
    one_shot_controlled_dequeue_valid_until: UtcSecond
    worker_intake_admission_id: CanonicalUuid4
    worker_intake_admission_fingerprint: FingerprintV1
    worker_intake_admission_status_fingerprint: FingerprintV1
    worker_intake_admission_valid_until: UtcSecond
    worker_subject_fingerprint: FingerprintV1
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

    @model_validator(mode="after")
    def exact(self) -> OneShotDequeueWorkerBindingCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class OneShotDequeueWorkerBindingAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["one-shot-dequeue-worker-binding-authority-context-v1"] = (
        "one-shot-dequeue-worker-binding-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class OneShotDequeueWorkerBindingEvaluationV1(ClosedAuthorityV1):
    schema: Literal["one-shot-dequeue-worker-binding-evaluation-v1"] = (
        "one-shot-dequeue-worker-binding-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    binding_state: Literal["readiness_gated", "blocked"]
    eligibility: Literal["one_shot_dequeue_worker_binding_recorded", "blocked"]
    blockers: tuple[BlockerV1, ...]
    recognized_successful_v045_dequeue_count: int
    recognized_worker_subject_count: int
    binding_record_build_allowed: bool
    evaluation_fingerprint: FingerprintV1
    one_shot_dequeue_worker_binding_recorded: bool = False

    @model_validator(mode="after")
    def exact(self) -> OneShotDequeueWorkerBindingEvaluationV1:
        _ordered(self.blockers)
        allowed = self.binding_state == "readiness_gated"
        if (self.eligibility == "one_shot_dequeue_worker_binding_recorded") != allowed:
            raise ValueError("v0.46 eligibility mismatch")
        if self.recognized_successful_v045_dequeue_count != (1 if allowed else 0):
            raise ValueError("v0.45 dequeue recognition count mismatch")
        if self.recognized_worker_subject_count != (1 if allowed else 0):
            raise ValueError("worker subject recognition count mismatch")
        if self.binding_record_build_allowed != allowed:
            raise ValueError("v0.46 build flag mismatch")
        if allowed and (
            self.blockers != SUCCESS_BLOCKERS
            or not self.one_shot_dequeue_worker_binding_recorded
        ):
            raise ValueError("recordable v0.46 binding shape mismatch")
        if not allowed and self.one_shot_dequeue_worker_binding_recorded:
            raise ValueError("blocked v0.46 binding shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("v0.46 evaluation fingerprint mismatch")
        _bounded(self)
        return self


class OneShotDequeueWorkerBindingValidationInputV1(ContractModel):
    """Injected facts only; no store, runtime, queue, worker, endpoint, or I/O."""

    operator_id: OperatorId
    authority: OneShotDequeueWorkerBindingAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: OneShotDequeueWorkerBindingCreateV1
    one_shot_controlled_dequeue: OneShotControlledDequeueReceiptV1
    one_shot_controlled_dequeue_status: OneShotControlledDequeueStatusV1
    worker_intake_admission: WorkerIntakeAdmissionV1
    worker_intake_admission_status: WorkerIntakeAdmissionStatusV1
    idempotency_key: VisibleIdempotencyKey
    home_assistant: bool = False
    ambiguous_worker_subject_count: int = 0
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> OneShotDequeueWorkerBindingValidationInputV1:
        dequeue, dequeue_status = (
            self.one_shot_controlled_dequeue,
            self.one_shot_controlled_dequeue_status,
        )
        worker, worker_status = (
            self.worker_intake_admission,
            self.worker_intake_admission_status,
        )
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if self.ambiguous_worker_subject_count != 0:
            raise ValueError("ambiguous worker subject")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or dequeue.operator_id != self.operator_id
            or dequeue_status.operator_id != self.operator_id
            or worker.operator_id != self.operator_id
            or worker_status.operator_id != self.operator_id
        ):
            raise ValueError("v0.46 ownership mismatch")
        if (
            dequeue.candidate_record_id != self.candidate_record_id
            or dequeue_status.candidate_record_id != self.candidate_record_id
            or worker.candidate_record_id != self.candidate_record_id
            or worker_status.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("v0.46 candidate linkage mismatch")
        if (
            self.create.one_shot_controlled_dequeue_id != dequeue.dequeue_id
            or self.create.one_shot_controlled_dequeue_valid_until != dequeue.valid_until
            or dequeue_status.dequeue_id != dequeue.dequeue_id
        ):
            raise ValueError("v0.45 dequeue linkage mismatch")
        if (
            self.create.one_shot_controlled_dequeue_fingerprint
            != dequeue.dequeue_record_fingerprint
            or self.create.one_shot_controlled_dequeue_status_fingerprint
            != dequeue_status.status_fingerprint
            or dequeue_status.dequeue_record_fingerprint
            != dequeue.dequeue_record_fingerprint
        ):
            raise ValueError("v0.45 dequeue fingerprint mismatch")
        if (
            self.create.worker_intake_admission_id != worker.admission_id
            or self.create.worker_intake_admission_valid_until != worker.valid_until
            or worker_status.admission_id != worker.admission_id
        ):
            raise ValueError("v0.40 worker intake linkage mismatch")
        if (
            self.create.worker_intake_admission_fingerprint != worker.record_fingerprint
            or self.create.worker_intake_admission_status_fingerprint
            != worker_status.status_fingerprint
            or worker_status.record_fingerprint != worker.record_fingerprint
        ):
            raise ValueError("v0.40 worker intake fingerprint mismatch")
        if (
            dequeue.dequeue_record_fingerprint
            != v045_dequeue_record_fingerprint(dequeue)
            or dequeue_status.status_fingerprint != v045_status_fingerprint(dequeue_status)
            or worker.record_fingerprint != v040_record_fingerprint(worker)
            or worker_status.status_fingerprint != v040_status_fingerprint(worker_status)
        ):
            raise ValueError("v0.46 prerequisite fingerprint mismatch")
        if dequeue_status.lifecycle != "active":
            raise ValueError("v0.45 dequeue is not active")
        if (
            dequeue.lifecycle != "active"
            or dequeue.dequeue_state != "one_shot_controlled_dequeue_recorded"
            or not dequeue.one_shot_controlled_dequeue_recorded
            or dequeue.outcome != "success"
            or dequeue.disposition != "exact_inert_item_dequeued"
            or dequeue_status.outcome != "success"
            or dequeue_status.disposition != "exact_inert_item_dequeued"
            or not dequeue_status.one_shot_controlled_dequeue_recorded
            or dequeue.blockers != V045_SUCCESS_BLOCKERS
            or dequeue_status.blockers != V045_SUCCESS_BLOCKERS
        ):
            raise ValueError("v0.45 dequeue is not successful")
        if worker_status.lifecycle != "active":
            raise ValueError("v0.40 worker intake is not active")
        if (
            worker.lifecycle != "active"
            or worker.eligibility != "worker_intake_admission_recorded"
            or worker_status.eligibility != "worker_intake_admission_recorded"
            or worker.blockers != V040_ADMISSION_BLOCKERS
            or worker_status.blockers != V040_ADMISSION_BLOCKERS
        ):
            raise ValueError("v0.40 worker intake is not recorded")
        if (
            self.create.worker_subject_fingerprint != worker.subject_fingerprint
            or self.create.worker_identity_id != worker.worker_identity.worker_identity_id
            or self.create.worker_identity_fingerprint
            != worker.worker_identity.worker_identity_fingerprint
            or self.create.worker_intake_reference_id
            != worker.worker_intake_reference.worker_intake_reference_id
            or self.create.worker_intake_reference_fingerprint
            != worker.worker_intake_reference.intake_reference_fingerprint
        ):
            raise ValueError("worker subject mismatch")
        link = worker.linkage
        item = dequeue.controlled_dequeue_admission.queue_observation_receipt.v042_enqueue.queue_item
        if (
            self.create.queue_intake_reference_id != link.queue_intake_reference_id
            or self.create.queue_intake_reference_fingerprint
            != link.queue_intake_reference_fingerprint
            or self.create.queue_item_reference_id != link.queue_item_reference_id
            or self.create.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
            or item.queue_intake_reference_id != link.queue_intake_reference_id
            or item.queue_intake_reference_fingerprint
            != link.queue_intake_reference_fingerprint
            or item.queue_item_reference_id != link.queue_item_reference_id
            or item.queue_item_reference_fingerprint
            != link.queue_item_reference_fingerprint
        ):
            raise ValueError("queue item reference mismatch")
        if (
            self.create.inherited_limits_fingerprint
            != dequeue.inherited_limits.limits_fingerprint
            or self.create.inherited_limits_fingerprint
            != worker.inherited_limits.limits_fingerprint
            or item.inherited_limits_fingerprint
            != worker.inherited_limits.limits_fingerprint
        ):
            raise ValueError("inherited limits mismatch")
        if (
            self.authority.credential_material_present
            or self.create.credential_material_present
        ):
            raise ValueError("caller supplied credential")
        if (
            self.authority.endpoint_material_present
            or self.create.endpoint_material_present
        ):
            raise ValueError("caller supplied endpoint")
        if self.authority.command_material_present or self.create.command_material_present:
            raise ValueError("caller supplied command")
        if (
            self.authority.store_contact_allowed
            or self.authority.runtime_contact_allowed
            or self.authority.worker_contact_allowed
            or self.authority.worker_start_allowed
            or self.authority.execution_start_allowed
            or self.authority.process_execution_allowed
            or self.authority.queue_ack_allowed
            or self.authority.queue_mutation_allowed
        ):
            raise ValueError("unsupported authority")
        now = _instant(self.authority.request_received_at)
        starts = (
            _instant(dequeue.recorded_at),
            _instant(dequeue_status.evaluated_at),
            _instant(worker.recorded_at),
            _instant(worker_status.evaluated_at),
        )
        if any(
            value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS)
            for value in starts
        ):
            raise ValueError("v0.46 evidence is stale or from the future")
        expiries = (
            _instant(dequeue.valid_until),
            _instant(dequeue_status.valid_until),
            _instant(worker.valid_until),
            _instant(worker_status.valid_until),
        )
        if any(now >= expiry for expiry in expiries):
            raise ValueError("v0.46 evidence is expired")
        return self


def evaluation_fingerprint(
    value: OneShotDequeueWorkerBindingEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:one-shot-dequeue-worker-binding-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    return fingerprint(
        "atlas:one-shot-dequeue-worker-binding-idempotency:v1",
        {"operator_id": operator_id, "idempotency_key": key},
    )


def build_create(
    *,
    dequeue: OneShotControlledDequeueReceiptV1,
    dequeue_status: OneShotControlledDequeueStatusV1,
    worker: WorkerIntakeAdmissionV1,
    worker_status: WorkerIntakeAdmissionStatusV1,
) -> OneShotDequeueWorkerBindingCreateV1:
    link = worker.linkage
    return OneShotDequeueWorkerBindingCreateV1(
        one_shot_controlled_dequeue_id=dequeue.dequeue_id,
        one_shot_controlled_dequeue_fingerprint=dequeue.dequeue_record_fingerprint,
        one_shot_controlled_dequeue_status_fingerprint=dequeue_status.status_fingerprint,
        one_shot_controlled_dequeue_valid_until=dequeue.valid_until,
        worker_intake_admission_id=worker.admission_id,
        worker_intake_admission_fingerprint=worker.record_fingerprint,
        worker_intake_admission_status_fingerprint=worker_status.status_fingerprint,
        worker_intake_admission_valid_until=worker.valid_until,
        worker_subject_fingerprint=worker.subject_fingerprint,
        worker_identity_id=worker.worker_identity.worker_identity_id,
        worker_identity_fingerprint=worker.worker_identity.worker_identity_fingerprint,
        worker_intake_reference_id=worker.worker_intake_reference.worker_intake_reference_id,
        worker_intake_reference_fingerprint=(
            worker.worker_intake_reference.intake_reference_fingerprint
        ),
        queue_intake_reference_id=link.queue_intake_reference_id,
        queue_intake_reference_fingerprint=link.queue_intake_reference_fingerprint,
        queue_item_reference_id=link.queue_item_reference_id,
        queue_item_reference_fingerprint=link.queue_item_reference_fingerprint,
        inherited_limits_fingerprint=worker.inherited_limits.limits_fingerprint,
    )


def evaluate_one_shot_dequeue_worker_binding(
    value: OneShotDequeueWorkerBindingValidationInputV1 | dict[str, Any],
) -> OneShotDequeueWorkerBindingEvaluationV1:
    preflight_blocker = _preflight_blocker(value)
    if preflight_blocker is not None:
        return _blocked_evaluation(value, preflight_blocker)
    try:
        validation = (
            value
            if isinstance(value, OneShotDequeueWorkerBindingValidationInputV1)
            else OneShotDequeueWorkerBindingValidationInputV1.model_validate(value)
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    earliest = min(
        _instant(validation.one_shot_controlled_dequeue.valid_until),
        _instant(validation.one_shot_controlled_dequeue_status.valid_until),
        _instant(validation.worker_intake_admission.valid_until),
        _instant(validation.worker_intake_admission_status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest,
        binding_state="readiness_gated",
        eligibility="one_shot_dequeue_worker_binding_recorded",
        blockers=SUCCESS_BLOCKERS,
    )


def _preflight_blocker(
    value: OneShotDequeueWorkerBindingValidationInputV1 | dict[str, Any],
) -> BlockerV1 | None:
    if isinstance(value, BaseModel) or not isinstance(value, dict):
        return None
    if value.get("ambiguous_worker_subject_count", 0):
        return "ambiguous_state"
    for section_name in ("create", "authority"):
        section = value.get(section_name)
        if not isinstance(section, dict):
            continue
        keys = set(section)
        if keys & _CREDENTIAL_KEYS or section.get("credential_material_present"):
            return "caller_supplied_credential"
        if keys & _ENDPOINT_KEYS or section.get("endpoint_material_present"):
            return "caller_supplied_endpoint"
        if keys & _COMMAND_KEYS or section.get("command_material_present"):
            return "caller_supplied_command"
        if section_name == "authority" and any(
            section.get(flag) for flag in _AUTHORITY_FLAGS
        ):
            return "unsupported_authority"
    keys = set(value)
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
    binding_state: Literal["readiness_gated", "blocked"],
    eligibility: Literal["one_shot_dequeue_worker_binding_recorded", "blocked"],
    blockers: tuple[BlockerV1, ...],
) -> OneShotDequeueWorkerBindingEvaluationV1:
    allowed = binding_state == "readiness_gated"
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "binding_state": binding_state,
        "eligibility": eligibility,
        "blockers": blockers,
        "recognized_successful_v045_dequeue_count": 1 if allowed else 0,
        "recognized_worker_subject_count": 1 if allowed else 0,
        "binding_record_build_allowed": allowed,
        "one_shot_dequeue_worker_binding_recorded": allowed,
    }
    seed = OneShotDequeueWorkerBindingEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return OneShotDequeueWorkerBindingEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: OneShotDequeueWorkerBindingValidationInputV1 | dict[str, Any],
    reason: str,
) -> OneShotDequeueWorkerBindingEvaluationV1:
    raw = value.model_dump(mode="python") if isinstance(value, BaseModel) else dict(value)
    authority = raw.get("authority") if isinstance(raw.get("authority"), dict) else {}
    operator_id = raw.get("operator_id") or authority.get("authenticated_operator_id")
    candidate_record_id = raw.get("candidate_record_id")
    return _evaluation(
        operator_id=operator_id or _BLOCKED_OPERATOR_ID,
        candidate_record_id=candidate_record_id or _BLOCKED_CANDIDATE_ID,
        evaluated_at=authority.get("request_received_at") or "1970-01-01T00:00:00Z",
        earliest_expiry=None,
        binding_state="blocked",
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
    if "not active" in lowered and "v0.45" in lowered:
        return "v045_dequeue_not_active"
    if "not successful" in lowered:
        return "v045_dequeue_not_successful"
    if "not active" in lowered and "v0.40" in lowered:
        return "v040_worker_intake_not_active"
    if "not recorded" in lowered and "v0.40" in lowered:
        return "v040_worker_intake_not_recorded"
    if "linkage" in lowered:
        return "linkage_mismatch"
    if "stale" in lowered or "future" in lowered:
        return "evidence_stale"
    if "expired" in lowered:
        return "evidence_expired"
    if "ambiguous" in lowered:
        return "ambiguous_state"
    if "worker subject" in lowered:
        return "worker_subject_mismatch"
    if "queue item reference" in lowered:
        return "queue_item_reference_mismatch"
    if "fingerprint" in lowered:
        return "fingerprint_mismatch"
    if "limits" in lowered:
        return "inherited_limits_mismatch"
    if "credential" in lowered:
        return "caller_supplied_credential"
    if "endpoint" in lowered:
        return "caller_supplied_endpoint"
    if "command" in lowered:
        return "caller_supplied_command"
    if "unsupported authority" in lowered:
        return "unsupported_authority"
    return "evidence_not_found"


def parse_create_json(raw: bytes | str) -> OneShotDequeueWorkerBindingCreateV1:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 16 KiB")
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise StrictContractError("create request must be UTF-8") from error
    if unicodedata.normalize("NFC", decoded) != decoded:
        raise StrictContractError("create request must be NFC normalized")
    try:
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as error:
        raise StrictContractError("invalid strict create JSON") from error
    if not isinstance(parsed, dict):
        raise StrictContractError("create request must be an object")
    return OneShotDequeueWorkerBindingCreateV1.model_validate(parsed)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictContractError(f"duplicate key: {key}")
        result[key] = value
    return result
