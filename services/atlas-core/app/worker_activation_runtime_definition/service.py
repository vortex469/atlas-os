"""Default-off owner-scoped service for reference-only definition evidence."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from . import contract as c
from .store import (
    WorkerActivationRuntimeDefinitionStore,
    WorkerActivationRuntimeDefinitionStoreError,
)


class DefinitionReader(Protocol):
    def read_owned(
        self, *, operator_id: str, definition_id: str
    ) -> c.WorkerActivationRuntimeDefinitionV1 | None: ...


def server_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None or value.microsecond:
        raise ValueError("invalid trusted clock")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorkerActivationRuntimeDefinitionService:
    def __init__(
        self,
        *,
        definition_reader: DefinitionReader,
        store: WorkerActivationRuntimeDefinitionStore,
        clock: Callable[[], datetime],
        enabled=False,
    ):
        self._reader, self._store, self._clock, self._enabled = (
            definition_reader,
            store,
            clock,
            enabled is True,
        )

    def create(
        self,
        create,
        *,
        authenticated_operator_id,
        permission_verified,
        candidate_record_id,
        idempotency_key,
        correlation_id,
    ):
        attempted = False
        try:
            operator = self._authorize(authenticated_operator_id, permission_verified)
            if not self._enabled:
                return self._failure(
                    "installation_capability_unsupported", correlation_id
                )
            candidate = TypeAdapter(c.CanonicalUuid4).validate_python(
                candidate_record_id, strict=True
            )
            request = c.WorkerActivationRuntimeDefinitionCreateV1.model_validate(create)
            idem = c.idempotency_key_fingerprint(operator, idempotency_key)
            req_fp = c.request_fingerprint(operator, candidate, request)
            existing = self._store.resolve(operator, idem.value, req_fp.value)
            if existing is not None:
                return self._result(existing, True)
            now = server_now(self._clock)
            reservation = (
                c.WorkerActivationRuntimeDefinitionSubjectReservationV1.model_validate(
                    {
                        "operator_id": operator,
                        "candidate_record_id": candidate,
                        "definition_id": request.definition_id,
                        "reserved_at": now,
                        "subject_fingerprint": c.subject_fingerprint(
                            operator, candidate, request.definition_id
                        ),
                        "idempotency_key_fingerprint": idem,
                        "request_fingerprint": req_fp,
                        "reservation_fingerprint": c.reservation_fingerprint(
                            {
                                "operator_id": operator,
                                "candidate_record_id": candidate,
                                "definition_id": request.definition_id,
                                "reserved_at": now,
                                "subject_fingerprint": c.subject_fingerprint(
                                    operator, candidate, request.definition_id
                                ),
                                "idempotency_key_fingerprint": idem,
                                "request_fingerprint": req_fp,
                                "permanent": True,
                            }
                        ),
                    }
                )
            )

            def prepare():
                definition = self._reader.read_owned(
                    operator_id=operator, definition_id=request.definition_id
                )
                if definition is None:
                    raise WorkerActivationRuntimeDefinitionStoreError(
                        "definition_not_found"
                    )
                definition = c.WorkerActivationRuntimeDefinitionV1.model_validate(
                    definition
                )
                if (
                    definition.operator_id != operator
                    or definition.candidate_record_id != candidate
                    or definition.definition_fingerprint
                    != request.definition_fingerprint
                    or definition.valid_until != request.valid_until
                ):
                    raise WorkerActivationRuntimeDefinitionStoreError("invalid_request")
                evaluation = c.evaluate_worker_activation_runtime_definition(
                    definition, evaluated_at=now
                )
                if evaluation.state != "recorded":
                    raise WorkerActivationRuntimeDefinitionStoreError("invalid_request")
                return _record(
                    operator,
                    candidate,
                    now,
                    definition,
                    evaluation,
                    idem,
                    reservation.subject_fingerprint,
                )

            def revalidate(record):
                if (
                    self._reader.read_owned(
                        operator_id=operator, definition_id=request.definition_id
                    )
                    != record.definition
                ):
                    raise WorkerActivationRuntimeDefinitionStoreError(
                        "fingerprint_mismatch"
                    )

            record, created = self._store.append(
                reservation, prepare, revalidate, self._correlation(correlation_id)
            )
            attempted = created
            return self._result(record, not created)
        except WorkerActivationRuntimeDefinitionStoreError as error:
            return self._failure(error.code, correlation_id)
        # Unexpected reader/model/storage errors fail closed after an append.
        except Exception:  # noqa: BLE001
            return self._failure(
                "append_indeterminate" if attempted else "invalid_request",
                correlation_id,
            )

    def get(
        self,
        *,
        authenticated_operator_id,
        permission_verified,
        candidate_record_id,
        definition_id,
        correlation_id,
    ):
        try:
            operator = self._authorize(authenticated_operator_id, permission_verified)
            candidate = TypeAdapter(c.CanonicalUuid4).validate_python(
                candidate_record_id, strict=True
            )
            definition = TypeAdapter(c.CanonicalUuid5).validate_python(
                definition_id, strict=True
            )
            return self._result(self._store.get(operator, candidate, definition), False)
        except WorkerActivationRuntimeDefinitionStoreError as e:
            return self._failure(e.code, correlation_id)
        # Unexpected read errors are deliberately redacted and fail closed.
        except Exception:  # noqa: BLE001
            return self._failure("invalid_request", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id,
        permission_verified,
        candidate_record_id,
        correlation_id,
    ):
        try:
            operator = self._authorize(authenticated_operator_id, permission_verified)
            candidate = TypeAdapter(c.CanonicalUuid4).validate_python(
                candidate_record_id, strict=True
            )
            items = self._store.list_owned(operator, candidate)
            return c.WorkerActivationRuntimeDefinitionCollectionV1.model_validate(
                {
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "items": items,
                    "count": len(items),
                    "collection_fingerprint": c.collection_fingerprint(
                        {
                            "operator_id": operator,
                            "candidate_record_id": candidate,
                            "items": items,
                            "count": len(items),
                        }
                    ),
                }
            )
        except WorkerActivationRuntimeDefinitionStoreError as e:
            return self._failure(e.code, correlation_id)
        # Unexpected read errors are deliberately redacted and fail closed.
        except Exception:  # noqa: BLE001
            return self._failure("invalid_request", correlation_id)

    @staticmethod
    def _authorize(operator, verified):
        if operator is None:
            raise WorkerActivationRuntimeDefinitionStoreError("unauthenticated")
        if verified is not True:
            raise WorkerActivationRuntimeDefinitionStoreError("forbidden")
        return TypeAdapter(c.OperatorId).validate_python(operator, strict=True)

    def _result(self, record, duplicate):
        now = server_now(self._clock)
        lifecycle = "expired" if now >= record.valid_until else "active"
        status_raw = {
            "definition_id": record.definition_id,
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "recorded_at": record.recorded_at,
            "valid_until": record.valid_until,
            "lifecycle": lifecycle,
            "evaluation_fingerprint": record.evaluation.evaluation_fingerprint,
        }
        status = c.WorkerActivationRuntimeDefinitionStatusV1.model_validate(
            {**status_raw, "status_fingerprint": c.status_fingerprint(status_raw)}
        )
        return c.WorkerActivationRuntimeDefinitionResultV1(
            record=record, status=status, exact_duplicate=duplicate
        )

    @staticmethod
    def _correlation(value):
        return c._fingerprint(
            "correlation",
            value if type(value) is str and len(value) <= 128 else "redacted",
        )

    @classmethod
    def _failure(cls, code, correlation):
        return c.WorkerActivationRuntimeDefinitionErrorV1(
            error_code=code, correlation_fingerprint=cls._correlation(correlation)
        )


def _record(operator, candidate, now, definition, evaluation, idem, subject):
    raw = {
        "definition_id": definition.definition_id,
        "operator_id": operator,
        "candidate_record_id": candidate,
        "recorded_at": now,
        "valid_until": definition.valid_until,
        "definition": definition,
        "evaluation": evaluation,
        "subject_fingerprint": subject,
        "idempotency_key_fingerprint": idem,
    }
    seed = c.WorkerActivationRuntimeDefinitionV1Record.model_construct(**raw)
    return c.WorkerActivationRuntimeDefinitionV1Record.model_validate(
        {**c._plain(seed), "record_fingerprint": c.record_fingerprint(seed)}
    )


def create_worker_activation_runtime_definition_service(**kwargs):
    return WorkerActivationRuntimeDefinitionService(**kwargs)
