"""Explicit Core-local v0.39 worker queue reservation evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from .contract import (
    PERMISSION,
    OperatorId,
    QueueIntakeReferenceV1,
    WorkerAdmissionStubStatusV1,
    WorkerAdmissionStubV1,
    WorkerQueueReservationAuditEvidenceV1,
    WorkerQueueReservationAuthorityContextV1,
    WorkerQueueReservationCreateV1,
    WorkerQueueReservationRedactedErrorV1,
    WorkerQueueReservationResultV1,
    WorkerQueueReservationValidationInputV1,
    audit_fingerprint,
    build_reservation,
    derive_status,
    idempotency_key_fingerprint,
    opaque_fingerprint,
)
from .store import WorkerQueueReservationStore, WorkerQueueReservationStoreError


class WorkerQueueReservationEvidenceReader(Protocol):
    """Read exact owner-scoped v0.38 evidence without external I/O."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        worker_admission_stub_id: str,
        worker_admission_stub_valid_until: str,
    ) -> tuple[WorkerAdmissionStubV1, WorkerAdmissionStubStatusV1, bool] | None: ...


class WorkerQueueIntakeReferenceReader(Protocol):
    """Read an abstract owner-scoped queue reference without contacting a queue."""

    def read_owned(
        self, *, operator_id: str, queue_intake_reference_id: str
    ) -> QueueIntakeReferenceV1 | None: ...


