"""Explicitly constructed Core-local v0.38 worker-admission evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.runner_binding_plan.contract import (
    RunnerBindingPlanStatusV1,
    RunnerBindingPlanV1,
)

from .contract import (
    PERMISSION,
    OperatorId,
    WorkerAdmissionAuthorityContextV1,
    WorkerAdmissionStubAuditEvidenceV1,
    WorkerAdmissionStubCreateV1,
    WorkerAdmissionStubRedactedErrorV1,
    WorkerAdmissionStubResultV1,
    WorkerAdmissionStubValidationInputV1,
    WorkerReferenceV1,
    audit_evidence_fingerprint,
    build_stub,
    derive_status,
    idempotency_key_fingerprint,
    opaque_fingerprint,
)
from .store import WorkerAdmissionStubStore, WorkerAdmissionStubStoreError


class WorkerAdmissionStubEvidenceReader(Protocol):
    """Read exact owner-scoped v0.37 facts without external I/O."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        runner_binding_plan_id: str,
        runner_binding_plan_valid_until: str,
    ) -> tuple[RunnerBindingPlanV1, RunnerBindingPlanStatusV1, bool] | None: ...


class WorkerAdmissionStubReferenceReader(Protocol):
    """Read an eligible owner-scoped worker reference without contacting it."""

    def read_owned(
        self, *, operator_id: str, worker_reference_id: str
    ) -> WorkerReferenceV1 | None: ...


