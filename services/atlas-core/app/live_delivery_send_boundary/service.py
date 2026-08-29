"""Explicitly constructed v0.31 P2 reservation evidence service; no send method."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, TypeAdapter

from .contract import (
    CorrelationId,
    IdempotencyKey,
    LiveDeliverySendAuditEvidenceV1,
    LiveDeliverySendCreateV1,
    LiveDeliverySendEvidenceV1,
    LiveDeliverySendOperationResultV1,
    LiveDeliverySendRedactedErrorV1,
    LiveDeliverySendStatusV1,
    LiveDeliveryTransportConfigurationV1,
    OperatorId,
    audit_evidence_fingerprint,
    create_send_attempt,
    idempotency_key_fingerprint,
    send_lifecycle,
)
from .store import (
    LiveDeliverySendStore,
    LiveDeliverySendStoredEvidence,
    LiveDeliverySendStoreError,
)


class LiveDeliverySendEvidenceReader(Protocol):
    """Resolve the exact owner-scoped local chain without transport activity."""

    def resolve(
        self, *, operator_id: str, create: LiveDeliverySendCreateV1
    ) -> LiveDeliverySendEvidenceV1: ...


class LiveDeliverySendService:
    """Reserve/read send evidence; exposes no send, retry, or receipt method."""

    def __init__(
        self,
        *,
        configuration: LiveDeliveryTransportConfigurationV1,
        evidence_reader: LiveDeliverySendEvidenceReader,
        store: LiveDeliverySendStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._configuration = LiveDeliveryTransportConfigurationV1.model_validate(
            configuration.model_dump(mode="python")
        )
        self._evidence_reader = evidence_reader
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    @property
    def configuration(self) -> LiveDeliveryTransportConfigurationV1:
        return self._configuration

    def create(
        self,
        create: LiveDeliverySendCreateV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> LiveDeliverySendOperationResultV1:
        safe_correlation = correlation_id
        try:
            exact_operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_key = TypeAdapter(IdempotencyKey).validate_python(
                idempotency_key, strict=True
            )
            safe_correlation = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
            exact_create = LiveDeliverySendCreateV1.model_validate(
                create.model_dump(mode="python")
            )
        except Exception:  # noqa: BLE001 - parsing details remain closed
            return self._failure("malformed", safe_correlation)
        try:
            create_fp = _create_fingerprint(exact_create)
            prior = self._store.resolve_reservation(
                operator_id=exact_operator,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                enablement_id=exact_create.enablement_id,
                delivery_preparation_id=exact_create.delivery_preparation_id,
            )
            if prior is not None:
                return self._success(prior, disposition="exact_replay", now=prior.attempt.created_at)
            if not self._configuration.enabled:
                return self._failure("not_current", safe_correlation)
            now = self._server_now()
            resolved = self._evidence_reader.resolve(
                operator_id=exact_operator, create=exact_create
            )
            resolved_value = (
                resolved.model_dump(mode="python")
                if isinstance(resolved, BaseModel)
                else resolved
            )
            evidence = LiveDeliverySendEvidenceV1.model_validate(resolved_value)
            if (
                evidence.operator_id != exact_operator
                or evidence.authenticated_operator_id != exact_operator
                or evidence.resolved_at != now
            ):
                raise ValueError("authenticated owner or trusted instant mismatch")
            attempt, envelope = create_send_attempt(
                exact_create,
                evidence=evidence,
                configuration=self._configuration,
                send_attempt_id=self._id_factory(),
                created_at=now,
                idempotency_key=exact_key,
            )
            stored, created = self._store.reserve(
                operator_id=exact_operator,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                evidence=LiveDeliverySendStoredEvidence(
                    attempt=attempt,
                    envelope=envelope,
                    audit_evidence=_audit(
                        attempt,
                        correlation_id=safe_correlation,
                        idempotency_key=exact_key,
                    ),
                ),
            )
            return self._success(
                stored,
                disposition="reserved" if created else "exact_replay",
                now=stored.attempt.created_at,
            )
        except LiveDeliverySendStoreError as error:
            code = error.code if error.code in {"replay_conflict", "quota_exceeded"} else "unavailable"
            mapped = "already_reserved" if code == "replay_conflict" else (
                "rate_limited" if code == "quota_exceeded" else code
            )
            return self._failure(mapped, safe_correlation)
        except ValueError as error:
            message = str(error)
            if any(marker in message for marker in ("stale", "expired", "freshness")):
                code = "expired"
            elif "fingerprint" in message:
                code = "fingerprint_mismatch"
            else:
                code = "linkage_mismatch"
            return self._failure(code, safe_correlation)
        except Exception:  # noqa: BLE001 - injected failures remain redacted
            return self._failure("unavailable", safe_correlation)

    def get(
        self,
        *,
        authenticated_operator_id: str,
        send_attempt_id: str,
        correlation_id: str,
    ) -> LiveDeliverySendOperationResultV1:
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            stored = self._store.get(
                operator_id=operator, send_attempt_id=send_attempt_id
            )
            return self._success(stored, disposition="exact_replay", now=self._server_now())
        except LiveDeliverySendStoreError as error:
            return self._failure(
                "not_found" if error.code == "not_found" else "unavailable",
                correlation_id,
            )
        except Exception:  # noqa: BLE001 - read failures remain closed
            return self._failure("unavailable", correlation_id)

    def list(
        self, *, authenticated_operator_id: str, correlation_id: str
    ) -> tuple[LiveDeliverySendOperationResultV1, ...]:
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
            operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            records = self._store.list_owned(operator_id=operator)
            now = self._server_now()
            return tuple(
                self._success(record, disposition="exact_replay", now=now)
                for record in records
            )
        except Exception:  # noqa: BLE001 - list failures remain closed
            return (self._failure("unavailable", correlation_id),)

    @staticmethod
    def _success(stored, *, disposition: str, now: str):
        lifecycle = send_lifecycle(
            stored.attempt, now=now, receipt=stored.receipt
        )
        return LiveDeliverySendOperationResultV1(
            disposition=disposition,
            attempt=stored.attempt,
            receipt=None,
            status=LiveDeliverySendStatusV1(
                send_attempt_id=stored.attempt.send_attempt_id,
                attempt_fingerprint=stored.attempt.attempt_fingerprint,
                observed_at=now,
                lifecycle=lifecycle,
            ),
            audit_evidence=stored.audit_evidence,
            error=None,
        )

    @staticmethod
    def _failure(code: str, correlation_id: str):
        try:
            safe = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
        except ValueError:
            safe = "live-send-redacted"
        return LiveDeliverySendOperationResultV1(
            disposition="unavailable" if code == "unavailable" else "rejected",
            attempt=None,
            receipt=None,
            status=None,
            audit_evidence=None,
            error=LiveDeliverySendRedactedErrorV1(
                error_code=code, correlation_id=safe
            ),
        )

    def _server_now(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("trusted Core clock must return UTC")
        if value.microsecond:
            raise ValueError("trusted Core clock must return whole seconds")
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_live_delivery_send_service(
    *,
    configuration: LiveDeliveryTransportConfigurationV1,
    evidence_reader: LiveDeliverySendEvidenceReader,
    store: LiveDeliverySendStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> LiveDeliverySendService:
    """Explicit P2 construction only; production does not call this factory."""
    return LiveDeliverySendService(
        configuration=configuration,
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        id_factory=id_factory,
    )


def _audit(attempt, *, correlation_id: str, idempotency_key: str):
    raw = {
        "schema": "live-delivery-send-audit-evidence-v1",
        "send_attempt_id": attempt.send_attempt_id,
        "attempt_fingerprint": attempt.attempt_fingerprint.model_dump(mode="json"),
        "correlation_id": correlation_id,
        "idempotency_key_fingerprint": idempotency_key_fingerprint(
            operator_id=attempt.operator_id, idempotency_key=idempotency_key
        ).model_dump(mode="json"),
        "endpoint_fingerprint": attempt.endpoint_fingerprint.model_dump(mode="json"),
        "request_fingerprint": attempt.request_fingerprint.model_dump(mode="json"),
        "receipt_fingerprint": None,
        "created_at": attempt.created_at,
        "completed_at": None,
        "lifecycle": "reserved",
        "agent_disposition": "not_contacted",
        "evidence_only": True,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "installation_allowed": False,
        "worker_allowed": False,
        "workflow_allowed": False,
        "deployment_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw).model_dump(
        mode="json"
    )
    return LiveDeliverySendAuditEvidenceV1.model_validate(raw)


def _create_fingerprint(create) -> str:
    return hashlib.sha256(
        b"atlas:live-delivery-send-create:v1\0" + _canonical(create)
    ).hexdigest()


def _canonical(value: object) -> bytes:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return unicodedata.normalize(
        "NFC",
        json.dumps(
            raw,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    ).encode()
