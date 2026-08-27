"""Bounded process-local retry presentation cache; never durable authority."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from app.installation_assessment.contract import InstallationAdmissionAssessmentV1


class AssessmentIdempotencyConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Entry:
    canonical_request: bytes
    assessment_bytes: bytes
    evaluation_time: datetime
    expires_at: datetime


class EphemeralAssessmentRetryCache:
    """A capacity-bounded cache scoped by principal, route, and client key."""

    def __init__(self, *, capacity: int = 256) -> None:
        if not 1 <= capacity <= 4096:
            raise ValueError("cache capacity must be between 1 and 4096")
        self._capacity = capacity
        self._entries: OrderedDict[tuple[str, str, str], _Entry] = OrderedDict()
        self._lock = Lock()

    def get_or_create(
        self,
        *,
        principal_id: str,
        route: str,
        idempotency_key: str,
        canonical_request: bytes,
        now: datetime,
        factory: Callable[[datetime], InstallationAdmissionAssessmentV1],
        maximum_expires_at: datetime | None = None,
    ) -> tuple[InstallationAdmissionAssessmentV1, bytes, datetime]:
        if now.tzinfo is None or now.utcoffset() != timedelta(0) or now.microsecond:
            raise ValueError("cache time must be an exact UTC whole second")
        if maximum_expires_at is not None and (
            maximum_expires_at.tzinfo is None
            or maximum_expires_at.utcoffset() != timedelta(0)
            or maximum_expires_at.microsecond
        ):
            raise ValueError("maximum cache expiry must be an exact UTC whole second")
        with self._lock:
            self._expire(now)
            scope = (principal_id, route, idempotency_key)
            entry = self._entries.get(scope)
            if entry is not None:
                if entry.canonical_request != canonical_request:
                    raise AssessmentIdempotencyConflictError("idempotency conflict")
                self._entries.move_to_end(scope)
                return (
                    InstallationAdmissionAssessmentV1.model_validate_json(
                        entry.assessment_bytes
                    ),
                    entry.assessment_bytes,
                    entry.evaluation_time,
                )
            assessment = factory(now)
            encoded = assessment.model_dump_json().encode("utf-8")
            default_expiry = now + timedelta(minutes=5)
            self._entries[scope] = _Entry(
                canonical_request=bytes(canonical_request),
                assessment_bytes=encoded,
                evaluation_time=now,
                expires_at=min(default_expiry, maximum_expires_at or default_expiry),
            )
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)
            return assessment, encoded, now

    def _expire(self, now: datetime) -> None:
        expired = [key for key, entry in self._entries.items() if now >= entry.expires_at]
        for key in expired:
            del self._entries[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
