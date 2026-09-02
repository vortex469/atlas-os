"""Explicit Core-local v0.40 worker intake admission evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from .contract import (
    PERMISSION,
    OperatorId,
    WorkerIntakeAdmissionAuthorityContextV1,
    WorkerIntakeAdmissionCollectionV1,
    WorkerIntakeAdmissionCreateV1,
    WorkerIntakeAdmissionRedactedErrorV1,
    WorkerIntakeAdmissionResultV1,
    WorkerIntakeAdmissionV1,
    WorkerIntakeAdmissionValidationInputV1,
    WorkerIntakeReferenceV1,
    WorkerIntakeWorkerIdentityV1,
    WorkerQueueReservationStatusV1,
    WorkerQueueReservationV1,
    build_admission,
    build_audit,
    build_collection,
    idempotency_key_fingerprint,
    opaque_fingerprint,
)
from .store import WorkerIntakeAdmissionStore, WorkerIntakeAdmissionStoreError


class WorkerIntakeAdmissionEvidenceReader(Protocol):
    """Read exact owner-scoped v0.39 queue reservation evidence without external I/O."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        worker_queue_reservation_id: str,
        worker_queue_reservation_valid_until: str,
    ) -> tuple[WorkerQueueReservationV1, WorkerQueueReservationStatusV1, bool] | None:
        ...


class WorkerIntakeWorkerIdentityReader(Protocol):
    """Read one abstract server-owned worker identity without contacting a worker."""

    def read_owned(
        self, *, operator_id: str, worker_identity_id: str
    ) -> WorkerIntakeWorkerIdentityV1 | None: ...


class WorkerIntakeReferenceReader(Protocol):
    """Read one abstract intake reference without contacting a queue or worker."""

    def read_owned(
        self, *, operator_id: str, worker_intake_reference_id: str
    ) -> WorkerIntakeReferenceV1 | None: ...


class WorkerIntakeAdmissionService:
    """Create/get/list evidence; exposes no queue, worker, or effect operation."""

    def __init__(
        self,
        *,
        evidence_reader: WorkerIntakeAdmissionEvidenceReader,
        worker_identity_reader: WorkerIntakeWorkerIdentityReader,
        worker_intake_reference_reader: WorkerIntakeReferenceReader,
        store: WorkerIntakeAdmissionStore,
        clock: Callable[[], datetime],
        admission_id_factory: Callable[[], str],
        decision_id_factory: Callable[[], str],
        enabled: bool = False,
    ) -> None:
        self._evidence_reader = evidence_reader
        self._worker_identity_reader = worker_identity_reader
        self._worker_intake_reference_reader = worker_intake_reference_reader
        self._store = store
        self._clock = clock
        self._admission_id_factory = admission_id_factory
        self._decision_id_factory = decision_id_factory
        self._enabled = enabled

    def create(
        self,
        create: WorkerIntakeAdmissionCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> WorkerIntakeAdmissionResultV1:
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
            exact_create = WorkerIntakeAdmissionCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idem = idempotency_key_fingerprint(operator, idempotency_key)
        except Exception:  # noqa: BLE001 - parsing detail remains redacted
            return _failure("invalid_request", correlation_id)

        try:
            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                worker_queue_reservation_valid_until=(
                    exact_create.worker_queue_reservation_valid_until
                ),
            )
            if existing is not None:
                if not _same_request(existing, candidate_record_id, exact_create):
                    return _failure("conflict", correlation_id)
                return _success(existing, correlation_id)

            recorded_at = self._server_now()
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                worker_queue_reservation_id=exact_create.worker_queue_reservation_id,
                worker_queue_reservation_valid_until=(
                    exact_create.worker_queue_reservation_valid_until
                ),
            )
            identity = self._worker_identity_reader.read_owned(
                operator_id=operator,
                worker_identity_id=exact_create.worker_identity_id,
            )
            intake = self._worker_intake_reference_reader.read_owned(
                operator_id=operator,
                worker_intake_reference_id=exact_create.worker_intake_reference_id,
            )
            if evidence is None or identity is None or intake is None:
                return _failure("not_found", correlation_id)
            reservation, status, home_assistant = evidence
            authority = WorkerIntakeAdmissionAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = WorkerIntakeAdmissionValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                worker_queue_reservation=reservation,
                worker_queue_reservation_status=status,
                worker_identity=identity,
                worker_intake_reference=intake,
                idempotency_key=idempotency_key,
                home_assistant=home_assistant,
            )
            record, _, subject_reservation = build_admission(
                validation,
                admission_id=self._admission_id_factory(),
                decision_id=self._decision_id_factory(),
            )
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
                worker_queue_reservation_valid_until=(
                    exact_create.worker_queue_reservation_valid_until
                ),
            )
            return _success(stored, correlation_id)
        except WorkerIntakeAdmissionStoreError as error:
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
    ) -> WorkerIntakeAdmissionResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(operator_id=operator, admission_id=admission_id)
            return _success(record, correlation_id)
        except WorkerIntakeAdmissionStoreError as error:
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
    ) -> WorkerIntakeAdmissionCollectionV1 | tuple[WorkerIntakeAdmissionResultV1, ...]:
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


def create_worker_intake_admission_service(
    *,
    evidence_reader: WorkerIntakeAdmissionEvidenceReader,
    worker_identity_reader: WorkerIntakeWorkerIdentityReader,
    worker_intake_reference_reader: WorkerIntakeReferenceReader,
    store: WorkerIntakeAdmissionStore,
    clock: Callable[[], datetime],
    admission_id_factory: Callable[[], str],
    decision_id_factory: Callable[[], str],
    enabled: bool = False,
) -> WorkerIntakeAdmissionService:
    """Explicit P2 construction; no production composition calls this."""
    return WorkerIntakeAdmissionService(
        evidence_reader=evidence_reader,
        worker_identity_reader=worker_identity_reader,
        worker_intake_reference_reader=worker_intake_reference_reader,
        store=store,
        clock=clock,
        admission_id_factory=admission_id_factory,
        decision_id_factory=decision_id_factory,
        enabled=enabled,
    )


def _same_request(
    record: WorkerIntakeAdmissionV1,
    candidate_record_id: str,
    create: WorkerIntakeAdmissionCreateV1,
) -> bool:
    return (
        record.candidate_record_id == candidate_record_id
        and record.linkage.queue_reservation_id == create.worker_queue_reservation_id
        and record.linkage.queue_reservation_fingerprint
        == create.worker_queue_reservation_fingerprint
        and record.valid_until <= create.worker_queue_reservation_valid_until
        and record.worker_identity.worker_identity_id == create.worker_identity_id
        and record.worker_identity.worker_identity_fingerprint
        == create.worker_identity_fingerprint
        and record.worker_intake_reference.worker_intake_reference_id
        == create.worker_intake_reference_id
        and record.worker_intake_reference.intake_reference_fingerprint
        == create.worker_intake_reference_fingerprint
        and record.inherited_limits.limits_fingerprint
        == create.inherited_limits_fingerprint
    )


def _success(
    admission: WorkerIntakeAdmissionV1, correlation_id: str
) -> WorkerIntakeAdmissionResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return WorkerIntakeAdmissionResultV1(
        ok=True,
        admission=admission,
        error=None,
        correlation_fingerprint=correlation,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:worker-intake-admission-correlation:v1", safe)


def _validation_failure(
    message: str, correlation_id: str
) -> WorkerIntakeAdmissionResultV1:
    if "Home Assistant" in message:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in message:
        return _failure("not_found", correlation_id)
    if "not active" in message:
        return _failure("worker_queue_reservation_not_active", correlation_id)
    if "stale" in message or "future" in message:
        return _failure("evidence_stale", correlation_id)
    if "expired" in message:
        return _failure("evidence_expired", correlation_id)
    if "limits" in message:
        return _failure("inherited_limits_mismatch", correlation_id)
    if "identity" in message or "intake reference" in message or "linkage" in message:
        return _failure("linkage_mismatch", correlation_id)
    if "fingerprint" in message:
        return _failure("fingerprint_mismatch", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(error_code: str, correlation_id: str) -> WorkerIntakeAdmissionResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return WorkerIntakeAdmissionResultV1(
        ok=False,
        admission=None,
        error=WorkerIntakeAdmissionRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )
