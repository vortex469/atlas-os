"""Explicitly constructed, default-off durable control-plane evidence service."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter

from . import contract as c
from .store import ControlPlaneEvidenceStore, ControlPlaneStoreError


def server_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None or value.microsecond:
        raise ValueError("invalid trusted clock")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ControlPlaneEvidenceService:
    def __init__(self, *, store: ControlPlaneEvidenceStore, clock: Callable[[], datetime],
                 expected_lineage_fingerprint: str, expected_policy_fingerprint: str,
                 expected_predecessor_fingerprint: str, enabled=False):
        self._store = store
        self._clock = clock
        self._lineage = TypeAdapter(c.Sha256).validate_python(expected_lineage_fingerprint, strict=True)
        self._policy = TypeAdapter(c.Sha256).validate_python(expected_policy_fingerprint, strict=True)
        self._predecessor = TypeAdapter(c.Sha256).validate_python(expected_predecessor_fingerprint, strict=True)
        self._enabled = enabled is True

    def create(self, value: Any, *, authenticated_owner_id: str | None,
               permission_verified: bool, correlation_id: str) -> c.ControlPlaneEvidenceRecordV1 | c.ControlPlaneEvidenceErrorV1:
        try:
            if authenticated_owner_id is None:
                raise ControlPlaneStoreError("unauthenticated")
            if permission_verified is not True:
                raise ControlPlaneStoreError("forbidden")
            owner = TypeAdapter(c.Identity).validate_python(authenticated_owner_id, strict=True)
            if not self._enabled:
                return self._error("disabled", correlation_id)
            request = c.ControlPlaneEvidenceCreateV1.model_validate(value)
            if request.owner_id != owner:
                raise ControlPlaneStoreError("forbidden")
            now = server_now(self._clock)
            if request.input.lineage.predecessor_fingerprint != self._predecessor:
                return self._error("foreign_lineage", correlation_id)
            evaluation = c.evaluate_control_plane(request.input, expected_lineage_fingerprint=self._lineage,
                                                  expected_policy_fingerprint=self._policy, evaluated_at=now)
            if evaluation.outcome != "accepted":
                reason = {"ambiguous_outcome": "ambiguous_state"}.get(evaluation.reason, evaluation.reason)
                return self._error(reason, correlation_id)

            def prepare():
                raw = {"owner_id": owner, "subject_id": request.input.subject_id, "input": request.input,
                       "evaluation": evaluation, "recorded_at": now, "valid_until": request.input.valid_until,
                       "subject_fingerprint": c.evidence_subject_fingerprint({"owner_id": owner, "subject_id": request.input.subject_id}),
                       "idempotency_key_fingerprint": c.idempotency_fingerprint(owner, request.idempotency_key),
                       "record_fingerprint": "0" * 64}
                raw["record_fingerprint"] = c.evidence_record_fingerprint(raw)
                return c.ControlPlaneEvidenceRecordV1.model_validate(raw)

            record, _ = self._store.append(request, prepare)
            return record
        except ControlPlaneStoreError as error:
            return self._error(error.code, correlation_id)
        except Exception:  # noqa: BLE001
            return self._error("invalid_request", correlation_id)

    def get(self, *, authenticated_owner_id: str | None, permission_verified: bool,
            subject_id: str, correlation_id: str):
        try:
            if authenticated_owner_id is None:
                raise ControlPlaneStoreError("unauthenticated")
            if permission_verified is not True:
                raise ControlPlaneStoreError("forbidden")
            owner = TypeAdapter(c.Identity).validate_python(authenticated_owner_id, strict=True)
            subject = TypeAdapter(c.Identity).validate_python(subject_id, strict=True)
            return self._store.get(owner, subject)
        except ControlPlaneStoreError as error:
            return self._error(error.code, correlation_id)
        except Exception:  # noqa: BLE001
            return self._error("invalid_request", correlation_id)

    def list(self, *, authenticated_owner_id: str | None, permission_verified: bool,
             correlation_id: str):
        try:
            if authenticated_owner_id is None:
                raise ControlPlaneStoreError("unauthenticated")
            if permission_verified is not True:
                raise ControlPlaneStoreError("forbidden")
            owner = TypeAdapter(c.Identity).validate_python(authenticated_owner_id, strict=True)
            return self._store.list(owner)
        except ControlPlaneStoreError as error:
            return self._error(error.code, correlation_id)
        except Exception:  # noqa: BLE001
            return self._error("invalid_request", correlation_id)

    @staticmethod
    def _error(code: str, correlation: str):
        if code not in {choice for choice in ("unauthenticated", "forbidden", "disabled", "invalid_request", "expired", "foreign_lineage", "policy_widening", "fingerprint_mismatch", "ambiguous_state", "authority_payload", "idempotency_conflict", "permanent_subject_reserved", "append_indeterminate", "quota_exceeded", "store_corrupt", "unavailable", "evidence_not_found")}:
            code = "invalid_request"
        safe = correlation if isinstance(correlation, str) and len(correlation) <= 128 else "redacted"
        return c.ControlPlaneEvidenceErrorV1(error_code=code, correlation_fingerprint=c.fingerprint("control-plane-correlation", safe))


def create_control_plane_evidence_service(**kwargs):
    return ControlPlaneEvidenceService(**kwargs)
