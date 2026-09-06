"""Explicit Core-local v0.48 worker binding activation evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from .contract import (
    PERMISSION,
    OperatorId,
    WorkerBindingActivationEvidenceAuthorityContextV1,
    WorkerBindingActivationEvidenceCollectionV1,
    WorkerBindingActivationEvidenceCreateV1,
    WorkerBindingActivationEvidenceRedactedErrorV1,
    WorkerBindingActivationEvidenceResultV1,
    WorkerBindingActivationEvidenceV1,
    WorkerBindingActivationEvidenceValidationInputV1,
    build_activation_evidence,
    build_audit,
    build_collection,
    build_reservations,
    derive_status,
    evaluate_worker_binding_activation_evidence,
    idempotency_key_fingerprint,
    opaque_fingerprint,
    request_fingerprint,
)
from .store import (
    WorkerBindingActivationEvidenceStore,
    WorkerBindingActivationEvidenceStoreError,
)


class WorkerBindingActivationEvidencePreflightReader(Protocol):
    """Read exact owner-scoped v0.47 preflight evidence without effects."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        preflight_id: str,
        preflight_valid_until: str,
    ) -> object | None: ...


class WorkerBindingActivationEvidenceService:
    """Create/get/list bounded evidence; no activation or worker contact exists."""

    def __init__(
        self,
        *,
        preflight_reader: WorkerBindingActivationEvidencePreflightReader,
        store: WorkerBindingActivationEvidenceStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ) -> None:
        self._preflight_reader = preflight_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled

    def create(
        self,
        create: WorkerBindingActivationEvidenceCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> WorkerBindingActivationEvidenceResultV1:
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
            exact_create = WorkerBindingActivationEvidenceCreateV1.model_validate(
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
                preflight_valid_until=exact_create.preflight_valid_until,
            )
            if existing is not None:
                return _success(existing, correlation_id, self._server_now())
        except WorkerBindingActivationEvidenceStoreError as error:
            if error.code == "append_indeterminate":
                return _failure(
                    "append_indeterminate", correlation_id, outcome="indeterminate"
                )
            if error.code in {"idempotency_conflict", "store_corrupt"}:
                return _failure(error.code, correlation_id)
            return _failure("internal_error", correlation_id)

        try:
            evidence = self._preflight_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                preflight_id=exact_create.preflight_id,
                preflight_valid_until=exact_create.preflight_valid_until,
            )
            if evidence is None:
                return _failure("not_found", correlation_id)
            preflight, preflight_status = evidence  # type: ignore[misc]
            authority = WorkerBindingActivationEvidenceAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=received_at,
            )
            validation = WorkerBindingActivationEvidenceValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                worker_binding_activation_preflight=preflight,
                worker_binding_activation_preflight_status=preflight_status,
                idempotency_key=idempotency_key,
            )
            evaluation = evaluate_worker_binding_activation_evidence(validation)
            if not evaluation.activation_evidence_record_build_allowed:
                return _failure(evaluation.blockers[0], correlation_id)
            record = build_activation_evidence(validation)
            idempotency, reservation = build_reservations(validation, record)
            audit = build_audit(
                record,
                event="worker_binding_activation_evidence_recorded",
                outcome="recorded",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                occurred_at=received_at,
            )
            stored, _created = self._store.append(
                record=record,
                idempotency_reservation=idempotency,
                subject_reservation=reservation,
                audit_evidence=audit,
                preflight_valid_until=exact_create.preflight_valid_until,
            )
            return _success(stored, correlation_id, received_at)
        except WorkerBindingActivationEvidenceStoreError as error:
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
        activation_evidence_id: str,
        correlation_id: str,
    ) -> WorkerBindingActivationEvidenceResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("forbidden", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(operator_id=operator, activation_evidence_id=activation_evidence_id)
            return _success(record, correlation_id, self._server_now())
        except WorkerBindingActivationEvidenceStoreError as error:
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
    ) -> WorkerBindingActivationEvidenceCollectionV1 | tuple[WorkerBindingActivationEvidenceResultV1, ...]:
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


def create_worker_binding_activation_evidence_service(
    *,
    preflight_reader: WorkerBindingActivationEvidencePreflightReader,
    store: WorkerBindingActivationEvidenceStore,
    clock: Callable[[], datetime],
    enabled: bool = False,
) -> WorkerBindingActivationEvidenceService:
    """Explicit P2 construction; no production composition calls this."""
    return WorkerBindingActivationEvidenceService(
        preflight_reader=preflight_reader,
        store=store,
        clock=clock,
        enabled=enabled,
    )


def _success(
    record: WorkerBindingActivationEvidenceV1,
    correlation_id: str,
    evaluated_at: str,
) -> WorkerBindingActivationEvidenceResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return WorkerBindingActivationEvidenceResultV1(
        ok=True,
        outcome="success",
        record=record,
        status=derive_status(record, evaluated_at=evaluated_at),
        error=None,
        correlation_fingerprint=correlation,
        worker_binding_activation_evidence_recorded=True,
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint(
        "atlas:worker-binding-activation-evidence-correlation:v1", safe
    )


def _validation_failure(
    message: str, correlation_id: str
) -> WorkerBindingActivationEvidenceResultV1:
    lowered = message.lower()
    if "home assistant" in lowered or "capability" in lowered:
        return _failure("installation_capability_unsupported", correlation_id)
    if "ownership" in lowered:
        return _failure("not_found", correlation_id)
    if "not active" in lowered and "v0.47" in lowered:
        return _failure("v047_preflight_not_active", correlation_id)
    if "not recorded" in lowered and "v0.47" in lowered:
        return _failure("v047_preflight_not_recorded", correlation_id)
    if "stale" in lowered or "future" in lowered:
        return _failure("evidence_stale", correlation_id)
    if "expired" in lowered:
        return _failure("evidence_expired", correlation_id)
    if "ambiguous" in lowered:
        return _failure("ambiguous_state", correlation_id)
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
) -> WorkerBindingActivationEvidenceResultV1:
    correlation = _correlation_fingerprint(correlation_id)
    return WorkerBindingActivationEvidenceResultV1(
        ok=False,
        outcome=outcome,
        record=None,
        status=None,
        error=WorkerBindingActivationEvidenceRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )


__all__ = (
    "WorkerBindingActivationEvidencePreflightReader",
    "WorkerBindingActivationEvidenceService",
    "create_worker_binding_activation_evidence_service",
)
