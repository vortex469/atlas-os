"""Explicitly constructed Core-local v0.36 admission-evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.execution_permission_grant.contract import (
    ExecutionPermissionGrantStatusV1,
    ExecutionPermissionGrantV1,
)

from .contract import (
    PERMISSION,
    BlockerV1,
    CorrelationId,
    InstallationExecutionAdmissionAuditEvidenceV1,
    InstallationExecutionAdmissionAuthorityContextV1,
    InstallationExecutionAdmissionCreateV1,
    InstallationExecutionAdmissionRedactedErrorV1,
    InstallationExecutionAdmissionResultV1,
    InstallationExecutionAdmissionValidationInputV1,
    OperatorId,
    audit_evidence_fingerprint,
    build_admission,
    derive_status,
    idempotency_key_fingerprint,
    operator_fingerprint,
    request_fingerprint,
)
from .store import (
    InstallationExecutionAdmissionStore,
    InstallationExecutionAdmissionStoreError,
)


class InstallationExecutionAdmissionEvidenceReader(Protocol):
    """Read exact owner-scoped v0.35 facts without external I/O."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        permission_grant_id: str,
        grant_valid_until: str,
    ) -> tuple[
        ExecutionPermissionGrantV1, ExecutionPermissionGrantStatusV1, bool
    ] | None: ...