class WorkerAdmissionStubService:
    """Create/get/list stub evidence; exposes no worker or effect operation."""

    def __init__(
        self,
        *,
        evidence_reader: WorkerAdmissionStubEvidenceReader,
        worker_reference_reader: WorkerAdmissionStubReferenceReader,
        store: WorkerAdmissionStubStore,
        clock: Callable[[], datetime],
        stub_id_factory: Callable[[], str],
        intent_id_factory: Callable[[], str],
    ) -> None:
        self._evidence_reader = evidence_reader
        self._worker_reference_reader = worker_reference_reader
        self._store = store
        self._clock = clock
        self._stub_id_factory = stub_id_factory
        self._intent_id_factory = intent_id_factory

    def create(
        self,
        create: WorkerAdmissionStubCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> WorkerAdmissionStubResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = WorkerAdmissionStubCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idem = idempotency_key_fingerprint(operator, idempotency_key)
        except Exception:  # noqa: BLE001 - parsing detail remains redacted
            return _failure("malformed", correlation_id)

        correlation = _correlation_fingerprint(correlation_id)
        try:
            reserved = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                runner_binding_plan_valid_until=exact_create.runner_binding_plan_valid_until,
            )
            if reserved is not None:
                if not _same_request(reserved, candidate_record_id, exact_create):
                    return _failure("conflict", correlation_id)
                return self._success(
                    reserved,
                    disposition="exact_duplicate",
                    correlation_fingerprint=correlation,
                    observed_at=self._server_now(),
                )

            recorded_at = self._server_now()
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                runner_binding_plan_id=exact_create.runner_binding_plan_id,
                runner_binding_plan_valid_until=exact_create.runner_binding_plan_valid_until,
            )
            worker = self._worker_reference_reader.read_owned(
                operator_id=operator,
                worker_reference_id=exact_create.worker_reference_id,
            )
            if evidence is None or worker is None:
                return _failure("not_found", correlation_id)
            plan, plan_status, home_assistant = evidence
            authority = WorkerAdmissionAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = WorkerAdmissionStubValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                runner_binding_plan=plan,
                runner_binding_plan_status=plan_status,
                worker_reference=worker,
                idempotency_key=idempotency_key,
                home_assistant=home_assistant,
            )
            stub, _, reservation = build_stub(
                validation,
                stub_id=self._stub_id_factory(),
                intent_id=self._intent_id_factory(),
            )
            audit = _audit(
                stub,
                outcome="recorded",
                correlation_fingerprint=correlation,
                occurred_at=recorded_at,
            )
            stored, created = self._store.append(
                stub=stub,
                reservation=reservation,
                audit_evidence=audit,
                runner_binding_plan_valid_until=exact_create.runner_binding_plan_valid_until,
            )
            return self._success(
                stored,
                disposition="recorded" if created else "exact_duplicate",
                correlation_fingerprint=correlation,
                observed_at=recorded_at if created else self._server_now(),
            )
        except WorkerAdmissionStubStoreError as error:
            code = error.code if error.code in {"conflict", "quota_exceeded"} else "unavailable"
            return _failure(code, correlation_id)
        except (TypeError, ValueError) as error:
            return _validation_failure(str(error), correlation_id)
        except Exception:  # noqa: BLE001 - injected dependency failures are redacted
            return _failure("unavailable", correlation_id)

    def get(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        stub_id: str,
        correlation_id: str,
    ) -> WorkerAdmissionStubResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            stub = self._store.get(operator_id=operator, stub_id=stub_id)
            return self._success(
                stub,
                disposition="read",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                observed_at=self._server_now(),
            )
        except WorkerAdmissionStubStoreError as error:
            return _failure(
                "not_found" if error.code == "not_found" else "unavailable",
                correlation_id,
            )
        except Exception:  # noqa: BLE001 - read details remain redacted
            return _failure("unavailable", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        correlation_id: str,
    ) -> tuple[WorkerAdmissionStubResultV1, ...]:
        if authenticated_operator_id is None:
            return (_failure("unauthenticated", correlation_id),)
        if not permission_verified:
            return (_failure("unauthorized", correlation_id),)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            observed_at = self._server_now()
            correlation = _correlation_fingerprint(correlation_id)
            return tuple(
                self._success(
                    stub,
                    disposition="read",
                    correlation_fingerprint=correlation,
                    observed_at=observed_at,
                )
                for stub in self._store.list_owned(operator_id=operator)
            )
        except Exception:  # noqa: BLE001 - listing details remain redacted
            return (_failure("unavailable", correlation_id),)

    def _success(
        self,
        stub,
        *,
        disposition: str,
        correlation_fingerprint,
        observed_at: str,
    ) -> WorkerAdmissionStubResultV1:
        return WorkerAdmissionStubResultV1(
            disposition=disposition,
            stub=stub,
            status=derive_status(stub, observed_at=observed_at),
            audit_evidence=_audit(
                stub,
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


def create_worker_admission_stub_service(
    *,
    evidence_reader: WorkerAdmissionStubEvidenceReader,
    worker_reference_reader: WorkerAdmissionStubReferenceReader,
    store: WorkerAdmissionStubStore,
    clock: Callable[[], datetime],
    stub_id_factory: Callable[[], str],
    intent_id_factory: Callable[[], str],
) -> WorkerAdmissionStubService:
    """Explicit P2 construction; no production composition calls this."""
    return WorkerAdmissionStubService(
        evidence_reader=evidence_reader,
        worker_reference_reader=worker_reference_reader,
        store=store,
        clock=clock,
        stub_id_factory=stub_id_factory,
        intent_id_factory=intent_id_factory,
    )


def _same_request(stub, candidate_record_id: str, create: WorkerAdmissionStubCreateV1) -> bool:
    return (
        stub.candidate_record_id == candidate_record_id
        and stub.linkage.runner_binding_plan_id == create.runner_binding_plan_id
        and stub.linkage.runner_binding_plan_fingerprint == create.runner_binding_plan_fingerprint
        and stub.worker_reference.worker_reference_id == create.worker_reference_id
        and stub.worker_reference.reference_fingerprint == create.worker_reference_fingerprint
        and stub.inherited_limits.limits_fingerprint == create.inherited_limits_fingerprint
    )


def _audit(stub, *, outcome: str, correlation_fingerprint, occurred_at: str):
    raw = {
        "event": "worker_admission_stub_recorded" if outcome == "recorded" else "worker_admission_stub_read",
        "outcome": outcome,
        "operator_fingerprint": opaque_fingerprint("atlas:worker-admission-stub-operator:v1", stub.operator_id),
        "candidate_record_fingerprint": opaque_fingerprint("atlas:worker-admission-stub-candidate:v1", stub.candidate_record_id),
        "stub_fingerprint": stub.stub_fingerprint,
        "correlation_fingerprint": correlation_fingerprint,
        "occurred_at": occurred_at,
    }
    seed = WorkerAdmissionStubAuditEvidenceV1.model_construct(
        **raw, audit_fingerprint=stub.stub_fingerprint
    )
    return WorkerAdmissionStubAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_evidence_fingerprint(seed)}
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:worker-admission-stub-correlation:v1", safe)


def _validation_failure(message: str, correlation_id: str) -> WorkerAdmissionStubResultV1:
    if "Home Assistant" in message:
        return _failure("not_eligible", correlation_id)
    if "ownership" in message:
        return _failure("not_found", correlation_id)
    if "not active" in message or "not binding_planned" in message:
        return _failure("not_eligible", correlation_id)
    if "stale" in message or "future" in message or "expired" in message:
        return _failure("expired", correlation_id)
    if "fingerprint" in message or "linkage" in message or "limits" in message:
        return _failure("not_eligible", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(error_code: str, correlation_id: str) -> WorkerAdmissionStubResultV1:
    return WorkerAdmissionStubResultV1(
        disposition="blocked",
        stub=None,
        status=None,
        audit_evidence=None,
        error=WorkerAdmissionStubRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=_correlation_fingerprint(correlation_id),
        ),
    )
