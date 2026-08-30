"""Explicitly constructed Core-local v0.37 binding-plan evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.installation_execution_admission.contract import (
    InstallationExecutionAdmissionStatusV1,
    InstallationExecutionAdmissionV1,
)

from .contract import (
    PERMISSION,
    OperatorId,
    RunnerBindingPlanAuditEvidenceV1,
    RunnerBindingPlanAuthorityContextV1,
    RunnerBindingPlanCreateV1,
    RunnerBindingPlanRedactedErrorV1,
    RunnerBindingPlanResultV1,
    RunnerBindingPlanValidationInputV1,
    RunnerReferenceV1,
    audit_evidence_fingerprint,
    build_plan,
    derive_status,
    idempotency_key_fingerprint,
    opaque_fingerprint,
)
from .store import RunnerBindingPlanStore, RunnerBindingPlanStoreError


class RunnerBindingPlanEvidenceReader(Protocol):
    """Read exact owner-scoped v0.36 admission facts without external I/O."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        admission_id: str,
        admission_valid_until: str,
    ) -> tuple[
        InstallationExecutionAdmissionV1,
        InstallationExecutionAdmissionStatusV1,
        bool,
    ] | None: ...


class RunnerBindingPlanRunnerReader(Protocol):
    """Read an eligible owner-scoped runner reference without contacting it."""

    def read_owned(
        self, *, operator_id: str, runner_reference_id: str
    ) -> RunnerReferenceV1 | None: ...


class RunnerBindingPlanService:
    """Create/get/list binding-plan evidence; exposes no effect operation."""

    def __init__(
        self,
        *,
        evidence_reader: RunnerBindingPlanEvidenceReader,
        runner_reader: RunnerBindingPlanRunnerReader,
        store: RunnerBindingPlanStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._evidence_reader = evidence_reader
        self._runner_reader = runner_reader
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    def create(
        self,
        create: RunnerBindingPlanCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> RunnerBindingPlanResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = RunnerBindingPlanCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idem = idempotency_key_fingerprint(operator, idempotency_key)
        except Exception:  # noqa: BLE001 - parsing detail remains redacted
            return _failure("malformed", correlation_id)

        safe_correlation = _correlation_fingerprint(correlation_id)
        try:
            reserved = self._store.resolve_idempotency(
                operator_id=operator,
                idempotency_key_fingerprint=idem.value,
                admission_valid_until=exact_create.admission_valid_until,
            )
            if reserved is not None:
                if not _same_request(reserved, candidate_record_id, exact_create):
                    return _failure("conflict", correlation_id)
                return self._success(
                    reserved,
                    disposition="exact_duplicate",
                    correlation_fingerprint=safe_correlation,
                    observed_at=self._server_now(),
                )

            recorded_at = self._server_now()
            evidence = self._evidence_reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                admission_id=exact_create.admission_id,
                admission_valid_until=exact_create.admission_valid_until,
            )
            runner = self._runner_reader.read_owned(
                operator_id=operator,
                runner_reference_id=exact_create.runner_reference_id,
            )
            if evidence is None or runner is None:
                return _failure("not_found", correlation_id)
            admission, admission_status, home_assistant = evidence
            authority = RunnerBindingPlanAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = RunnerBindingPlanValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                execution_admission=admission,
                execution_admission_status=admission_status,
                runner_reference=runner,
                idempotency_key=idempotency_key,
                home_assistant=home_assistant,
            )
            plan, _, reservation = build_plan(validation, plan_id=self._id_factory())
            audit = _audit(
                plan,
                outcome="recorded",
                correlation_fingerprint=safe_correlation,
                occurred_at=recorded_at,
            )
            stored, created = self._store.append(
                plan=plan,
                reservation=reservation,
                audit_evidence=audit,
                admission_valid_until=exact_create.admission_valid_until,
            )
            return self._success(
                stored,
                disposition="recorded" if created else "exact_duplicate",
                correlation_fingerprint=safe_correlation,
                observed_at=recorded_at if created else self._server_now(),
            )
        except RunnerBindingPlanStoreError as error:
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
        plan_id: str,
        correlation_id: str,
    ) -> RunnerBindingPlanResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            plan = self._store.get(operator_id=operator, plan_id=plan_id)
            return self._success(
                plan,
                disposition="read",
                correlation_fingerprint=_correlation_fingerprint(correlation_id),
                observed_at=self._server_now(),
            )
        except RunnerBindingPlanStoreError as error:
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
    ) -> tuple[RunnerBindingPlanResultV1, ...]:
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
                    plan,
                    disposition="read",
                    correlation_fingerprint=correlation,
                    observed_at=observed_at,
                )
                for plan in self._store.list_owned(operator_id=operator)
            )
        except Exception:  # noqa: BLE001 - listing details remain redacted
            return (_failure("unavailable", correlation_id),)

    def _success(
        self,
        plan,
        *,
        disposition: str,
        correlation_fingerprint,
        observed_at: str,
    ) -> RunnerBindingPlanResultV1:
        return RunnerBindingPlanResultV1(
            disposition=disposition,
            plan=plan,
            status=derive_status(plan, observed_at=observed_at),
            audit_evidence=_audit(
                plan,
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


def create_runner_binding_plan_service(
    *,
    evidence_reader: RunnerBindingPlanEvidenceReader,
    runner_reader: RunnerBindingPlanRunnerReader,
    store: RunnerBindingPlanStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> RunnerBindingPlanService:
    """Explicit P2 construction; no production composition calls this."""
    return RunnerBindingPlanService(
        evidence_reader=evidence_reader,
        runner_reader=runner_reader,
        store=store,
        clock=clock,
        id_factory=id_factory,
    )


def _same_request(plan, candidate_record_id: str, create: RunnerBindingPlanCreateV1) -> bool:
    return (
        plan.candidate_record_id == candidate_record_id
        and plan.linkage.execution_admission_id == create.admission_id
        and plan.linkage.execution_admission_fingerprint == create.admission_fingerprint
        and plan.runner_reference.runner_reference_id == create.runner_reference_id
        and plan.runner_reference.reference_fingerprint == create.runner_reference_fingerprint
        and plan.limits.limits_fingerprint == create.limits_fingerprint
    )


def _audit(plan, *, outcome: str, correlation_fingerprint, occurred_at: str):
    raw = {
        "event": "runner_binding_plan_recorded" if outcome == "recorded" else "runner_binding_plan_read",
        "outcome": outcome,
        "operator_fingerprint": opaque_fingerprint("atlas:runner-binding-plan-operator:v1", plan.operator_id),
        "candidate_record_fingerprint": opaque_fingerprint("atlas:runner-binding-plan-candidate:v1", plan.candidate_record_id),
        "plan_fingerprint": plan.plan_fingerprint,
        "correlation_fingerprint": correlation_fingerprint,
        "occurred_at": occurred_at,
    }
    seed = RunnerBindingPlanAuditEvidenceV1.model_construct(
        **raw, audit_fingerprint=plan.plan_fingerprint
    )
    return RunnerBindingPlanAuditEvidenceV1.model_validate(
        {**raw, "audit_fingerprint": audit_evidence_fingerprint(seed)}
    )


def _correlation_fingerprint(value: str):
    safe = value if isinstance(value, str) and 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:runner-binding-plan-correlation:v1", safe)


def _validation_failure(message: str, correlation_id: str) -> RunnerBindingPlanResultV1:
    if "Home Assistant" in message:
        return _failure("not_eligible", correlation_id)
    if "ownership" in message:
        return _failure("not_found", correlation_id)
    if "not active" in message or "not admission_gated" in message:
        return _failure("not_eligible", correlation_id)
    if "stale" in message or "future" in message:
        return _failure("expired", correlation_id)
    if "expired" in message:
        return _failure("expired", correlation_id)
    if "fingerprint" in message or "linkage" in message or "binding mismatch" in message:
        return _failure("not_eligible", correlation_id)
    return _failure("not_found", correlation_id)


def _failure(error_code: str, correlation_id: str) -> RunnerBindingPlanResultV1:
    return RunnerBindingPlanResultV1(
        disposition="blocked",
        plan=None,
        status=None,
        audit_evidence=None,
        error=RunnerBindingPlanRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=_correlation_fingerprint(correlation_id),
        ),
    )