class InstallationExecutionAdmissionService:
    """Create/get/list admission evidence; exposes no effect operation."""

    def __init__(
        self,
        *,
        evidence_reader: InstallationExecutionAdmissionEvidenceReader,
        store: InstallationExecutionAdmissionStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._reader = evidence_reader
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    def create(
        self,
        create: InstallationExecutionAdmissionCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> InstallationExecutionAdmissionResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        safe_correlation = _safe_correlation(correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = InstallationExecutionAdmissionCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            idempotency_fingerprint = idempotency_key_fingerprint(
                operator, idempotency_key
            )
            request = request_fingerprint(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                idempotency_fingerprint=idempotency_fingerprint,
            )
        except Exception:  # noqa: BLE001 - parsing details remain redacted
            return _failure("malformed", safe_correlation)

        try:
            reserved = self._store.resolve_reservation(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                idempotency_key_fingerprint=idempotency_fingerprint.value,
                v035_grant_fingerprint=exact_create.permission_grant_fingerprint.value,
                request_fingerprint=request.value,
            )
            if reserved is not None:
                return self._success(
                    reserved,
                    disposition="exact_duplicate",
                    correlation_id=safe_correlation,
                    observed_at=self._server_now(),
                )

            recorded_at = self._server_now()
            evidence = self._reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                permission_grant_id=exact_create.permission_grant_id,
                grant_valid_until=exact_create.grant_valid_until,
            )
            if evidence is None:
                return _failure(
                    "not_found", safe_correlation, ("missing_evidence",)
                )
            grant, grant_status, home_assistant = evidence
            authority = InstallationExecutionAdmissionAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                request_received_at=recorded_at,
            )
            validation = InstallationExecutionAdmissionValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                permission_grant=grant,
                permission_grant_status=grant_status,
                idempotency_key=idempotency_key,
                home_assistant=home_assistant,
            )
            admission, _, reservation = build_admission(
                validation, admission_id=self._id_factory()
            )
            recorded_audit = _audit(
                admission,
                outcome="recorded",
                correlation_id=safe_correlation,
                occurred_at=recorded_at,
            )
            stored, created = self._store.append(
                admission=admission,
                reservation=reservation,
                audit_evidence=recorded_audit,
            )
            return self._success(
                stored,
                disposition="recorded" if created else "exact_duplicate",
                correlation_id=safe_correlation,
                observed_at=recorded_at if created else self._server_now(),
            )
        except InstallationExecutionAdmissionStoreError as error:
            code = error.code if error.code in {"conflict", "quota_exceeded"} else "unavailable"
            blockers: tuple[BlockerV1, ...] = (
                ("subject_reserved",) if code == "conflict" else ()
            )
            return _failure(code, safe_correlation, blockers)
        except (TypeError, ValueError) as error:
            return _validation_failure(str(error), safe_correlation)
        except Exception:  # noqa: BLE001 - injected reader failures are redacted
            return _failure("unavailable", safe_correlation)

    def get(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        admission_id: str,
        correlation_id: str,
    ) -> InstallationExecutionAdmissionResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            admission = self._store.get(
                operator_id=operator, admission_id=admission_id
            )
            return self._success(
                admission,
                disposition="exact_duplicate",
                correlation_id=_safe_correlation(correlation_id),
                observed_at=self._server_now(),
            )
        except InstallationExecutionAdmissionStoreError as error:
            return _failure(
                "not_found" if error.code == "not_found" else "unavailable",
                correlation_id,
            )
        except Exception:  # noqa: BLE001 - read failures remain redacted
            return _failure("unavailable", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        correlation_id: str,
    ) -> tuple[InstallationExecutionAdmissionResultV1, ...]:
        if authenticated_operator_id is None:
            return (_failure("unauthenticated", correlation_id),)
        if not permission_verified:
            return (_failure("unauthorized", correlation_id),)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            observed_at = self._server_now()
            return tuple(
                self._success(
                    admission,
                    disposition="exact_duplicate",
                    correlation_id=_safe_correlation(correlation_id),
                    observed_at=observed_at,
                )
                for admission in self._store.list_owned(operator_id=operator)
            )
        except Exception:  # noqa: BLE001 - listing failures remain redacted
            return (_failure("unavailable", correlation_id),)

    def _success(
        self,
        admission,
        *,
        disposition: str,
        correlation_id: str,
        observed_at: str,
    ) -> InstallationExecutionAdmissionResultV1:
        status = derive_status(admission, observed_at=observed_at)
        audit = _audit(
            admission,
            outcome=disposition,
            correlation_id=correlation_id,
            occurred_at=observed_at,
        )
        return InstallationExecutionAdmissionResultV1(
            disposition=disposition,
            admission=admission,
            status=status,
            audit_evidence=audit,
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


def create_installation_execution_admission_service(
    *,
    evidence_reader: InstallationExecutionAdmissionEvidenceReader,
    store: InstallationExecutionAdmissionStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> InstallationExecutionAdmissionService:
    """Explicit P2 construction; no production composition calls this."""
    return InstallationExecutionAdmissionService(
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        id_factory=id_factory,
    )


def _audit(
    admission,
    *,
    outcome: str,
    correlation_id: str,
    occurred_at: str,
) -> InstallationExecutionAdmissionAuditEvidenceV1:
    raw = {
        "admission_id": admission.admission_id,
        "candidate_record_id": admission.candidate_record_id,
        "operator_fingerprint": operator_fingerprint(admission.operator_id),
        "request_fingerprint": admission.request_fingerprint,
        "idempotency_key_fingerprint": admission.idempotency_key_fingerprint,
        "v035_grant_fingerprint": admission.linkage.v035_grant_fingerprint,
        "linkage_fingerprint": admission.linkage.linkage_fingerprint,
        "eligibility_fingerprint": admission.runner_eligibility.eligibility_fingerprint,
        "admission_fingerprint": admission.admission_fingerprint,
        "blocker_codes": admission.blockers,
        "correlation_id": correlation_id,
        "occurred_at": occurred_at,
        "outcome": outcome,
    }
    seed = InstallationExecutionAdmissionAuditEvidenceV1.model_construct(
        **raw, evidence_fingerprint=admission.admission_fingerprint
    )
    return InstallationExecutionAdmissionAuditEvidenceV1.model_validate(
        {**raw, "evidence_fingerprint": audit_evidence_fingerprint(seed)}
    )


def _safe_correlation(value: str) -> str:
    try:
        return TypeAdapter(CorrelationId).validate_python(value, strict=True)
    except ValueError:
        return "execution-admission-redacted"


def _validation_failure(
    message: str, correlation_id: str
) -> InstallationExecutionAdmissionResultV1:
    if "Home Assistant" in message:
        return _failure(
            "not_eligible",
            correlation_id,
            ("installation_capability_unsupported",),
        )
    if "ownership" in message:
        return _failure("not_found", correlation_id)
    if "scope" in message:
        return _failure(
            "not_eligible", correlation_id, ("grant_scope_mismatch",)
        )
    if "not active" in message:
        return _failure("not_eligible", correlation_id, ("grant_not_active",))
    if any(marker in message for marker in ("stale", "future")):
        return _failure("expired", correlation_id, ("stale_evidence",))
    if "expired" in message:
        return _failure("expired", correlation_id, ("expired_evidence",))
    if "fingerprint" in message:
        return _failure(
            "not_eligible", correlation_id, ("fingerprint_mismatch",)
        )
    if any(marker in message for marker in ("binding", "linkage")):
        return _failure("not_eligible", correlation_id, ("linkage_mismatch",))
    return _failure("not_found", correlation_id)


def _failure(
    error_code: str,
    correlation_id: str,
    blockers: tuple[BlockerV1, ...] = (),
) -> InstallationExecutionAdmissionResultV1:
    return InstallationExecutionAdmissionResultV1(
        disposition="unavailable" if error_code == "unavailable" else "rejected",
        admission=None,
        status=None,
        audit_evidence=None,
        error=InstallationExecutionAdmissionRedactedErrorV1(
            error_code=error_code,
            blocker_codes=blockers,
            correlation_id=_safe_correlation(correlation_id),
        ),
    )
