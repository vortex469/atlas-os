"""Explicit Core-local v0.41 live enqueue admission evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from .contract import (
    PERMISSION,
    LiveEnqueueAdmissionAuthorityContextV1,
    LiveEnqueueAdmissionCollectionV1,
    LiveEnqueueAdmissionCreateV1,
    LiveEnqueueAdmissionRedactedErrorV1,
    LiveEnqueueAdmissionResultV1,
    LiveEnqueueAdmissionV1,
    LiveEnqueueAdmissionValidationInputV1,
    OperatorId,
    WorkerIntakeAdmissionStatusV1,
    WorkerIntakeAdmissionV1,
    WorkerQueueReservationStatusV1,
    WorkerQueueReservationV1,
    build_admission,
    build_audit,
    build_collection,
    derive_status,
    idempotency_key_fingerprint,
    opaque_fingerprint,
)
from .store import LiveEnqueueAdmissionStore, LiveEnqueueAdmissionStoreError


class LiveEnqueueAdmissionEvidenceReader(Protocol):
    """Read exact owner-scoped v0.40/v0.39 predecessor evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        worker_intake_admission_id: str,
        worker_intake_admission_valid_until: str,
    ) -> (
        tuple[
            WorkerIntakeAdmissionV1,
            WorkerIntakeAdmissionStatusV1,
            WorkerQueueReservationV1,
            WorkerQueueReservationStatusV1,
        ]
        | None
    ): ...


class LiveEnqueueAdmissionService:
    """Create/get/list evidence; exposes no queue, worker, or effect operation."""

    def __init__(
        self,
        *,
        evidence_reader: LiveEnqueueAdmissionEvidenceReader,
        store: LiveEnqueueAdmissionStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ) -> None:
        self._evidence_reader = evidence_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled

    def create(
        self,
        create: LiveEnqueueAdmissionCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> LiveEnqueueAdmissionResultV1:
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
            exact_create = LiveEnqueueAdmissionCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idem = idempotency_key_fingerprint(operator, idempotency_key)
        except Exception:  # noqa: BLE001 - parsing detail remains redacted
            return _failure("invalid_request", correlation_id)

        try:
            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                worker_intake_admission_valid_until=(
                    exact_create.worker_intake_admission_valid_until
                ),
            )
            if existing is not None:
                if not _same_request(existing, candidate_record_id, exact_create):
                    return _failure("conflict", correlation_id)
                return _success(existing, correlation_id, self._server_now())

            recorded_at = self._server_now()
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                worker_intake_admission_id=exact_create.worker_intake_admission_id,
                worker_intake_admission_valid_until=(
                    exact_create.worker_intake_admission_valid_until
                ),
            )
            if evidence is None:
                return _failure("not_found", correlation_id)
            (
                worker_intake_admission,
                worker_intake_admission_status,
                worker_queue_reservation,
                worker_queue_reservation_status,
            ) = evidence
            authority = LiveEnqueueAdmissionAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = LiveEnqueueAdmissionValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                worker_intake_admission=worker_intake_admission,
                worker_intake_admission_status=worker_intake_admission_status,
                worker_queue_reservation=worker_queue_reservation,
                worker_queue_reservation_status=worker_queue_reservation_status,
                idempotency_key=idempotency_key,
            )
            record, _idempotency, subject_reservation = build_admission(validation)
            audit = build_audit(
                record,
                outcome="recorded",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                occurred_at=recorded_at,
            )
            stored, _created = self._store.append(
                record=record,
                reservation=subject_reservation,
                audit_evidence=audit,
                worker_intake_admission_valid_until=(
                    exact_create.worker_intake_admission_valid_until
                ),
            )
            return _success(stored, correlation_id, recorded_at)
        except LiveEnqueueAdmissionStoreError as error:
            code = (
                error.code
                if error.code
                in {
                    "conflict",
                    "quota_exceeded",
                    "record_too_large",
                    "store_corrupt",
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
    ) -> LiveEnqueueAdmissionResultV1:
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
        except LiveEnqueueAdmissionStoreError as error:
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
    ) -> LiveEnqueueAdmissionCollectionV1 | tuple[LiveEnqueueAdmissionResultV1, ...]:
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


def create_live_enqueue_admission_service(
    *,
    evidence_reader: LiveEnqueueAdmissionEvidenceReader,
    store: LiveEnqueueAdmissionStore,
    clock: Callable[[], datetime],
    enabled: bool = False,
) -> LiveEnqueueAdmissionService:
    """Explicit P2 construction; no production composition calls this."""
    return LiveEnqueueAdmissionService(
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        enabled=enabled,
    )


def _same_request(
    record: LiveEnqueueAdmissionV1,
    candidate_record_id: str,
    create: LiveEnqueueAdmissionCreateV1,
) -> bool:
    link = record.linkage
    return (
        record.candidate_record_id == candidate_record_id
        and link.worker_intake_admission_id == create.worker_intake_admission_id
        and link.worker_intake_admission_fingerprint
        == create.worker_intake_admission_fingerprint
        and record.valid_until <= create.worker_intake_admission_valid_until
        and link.queue_reservation_id == create.worker_queue_reservation_id
        and link.queue_reservation_fingerprint
        == create.worker_queue_reservation_fingerprint
        and link.queue_item_reference_id == create.queue_item_reference_id
        and link.queue_item_reference_fingerprint
        == create.queue_item_reference_fingerprint
        and link.worker_identity_id == create.worker_identity_id
        and link.worker_identity_fingerprint == create.worker_identity_fingerprint
        and link.worker_intake_reference_id == create.worker_intake_reference_id
        and link.worker_intake_reference_fingerprint
        == create.worker_intake_reference_fingerprint
        and link.inherited_limits_fingerprint == create.inherited_limits_fingerprint
    )


def _success(
    admission: LiveEnqueueAdmissionV1,
    correlation_id: str,
    evaluated_at: str,
) -> LiveEnqueueAdmissionResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return LiveEnqueueAdmissionResultV1(
        ok=True,
        admission=admission,
        status=derive_status(admission, evaluated_at=evaluated_at),
        error=None,
        correlation_fingerprint=correlation,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:live-enqueue-admission-correlation:v1", safe)


def _validation_failure(
    message: str, correlation_id: str
) -> LiveEnqueueAdmissionResultV1:
    lowered = message.lower()
    if "home assistant" in message:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in lowered:
        return _failure("not_found", correlation_id)
    if "worker intake admission is not active" in lowered:
        return _failure("worker_intake_admission_not_active", correlation_id)
    if "queue reservation is not active" in lowered:
        return _failure("queue_reservation_not_active", correlation_id)
    if "stale" in lowered or "future" in lowered:
        return _failure("evidence_stale", correlation_id)
    if "expired" in lowered:
        return _failure("evidence_expired", correlation_id)
    if "limits" in lowered:
        return _failure("inherited_limits_mismatch", correlation_id)
    if "identity" in lowered:
        return _failure("worker_identity_ineligible", correlation_id)
    if "intake reference" in lowered:
        return _failure("worker_intake_reference_ineligible", correlation_id)
    if "linkage" in lowered:
        return _failure("linkage_mismatch", correlation_id)
    if "fingerprint" in lowered:
        return _failure("fingerprint_mismatch", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(error_code: str, correlation_id: str) -> LiveEnqueueAdmissionResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return LiveEnqueueAdmissionResultV1(
        ok=False,
        admission=None,
        status=None,
        error=LiveEnqueueAdmissionRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )
