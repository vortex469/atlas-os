"""Explicit Core-local v0.44 controlled dequeue admission evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.queue_observation_receipt.contract import (
    QueueObservationReceiptStatusV1,
    QueueObservationReceiptV1,
)

from .contract import (
    PERMISSION,
    ControlledDequeueAdmissionAuthorityContextV1,
    ControlledDequeueAdmissionCollectionV1,
    ControlledDequeueAdmissionCreateV1,
    ControlledDequeueAdmissionRedactedErrorV1,
    ControlledDequeueAdmissionResultV1,
    ControlledDequeueAdmissionV1,
    ControlledDequeueAdmissionValidationInputV1,
    OperatorId,
    build_admission,
    build_audit,
    build_collection,
    build_reservations,
    derive_status,
    evaluate_controlled_dequeue_admission,
    idempotency_key_fingerprint,
    opaque_fingerprint,
)
from .store import ControlledDequeueAdmissionStore, ControlledDequeueAdmissionStoreError


class ControlledDequeueAdmissionEvidenceReader(Protocol):
    """Read exact owner-scoped v0.43/v0.42 evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        queue_observation_receipt_id: str,
        queue_observation_receipt_valid_until: str,
    ) -> tuple[QueueObservationReceiptV1, QueueObservationReceiptStatusV1] | None: ...


class ControlledDequeueAdmissionService:
    """Create/get/list bounded evidence; no queue client or consumer exists."""

    def __init__(
        self,
        *,
        evidence_reader: ControlledDequeueAdmissionEvidenceReader,
        store: ControlledDequeueAdmissionStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ) -> None:
        self._evidence_reader = evidence_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled

    def create(
        self,
        create: ControlledDequeueAdmissionCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ControlledDequeueAdmissionResultV1:
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
            exact_create = ControlledDequeueAdmissionCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idem = idempotency_key_fingerprint(operator, idempotency_key)
        except Exception:  # noqa: BLE001 - details remain redacted
            return _failure("invalid_request", correlation_id)

        try:
            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                v043_receipt_valid_until=exact_create.queue_observation_receipt_valid_until,
            )
            if existing is not None:
                if not _same_request(existing, candidate_record_id, exact_create):
                    return _failure("idempotency_conflict", correlation_id)
                return _success(existing, correlation_id, self._server_now())

            recorded_at = self._server_now()
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                queue_observation_receipt_id=exact_create.queue_observation_receipt_id,
                queue_observation_receipt_valid_until=(
                    exact_create.queue_observation_receipt_valid_until
                ),
            )
            if evidence is None:
                return _failure("not_found", correlation_id)
            receipt, status = evidence
            authority = ControlledDequeueAdmissionAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = ControlledDequeueAdmissionValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                queue_observation_receipt=receipt,
                queue_observation_receipt_status=status,
                idempotency_key=idempotency_key,
            )
            evaluation = evaluate_controlled_dequeue_admission(validation)
            if not evaluation.controlled_dequeue_admission_build_allowed:
                return _failure(evaluation.blockers[0], correlation_id)
            record = build_admission(validation)
            idempotency, reservation = build_reservations(validation, record)
            audit = build_audit(
                record,
                event="controlled_dequeue_admission_recorded",
                outcome="recorded",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                occurred_at=recorded_at,
            )
            stored, _created = self._store.append(
                record=record,
                idempotency_reservation=idempotency,
                subject_reservation=reservation,
                audit_evidence=audit,
                v043_receipt_valid_until=(
                    exact_create.queue_observation_receipt_valid_until
                ),
            )
            return _success(stored, correlation_id, recorded_at)
        except ControlledDequeueAdmissionStoreError as error:
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
        admission_id: str,
        correlation_id: str,
    ) -> ControlledDequeueAdmissionResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(operator_id=operator, admission_id=admission_id)
            return _success(record, correlation_id, self._server_now())
        except ControlledDequeueAdmissionStoreError as error:
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
    ) -> ControlledDequeueAdmissionCollectionV1 | tuple[ControlledDequeueAdmissionResultV1, ...]:
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


