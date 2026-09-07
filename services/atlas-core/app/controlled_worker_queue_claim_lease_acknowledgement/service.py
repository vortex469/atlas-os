"""Explicit Core-local v0.52 queue claim/lease/ack receipt service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
)

from .contract import (
    PERMISSION,
    ControlledWorkerQueueAdapterReceiptFactsV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementRedactedErrorV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementResultV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1,
    OperatorId,
    build_audit,
    build_collection,
    build_receipt,
    build_reservations,
    derive_status,
    evaluate_controlled_worker_queue_claim_lease_acknowledgement,
    idempotency_key_fingerprint,
    opaque_fingerprint,
    request_fingerprint,
)
from .store import (
    ControlledWorkerQueueClaimLeaseAcknowledgementStore,
    ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
)


class ControlledWorkerQueueClaimLeaseAcknowledgementReader(Protocol):
    """Read exact owner-scoped v0.51 admission evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        admission_id: str,
        admission_valid_until: str,
    ) -> (
        tuple[
            ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
            ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1,
        ]
        | None
    ): ...


class ControlledWorkerQueueClaimLeaseAcknowledgementAdapterReceiptReader(Protocol):
    """Read redacted owner-scoped adapter receipt facts; no queue contact."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        admission_id: str,
        adapter_identity_fingerprint: str,
        expected_queue_subject_fingerprint: str,
        expected_claim_receipt_fingerprint: str,
        expected_lease_receipt_fingerprint: str,
        expected_acknowledgement_receipt_fingerprint: str,
    ) -> ControlledWorkerQueueAdapterReceiptFactsV1 | None: ...


class ControlledWorkerQueueClaimLeaseAcknowledgementService:
    """Create/get/list bounded evidence; no queue, worker, Agent, or execution API."""

    def __init__(
        self,
        *,
        admission_reader: ControlledWorkerQueueClaimLeaseAcknowledgementReader,
        adapter_receipt_reader: (
            ControlledWorkerQueueClaimLeaseAcknowledgementAdapterReceiptReader
        ),
        store: ControlledWorkerQueueClaimLeaseAcknowledgementStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ) -> None:
        self._admission_reader = admission_reader
        self._adapter_receipt_reader = adapter_receipt_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled is True

    def create(
        self,
        create: ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if permission_verified is not True:
            return _failure("forbidden", correlation_id)
        if not self._enabled:
            return _failure("installation_capability_unsupported", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = (
                ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1.model_validate(
                    create.model_dump(mode="python")
                )
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
                admission_valid_until=exact_create.admission_valid_until,
            )
            if existing is not None:
                return _success(existing, correlation_id, received_at)
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError as error:
            if error.code == "append_indeterminate":
                return _failure(
                    "append_indeterminate", correlation_id, outcome="indeterminate"
                )
            if error.code in {"idempotency_conflict", "store_corrupt"}:
                return _failure(error.code, correlation_id)
            return _failure("internal_error", correlation_id)

        try:
            admission = self._admission_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                admission_id=exact_create.admission_id,
                admission_valid_until=exact_create.admission_valid_until,
            )
            if admission is None:
                return _failure("not_found", correlation_id)
            admission_record, admission_status = admission
            adapter_receipt = self._adapter_receipt_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                admission_id=exact_create.admission_id,
                adapter_identity_fingerprint=(
                    exact_create.adapter_identity_fingerprint.value
                ),
                expected_queue_subject_fingerprint=(
                    exact_create.expected_queue_subject_fingerprint.value
                ),
                expected_claim_receipt_fingerprint=(
                    exact_create.expected_claim_receipt_fingerprint.value
                ),
                expected_lease_receipt_fingerprint=(
                    exact_create.expected_lease_receipt_fingerprint.value
                ),
                expected_acknowledgement_receipt_fingerprint=(
                    exact_create.expected_acknowledgement_receipt_fingerprint.value
                ),
            )
            if adapter_receipt is None:
                return _failure("not_found", correlation_id)
            authority = (
                ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1(
                    authenticated_operator_id=operator,
                    permission=PERMISSION,
                    request_received_at=received_at,
                )
            )
            validation = ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                controlled_worker_queue_claim_lease_acknowledgement_admission=(
                    admission_record
                ),
                controlled_worker_queue_claim_lease_acknowledgement_admission_status=(
                    admission_status
                ),
                adapter_receipt=adapter_receipt,
                idempotency_key=idempotency_key,
            )
            evaluation = evaluate_controlled_worker_queue_claim_lease_acknowledgement(
                validation
            )
            if not evaluation.controlled_worker_queue_claim_lease_acknowledgement_recorded:
                return _failure(evaluation.blockers[0], correlation_id)
            record = build_receipt(validation)
            idempotency, reservation = build_reservations(validation, record)
            audit = build_audit(
                record,
                event="controlled_worker_queue_claim_lease_acknowledgement_recorded",
                outcome="recorded",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                occurred_at=received_at,
            )

            def revalidate() -> None:
                try:
                    current = self._admission_reader.read_owned(
                        operator_id=operator,
                        candidate_record_id=candidate_record_id,
                        admission_id=exact_create.admission_id,
                        admission_valid_until=exact_create.admission_valid_until,
                    )
                    if current is None:
                        raise ValueError("v0.51 admission is not active")
                    # Reparse nested models and check exact IDs, fingerprints and
                    # inherited lineage again while holding the reservation lock.
                    current_record, current_status = current
                    raw = validation.model_dump(mode="python")
                    raw[
                        "controlled_worker_queue_claim_lease_acknowledgement_admission"
                    ] = current_record.model_dump(mode="python")
                    raw[
                        "controlled_worker_queue_claim_lease_acknowledgement_admission_status"
                    ] = current_status.model_dump(mode="python")
                    raw["authority"]["request_received_at"] = self._server_now()
                    ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1.model_validate(
                        raw
                    )
                except (TypeError, ValueError) as error:
                    failure = _validation_failure(str(error), correlation_id)
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        failure.error.error_code
                    ) from None

            stored, _created = self._store.append(
                record=record,
                idempotency_reservation=idempotency,
                subject_reservation=reservation,
                audit_evidence=audit,
                admission_valid_until=exact_create.admission_valid_until,
                revalidate=revalidate,
            )
            return _success(stored, correlation_id, received_at)
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError as error:
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
                    "not_found",
                    "v051_admission_not_active",
                    "fingerprint_mismatch",
                    "linkage_mismatch",
                    "inherited_limits_mismatch",
                    "evidence_stale",
                    "evidence_expired",
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
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if permission_verified is not True:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(operator_id=operator, admission_id=admission_id)
            return _success(record, correlation_id, self._server_now())
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError as error:
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
    ) -> (
        ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1
        | tuple[ControlledWorkerQueueClaimLeaseAcknowledgementResultV1, ...]
    ):
        if authenticated_operator_id is None:
            return (_failure("unauthenticated", correlation_id),)
        if permission_verified is not True:
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
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError as error:
            return (
                _failure(
                    "store_corrupt"
                    if error.code == "store_corrupt"
                    else "internal_error",
                    correlation_id,
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


def create_controlled_worker_queue_claim_lease_acknowledgement_service(
    *,
    admission_reader: ControlledWorkerQueueClaimLeaseAcknowledgementReader,
    adapter_receipt_reader: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdapterReceiptReader
    ),
    store: ControlledWorkerQueueClaimLeaseAcknowledgementStore,
    clock: Callable[[], datetime],
    enabled: bool = False,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementService:
    """Explicit P2 construction; no production composition calls this."""
    return ControlledWorkerQueueClaimLeaseAcknowledgementService(
        admission_reader=admission_reader,
        adapter_receipt_reader=adapter_receipt_reader,
        store=store,
        clock=clock,
        enabled=enabled,
    )


def _success(
    record: ControlledWorkerQueueClaimLeaseAcknowledgementV1,
    correlation_id: str,
    evaluated_at: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return ControlledWorkerQueueClaimLeaseAcknowledgementResultV1(
        ok=True,
        outcome="success",
        record=record,
        status=derive_status(record, evaluated_at=evaluated_at),
        error=None,
        correlation_fingerprint=correlation,
        controlled_worker_queue_claim_lease_acknowledgement_recorded=True,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-correlation:v1",
        safe,
    )


def _validation_failure(
    message: str, correlation_id: str
) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1:
    lowered = message.lower()
    if "home assistant" in lowered or "capability" in lowered:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in lowered:
        return _failure("not_found", correlation_id)
    if "not active" in lowered and "v0.51" in lowered:
        return _failure("v051_admission_not_active", correlation_id)
    if "not recorded" in lowered and "v0.51" in lowered:
        return _failure("v051_admission_not_recorded", correlation_id)
    if "stale" in lowered or "future" in lowered:
        return _failure("evidence_stale", correlation_id)
    if "expired" in lowered:
        return _failure("evidence_expired", correlation_id)
    if "ambiguous" in lowered:
        return _failure("ambiguous_state", correlation_id)
    if "queue selector" in lowered:
        return _failure("caller_supplied_queue_selector", correlation_id)
    if "claim token" in lowered:
        return _failure("caller_supplied_claim_token", correlation_id)
    if "lease token" in lowered:
        return _failure("caller_supplied_lease_token", correlation_id)
    if "acknowledgement handle" in lowered:
        return _failure("caller_supplied_acknowledgement_handle", correlation_id)
    if "credential" in lowered:
        return _failure("caller_supplied_credential", correlation_id)
    if "endpoint" in lowered:
        return _failure("caller_supplied_endpoint", correlation_id)
    if "command" in lowered or "payload" in lowered:
        return _failure("caller_supplied_command", correlation_id)
    if "authority" in lowered:
        return _failure("unsupported_authority", correlation_id)
    if "limits" in lowered:
        return _failure("inherited_limits_mismatch", correlation_id)
    if "fingerprint" in lowered:
        return _failure("fingerprint_mismatch", correlation_id)
    if "linkage" in lowered:
        return _failure("linkage_mismatch", correlation_id)
    if "reservation before effect" in lowered:
        return _failure("reservation_before_effect_missing", correlation_id)
    if "claim receipt" in lowered:
        return _failure("claim_receipt_mismatch", correlation_id)
    if "lease receipt" in lowered:
        return _failure("lease_receipt_mismatch", correlation_id)
    if "acknowledgement receipt" in lowered:
        return _failure("acknowledgement_receipt_mismatch", correlation_id)
    if "replay" in lowered:
        return _failure("replay_detected", correlation_id)
    if "corrupt" in lowered:
        return _failure("corrupt_adapter_evidence", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(
    error_code: str,
    correlation_id: str,
    *,
    outcome: str = "failure",
) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return ControlledWorkerQueueClaimLeaseAcknowledgementResultV1(
        ok=False,
        outcome=outcome,
        record=None,
        status=None,
        error=ControlledWorkerQueueClaimLeaseAcknowledgementRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )


__all__ = (
    "ControlledWorkerQueueClaimLeaseAcknowledgementAdapterReceiptReader",
    "ControlledWorkerQueueClaimLeaseAcknowledgementReader",
    "ControlledWorkerQueueClaimLeaseAcknowledgementService",
    "create_controlled_worker_queue_claim_lease_acknowledgement_service",
)
