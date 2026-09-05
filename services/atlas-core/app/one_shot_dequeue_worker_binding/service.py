"""Explicit Core-local v0.46 one-shot dequeue worker binding evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.one_shot_controlled_dequeue.contract import (
    OneShotControlledDequeueReceiptV1,
    OneShotControlledDequeueStatusV1,
)
from app.worker_intake_admission.contract import (
    WorkerIntakeAdmissionStatusV1,
    WorkerIntakeAdmissionV1,
)

from .contract import (
    PERMISSION,
    OneShotDequeueWorkerBindingAuthorityContextV1,
    OneShotDequeueWorkerBindingCollectionV1,
    OneShotDequeueWorkerBindingCreateV1,
    OneShotDequeueWorkerBindingRedactedErrorV1,
    OneShotDequeueWorkerBindingResultV1,
    OneShotDequeueWorkerBindingV1,
    OneShotDequeueWorkerBindingValidationInputV1,
    OperatorId,
    build_audit,
    build_binding,
    build_collection,
    build_reservations,
    derive_status,
    evaluate_one_shot_dequeue_worker_binding,
    idempotency_key_fingerprint,
    opaque_fingerprint,
    request_fingerprint,
)
from .store import (
    OneShotDequeueWorkerBindingStore,
    OneShotDequeueWorkerBindingStoreError,
)


class OneShotDequeueWorkerBindingDequeueReader(Protocol):
    """Read exact owner-scoped v0.45 dequeue evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        one_shot_controlled_dequeue_id: str,
        one_shot_controlled_dequeue_valid_until: str,
    ) -> tuple[OneShotControlledDequeueReceiptV1, OneShotControlledDequeueStatusV1] | None: ...


