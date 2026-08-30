"""Explicitly constructed Core-local v0.35 permission-evidence service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter

from app.installation_readiness_review.contract import (
    InstallationReadinessReviewResponseV1,
)

from .contract import (
    CONFIRMATION_TEXT,
    PERMISSION,
    CorrelationId,
    ExecutionPermissionGrantAuditEvidenceV1,
    ExecutionPermissionGrantAuthorityContextV1,
    ExecutionPermissionGrantCreateV1,
    ExecutionPermissionGrantRedactedErrorV1,
    ExecutionPermissionGrantResultV1,
    ExecutionPermissionGrantValidationInputV1,
    OperatorId,
    audit_evidence_fingerprint,
    build_grant,
    derive_status,
    idempotency_key_fingerprint,
    request_fingerprint,
)
from .store import ExecutionPermissionGrantStore, ExecutionPermissionGrantStoreError


class ExecutionPermissionGrantEvidenceReader(Protocol):
    """Read the exact owner-scoped v0.34 response without external I/O."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        readiness_review_id: str,
        review_observed_at: str,
    ) -> InstallationReadinessReviewResponseV1 | None: ...


class ExecutionPermissionGrantService:
    """Create/get/list permission evidence; exposes no execution operation."""

    def __init__(
        self,
        *,
        evidence_reader: ExecutionPermissionGrantEvidenceReader,
        store: ExecutionPermissionGrantStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._reader = evidence_reader
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    def create(
        self,
        create: ExecutionPermissionGrantCreateV1,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        candidate_record_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ExecutionPermissionGrantResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        safe_correlation = _safe_correlation(correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = ExecutionPermissionGrantCreateV1.model_validate(
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
        except Exception:  # noqa: BLE001 - parsing detail remains redacted
            code = (
                "confirmation_mismatch"
                if getattr(create, "confirmation_text", None) != CONFIRMATION_TEXT
                else "malformed"
            )
            return _failure(code, safe_correlation)

        try:
            reserved = self._store.resolve_reservation(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                idempotency_key_fingerprint=idempotency_fingerprint.value,
                v034_review_fingerprint=exact_create.readiness_review_fingerprint.value,
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
            response = self._reader.read_owned(
                operator_id=operator,
                candidate_record_id=candidate_record_id,
                readiness_review_id=exact_create.readiness_review_id,
                review_observed_at=exact_create.review_observed_at,
            )
            if response is None:
                return _failure("not_found", safe_correlation)
            authority = ExecutionPermissionGrantAuthorityContextV1(
                authenticated_operator_id=operator,
                permission=PERMISSION,
                permission_verified=True,
                request_received_at=recorded_at,
            )
            validation = ExecutionPermissionGrantValidationInputV1(
                operator_id=operator,
                authority=authority,
                candidate_record_id=candidate_record_id,
                create=exact_create,
                readiness_response=response,
                idempotency_key=idempotency_key,
                home_assistant=(
                    response.review.readiness == "blocked"
                    and "installation_capability_unsupported"
                    in response.review.blockers
                ),
            )
            grant, _, reservation = build_grant(validation, grant_id=self._id_factory())
            recorded_audit = _audit(
                grant,
                outcome="recorded",
                correlation_id=safe_correlation,
                occurred_at=recorded_at,
            )
            stored, created = self._store.append(
                grant=grant,
                reservation=reservation,
                audit_evidence=recorded_audit,
            )
            return self._success(
                stored,
                disposition="recorded" if created else "exact_duplicate",
                correlation_id=safe_correlation,
                observed_at=(recorded_at if created else self._server_now()),
            )
        except ExecutionPermissionGrantStoreError as error:
            code = (
                error.code
                if error.code in {"conflict", "quota_exceeded"}
                else "unavailable"
            )
            return _failure(code, safe_correlation)
        except (TypeError, ValueError) as error:
            message = str(error)
            if "not readiness gated" in message:
                code = "not_readiness_gated"
            elif any(marker in message for marker in ("stale", "expired", "future")):
                code = "expired"
            else:
                code = "not_found"
            return _failure(code, safe_correlation)
        except Exception:  # noqa: BLE001 - injected reader failures are redacted
            return _failure("unavailable", safe_correlation)

    def get(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        grant_id: str,
        correlation_id: str,
    ) -> ExecutionPermissionGrantResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            grant = self._store.get(operator_id=operator, grant_id=grant_id)
            return self._success(
                grant,
                disposition="exact_duplicate",
                correlation_id=_safe_correlation(correlation_id),
                observed_at=self._server_now(),
            )
        except ExecutionPermissionGrantStoreError as error:
            return _failure(
                "not_found" if error.code == "not_found" else "unavailable",
                correlation_id,
            )
        except Exception:  # noqa: BLE001 - read failures are redacted
            return _failure("unavailable", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id: str | None,
        permission_verified: bool,
        correlation_id: str,
    ) -> tuple[ExecutionPermissionGrantResultV1, ...]:
        if authenticated_operator_id is None:
            return (_failure("unauthenticated", correlation_id),)
        if not permission_verified:
            return (_failure("unauthorized", correlation_id),)
        try:
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            observed_at = self._server_now()
            grants = self._store.list_owned(operator_id=operator)
            return tuple(
                self._success(
                    grant,
                    disposition="exact_duplicate",
                    correlation_id=_safe_correlation(correlation_id),
                    observed_at=observed_at,
                )
                for grant in grants
            )
        except Exception:  # noqa: BLE001 - listing failures are redacted
            return (_failure("unavailable", correlation_id),)

    def _success(
        self,
        grant,
        *,
        disposition: str,
        correlation_id: str,
        observed_at: str,
    ) -> ExecutionPermissionGrantResultV1:
        status = derive_status(grant, observed_at=observed_at)
        audit = _audit(
            grant,
            outcome=disposition,
            correlation_id=correlation_id,
            occurred_at=observed_at,
        )
        return ExecutionPermissionGrantResultV1(
            disposition=disposition,
            grant=grant,
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


def create_execution_permission_grant_service(
    *,
    evidence_reader: ExecutionPermissionGrantEvidenceReader,
    store: ExecutionPermissionGrantStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> ExecutionPermissionGrantService:
    """Explicit P2 construction only; no production composition calls this."""
    return ExecutionPermissionGrantService(
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        id_factory=id_factory,
    )


def _audit(
    grant,
    *,
    outcome: str,
    correlation_id: str,
    occurred_at: str,
) -> ExecutionPermissionGrantAuditEvidenceV1:
    raw = {
        "grant_id": grant.grant_id,
        "candidate_record_id": grant.candidate_record_id,
        "operator_fingerprint": grant.linkage.v034_operator_fingerprint,
        "request_fingerprint": grant.request_fingerprint,
        "idempotency_key_fingerprint": grant.idempotency_key_fingerprint,
        "confirmation_fingerprint": grant.confirmation_fingerprint,
        "v034_review_fingerprint": grant.linkage.v034_review_fingerprint,
        "linkage_fingerprint": grant.linkage.linkage_fingerprint,
        "grant_fingerprint": grant.grant_fingerprint,
        "correlation_id": correlation_id,
        "occurred_at": occurred_at,
        "outcome": outcome,
    }
    seed = ExecutionPermissionGrantAuditEvidenceV1.model_construct(
        **raw,
        evidence_fingerprint=grant.grant_fingerprint,
    )
    return ExecutionPermissionGrantAuditEvidenceV1.model_validate(
        {**raw, "evidence_fingerprint": audit_evidence_fingerprint(seed)}
    )


def _safe_correlation(value: str) -> str:
    try:
        return TypeAdapter(CorrelationId).validate_python(value, strict=True)
    except ValueError:
        return "execution-permission-redacted"


def _failure(error_code: str, correlation_id: str) -> ExecutionPermissionGrantResultV1:
    return ExecutionPermissionGrantResultV1(
        disposition="unavailable" if error_code == "unavailable" else "rejected",
        grant=None,
        status=None,
        audit_evidence=None,
        error=ExecutionPermissionGrantRedactedErrorV1(
            error_code=error_code,
            correlation_id=_safe_correlation(correlation_id),
        ),
    )
