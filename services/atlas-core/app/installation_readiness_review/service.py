"""Read-only owner-scoped composition for installation readiness review v1."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import ValidationError

from .contract import (
    InstallationReadinessReviewEvidenceV1,
    InstallationReadinessReviewRedactedErrorV1,
    InstallationReadinessReviewResultV1,
    create_installation_readiness_review,
)


class InstallationReadinessReviewEvidenceReader(Protocol):
    """Resolve an existing chain using Core-local owner-scoped reads only."""

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        observed_at: str,
    ) -> InstallationReadinessReviewEvidenceV1 | None: ...


class InstallationReadinessReviewService:
    """Derive an ephemeral review without reserving, consuming, or writing evidence."""

    def __init__(
        self,
        *,
        evidence_reader: InstallationReadinessReviewEvidenceReader,
        clock: Callable[[], datetime],
    ) -> None:
        self._reader = evidence_reader
        self._clock = clock

    def review(
        self,
        *,
        candidate_record_id: str,
        authenticated_operator_id: str | None,
        read_permission_verified: bool,
        correlation_id: str,
    ) -> InstallationReadinessReviewResultV1:
        if authenticated_operator_id is None:
            return _failure("unauthenticated", correlation_id)
        if not read_permission_verified:
            return _failure("unauthorized", correlation_id)
        try:
            observed_at = _utc_second(self._clock())
            resolved = self._reader.read_owned(
                operator_id=authenticated_operator_id,
                candidate_record_id=candidate_record_id,
                observed_at=observed_at,
            )
            if resolved is None:
                return _failure("not_found", correlation_id)
            evidence = InstallationReadinessReviewEvidenceV1.model_validate(resolved)
            if not (
                evidence.operator_id == authenticated_operator_id
                and evidence.authenticated_operator_id == authenticated_operator_id
                and evidence.candidate_record_id == candidate_record_id
                and evidence.observed_at == observed_at
                and evidence.authentication_verified
                and evidence.read_permission_verified
                and evidence.source_was_owner_scoped_local_readers
            ):
                return _failure("not_found", correlation_id)
            response = create_installation_readiness_review(
                evidence,
                correlation_id=correlation_id,
            )
            return InstallationReadinessReviewResultV1(
                disposition="reviewed",
                response=response,
                error=None,
            )
        except (TypeError, ValueError, ValidationError):
            return _failure("unavailable", correlation_id)
        except Exception:  # noqa: BLE001 - reader failures are always redacted
            return _failure("unavailable", correlation_id)


def _utc_second(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("trusted clock must be timezone-aware")
    exact = value.astimezone(UTC)
    if exact.microsecond:
        raise ValueError("trusted clock must provide a whole second")
    return exact.strftime("%Y-%m-%dT%H:%M:%SZ")


def _failure(
    error_code: str,
    correlation_id: str,
) -> InstallationReadinessReviewResultV1:
    error = InstallationReadinessReviewRedactedErrorV1(
        error_code=error_code,
        correlation_id=correlation_id,
    )
    return InstallationReadinessReviewResultV1(
        disposition=("unavailable" if error_code == "unavailable" else "rejected"),
        response=None,
        error=error,
    )