class OneShotDequeueWorkerBindingWorkerReader(Protocol):
    """Read exact owner-scoped v0.40 worker intake evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        worker_intake_admission_id: str,
        worker_intake_admission_valid_until: str,
    ) -> tuple[WorkerIntakeAdmissionV1, WorkerIntakeAdmissionStatusV1] | None: ...


class OneShotDequeueWorkerBindingService:
    """Create/get/list bounded evidence; no worker or runtime contact exists."""

    def __init__(
        self,
        *,
        dequeue_reader: OneShotDequeueWorkerBindingDequeueReader,
        worker_reader: OneShotDequeueWorkerBindingWorkerReader,
        store: OneShotDequeueWorkerBindingStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ) -> None:
        self._dequeue_reader = dequeue_reader
        self._worker_reader = worker_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled

    def create(
        self,
        create: OneShotDequeueWorkerBindingCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OneShotDequeueWorkerBindingResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        if not self._enabled:
            return _failure("installation_capability_unsupported", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = OneShotDequeueWorkerBindingCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            received_at = self._server_now()
            idem = idempotency_key_fingerprint(operator, idempotency_key)
            request_fp = request_fingerprint(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                request_received_at=received_at,
                idempotency_fingerprint=idem,
            )
        except Exception:  # noqa: BLE001 - details remain redacted
            return _failure("invalid_request", correlation_id)

        try:
            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                request_fingerprint=request_fp.value,
                v045_dequeue_valid_until=(
                    exact_create.one_shot_controlled_dequeue_valid_until
                ),
                v040_worker_intake_valid_until=(
                    exact_create.worker_intake_admission_valid_until
                ),
            )
            if existing is not None:
                return _success(existing, correlation_id, self._server_now())
        except OneShotDequeueWorkerBindingStoreError as error:
            if error.code == "append_indeterminate":
                return _failure(
                    "append_indeterminate", correlation_id, outcome="indeterminate"
                )
            if error.code in {"idempotency_conflict", "store_corrupt"}:
                return _failure(error.code, correlation_id)
            return _failure("internal_error", correlation_id)

        try:
            dequeue_evidence = self._dequeue_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                one_shot_controlled_dequeue_id=(
                    exact_create.one_shot_controlled_dequeue_id
                ),
                one_shot_controlled_dequeue_valid_until=(
                    exact_create.one_shot_controlled_dequeue_valid_until
                ),
            )
            worker_evidence = self._worker_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                worker_intake_admission_id=exact_create.worker_intake_admission_id,
                worker_intake_admission_valid_until=(
                    exact_create.worker_intake_admission_valid_until
                ),
            )
            if dequeue_evidence is None or worker_evidence is None:
                return _failure("not_found", correlation_id)
            dequeue, dequeue_status = dequeue_evidence
            worker, worker_status = worker_evidence
            authority = OneShotDequeueWorkerBindingAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=received_at,
            )
            validation = OneShotDequeueWorkerBindingValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                one_shot_controlled_dequeue=dequeue,
                one_shot_controlled_dequeue_status=dequeue_status,
                worker_intake_admission=worker,
                worker_intake_admission_status=worker_status,
                idempotency_key=idempotency_key,
            )
            evaluation = evaluate_one_shot_dequeue_worker_binding(validation)
            if not evaluation.binding_record_build_allowed:
                return _failure(evaluation.blockers[0], correlation_id)
            record = build_binding(validation)
            idempotency, reservation = build_reservations(validation, record)
            audit = build_audit(
                record,
                event="one_shot_dequeue_worker_binding_recorded",
                outcome="recorded",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                occurred_at=received_at,
            )
            stored, _created = self._store.append(
                record=record,
                idempotency_reservation=idempotency,
                subject_reservation=reservation,
                audit_evidence=audit,
                v045_dequeue_valid_until=(
                    exact_create.one_shot_controlled_dequeue_valid_until
                ),
                v040_worker_intake_valid_until=(
                    exact_create.worker_intake_admission_valid_until
                ),
            )
            return _success(stored, correlation_id, received_at)
        except OneShotDequeueWorkerBindingStoreError as error:
            if error.code == "append_indeterminate":
                return _failure(
                    "append_indeterminate", correlation_id, outcome="indeterminate"
                )
            code = (
                error.code
                if error.code
                in {
                    "conflict",
                    "idempotency_conflict",
                    "permanent_subject_reserved",
                    "quota_exceeded",
                    "record_too_large",
                    "store_corrupt",
                    "reservation_before_effect_failed",
                }
                else "internal_error"
            )
            return _failure(code, correlation_id)
        except (TypeError, ValueError) as error:
            return _validation_failure(str(error), correlation_id)
        except Exception:  # noqa: BLE001 - injected dependency details are redacted
            return _failure("internal_error", correlation_id)

    def get(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        binding_id: str,
        correlation_id: str,
    ) -> OneShotDequeueWorkerBindingResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(operator_id=operator, binding_id=binding_id)
            return _success(record, correlation_id, self._server_now())
        except OneShotDequeueWorkerBindingStoreError as error:
            code = (
                error.code
                if error.code in {"not_found", "store_corrupt"}
                else "internal_error"
            )
            return _failure(code, correlation_id)
        except Exception:  # noqa: BLE001 - read details remain redacted
            return _failure("internal_error", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        correlation_id: str,
    ) -> OneShotDequeueWorkerBindingCollectionV1 | tuple[OneShotDequeueWorkerBindingResultV1, ...]:
        if authenticated_operator_id is None:
            return (_failure("unauthenticated", correlation_id),)
        if not permission_verified:
            return (_failure("forbidden", correlation_id),)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            return build_collection(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                items=self._store.list_owned(
                    operator_id=operator,
                    candidate_record_id=candidate_record_id,
                ),
            )
        except Exception:  # noqa: BLE001 - listing details remain redacted
            return (_failure("internal_error", correlation_id),)

    def _server_now(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trusted Core clock must be timezone-aware")
        exact = value.astimezone(UTC)
        if exact.microsecond:
            raise ValueError("trusted Core clock must return whole seconds")
        return exact.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_one_shot_dequeue_worker_binding_service(
    *,
    dequeue_reader: OneShotDequeueWorkerBindingDequeueReader,
    worker_reader: OneShotDequeueWorkerBindingWorkerReader,
    store: OneShotDequeueWorkerBindingStore,
    clock: Callable[[], datetime],
    enabled: bool = False,
) -> OneShotDequeueWorkerBindingService:
    """Explicit P2 construction; no production composition calls this."""
    return OneShotDequeueWorkerBindingService(
        dequeue_reader=dequeue_reader,
        worker_reader=worker_reader,
        store=store,
        clock=clock,
        enabled=enabled,
    )


def _success(
    record: OneShotDequeueWorkerBindingV1,
    correlation_id: str,
    evaluated_at: str,
) -> OneShotDequeueWorkerBindingResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return OneShotDequeueWorkerBindingResultV1(
        ok=True,
        outcome="success",
        record=record,
        status=derive_status(record, evaluated_at=evaluated_at),
        error=None,
        correlation_fingerprint=correlation,
        one_shot_dequeue_worker_binding_recorded=True,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:one-shot-dequeue-worker-binding-correlation:v1", safe)


def _validation_failure(
    message: str, correlation_id: str
) -> OneShotDequeueWorkerBindingResultV1:
    lowered = message.lower()
    if "home assistant" in lowered or "capability" in lowered:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in lowered:
        return _failure("not_found", correlation_id)
    if "not active" in lowered and "v0.45" in lowered:
        return _failure("v045_dequeue_not_active", correlation_id)
    if "not successful" in lowered and "v0.45" in lowered:
        return _failure("v045_dequeue_not_successful", correlation_id)
    if "not recorded" in lowered and "v0.45" in lowered:
        return _failure("v045_dequeue_not_recorded", correlation_id)
    if "not active" in lowered and "v0.40" in lowered:
        return _failure("v040_worker_intake_not_active", correlation_id)
    if "not recorded" in lowered and "v0.40" in lowered:
        return _failure("v040_worker_intake_not_recorded", correlation_id)
    if "stale" in lowered or "future" in lowered:
        return _failure("evidence_stale", correlation_id)
    if "expired" in lowered:
        return _failure("evidence_expired", correlation_id)
    if "ambiguous" in lowered:
        return _failure("ambiguous_state", correlation_id)
    if "worker subject" in lowered:
        return _failure("worker_subject_mismatch", correlation_id)
    if "queue item reference" in lowered:
        return _failure("queue_item_reference_mismatch", correlation_id)
    if "fingerprint" in lowered:
        return _failure("fingerprint_mismatch", correlation_id)
    if "limits" in lowered:
        return _failure("inherited_limits_mismatch", correlation_id)
    if "credential" in lowered:
        return _failure("caller_supplied_credential", correlation_id)
    if "endpoint" in lowered:
        return _failure("caller_supplied_endpoint", correlation_id)
    if "command" in lowered:
        return _failure("caller_supplied_command", correlation_id)
    if "authority" in lowered:
        return _failure("unsupported_authority", correlation_id)
    if "linkage" in lowered:
        return _failure("linkage_mismatch", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(
    error_code: str,
    correlation_id: str,
    *,
    outcome: str = "failure",
) -> OneShotDequeueWorkerBindingResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return OneShotDequeueWorkerBindingResultV1(
        ok=False,
        outcome=outcome,
        record=None,
        status=None,
        error=OneShotDequeueWorkerBindingRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )


__all__ = (
    "OneShotDequeueWorkerBindingDequeueReader",
    "OneShotDequeueWorkerBindingService",
    "OneShotDequeueWorkerBindingWorkerReader",
    "create_one_shot_dequeue_worker_binding_service",
)