def create_controlled_dequeue_admission_service(
    *,
    evidence_reader: ControlledDequeueAdmissionEvidenceReader,
    store: ControlledDequeueAdmissionStore,
    clock: Callable[[], datetime],
    enabled: bool = False,
) -> ControlledDequeueAdmissionService:
    """Explicit P2 construction; no production composition calls this."""
    return ControlledDequeueAdmissionService(
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        enabled=enabled,
    )


def _same_request(
    record: ControlledDequeueAdmissionV1,
    candidate_record_id: str,
    create: ControlledDequeueAdmissionCreateV1,
) -> bool:
    receipt = record.queue_observation_receipt
    status = record.queue_observation_receipt_status
    enqueue = receipt.v042_enqueue
    item = enqueue.queue_item
    return (
        record.candidate_record_id == candidate_record_id
        and receipt.receipt_id == create.queue_observation_receipt_id
        and receipt.receipt_record_fingerprint
        == create.queue_observation_receipt_fingerprint
        and status.status_fingerprint
        == create.queue_observation_receipt_status_fingerprint
        and receipt.valid_until == create.queue_observation_receipt_valid_until
        and enqueue.enqueue_id == create.enqueue_id
        and item.queue_item_id == create.inert_queue_item_id
        and item.item_fingerprint == create.inert_queue_item_fingerprint
        and enqueue.inherited_limits.limits_fingerprint
        == create.inherited_limits_fingerprint
    )


def _success(
    record: ControlledDequeueAdmissionV1,
    correlation_id: str,
    evaluated_at: str,
) -> ControlledDequeueAdmissionResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return ControlledDequeueAdmissionResultV1(
        ok=True,
        outcome="success",
        record=record,
        status=derive_status(record, evaluated_at=evaluated_at),
        error=None,
        correlation_fingerprint=correlation,
        controlled_dequeue_admission_recorded=True,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:controlled-dequeue-admission-correlation:v1", safe)


def _validation_failure(
    message: str, correlation_id: str
) -> ControlledDequeueAdmissionResultV1:
    lowered = message.lower()
    if "home assistant" in lowered or "capability" in lowered:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in lowered:
        return _failure("not_found", correlation_id)
    if "not active" in lowered and "v0.43" in lowered:
        return _failure("v043_observation_not_active", correlation_id)
    if "not recorded" in lowered and "v0.43" in lowered:
        return _failure("v043_observation_not_recorded", correlation_id)
    if "contract eligible" in lowered:
        return _failure("v043_receipt_not_contract_eligible", correlation_id)
    if "not active" in lowered and "v0.42" in lowered:
        return _failure("v042_enqueue_not_active", correlation_id)
    if "not recorded" in lowered and "v0.42" in lowered:
        return _failure("v042_enqueue_not_recorded", correlation_id)
    if "stale" in lowered or "future" in lowered:
        return _failure("evidence_stale", correlation_id)
    if "expired" in lowered:
        return _failure("evidence_expired", correlation_id)
    if "queue identity" in lowered:
        return _failure("queue_identity_mismatch", correlation_id)
    if "item identity" in lowered or "inert queue item" in lowered:
        return _failure("item_identity_mismatch", correlation_id)
    if "observation receipt" in lowered or "item mismatch" in lowered:
        return _failure("observation_receipt_mismatch", correlation_id)
    if "ambiguous" in lowered:
        return _failure("ambiguous_state", correlation_id)
    if "executable" in lowered or "payload" in lowered:
        return _failure("executable_payload", correlation_id)
    if "authority" in lowered:
        return _failure("unsupported_authority", correlation_id)
    if "fingerprint" in lowered:
        return _failure("fingerprint_mismatch", correlation_id)
    if "inherited limits" in lowered:
        return _failure("inherited_limits_mismatch", correlation_id)
    if "linkage" in lowered:
        return _failure("linkage_mismatch", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(
    error_code: str,
    correlation_id: str,
    *,
    outcome: str = "failure",
) -> ControlledDequeueAdmissionResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return ControlledDequeueAdmissionResultV1(
        ok=False,
        outcome=outcome,
        record=None,
        status=None,
        error=ControlledDequeueAdmissionRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )


__all__ = (
    "ControlledDequeueAdmissionEvidenceReader",
    "ControlledDequeueAdmissionService",
    "create_controlled_dequeue_admission_service",
)
