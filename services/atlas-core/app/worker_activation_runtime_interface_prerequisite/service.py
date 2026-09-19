"""Default-off Core-local evidence service. Construction grants no runtime authority."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from . import contract as c
from .store import (
    WorkerActivationRuntimeInterfacePrerequisiteStore,
    WorkerActivationRuntimeInterfacePrerequisiteStoreError,
)

DEFAULT_ENABLED = False


class WorkerActivationRuntimeInterfacePrerequisiteReader(Protocol):
    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        runtime_plan_review_id: str,
        valid_until: str,
    ) -> (
        tuple[
            c.v056.WorkerActivationRuntimePlanReviewV1,
            c.v056.WorkerActivationRuntimePlanReviewStatusV1,
        ]
        | None
    ): ...


def server_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None or value.microsecond:
        raise ValueError("invalid trusted clock")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorkerActivationRuntimeInterfacePrerequisiteService:
    def __init__(
        self,
        *,
        prerequisite_reader: WorkerActivationRuntimeInterfacePrerequisiteReader,
        store: WorkerActivationRuntimeInterfacePrerequisiteStore,
        clock: Callable[[], datetime],
        enabled: bool = DEFAULT_ENABLED,
    ):
        self._prerequisite_reader = prerequisite_reader
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
            create = (
                c.WorkerActivationRuntimeInterfacePrerequisiteCreateV1.model_validate(
                    create
                )
            )
            idem = c.idempotency_key_fingerprint(operator, idempotency_key)
            request = c.request_fingerprint(
                operator_id=operator, candidate_record_id=candidate, create=create
            )

            def checked_result(record, duplicate):
                # Reparse even injected/copy-constructed store results, and bind
                # both readback paths to this exact request without consulting
                # the predecessor or renewing the retained evidence timestamp.
                record = (
                    c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate(
                        record
                    )
                )
                if (
                    record.operator_id != operator
                    or record.candidate_record_id != candidate
                    or record.idempotency_key_fingerprint != idem
                    or c.build_create(
                        receipt=record.worker_activation_runtime_plan_review,
                        receipt_status=record.worker_activation_runtime_plan_review_status,
                    )
                    != create
                ):
                    raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                        "fingerprint_mismatch"
                    )
                return self._result(record, duplicate)

            existing = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                request_fingerprint=request.value,
            )
            if existing is not None:
                return checked_result(existing, True)
            received_at = server_now(self._clock)
            reservation = c._signed(
                c.WorkerActivationRuntimeInterfacePrerequisiteSubjectReservationV1,
                {
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "runtime_plan_review_id": create.runtime_plan_review_id,
                    "reserved_at": received_at,
                    "subject_fingerprint": c.subject_fingerprint(
                        operator_id=operator,
                        candidate_record_id=candidate,
                        runtime_plan_review_id=create.runtime_plan_review_id,
                    ),
                    "idempotency_key_fingerprint": idem,
                    "request_fingerprint": request,
                },
                "reservation_fingerprint",
                c.reservation_fingerprint,
            )

            last_validated_at = received_at

            def validate():
                nonlocal last_validated_at
                pair = self._prerequisite_reader.read_owned(
                    operator_id=operator,
                    candidate_record_id=candidate,
                    runtime_plan_review_id=create.runtime_plan_review_id,
                    valid_until=create.valid_until,
                )
                if pair is None:
                    raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                        "evidence_not_found"
                    )
                # Create pins the stable durable review status, never a GET-time
                # projection that would change the request identity on each read.
                if pair[1].evaluated_at != pair[0].recorded_at:
                    raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                        "fingerprint_mismatch"
                    )
                now = server_now(self._clock)
                if now < last_validated_at:
                    raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                        "evidence_stale"
                    )
                last_validated_at = now
                # The journal established absence before prepare; revalidation
                # is exclusively for this call's own committed reservation.
                raw = {
                    "subject_previously_reserved": False,
                    "idempotency_key_previously_reserved": False,
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "authority": c.WorkerActivationRuntimeInterfacePrerequisiteAuthorityContextV1(
                        authenticated_operator_id=operator,
                        permission=c.PERMISSION,
                        permission_verified=True,
                        request_received_at=now,
                    ),
                    "create": create,
                    "worker_activation_runtime_plan_review": pair[0],
                    "worker_activation_runtime_plan_review_status": pair[1],
                }
                evaluation = (
                    c.evaluate_worker_activation_runtime_interface_prerequisite(raw)
                )
                if not evaluation.worker_activation_runtime_interface_prerequisite_recorded:
                    raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                        evaluation.blockers[0]
                    )
                raw["authority"] = (
                    c.WorkerActivationRuntimeInterfacePrerequisiteAuthorityContextV1(
                        authenticated_operator_id=operator,
                        permission=c.PERMISSION,
                        permission_verified=True,
                        request_received_at=received_at,
                    )
                )
                return c.WorkerActivationRuntimeInterfacePrerequisiteValidationInputV1.model_validate(
                    raw
                )

            def prepare():
                return c.build_runtime_interface_prerequisite(
                    validate(), idempotency_key=idempotency_key
                )

            def revalidate(record):
                current = prepare()
                if current != record:
                    raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                        "fingerprint_mismatch"
                    )

            record, created = self._store.append(
                reservation=reservation,
                prepare=prepare,
                revalidate=revalidate,
                correlation_fingerprint=self._correlation(correlation_id),
            )
            appended = created
            return checked_result(record, not created)
        except WorkerActivationRuntimeInterfacePrerequisiteStoreError as error:
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
        runtime_interface_prerequisite_id,
        correlation_id,
    ):
        try:
            operator = self._authorize(authenticated_operator_id, permission_verified)
            candidate = TypeAdapter(c.CanonicalUuid4).validate_python(
                candidate_record_id, strict=True
            )
            prerequisite_id = TypeAdapter(c.CanonicalUuid5).validate_python(
                runtime_interface_prerequisite_id, strict=True
            )
            record = self._store.get(
                operator_id=operator,
                candidate_record_id=candidate,
                runtime_interface_prerequisite_id=prerequisite_id,
            )
            record = c.WorkerActivationRuntimeInterfacePrerequisiteV1.model_validate(
                record
            )
            if (
                record.operator_id != operator
                or record.candidate_record_id != candidate
                or record.runtime_interface_prerequisite_id != prerequisite_id
            ):
                raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                    "evidence_not_found"
                )
            return self._result(record, False)
        except WorkerActivationRuntimeInterfacePrerequisiteStoreError as error:
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
                c.WorkerActivationRuntimeInterfacePrerequisiteCollectionV1,
                {
                    "operator_id": operator,
                    "candidate_record_id": candidate,
                    "items": items,
                    "count": len(items),
                },
                "collection_fingerprint",
                c.collection_fingerprint,
            )
        except WorkerActivationRuntimeInterfacePrerequisiteStoreError as error:
            return self._failure(error.code, correlation_id)
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            return self._failure("invalid_request", correlation_id)

    @staticmethod
    def _authorize(operator, permission):
        if operator is None:
            raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                "unauthenticated"
            )
        if permission is not True:
            raise WorkerActivationRuntimeInterfacePrerequisiteStoreError("forbidden")
        return TypeAdapter(c.OperatorId).validate_python(operator, strict=True)

    def _result(self, record, duplicate):
        return c.WorkerActivationRuntimeInterfacePrerequisiteResultV1(
            record=record,
            status=c.derive_status(record, evaluated_at=server_now(self._clock)),
            exact_duplicate=duplicate,
        )

    @staticmethod
    def _correlation(value):
        safe = (
            value
            if type(value) is str
            and 0 < len(value) <= 128
            and all(32 <= ord(char) <= 126 for char in value)
            else "redacted"
        )
        return c.fingerprint("correlation", safe)

    @classmethod
    def _failure(cls, code, correlation):
        return c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1(
            error_code=code, correlation_fingerprint=cls._correlation(correlation)
        )


def create_worker_activation_runtime_interface_prerequisite_service(**kwargs):
    """Explicit opt-in composition only; never called by production startup."""
    # Keep composition fail-closed when the feature flag is omitted. Enabling
    # remains an explicit construction decision for separately authorized use.
    kwargs.setdefault("enabled", DEFAULT_ENABLED)
    return WorkerActivationRuntimeInterfacePrerequisiteService(**kwargs)
