"""Explicit Core-local v0.45 one-shot controlled dequeue reservation service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.controlled_dequeue_admission.contract import (
    ControlledDequeueAdmissionStatusV1,
    ControlledDequeueAdmissionV1,
)

from .contract import (
    PERMISSION,
    OneShotControlledDequeueAuthorityContextV1,
    OneShotControlledDequeueCollectionV1,
    OneShotControlledDequeueCreateV1,
    OneShotControlledDequeueRedactedErrorV1,
    OneShotControlledDequeueResultV1,
    OneShotControlledDequeueValidationInputV1,
    OperatorId,
    build_audit,
    build_collection,
    build_reservations,
    derive_status,
    evaluate_one_shot_controlled_dequeue,
    idempotency_key_fingerprint,
    opaque_fingerprint,
    request_fingerprint,
)
from .store import OneShotControlledDequeueStore, OneShotControlledDequeueStoreError


class OneShotControlledDequeueEvidenceReader(Protocol):
    """Read exact owner-scoped v0.44/v0.43/v0.42 evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        controlled_dequeue_admission_id: str,
        controlled_dequeue_admission_valid_until: str,
    ) -> tuple[ControlledDequeueAdmissionV1, ControlledDequeueAdmissionStatusV1] | None: ...


class OneShotControlledDequeueReservationService:
    """Create/get/list bounded reservation evidence; no live dequeue consumer exists."""

    def __init__(
        self,
        *,
        evidence_reader: OneShotControlledDequeueEvidenceReader,
        store: OneShotControlledDequeueStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ) -> None:
        self._evidence_reader = evidence_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled

    def create(
        self,
        create: OneShotControlledDequeueCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OneShotControlledDequeueResultV1:
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
            exact_create = OneShotControlledDequeueCreateV1.model_validate(
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
                controlled_dequeue_admission_valid_until=(
                    exact_create.controlled_dequeue_admission_valid_until
                ),
            )
            if existing is not None:
                return _success(existing, correlation_id, self._server_now())
        except OneShotControlledDequeueStoreError as error:
            if error.code == "dequeue_adapter_unavailable":
                return _failure(
                    "dequeue_adapter_unavailable",
                    correlation_id,
                    outcome="indeterminate",
                )
            if error.code == "idempotency_conflict":
                return _failure("idempotency_conflict", correlation_id)
            if error.code == "store_corrupt":
                return _failure("store_corrupt", correlation_id)
            return _failure("internal_error", correlation_id)

        try:
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                controlled_dequeue_admission_id=(
                    exact_create.controlled_dequeue_admission_id
                ),
                controlled_dequeue_admission_valid_until=(
                    exact_create.controlled_dequeue_admission_valid_until
                ),
            )
            if evidence is None:
                return _failure("not_found", correlation_id)
            admission, status = evidence
            authority = OneShotControlledDequeueAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=received_at,
            )
            validation = OneShotControlledDequeueValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                controlled_dequeue_admission=admission,
                controlled_dequeue_admission_status=status,
                idempotency_key=idempotency_key,
            )
            evaluation = evaluate_one_shot_controlled_dequeue(validation)
            if not evaluation.one_shot_controlled_dequeue_build_allowed:
                return _failure(evaluation.blockers[0], correlation_id)
            idempotency_reservation, subject_reservation = build_reservations(
                validation
            )
            audit = build_audit(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                dequeue_id=subject_reservation.dequeue_id,
                event="one_shot_controlled_dequeue_indeterminate",
                outcome="indeterminate",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                occurred_at=received_at,
                dequeue_subject_fingerprint=(
                    subject_reservation.dequeue_subject_fingerprint
                ),
            )
            self._store.reserve_attempt(
                idempotency_reservation=idempotency_reservation,
                subject_reservation=subject_reservation,
                audit_evidence=audit,
                controlled_dequeue_admission_valid_until=(
                    exact_create.controlled_dequeue_admission_valid_until
                ),
            )
            return _failure(
                "dequeue_adapter_unavailable",
                correlation_id,
                outcome="indeterminate",
            )
        except OneShotControlledDequeueStoreError as error:
            code = (
                error.code
                if error.code
                in {
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
        dequeue_id: str,
        correlation_id: str,
    ) -> OneShotControlledDequeueResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(operator_id=operator, dequeue_id=dequeue_id)
            return _success(record, correlation_id, self._server_now())
        except OneShotControlledDequeueStoreError as error:
            code = error.code if error.code in {"not_found", "store_corrupt"} else "internal_error"
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
    ) -> OneShotControlledDequeueCollectionV1 | tuple[OneShotControlledDequeueResultV1, ...]:
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


def create_one_shot_controlled_dequeue_reservation_service(
    *,
    evidence_reader: OneShotControlledDequeueEvidenceReader,
    store: OneShotControlledDequeueStore,
    clock: Callable[[], datetime],
    enabled: bool = False,
) -> OneShotControlledDequeueReservationService:
    """Explicit P2 construction; no production composition calls this."""
    return OneShotControlledDequeueReservationService(
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        enabled=enabled,
    )


def _success(
    record,
    correlation_id: str,
    evaluated_at: str,
) -> OneShotControlledDequeueResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return OneShotControlledDequeueResultV1(
        ok=True,
        outcome="success",
        record=record,
        status=derive_status(record, evaluated_at=evaluated_at),
        error=None,
        correlation_fingerprint=correlation,
        one_shot_controlled_dequeue_recorded=True,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:one-shot-controlled-dequeue-correlation:v1", safe)


def _validation_failure(
    message: str, correlation_id: str
) -> OneShotControlledDequeueResultV1:
    lowered = message.lower()
    if "home assistant" in lowered or "capability" in lowered:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in lowered:
        return _failure("not_found", correlation_id)
    if "not active" in lowered and "v0.44" in lowered:
        return _failure("v044_admission_not_active", correlation_id)
    if "not recorded" in lowered and "v0.44" in lowered:
        return _failure("v044_admission_not_recorded", correlation_id)
    if "not eligible" in lowered and "v0.44" in lowered:
        return _failure("v044_admission_not_eligible", correlation_id)
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
    if "executable" in lowered or "payload" in lowered or "dequeued" in lowered:
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
) -> OneShotControlledDequeueResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return OneShotControlledDequeueResultV1(
        ok=False,
        outcome=outcome,
        record=None,
        status=None,
        error=OneShotControlledDequeueRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )


__all__ = (
    "OneShotControlledDequeueEvidenceReader",
    "OneShotControlledDequeueReservationService",
    "create_one_shot_controlled_dequeue_reservation_service",
)
