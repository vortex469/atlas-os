"""Pure v0.56 Worker Activation Runtime Plan Review evidence contract.

All facts are injected. No persistence, clock reads, queue/worker contact or
runtime effects occur here. The complete immutable v0.55 pair preserves lineage.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import timedelta
from typing import Any, ClassVar, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.execution_permission_grant.contract import (
    CanonicalUuid5,
    OperatorId,
    canonical_json,
)
from app.installation_execution_admission.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.worker_activation_runtime_plan import contract as v055

MAX_MODEL_BYTES = 192 * 1024
MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.worker_activation_runtime_plan_review.evaluate"
SCOPE = "worker_activation_runtime_plan_review_only"
MARKER = "worker_activation_runtime_plan_review_recorded"
SUCCESS_BLOCKERS = v055.SUCCESS_BLOCKERS
PROFILE = "core_owned_reference_only_runtime_plan_review_v1"
FindingV1 = Literal[
    "exact_plan_lineage",
    "fixed_design_consistent",
    "unresolved_interfaces_preserved",
]
SUCCESS_FINDINGS = get_args(FindingV1)
SAFE_MESSAGE = "worker activation runtime plan review request could not be completed"

RefusalV1 = Literal[
    "invalid_request",
    "evidence_not_found",
    "installation_capability_unsupported",
    "ambiguous_state",
    "fingerprint_mismatch",
    "linkage_mismatch",
    "evidence_stale",
    "evidence_expired",
    "v055_plan_not_active",
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
    _json_byte_limit: ClassVar[int] = MAX_MODEL_BYTES
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )

    @classmethod
    def model_validate_json(
        cls, json_data: str | bytes | bytearray, **kwargs: Any
    ) -> Any:
        # Pydantic's default JSON decoder accepts duplicate keys. Stored evidence
        # must use the same strict decoding as requests, without altering strings.
        if not isinstance(json_data, str | bytes | bytearray):
            raise TypeError("invalid JSON input type")
        encoded = json_data.encode("utf-8") if isinstance(json_data, str) else json_data
        if len(encoded) > cls._json_byte_limit:
            raise ValueError("contract envelope exceeds bound")
        raw = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_keys)
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


class ClosedAuthorityV1(ContractModel, v055.ClosedAuthorityV1):
    """The complete unchanged v0.55 authority ceiling."""


class WorkerActivationRuntimePlanReviewCreateV1(ClosedAuthorityV1):
    _json_byte_limit: ClassVar[int] = MAX_CREATE_BYTES
    schema: Literal["worker-activation-runtime-plan-review-create-v1"] = (
        "worker-activation-runtime-plan-review-create-v1"
    )
    runtime_plan_id: CanonicalUuid5
    valid_until: UtcSecond
    runtime_plan_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def bounded(self) -> WorkerActivationRuntimePlanReviewCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create envelope exceeds bound")
        return self


class WorkerActivationRuntimePlanReviewAuthorityContextV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-authority-context-v1"] = (
        "worker-activation-runtime-plan-review-authority-context-v1"
    )
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True]
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
    record: v055.WorkerActivationRuntimePlanV1,
    status: v055.WorkerActivationRuntimePlanStatusV1,
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerActivationRuntimePlanReviewCreateV1,
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
        create.runtime_plan_id != record.runtime_plan_id
        or status.runtime_plan_id != record.runtime_plan_id
        or create.valid_until != record.valid_until
        or status.valid_until != record.valid_until
    ):
        raise _Refusal("linkage_mismatch")
    if (
        create.runtime_plan_record_fingerprint != record.runtime_plan_record_fingerprint
        or create.status_fingerprint != status.status_fingerprint
        or status.runtime_plan_record_fingerprint
        != record.runtime_plan_record_fingerprint
        or record.runtime_plan_record_fingerprint
        != v055.runtime_plan_record_fingerprint(record)
        or status.status_fingerprint != v055.status_fingerprint(status)
    ):
        raise _Refusal("fingerprint_mismatch")
    if status.lifecycle != "active":
        raise _Refusal("v055_plan_not_active")
    instant = v055.v054.v053.v052._instant(now)
    if any(
        v055.v054.v053.v052._instant(start) > instant
        or instant - v055.v054.v053.v052._instant(start)
        > timedelta(seconds=MAX_FRESHNESS_SECONDS)
        for start in (record.recorded_at, status.evaluated_at)
    ):
        raise _Refusal("evidence_stale")
    if status.evaluated_at < record.recorded_at:
        raise _Refusal("evidence_stale")
    if now >= record.valid_until:
        raise _Refusal("evidence_expired")
    if record.design != v055.WorkerActivationRuntimePlanDesignV1():
        raise _Refusal("invalid_request")
    if v055.derive_status(record, evaluated_at=now).lifecycle != "active":
        raise _Refusal("v055_plan_not_active")
    # Canonical status also binds every authority/material flag and receipt marker.
    if status != v055.derive_status(record, evaluated_at=status.evaluated_at):
        raise _Refusal("invalid_request")
    for item in (record, status):
        if any(
            getattr(item, name)
            for name in type(item).model_fields
            if name.endswith("_material_present")
        ):
            raise _Refusal("invalid_request")


class WorkerActivationRuntimePlanReviewValidationInputV1(ContractModel):
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    authority: WorkerActivationRuntimePlanReviewAuthorityContextV1
    create: WorkerActivationRuntimePlanReviewCreateV1
    worker_activation_runtime_plan: v055.WorkerActivationRuntimePlanV1
    worker_activation_runtime_plan_status: v055.WorkerActivationRuntimePlanStatusV1
    home_assistant: bool = False
    ambiguous_prerequisite_count: Literal[0] = 0
    boundary_enabled: Literal[False] = False
    # Required trusted Core facts: absence is not proof of no prior reservation.
    subject_previously_reserved: Literal[False]
    idempotency_key_previously_reserved: Literal[False]

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewValidationInputV1:
        if self.home_assistant:
            raise _Refusal("installation_capability_unsupported")
        if self.operator_id != self.authority.authenticated_operator_id:
            raise _Refusal("evidence_not_found")
        _validate_pair(
            self.worker_activation_runtime_plan,
            self.worker_activation_runtime_plan_status,
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            create=self.create,
            now=self.authority.request_received_at,
        )
        return self


def fingerprint(kind: str, value: Any) -> FingerprintV1:
    return v055.v054.v053.v052.fingerprint(
        f"atlas:worker-activation-runtime-plan-review-{kind}:v1", value
    )


def _model_fingerprint(kind: str, value: BaseModel | dict, field: str) -> FingerprintV1:
    raw = _plain(value)
    raw.pop(field, None)
    return fingerprint(kind, raw)


def evaluation_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("evaluation", value, "evaluation_fingerprint")


def runtime_plan_review_record_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("record", value, "runtime_plan_review_record_fingerprint")


def status_fingerprint(value: BaseModel | dict) -> FingerprintV1:
    return _model_fingerprint("status", value, "status_fingerprint")


def subject_fingerprint(
    *, operator_id: str, candidate_record_id: str, runtime_plan_id: str
) -> FingerprintV1:
    """Permanent subject deliberately excludes mutable expiry/status/request/key."""
    return fingerprint(
        "subject",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "runtime_plan_id": runtime_plan_id,
        },
    )


def idempotency_key_fingerprint(operator_id: str, key: str) -> FingerprintV1:
    return fingerprint(
        "idempotency-key",
        {"operator_id": operator_id, "key": v055.v054.v053.v052._visible(key)},
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: WorkerActivationRuntimePlanReviewCreateV1,
) -> FingerprintV1:
    create = WorkerActivationRuntimePlanReviewCreateV1.model_validate(create)
    return fingerprint(
        "request",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
        },
    )


def derived_runtime_plan_review_id(subject: FingerprintV1) -> str:
    return v055.v054.v053.v052.derived_uuid5(
        "atlas:worker-activation-runtime-plan-review-id:v1", subject
    )


class WorkerActivationRuntimePlanReviewEvaluationV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-evaluation-v1"] = (
        "worker-activation-runtime-plan-review-evaluation-v1"
    )
    profile: Literal[PROFILE] = PROFILE
    findings: tuple[FindingV1, ...]
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    review_state: Literal["recorded", "blocked"]
    eligibility: Literal[MARKER, "blocked"]
    blockers: tuple[v055.v054.v053.v052.BlockerV1 | RefusalV1, ...]
    recognized_v055_plan_count: int
    worker_activation_runtime_plan_recorded: bool
    worker_activation_runtime_plan_review_recorded: bool
    evaluation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewEvaluationV1:
        success = self.review_state == "recorded"
        if (
            self.worker_activation_runtime_plan_review_recorded != success
            or self.worker_activation_runtime_plan_recorded != success
            or self.eligibility != (MARKER if success else "blocked")
            or self.recognized_v055_plan_count != int(success)
        ):
            raise ValueError("evaluation shape mismatch")
        if success:
            if (
                self.blockers != SUCCESS_BLOCKERS
                or self.findings != SUCCESS_FINDINGS
                or self.earliest_expiry is None
            ):
                raise ValueError("success blockers or expiry mismatch")
            if not (
                v055.v054.v053.v052._instant(self.evaluated_at)
                < v055.v054.v053.v052._instant(self.earliest_expiry)
                <= v055.v054.v053.v052._instant(self.evaluated_at)
                + timedelta(seconds=30)
            ):
                raise ValueError("evaluation expiry mismatch")
        elif (
            self.earliest_expiry is not None
            or self.findings != ()
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


def evaluate_worker_activation_runtime_plan_review(
    value: Any,
) -> WorkerActivationRuntimePlanReviewEvaluationV1:
    """Deterministic redacted refusal; never echoes invalid caller material."""
    code: RefusalV1 = "invalid_request"
    try:
        raw = _plain(value)
        if not isinstance(raw, dict) or any(
            raw.get(name) is None
            for name in (
                "worker_activation_runtime_plan",
                "worker_activation_runtime_plan_status",
            )
        ):
            code = "evidence_not_found"
            raise _Refusal(code)
        validation = WorkerActivationRuntimePlanReviewValidationInputV1.model_validate(
            raw
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
            WorkerActivationRuntimePlanReviewEvaluationV1,
            {
                "operator_id": "blocked-evaluation",
                "candidate_record_id": "00000000-0000-4000-8000-000000000000",
                "evaluated_at": "1970-01-01T00:00:00Z",
                "earliest_expiry": None,
                "review_state": "blocked",
                "findings": (),
                "eligibility": "blocked",
                "blockers": (code,),
                "recognized_v055_plan_count": 0,
                "worker_activation_runtime_plan_recorded": False,
                "worker_activation_runtime_plan_review_recorded": False,
            },
            "evaluation_fingerprint",
            evaluation_fingerprint,
        )
    return _signed(
        WorkerActivationRuntimePlanReviewEvaluationV1,
        {
            "operator_id": validation.operator_id,
            "candidate_record_id": validation.candidate_record_id,
            "evaluated_at": validation.authority.request_received_at,
            "earliest_expiry": validation.create.valid_until,
            "review_state": "recorded",
            "findings": SUCCESS_FINDINGS,
            "eligibility": MARKER,
            "blockers": SUCCESS_BLOCKERS,
            "recognized_v055_plan_count": 1,
            "worker_activation_runtime_plan_recorded": True,
            "worker_activation_runtime_plan_review_recorded": True,
        },
        "evaluation_fingerprint",
        evaluation_fingerprint,
    )


class WorkerActivationRuntimePlanReviewV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-v1"] = (
        "worker-activation-runtime-plan-review-v1"
    )
    runtime_plan_review_id: CanonicalUuid5
    runtime_admission_id: CanonicalUuid5
    prerequisite_id: CanonicalUuid5
    admission_id: CanonicalUuid5
    profile: Literal[PROFILE] = PROFILE
    findings: tuple[FindingV1, ...] = SUCCESS_FINDINGS
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runtime_plan_id: CanonicalUuid5
    recorded_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active"] = "active"
    eligibility: Literal[MARKER] = MARKER
    blockers: tuple[v055.v054.v053.v052.BlockerV1, ...] = SUCCESS_BLOCKERS
    worker_activation_runtime_plan: v055.WorkerActivationRuntimePlanV1
    worker_activation_runtime_plan_status: v055.WorkerActivationRuntimePlanStatusV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    runtime_plan_review_record_fingerprint: FingerprintV1
    worker_activation_runtime_plan_recorded: Literal[True] = True
    worker_activation_runtime_plan_review_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewV1:
        receipt = self.worker_activation_runtime_plan
        status = self.worker_activation_runtime_plan_status
        _validate_pair(
            receipt,
            status,
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            create=build_create(receipt=receipt, receipt_status=status),
            now=self.recorded_at,
        )
        if (
            self.runtime_plan_id != receipt.runtime_plan_id
            or self.runtime_admission_id != receipt.runtime_admission_id
            or self.prerequisite_id != receipt.prerequisite_id
            or self.admission_id != receipt.admission_id
            or not self.recorded_at < self.valid_until == receipt.valid_until
            or v055.v054.v053.v052._instant(self.valid_until)
            > v055.v054.v053.v052._instant(self.recorded_at)
            + timedelta(seconds=MAX_FRESHNESS_SECONDS)
            or self.blockers != SUCCESS_BLOCKERS
            or self.findings != SUCCESS_FINDINGS
        ):
            raise ValueError("record linkage, expiry or blockers mismatch")
        if self.subject_fingerprint != subject_fingerprint(
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            runtime_plan_id=self.runtime_plan_id,
        ) or self.runtime_plan_review_id != derived_runtime_plan_review_id(
            self.subject_fingerprint
        ):
            raise ValueError("subject or id mismatch")
        if (
            self.runtime_plan_review_record_fingerprint
            != runtime_plan_review_record_fingerprint(self)
        ):
            raise ValueError("record fingerprint mismatch")
        return self


class WorkerActivationRuntimePlanReviewStatusV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-status-v1"] = (
        "worker-activation-runtime-plan-review-status-v1"
    )
    runtime_plan_review_id: CanonicalUuid5
    runtime_admission_id: CanonicalUuid5
    prerequisite_id: CanonicalUuid5
    admission_id: CanonicalUuid5
    profile: Literal[PROFILE] = PROFILE
    findings: tuple[FindingV1, ...] = SUCCESS_FINDINGS
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runtime_plan_id: CanonicalUuid5
    recorded_at: UtcSecond
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal[MARKER] = MARKER
    blockers: tuple[v055.v054.v053.v052.BlockerV1, ...] = SUCCESS_BLOCKERS
    runtime_plan_review_record_fingerprint: FingerprintV1
    status_fingerprint: FingerprintV1
    worker_activation_runtime_plan_recorded: Literal[True] = True
    worker_activation_runtime_plan_review_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewStatusV1:
        if self.runtime_plan_review_id != derived_runtime_plan_review_id(
            subject_fingerprint(
                operator_id=self.operator_id,
                candidate_record_id=self.candidate_record_id,
                runtime_plan_id=self.runtime_plan_id,
            )
        ):
            raise ValueError("status identity mismatch")
        if (
            self.blockers != SUCCESS_BLOCKERS
            or self.findings != SUCCESS_FINDINGS
            or self.evaluated_at < self.recorded_at
            or not (
                v055.v054.v053.v052._instant(self.recorded_at)
                < v055.v054.v053.v052._instant(self.valid_until)
                <= v055.v054.v053.v052._instant(self.recorded_at)
                + timedelta(seconds=30)
            )
            or self.lifecycle
            != ("expired" if self.evaluated_at >= self.valid_until else "active")
        ):
            raise ValueError("status lifecycle mismatch")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("status fingerprint mismatch")
        return self


class WorkerActivationRuntimePlanReviewResultV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-result-v1"] = (
        "worker-activation-runtime-plan-review-result-v1"
    )
    record: WorkerActivationRuntimePlanReviewV1
    status: WorkerActivationRuntimePlanReviewStatusV1
    exact_duplicate: bool = False
    worker_activation_runtime_plan_recorded: Literal[True] = True
    worker_activation_runtime_plan_review_recorded: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewResultV1:
        if self.status != derive_status(
            self.record, evaluated_at=self.status.evaluated_at
        ):
            raise ValueError("result linkage mismatch")
        return self


class WorkerActivationRuntimePlanReviewCollectionV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-collection-v1"] = (
        "worker-activation-runtime-plan-review-collection-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    items: tuple[WorkerActivationRuntimePlanReviewV1, ...]
    count: int
    collection_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewCollectionV1:
        if self.count != len(self.items) or not 0 <= self.count <= 16:
            raise ValueError("collection bound mismatch")
        if len(
            {item.runtime_plan_review_id for item in self.items}
        ) != self.count or any(
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


class WorkerActivationRuntimePlanReviewSubjectReservationV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-reservation-v1"] = (
        "worker-activation-runtime-plan-review-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    runtime_plan_id: CanonicalUuid5
    reserved_at: UtcSecond
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    reservation_fingerprint: FingerprintV1
    permanent: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewSubjectReservationV1:
        if self.subject_fingerprint != subject_fingerprint(
            operator_id=self.operator_id,
            candidate_record_id=self.candidate_record_id,
            runtime_plan_id=self.runtime_plan_id,
        ) or self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("reservation fingerprint mismatch")
        return self


class WorkerActivationRuntimePlanReviewAuditEvidenceV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-audit-v1"] = (
        "worker-activation-runtime-plan-review-audit-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    occurred_at: UtcSecond
    outcome: Literal["recorded", "indeterminate"]
    subject_fingerprint: FingerprintV1
    correlation_fingerprint: FingerprintV1
    runtime_plan_review_record_fingerprint: FingerprintV1 | None
    worker_activation_runtime_plan_recorded: bool
    worker_activation_runtime_plan_review_recorded: bool
    audit_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> WorkerActivationRuntimePlanReviewAuditEvidenceV1:
        success = self.outcome == "recorded"
        if (
            self.worker_activation_runtime_plan_review_recorded != success
            or self.worker_activation_runtime_plan_recorded != success
            or (self.runtime_plan_review_record_fingerprint is not None) != success
            or self.audit_fingerprint != audit_fingerprint(self)
        ):
            raise ValueError("audit shape or fingerprint mismatch")
        return self


class WorkerActivationRuntimePlanReviewRedactedErrorV1(ClosedAuthorityV1):
    schema: Literal["worker-activation-runtime-plan-review-error-v1"] = (
        "worker-activation-runtime-plan-review-error-v1"
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
    worker_activation_runtime_plan_review_recorded: Literal[False] = False


def build_create(
    *,
    receipt: v055.WorkerActivationRuntimePlanV1,
    receipt_status: v055.WorkerActivationRuntimePlanStatusV1,
) -> WorkerActivationRuntimePlanReviewCreateV1:
    return WorkerActivationRuntimePlanReviewCreateV1(
        runtime_plan_id=receipt.runtime_plan_id,
        valid_until=receipt.valid_until,
        runtime_plan_record_fingerprint=receipt.runtime_plan_record_fingerprint,
        status_fingerprint=receipt_status.status_fingerprint,
    )


def build_runtime_plan_review(
    validation: WorkerActivationRuntimePlanReviewValidationInputV1,
    *,
    idempotency_key: str,
) -> WorkerActivationRuntimePlanReviewV1:
    validation = WorkerActivationRuntimePlanReviewValidationInputV1.model_validate(
        validation
    )
    subject = subject_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        runtime_plan_id=validation.create.runtime_plan_id,
    )
    return _signed(
        WorkerActivationRuntimePlanReviewV1,
        {
            "runtime_plan_review_id": derived_runtime_plan_review_id(subject),
            "runtime_admission_id": validation.worker_activation_runtime_plan.runtime_admission_id,
            "prerequisite_id": validation.worker_activation_runtime_plan.prerequisite_id,
            "admission_id": validation.worker_activation_runtime_plan.admission_id,
            "operator_id": validation.operator_id,
            "candidate_record_id": validation.candidate_record_id,
            "runtime_plan_id": validation.create.runtime_plan_id,
            "recorded_at": validation.authority.request_received_at,
            "valid_until": validation.create.valid_until,
            "worker_activation_runtime_plan": (
                validation.worker_activation_runtime_plan
            ),
            "worker_activation_runtime_plan_status": (
                validation.worker_activation_runtime_plan_status
            ),
            "subject_fingerprint": subject,
            "idempotency_key_fingerprint": idempotency_key_fingerprint(
                validation.operator_id, idempotency_key
            ),
        },
        "runtime_plan_review_record_fingerprint",
        runtime_plan_review_record_fingerprint,
    )


def derive_status(
    record: WorkerActivationRuntimePlanReviewV1, *, evaluated_at: str
) -> WorkerActivationRuntimePlanReviewStatusV1:
    record = WorkerActivationRuntimePlanReviewV1.model_validate(record)
    return _signed(
        WorkerActivationRuntimePlanReviewStatusV1,
        {
            **{
                name: getattr(record, name)
                for name in (
                    "runtime_plan_review_id",
                    "runtime_admission_id",
                    "prerequisite_id",
                    "admission_id",
                    "operator_id",
                    "candidate_record_id",
                    "runtime_plan_id",
                    "recorded_at",
                    "valid_until",
                    "runtime_plan_review_record_fingerprint",
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


def parse_create_json(data: str | bytes) -> WorkerActivationRuntimePlanReviewCreateV1:
    try:
        if not isinstance(data, str | bytes):
            raise TypeError("invalid JSON input type")
        if len(data) > MAX_CREATE_BYTES:
            raise ValueError("oversized")
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        if (
            len(text.encode("utf-8")) > MAX_CREATE_BYTES
            or unicodedata.normalize("NFC", text) != text
        ):
            raise ValueError("encoding")
        raw = json.loads(text, object_pairs_hook=_unique_keys)
        return WorkerActivationRuntimePlanReviewCreateV1.model_validate(raw)
    except (ValueError, TypeError, RecursionError):
        raise StrictContractError(SAFE_MESSAGE) from None


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result
