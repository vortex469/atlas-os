"""Default-off Core-local evidence service. Construction grants no runtime authority."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from . import contract as c
from .store import (
    WorkerActivationRuntimePrerequisiteStore,
    WorkerActivationRuntimePrerequisiteStoreError,
)


class WorkerActivationRuntimePrerequisiteReader(Protocol):
    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        admission_id: str,
        valid_until: str,
    ) -> (
        tuple[
            c.v052.ControlledWorkerQueueClaimLeaseAcknowledgementV1,
            c.v052.ControlledWorkerQueueClaimLeaseAcknowledgementStatusV1,
        ]
        | None
    ): ...


def server_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None or value.microsecond:
        raise ValueError("invalid trusted clock")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorkerActivationRuntimePrerequisiteService:
    def __init__(
        self,
        *,
        receipt_reader: WorkerActivationRuntimePrerequisiteReader,
        store: WorkerActivationRuntimePrerequisiteStore,
        clock: Callable[[], datetime],
        enabled: bool = False,
    ):
        self._receipt_reader = receipt_reader
        self._store = store
        self._clock = clock
        self._enabled = enabled is True

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
        appended = False
        try:
            operator = self._authorize(authenticated_operator_id, permission_verified)
            if not self._enabled:
                return self._failure(
                    "installation_capability_unsupported", correlation_id
                )
            candidate = TypeAdapter(c.CanonicalUuid4).validate_python(
                candidate_record_id, strict=True
            )
            create = c.WorkerActivationRuntimePrerequisiteCreateV1.model_validate(
                create
            )
            idem = c.idempotency_key_fingerprint(operator, idempotency_key)
            request = c.request_fingerprint(
                operator_id=operator, candidate_record_id=candidate, create=create
            )
            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                request_fingerprint=request.value,
            )
            if existing is not None:
                return self._result(existing, True)
            received_at = server_now(self._clock)
            reservation = c._signed(
                c.WorkerActivationRuntimePrerequisiteSubjectReservationV1,
                {
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "admission_id": create.admission_id,
                    "reserved_at": received_at,
                    "subject_fingerprint": c.subject_fingerprint(
                        operator_id=operator,
                        candidate_record_id=candidate,
                        admission_id=create.admission_id,
                    ),
                    "idempotency_key_fingerprint": idem,
                    "request_fingerprint": request,
                },
                "reservation_fingerprint",
                c.reservation_fingerprint,
            )

            def validate():
                pair = self._receipt_reader.read_owned(
                    operator_id=operator,
                    candidate_record_id=candidate,
                    admission_id=create.admission_id,
                    valid_until=create.valid_until,
                )
                if pair is None:
                    raise WorkerActivationRuntimePrerequisiteStoreError(
                        "evidence_not_found"
                    )
                now = server_now(self._clock)
                if now < received_at:
                    raise WorkerActivationRuntimePrerequisiteStoreError(
                        "evidence_stale"
                    )
                raw = {
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "authority": c.WorkerActivationRuntimePrerequisiteAuthorityContextV1(
                        authenticated_operator_id=operator,
                        permission=c.PERMISSION,
                        request_received_at=now,
                    ),
                    "create": create,
                    "controlled_worker_queue_claim_lease_acknowledgement": pair[0],
                    "controlled_worker_queue_claim_lease_acknowledgement_status": pair[
                        1
                    ],
                }
                evaluation = c.evaluate_worker_activation_runtime_prerequisite(raw)
                if not evaluation.worker_activation_runtime_prerequisite_recorded:
                    raise WorkerActivationRuntimePrerequisiteStoreError(
                        evaluation.blockers[0]
                    )
                raw["authority"] = (
                    c.WorkerActivationRuntimePrerequisiteAuthorityContextV1(
                        authenticated_operator_id=operator,
                        permission=c.PERMISSION,
                        request_received_at=received_at,
                    )
                )
                return c.WorkerActivationRuntimePrerequisiteValidationInputV1.model_validate(
                    raw
                )

            def prepare():
                return c.build_prerequisite(validate(), idempotency_key=idempotency_key)

            def revalidate(record):
                current = prepare()
                if current != record:
                    raise WorkerActivationRuntimePrerequisiteStoreError(
                        "fingerprint_mismatch"
                    )

            record, created = self._store.append(
                reservation=reservation,
                prepare=prepare,
                revalidate=revalidate,
                correlation_fingerprint=self._correlation(correlation_id),
            )
            appended = created
            return self._result(record, not created)
        except WorkerActivationRuntimePrerequisiteStoreError as error:
            return self._failure(error.code, correlation_id)
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            return self._failure(
                "append_indeterminate" if appended else "invalid_request",
                correlation_id,
            )

    def get(
        self,
        *,
        authenticated_operator_id,
        permission_verified,
        candidate_record_id,
        prerequisite_id,
        correlation_id,
    ):
        try:
            operator = self._authorize(authenticated_operator_id, permission_verified)
            record = self._store.get(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                prerequisite_id=prerequisite_id,
            )
            return self._result(record, False)
        except WorkerActivationRuntimePrerequisiteStoreError as error:
            return self._failure(error.code, correlation_id)
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
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
            items = self._store.list_owned(
                operator_id=operator, candidate_record_id=candidate
            )
            return c._signed(
                c.WorkerActivationRuntimePrerequisiteCollectionV1,
                {
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "items": items,
                    "count": len(items),
                },
                "collection_fingerprint",
                c.collection_fingerprint,
            )
        except WorkerActivationRuntimePrerequisiteStoreError as error:
            return self._failure(error.code, correlation_id)
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            return self._failure("invalid_request", correlation_id)

    @staticmethod
    def _authorize(operator, permission):
        if operator is None:
            raise WorkerActivationRuntimePrerequisiteStoreError("unauthenticated")
        if permission is not True:
            raise WorkerActivationRuntimePrerequisiteStoreError("forbidden")
        return TypeAdapter(c.OperatorId).validate_python(operator, strict=True)

    def _result(self, record, duplicate):
        return c.WorkerActivationRuntimePrerequisiteResultV1(
            record=record,
            status=c.derive_status(record, evaluated_at=server_now(self._clock)),
            exact_duplicate=duplicate,
        )

    @staticmethod
    def _correlation(value):
        safe = value if type(value) is str and 0 < len(value) <= 128 else "redacted"
        return c.fingerprint("correlation", safe)

    @classmethod
    def _failure(cls, code, correlation):
        return c.WorkerActivationRuntimePrerequisiteRedactedErrorV1(
            error_code=code, correlation_fingerprint=cls._correlation(correlation)
        )


def create_worker_activation_runtime_prerequisite_service(**kwargs):
    """Explicit opt-in composition only; never called by production startup."""
    return WorkerActivationRuntimePrerequisiteService(**kwargs)