class WorkerQueueReservationService:
    """Create/get/list evidence; exposes no queue, worker, or effect operation."""

    def __init__(
        self,
        *,
        evidence_reader: WorkerQueueReservationEvidenceReader,
        queue_reference_reader: WorkerQueueIntakeReferenceReader,
        store: WorkerQueueReservationStore,
        clock: Callable[[], datetime],
        reservation_id_factory: Callable[[], str],
        enabled: bool = False,
    ) -> None:
        self._evidence_reader = evidence_reader
        self._queue_reference_reader = queue_reference_reader
        self._store = store
        self._clock = clock
        self._reservation_id_factory = reservation_id_factory
        self._enabled = enabled

    def create(
        self,
        create: WorkerQueueReservationCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> WorkerQueueReservationResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        if not self._enabled:
            return _failure("not_eligible", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = WorkerQueueReservationCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idem = idempotency_key_fingerprint(operator, idempotency_key)
        except Exception:  # noqa: BLE001 - parsing detail remains redacted
            return _failure("malformed", correlation_id)

        correlation = _correlation_fingerprint(correlation_id)
        try:
            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                worker_admission_stub_valid_until=(
                    exact_create.worker_admission_stub_valid_until
                ),
            )
            if existing is not None:
                if not _same_request(existing, candidate_record_id, exact_create):
                    return _failure("conflict", correlation_id)
                return self._success(
                    existing,
                    disposition="exact_duplicate",
                    correlation_fingerprint=correlation,
                    observed_at=self._server_now(),
                )

            recorded_at = self._server_now()
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                worker_admission_stub_id=exact_create.worker_admission_stub_id,
                worker_admission_stub_valid_until=(
                    exact_create.worker_admission_stub_valid_until
                ),
            )
            queue_reference = self._queue_reference_reader.read_owned(
                operator_id=operator,
                queue_intake_reference_id=exact_create.queue_intake_reference_id,
            )
            if evidence is None or queue_reference is None:
                return _failure("not_found", correlation_id)
            stub, stub_status, home_assistant = evidence
            authority = WorkerQueueReservationAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = WorkerQueueReservationValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                worker_admission_stub=stub,
                worker_admission_stub_status=stub_status,
                queue_intake_reference=queue_reference,
                idempotency_key=idempotency_key,
                home_assistant=home_assistant,
            )
            record, _, subject_reservation = build_reservation(
                validation, reservation_id=self._reservation_id_factory()
            )
            audit = _audit(
                record,
                outcome="recorded",
                correlation_fingerprint=correlation,
                occurred_at=recorded_at,
            )
            stored, created = self._store.append(
                record=record,
                reservation=subject_reservation,
                audit_evidence=audit,
                worker_admission_stub_valid_until=(
                    exact_create.worker_admission_stub_valid_until
                ),
            )
            return self._success(
                stored,
                disposition="recorded" if created else "exact_duplicate",
                correlation_fingerprint=correlation,
                observed_at=recorded_at if created else self._server_now(),
            )
        except WorkerQueueReservationStoreError as error:
            code = (
                error.code
                if error.code
                in {"conflict", "quota_exceeded", "record_too_large"}
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
        reservation_id: str,
        correlation_id: str,
    ) -> WorkerQueueReservationResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(
                operator_id=operator, reservation_id=reservation_id
            )
            return self._success(
                record,
                disposition="read",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                observed_at=self._server_now(),
            )
        except WorkerQueueReservationStoreError as error:
            return _failure(
                "not_found" if error.code == "not_found" else "internal_error",
                correlation_id,
            )
        except Exception:  # noqa: BLE001 - read details remain redacted
            return _failure("internal_error", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        correlation_id: str,
    ) -> tuple[WorkerQueueReservationResultV1, ...]:
        if authenticated_operator_id is None:
            return (_failure("unauthenticated", correlation_id),)
        if not permission_verified:
            return (_failure("forbidden", correlation_id),)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            observed_at = self._server_now()
            correlation = _correlation_fingerprint(correlation_id)
            return tuple(
                self._success(
                    record,
                    disposition="read",
                    correlation_fingerprint=correlation,
                    observed_at=observed_at,
                )
                for record in self._store.list_owned(operator_id=operator)
            )
        except Exception:  # noqa: BLE001 - listing details remain redacted
            return (_failure("internal_error", correlation_id),)

    def _success(
        self,
        record: object,
        *,
        disposition: str,
        correlation_fingerprint: object,
        observed_at: str,
    ) -> WorkerQueueReservationResultV1:
        return WorkerQueueReservationResultV1(
            disposition=disposition,
            reservation=record,
            status=derive_status(record, observed_at=observed_at),
            audit_evidence=_audit(
                record,
                outcome=disposition,
                correlation_fingerprint=correlation_fingerprint,
                occurred_at=observed_at,
            ),
            error=None,
        )

    def _server_now(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trusted Core clock must be timezone-aware")
        exact = value.astimezone(UTC)
        if exact.microsecond:
            raise ValueError("trusted Core clock must return whole seconds")
        return exact.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_worker_queue_reservation_service(
    *,
    evidence_reader: WorkerQueueReservationEvidenceReader,
    queue_reference_reader: WorkerQueueIntakeReferenceReader,
    store: WorkerQueueReservationStore,
    clock: Callable[[], datetime],
    reservation_id_factory: Callable[[], str],
    enabled: bool = False,
) -> WorkerQueueReservationService:
    """Explicit P2 construction; no production composition calls this."""
    return WorkerQueueReservationService(
        evidence_reader=evidence_reader,
        queue_reference_reader=queue_reference_reader,
        store=store,
        clock=clock,
        reservation_id_factory=reservation_id_factory,
        enabled=enabled,
    )


def _same_request(
    record: object,
    candidate_record_id: str,
    create: WorkerQueueReservationCreateV1,
) -> bool:
    return (
        record.candidate_record_id == candidate_record_id
        and record.linkage.worker_admission_stub_id
        == create.worker_admission_stub_id
        and record.linkage.worker_admission_stub_fingerprint
        == create.worker_admission_stub_fingerprint
        and record.queue_intake_reference.queue_intake_reference_id
        == create.queue_intake_reference_id
        and record.queue_intake_reference.reference_fingerprint
        == create.queue_intake_reference_fingerprint
        and record.queue_item_reference.queue_item_reference_id
        == create.queue_item_reference_id
        and record.queue_item_reference.item_fingerprint
        == create.queue_item_reference_fingerprint
        and record.inherited_limits.limits_fingerprint
        == create.inherited_limits_fingerprint
    )


def _audit(
    record: object,
    *,
    outcome: str,
    correlation_fingerprint: object,
    occurred_at: str,
) -> WorkerQueueReservationAuditEvidenceV1:
    raw = {
        "event": "reservation_recorded" if outcome == "recorded" else "reservation_read",
        "outcome": outcome,
        "operator_fingerprint": opaque_fingerprint(
            "atlas:worker-queue-reservation-operator:v1", record.operator_id
        ),
        "candidate_record_fingerprint": opaque_fingerprint(
            "atlas:worker-queue-reservation-candidate:v1",
            record.candidate_record_id,
        ),
        "reservation_id": record.reservation_id,
        "subject_fingerprint": record.subject_fingerprint,
        "record_fingerprint": record.record_fingerprint,
        "correlation_fingerprint": correlation_fingerprint,
        "occurred_at": occurred_at,
    }
    seed = WorkerQueueReservationAuditEvidenceV1.model_construct(
        **raw, audit_fingerprint=record.record_fingerprint
    )
    return WorkerQueueReservationAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_fingerprint(seed)}
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint(
        "atlas:worker-queue-reservation-correlation:v1", safe
    )


def _validation_failure(
    message: str, correlation_id: str
) -> WorkerQueueReservationResultV1:
    if "Home Assistant" in message or "not active" in message:
        return _failure("not_eligible", correlation_id)
    if "ownership" in message:
        return _failure("not_found", correlation_id)
    if "stale" in message or "future" in message or "expired" in message:
        return _failure("expired", correlation_id)
    if "fingerprint" in message or "linkage" in message or "limits" in message:
        return _failure("not_eligible", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(
    error_code: str, correlation_id: str
) -> WorkerQueueReservationResultV1:
    return WorkerQueueReservationResultV1(
        disposition="blocked",
        reservation=None,
        status=None,
        audit_evidence=None,
        error=WorkerQueueReservationRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=_correlation_fingerprint(correlation_id),
        ),
    )
