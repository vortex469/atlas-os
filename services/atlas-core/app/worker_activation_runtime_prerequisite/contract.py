"""Pure v0.53 Worker Activation Runtime Prerequisite evidence contract.

All facts are injected. No persistence, clock reads, queue/worker contact or
runtime effects occur here. The complete immutable v0.52 pair preserves lineage.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import timedelta
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.controlled_worker_queue_claim_lease_acknowledgement import contract as v052
from app.execution_permission_grant.contract import (
    CanonicalUuid5,
    OperatorId,
    canonical_json,
)
from app.installation_execution_admission.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_MODEL_BYTES = 192 * 1024
MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.worker_activation_runtime_prerequisite.evaluate"
SCOPE = "worker_activation_runtime_prerequisite_only"
MARKER = "worker_activation_runtime_prerequisite_recorded"
SUCCESS_BLOCKERS = v052.SUCCESS_BLOCKERS
SAFE_MESSAGE = "worker activation runtime prerequisite request could not be completed"

RefusalV1 = Literal[
    "invalid_request",
    "evidence_not_found",
    "installation_capability_unsupported",
    "ambiguous_state",
    "fingerprint_mismatch",
    "linkage_mismatch",
    "evidence_stale",
    "evidence_expired",
    "v052_receipt_not_active",
]


def _plain(value: Any, depth: int = 0) -> Any:
    """Reparse even model_construct/model_copy objects, including injected extras."""
    if depth > 128:
        raise ValueError("contract nesting exceeds bound")
    if isinstance(value, BaseModel):
        value = {**value.__dict__, **(value.__pydantic_extra__ or {})}
    if isinstance(value, dict):
        return {key: _plain(item, depth + 1) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return type(value)(_plain(item, depth + 1) for item in value)
    return value


def _strict_literals(annotation: Any, value: Any) -> Any:
    """Pydantic Literal[False]/Literal[0] otherwise accept 0/False respectively.

    Inspect the actual historical schemas recursively; historical true evidence
    markers must not be mistaken for newly granted authority.
    """
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        if not any(type(value) is type(item) and value == item for item in args):
            raise ValueError("literal type or value mismatch")
    elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, dict):
            for name, field in annotation.model_fields.items():
                if name in value:
                    if name.endswith("_material_present") and value[name] is not False:
                        raise ValueError("material is forbidden in inherited evidence")
                    value[name] = _strict_literals(field.annotation, value[name])
    elif origin is tuple and isinstance(value, tuple | list):
        return tuple(_strict_literals(args[0], item) for item in value)
    elif args:
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                value = _strict_literals(arg, value)
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @classmethod
    def model_validate_json(
        cls, json_data: str | bytes | bytearray, **kwargs: Any
    ) -> Any:
        # Pydantic's default JSON decoder accepts duplicate keys. Stored evidence
        # must use the same strict decoding as requests, without altering strings.
        if len(json_data) > MAX_MODEL_BYTES:
            raise ValueError("contract envelope exceeds bound")
        raw = json.loads(json_data, object_pairs_hook=_unique_keys)
        return cls.model_validate(raw, **kwargs)

    @model_validator(mode="before")
    @classmethod
    def reparse(cls, value: Any) -> Any:
        raw = _plain(value)
        _strict_literals(cls, raw)
        if len(canonical_json(raw)) > MAX_MODEL_BYTES:
            raise ValueError("contract envelope exceeds bound")
        return raw

    @model_validator(mode="after")
    def bounded_serialized_model(self) -> ContractModel:
        # Defaults and inherited authority fields also count toward the envelope.
        if len(canonical_json(self)) > MAX_MODEL_BYTES:
            raise ValueError("contract envelope exceeds bound")
        return self


class ClosedAuthorityV1(v052.ClosedAuthorityV1, ContractModel):
    queue_adapter_defined: Literal[False] = False
    queue_contact_allowed: Literal[False] = False
    queue_claim_allowed: Literal[False] = False
    queue_lease_allowed: Literal[False] = False
    queue_ack_allowed: Literal[False] = False
    worker_discovery_allowed: Literal[False] = False
    worker_registration_allowed: Literal[False] = False
    worker_start_admission_build_allowed: Literal[False] = False
    execution_start_admission_build_allowed: Literal[False] = False
    runtime_effect_allowed: Literal[False] = False

    @model_validator(mode="after")
    def no_material(self) -> ClosedAuthorityV1:
        if any(
            getattr(self, name)
            for name in type(self).model_fields
            if name.endswith("_material_present")
        ):
            raise ValueError("material is forbidden")
        return self


class WorkerActivationRuntimePrerequisiteCreateV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-create-v1"] = (
        "worker-activation-runtime-prerequisite-create-v1"
    )
    admission_id: CanonicalUuid5
    valid_until: UtcSecond
    receipt_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def bounded(self) -> WorkerActivationRuntimePrerequisiteCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create envelope exceeds bound")
        return self


class WorkerActivationRuntimePrerequisiteAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-authority-context-v1"] = (
        "worker-activation-runtime-prerequisite-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class _Refusal(ValueError):
    def __init__(self, code: RefusalV1):
        self.code = code
        super().__init__(code)


def _validate_pair(
    record: v052.ControlledWorkerQueueClaimLeaseAcknowledgementV1,
    status: v052.ControlledWorkerQueueClaimLeaseAcknowledgementStatusV1,
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerActivationRuntimePrerequisiteCreateV1,
    now: str,
) -> None:
    # Missing and foreign evidence are indistinguishable in public refusals.
    if any(
        item.operator_id != operator_id
        or item.candidate_record_id != candidate_record_id
        for item in (record, status)
    ):
        raise _Refusal("evidence_not_found")
    if (
        create.admission_id != record.admission_id
        or status.admission_id != record.admission_id
        or create.valid_until != record.valid_until
        or status.valid_until != record.valid_until
    ):
        raise _Refusal("linkage_mismatch")
    if (
        create.receipt_record_fingerprint != record.receipt_record_fingerprint
        or create.status_fingerprint != status.status_fingerprint
        or status.receipt_record_fingerprint != record.receipt_record_fingerprint
        or record.receipt_record_fingerprint != v052.receipt_record_fingerprint(record)
        or status.status_fingerprint != v052.status_fingerprint(status)
    ):
        raise _Refusal("fingerprint_mismatch")
    if status.lifecycle != "active":
        raise _Refusal("v052_receipt_not_active")
    instant = v052._instant(now)
    if any(
        v052._instant(start) > instant
        or instant - v052._instant(start) > timedelta(seconds=MAX_FRESHNESS_SECONDS)
        for start in (record.recorded_at, status.evaluated_at)
    ):
        raise _Refusal("evidence_stale")
    if status.evaluated_at < record.recorded_at:
        raise _Refusal("evidence_stale")
    if now >= record.valid_until:
        raise _Refusal("evidence_expired")
    # Canonical status also binds every authority/material flag and receipt marker.
    if status != v052.derive_status(record, evaluated_at=status.evaluated_at):
        raise _Refusal("invalid_request")
    for item in (record, status):
        if any(
            getattr(item, name)
            for name in type(item).model_fields
            if name.endswith("_material_present")
        ):
            raise _Refusal("invalid_request")


class WorkerActivationRuntimePrerequisiteValidationInputV1(ContractModel):
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    authority: WorkerActivationRuntimePrerequisiteAuthorityContextV1
    create: WorkerActivationRuntimePrerequisiteCreateV1
    controlled_worker_queue_claim_lease_acknowledgement: (
        v052.ControlledWorkerQueueClaimLeaseAcknowledgementV1
    )
    controlled_worker_queue_claim_lease_acknowledgement_status: (
        v052.ControlledWorkerQueueClaimLeaseAcknowledgementStatusV1
    )
    home_assistant: bool = False
    ambiguous_prerequisite_count: Literal[0] = 0
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteValidationInputV1:
        if self.home_assistant:
            raise _Refusal("installation_capability_unsupported")
        if self.operator_id != self.authority.authenticated_operator_id:
            raise _Refusal("evidence_not_found")
        _validate_pair(
            self.controlled_worker_queue_claim_lease_acknowledgement,
            self.controlled_worker_queue_claim_lease_acknowledgement_status,
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            create=self.create,
            now=self.authority.request_received_at,
        )
        return self


def fingerprint(kind: str, value: Any) -> FingerprintV1:
    return v052.fingerprint(
        f"atlas:worker-activation-runtime-prerequisite-{kind}:v1", value
    )


def _model_fingerprint(kind: str, value: BaseModel | dict, field: str) -> FingerprintV1:
    raw = _plain(value)
    raw.pop(field, None)
    return fingerprint(kind, raw)


def evaluation_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("evaluation", value, "evaluation_fingerprint")


def prerequisite_record_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("record", value, "prerequisite_record_fingerprint")


def status_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("status", value, "status_fingerprint")


def subject_fingerprint(
    *, operator_id: str, candidate_record_id: str, admission_id: str
) -> FingerprintV1:
    """Permanent subject deliberately excludes mutable expiry/status/request/key."""
    return fingerprint(
        "subject",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "admission_id": admission_id,
        },
    )


def idempotency_key_fingerprint(operator_id: str, key: str) -> FingerprintV1:
    return fingerprint(
        "idempotency-key", {"operator_id": operator_id, "key": v052._visible(key)}
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerActivationRuntimePrerequisiteCreateV1,
) -> FingerprintV1:
    create = WorkerActivationRuntimePrerequisiteCreateV1.model_validate(create)
    return fingerprint(
        "request",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
        },
    )


def derived_prerequisite_id(subject: FingerprintV1) -> str:
    return v052.derived_uuid5(
        "atlas:worker-activation-runtime-prerequisite-id:v1", subject
    )


class WorkerActivationRuntimePrerequisiteEvaluationV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-evaluation-v1"] = (
        "worker-activation-runtime-prerequisite-evaluation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    prerequisite_state: Literal["recorded", "blocked"]
    eligibility: Literal[MARKER, "blocked"]
    blockers: tuple[v052.BlockerV1 | RefusalV1, ...]
    recognized_v052_receipt_count: int
    worker_activation_runtime_prerequisite_recorded: bool
    evaluation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteEvaluationV1:
        success = self.prerequisite_state == "recorded"
        if (
            self.worker_activation_runtime_prerequisite_recorded != success
            or self.eligibility != (MARKER if success else "blocked")
            or self.recognized_v052_receipt_count != int(success)
        ):
            raise ValueError("evaluation shape mismatch")
        if success:
            if self.blockers != SUCCESS_BLOCKERS or self.earliest_expiry is None:
                raise ValueError("success blockers or expiry mismatch")
            if not (
                v052._instant(self.evaluated_at)
                < v052._instant(self.earliest_expiry)
                <= v052._instant(self.evaluated_at) + timedelta(seconds=30)
            ):
                raise ValueError("evaluation expiry mismatch")
        elif (
            self.earliest_expiry is not None
            or len(self.blockers) != 1
            or self.blockers[0] not in get_args(RefusalV1)
        ):
            raise ValueError("refusal shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("evaluation fingerprint mismatch")
        return self


def _signed(model: type[BaseModel], raw: dict, field: str, function: Any) -> Any:
    seed = model.model_construct(**raw)
    return model.model_validate({**_plain(seed), field: function(seed)})


def evaluate_worker_activation_runtime_prerequisite(
    value: Any,
) -> WorkerActivationRuntimePrerequisiteEvaluationV1:
    """Deterministic redacted refusal; never echoes invalid caller material."""
    code: RefusalV1 = "invalid_request"
    try:
        raw = _plain(value)
        if not isinstance(raw, dict) or any(
            raw.get(name) is None
            for name in (
                "controlled_worker_queue_claim_lease_acknowledgement",
                "controlled_worker_queue_claim_lease_acknowledgement_status",
            )
        ):
            code = "evidence_not_found"
            raise _Refusal(code)
        validation = (
            WorkerActivationRuntimePrerequisiteValidationInputV1.model_validate(raw)
        )
    except (ValueError, TypeError, RecursionError, OverflowError) as error:
        if isinstance(error, ValidationError):
            for detail in error.errors(include_url=False, include_input=False):
                reason = detail.get("ctx", {}).get("error")
                if isinstance(reason, _Refusal):
                    code = reason.code
                    break
        # Validation errors can contain attacker-controlled values. Never stringify them.
        return _signed(
            WorkerActivationRuntimePrerequisiteEvaluationV1,
            {
                "operator_id": "blocked-evaluation",
                "candidate_record_id": "00000000-0000-4000-8000-000000000000",
                "evaluated_at": "1970-01-01T00:00:00Z",
                "earliest_expiry": None,
                "prerequisite_state": "blocked",
                "eligibility": "blocked",
                "blockers": (code,),
                "recognized_v052_receipt_count": 0,
                "worker_activation_runtime_prerequisite_recorded": False,
            },
            "evaluation_fingerprint",
            evaluation_fingerprint,
        )
    return _signed(
        WorkerActivationRuntimePrerequisiteEvaluationV1,
        {
            "operator_id": validation.operator_id,
            "candidate_record_id": validation.candidate_record_id,
            "evaluated_at": validation.authority.request_received_at,
            "earliest_expiry": validation.create.valid_until,
            "prerequisite_state": "recorded",
            "eligibility": MARKER,
            "blockers": SUCCESS_BLOCKERS,
            "recognized_v052_receipt_count": 1,
            "worker_activation_runtime_prerequisite_recorded": True,
        },
        "evaluation_fingerprint",
        evaluation_fingerprint,
    )


class WorkerActivationRuntimePrerequisiteV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-v1"] = (
        "worker-activation-runtime-prerequisite-v1"
    )
    prerequisite_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    admission_id: CanonicalUuid5
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    eligibility: Literal[MARKER] = MARKER
    blockers: tuple[v052.BlockerV1, ...] = SUCCESS_BLOCKERS
    controlled_worker_queue_claim_lease_acknowledgement: (
        v052.ControlledWorkerQueueClaimLeaseAcknowledgementV1
    )
    controlled_worker_queue_claim_lease_acknowledgement_status: (
        v052.ControlledWorkerQueueClaimLeaseAcknowledgementStatusV1
    )
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    prerequisite_record_fingerprint: FingerprintV1
    worker_activation_runtime_prerequisite_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteV1:
        receipt = self.controlled_worker_queue_claim_lease_acknowledgement
        status = self.controlled_worker_queue_claim_lease_acknowledgement_status
        _validate_pair(
            receipt,
            status,
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            create=build_create(receipt=receipt, receipt_status=status),
            now=self.recorded_at,
        )
        if (
            self.admission_id != receipt.admission_id
            or not self.recorded_at < self.valid_until <= receipt.valid_until
            or self.blockers != SUCCESS_BLOCKERS
        ):
            raise ValueError("record linkage, expiry or blockers mismatch")
        if self.subject_fingerprint != subject_fingerprint(
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            admission_id=self.admission_id,
        ) or self.prerequisite_id != derived_prerequisite_id(self.subject_fingerprint):
            raise ValueError("subject or id mismatch")
        if self.prerequisite_record_fingerprint != prerequisite_record_fingerprint(
            self
        ):
            raise ValueError("record fingerprint mismatch")
        return self


class WorkerActivationRuntimePrerequisiteStatusV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-status-v1"] = (
        "worker-activation-runtime-prerequisite-status-v1"
    )
    prerequisite_id: CanonicalUuid5
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    admission_id: CanonicalUuid5
    recorded_at: UtcSecond
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal[MARKER] = MARKER
    blockers: tuple[v052.BlockerV1, ...] = SUCCESS_BLOCKERS
    prerequisite_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    worker_activation_runtime_prerequisite_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteStatusV1:
        if (
            self.blockers != SUCCESS_BLOCKERS
            or self.evaluated_at < self.recorded_at
            or not (
                v052._instant(self.recorded_at)
                < v052._instant(self.valid_until)
                <= v052._instant(self.recorded_at) + timedelta(seconds=30)
            )
            or self.lifecycle
            != ("expired" if self.evaluated_at >= self.valid_until else "active")
        ):
            raise ValueError("status lifecycle mismatch")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("status fingerprint mismatch")
        return self


class WorkerActivationRuntimePrerequisiteResultV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-result-v1"] = (
        "worker-activation-runtime-prerequisite-result-v1"
    )
    record: WorkerActivationRuntimePrerequisiteV1
    status: WorkerActivationRuntimePrerequisiteStatusV1
    exact_duplicate: bool = False
    worker_activation_runtime_prerequisite_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteResultV1:
        if self.status != derive_status(
            self.record, evaluated_at=self.status.evaluated_at
        ):
            raise ValueError("result linkage mismatch")
        return self


class WorkerActivationRuntimePrerequisiteCollectionV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-collection-v1"] = (
        "worker-activation-runtime-prerequisite-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[WorkerActivationRuntimePrerequisiteV1, ...]
    count: int
    collection_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteCollectionV1:
        if self.count != len(self.items) or not 0 <= self.count <= 16:
            raise ValueError("collection bound mismatch")
        if len({item.prerequisite_id for item in self.items}) != self.count or any(
            item.operator_id != self.operator_id
            or item.candidate_record_id != self.candidate_record_id
            for item in self.items
        ):
            raise ValueError("collection linkage mismatch")
        if self.collection_fingerprint != collection_fingerprint(self):
            raise ValueError("collection fingerprint mismatch")
        return self


def collection_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("collection", value, "collection_fingerprint")


def reservation_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("reservation", value, "reservation_fingerprint")


def audit_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("audit", value, "audit_fingerprint")


class WorkerActivationRuntimePrerequisiteSubjectReservationV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-reservation-v1"] = (
        "worker-activation-runtime-prerequisite-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    admission_id: CanonicalUuid5
    reserved_at: UtcSecond
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteSubjectReservationV1:
        if self.subject_fingerprint != subject_fingerprint(
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            admission_id=self.admission_id,
        ) or self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("reservation fingerprint mismatch")
        return self


class WorkerActivationRuntimePrerequisiteAuditEvidenceV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-audit-v1"] = (
        "worker-activation-runtime-prerequisite-audit-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    occurred_at: UtcSecond
    outcome: Literal["recorded", "indeterminate"]
    subject_fingerprint: FingerprintV1
    correlation_fingerprint: FingerprintV1
    prerequisite_record_fingerprint: FingerprintV1 | None
    worker_activation_runtime_prerequisite_recorded: bool
    audit_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePrerequisiteAuditEvidenceV1:
        success = self.outcome == "recorded"
        if (
            self.worker_activation_runtime_prerequisite_recorded != success
            or (self.prerequisite_record_fingerprint is not None) != success
            or self.audit_fingerprint != audit_fingerprint(self)
        ):
            raise ValueError("audit shape or fingerprint mismatch")
        return self


class WorkerActivationRuntimePrerequisiteRedactedErrorV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-prerequisite-error-v1"] = (
        "worker-activation-runtime-prerequisite-error-v1"
    )
    error_code: (
        RefusalV1
        | Literal[
            "unauthenticated",
            "forbidden",
            "store_corrupt",
            "unavailable",
            "quota_exceeded",
            "record_too_large",
            "idempotency_conflict",
            "permanent_subject_reserved",
            "append_indeterminate",
        ]
    )
    message: Literal[SAFE_MESSAGE] = SAFE_MESSAGE
    correlation_fingerprint: FingerprintV1
    retryable: Literal[False] = False
    redacted: Literal[True] = True
    worker_activation_runtime_prerequisite_recorded: Literal[False] = False


def build_create(
    *,
    receipt: v052.ControlledWorkerQueueClaimLeaseAcknowledgementV1,
    receipt_status: v052.ControlledWorkerQueueClaimLeaseAcknowledgementStatusV1,
) -> WorkerActivationRuntimePrerequisiteCreateV1:
    return WorkerActivationRuntimePrerequisiteCreateV1(
        admission_id=receipt.admission_id,
        valid_until=receipt.valid_until,
        receipt_record_fingerprint=receipt.receipt_record_fingerprint,
        status_fingerprint=receipt_status.status_fingerprint,
    )


def build_prerequisite(
    validation: WorkerActivationRuntimePrerequisiteValidationInputV1,
    *,
    idempotency_key: str,
) -> WorkerActivationRuntimePrerequisiteV1:
    validation = WorkerActivationRuntimePrerequisiteValidationInputV1.model_validate(
        validation
    )
    subject = subject_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        admission_id=validation.create.admission_id,
    )
    return _signed(
        WorkerActivationRuntimePrerequisiteV1,
        {
            "prerequisite_id": derived_prerequisite_id(subject),
            "operator_id": validation.operator_id,
            "candidate_record_id": validation.candidate_record_id,
            "admission_id": validation.create.admission_id,
            "recorded_at": validation.authority.request_received_at,
            "valid_until": validation.create.valid_until,
            "controlled_worker_queue_claim_lease_acknowledgement": (
                validation.controlled_worker_queue_claim_lease_acknowledgement
            ),
            "controlled_worker_queue_claim_lease_acknowledgement_status": (
                validation.controlled_worker_queue_claim_lease_acknowledgement_status
            ),
            "subject_fingerprint": subject,
            "idempotency_key_fingerprint": idempotency_key_fingerprint(
                validation.operator_id, idempotency_key
            ),
        },
        "prerequisite_record_fingerprint",
        prerequisite_record_fingerprint,
    )


def derive_status(
    record: WorkerActivationRuntimePrerequisiteV1, *, evaluated_at: str
) -> WorkerActivationRuntimePrerequisiteStatusV1:
    record = WorkerActivationRuntimePrerequisiteV1.model_validate(record)
    return _signed(
        WorkerActivationRuntimePrerequisiteStatusV1,
        {
            **{
                name: getattr(record, name)
                for name in (
                    "prerequisite_id",
                    "operator_id",
                    "candidate_record_id",
                    "admission_id",
                    "recorded_at",
                    "valid_until",
                    "prerequisite_record_fingerprint",
                )
            },
            "evaluated_at": evaluated_at,
            "lifecycle": "expired" if evaluated_at >= record.valid_until else "active",
        },
        "status_fingerprint",
        status_fingerprint,
    )


class StrictContractError(ValueError):
    pass


def parse_create_json(data: str | bytes) -> WorkerActivationRuntimePrerequisiteCreateV1:
    try:
        if len(data) > MAX_CREATE_BYTES:
            raise ValueError("oversized")
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        if (
            len(text.encode("utf-8")) > MAX_CREATE_BYTES
            or unicodedata.normalize("NFC", text) != text
        ):
            raise ValueError("encoding")
        raw = json.loads(text, object_pairs_hook=_unique_keys)
        return WorkerActivationRuntimePrerequisiteCreateV1.model_validate(raw)
    except (ValueError, TypeError, RecursionError):
        raise StrictContractError(SAFE_MESSAGE) from None


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result
