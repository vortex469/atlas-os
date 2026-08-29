"""Explicitly constructed Core-local v0.29 preflight evidence service."""

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
    DeliveryActivationPreflightAuditEvidenceV1,
    DeliveryActivationPreflightConfigurationV1,
    DeliveryActivationPreflightCreateV1,
    DeliveryActivationPreflightEvidenceV1,
    DeliveryActivationPreflightOperationResultV1,
    DeliveryActivationPreflightRedactedErrorV1,
    DeliveryActivationPreflightResultV1,
    DeliveryActivationPreflightStatusV1,
    IdempotencyKey,
    audit_evidence_fingerprint,
    evaluate_delivery_activation_preflight,
    preflight_lifecycle,
)
from .store import (
    DeliveryActivationPreflightStore,
    DeliveryActivationPreflightStoreError,
)


class DeliveryActivationPreflightEvidenceReader(Protocol):
    """Resolve the exact owner-scoped local chain without any network access."""

    def resolve(
        self, *, operator_id: str, create: DeliveryActivationPreflightCreateV1
    ) -> DeliveryActivationPreflightEvidenceV1: ...


class DeliveryActivationPreflightService:
    """Create and read non-authorizing evidence; exposes no activation method."""

    def __init__(
        self,
        *,
        configuration: DeliveryActivationPreflightConfigurationV1,
        evidence_reader: DeliveryActivationPreflightEvidenceReader,
        store: DeliveryActivationPreflightStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._configuration = DeliveryActivationPreflightConfigurationV1.model_validate(
            configuration.model_dump(mode="python")
        )
        self._evidence_reader = evidence_reader
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    @property
    def configuration(self) -> DeliveryActivationPreflightConfigurationV1:
        return self._configuration

    def create(
        self,
        create: DeliveryActivationPreflightCreateV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> DeliveryActivationPreflightOperationResultV1:
        safe_correlation = correlation_id
        try:
            exact_key = TypeAdapter(IdempotencyKey).validate_python(
                idempotency_key, strict=True
            )
            safe_correlation = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
            exact_create = DeliveryActivationPreflightCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            create_fp = _create_fingerprint(exact_create)
            reserved = self._store.resolve_reservation(
                operator_id=authenticated_operator_id,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                delivery_preparation_id=exact_create.delivery_preparation_id,
                preparation_fingerprint=exact_create.preparation_fingerprint.value,
            )
            if reserved is not None:
                return self._success(reserved, disposition="exact_replay", now=reserved.evaluated_at)

            now = self._server_now()
            evidence = DeliveryActivationPreflightEvidenceV1.model_validate(
                self._evidence_reader.resolve(
                    operator_id=authenticated_operator_id, create=exact_create
                ).model_dump(mode="python")
            )
            if (
                evidence.operator_id != authenticated_operator_id
                or evidence.authenticated_operator_id != authenticated_operator_id
            ):
                raise ValueError("authenticated ownership mismatch")
            if evidence.resolved_at != now:
                raise ValueError("evidence was not resolved at trusted instant")
            result = evaluate_delivery_activation_preflight(
                exact_create,
                evidence=evidence,
                configuration=self._configuration,
                preflight_id=self._id_factory(),
                evaluated_at=now,
            )
            stored, created = self._store.reserve(
                operator_id=authenticated_operator_id,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                result=result,
            )
            return self._success(
                stored,
                disposition="created" if created else "exact_replay",
                now=stored.evaluated_at,
            )
        except DeliveryActivationPreflightStoreError as error:
            code = error.code if error.code in {"replay_conflict", "quota_exceeded"} else "unavailable"
            return self._failure(code, safe_correlation)
        except ValueError:
            return self._failure("linkage_mismatch", safe_correlation)
        except Exception:  # noqa: BLE001 - injected dependency failures are redacted
            return self._failure("unavailable", safe_correlation)

    def get(
        self,
        *,
        authenticated_operator_id: str,
        preflight_id: str,
        correlation_id: str,
    ) -> DeliveryActivationPreflightOperationResultV1:
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
            result = self._store.get(
                operator_id=authenticated_operator_id, preflight_id=preflight_id
            )
            now = self._server_now()
            create = DeliveryActivationPreflightCreateV1(
                delivery_preparation_id=result.delivery_preparation_id,
                preparation_fingerprint=result.preparation_fingerprint,
            )
            evidence = DeliveryActivationPreflightEvidenceV1.model_validate(
                self._evidence_reader.resolve(
                    operator_id=authenticated_operator_id, create=create
                ).model_dump(mode="python")
            )
            if (
                evidence.operator_id != authenticated_operator_id
                or evidence.authenticated_operator_id != authenticated_operator_id
                or evidence.resolved_at != now
                or evidence.linkage != result.linkage
            ):
                raise ValueError("current evidence revalidation mismatch")
            return self._success(result, disposition="exact_replay", now=now)
        except DeliveryActivationPreflightStoreError as error:
            return self._failure(
                "not_found" if error.code == "not_found" else "unavailable",
                correlation_id,
            )
        except ValueError:
            return self._failure("unavailable", correlation_id)
        except Exception:  # noqa: BLE001 - injected dependency failures are redacted
            return self._failure("unavailable", correlation_id)

    def list(
        self,
        *,
        authenticated_operator_id: str,
        correlation_id: str,
    ) -> tuple[DeliveryActivationPreflightOperationResultV1, ...]:
        """Read and currently revalidate every bounded owner-scoped record."""
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
            records = self._store.list_owned(operator_id=authenticated_operator_id)
        except Exception:  # noqa: BLE001 - store details remain redacted
            return (self._failure("unavailable", correlation_id),)
        return tuple(
            self.get(
                authenticated_operator_id=authenticated_operator_id,
                preflight_id=record.preflight_id,
                correlation_id=correlation_id,
            )
            for record in records
        )

    @staticmethod
    def _success(
        result: DeliveryActivationPreflightResultV1,
        *,
        disposition: str,
        now: str,
    ) -> DeliveryActivationPreflightOperationResultV1:
        lifecycle = preflight_lifecycle(result, now=now)
        status = DeliveryActivationPreflightStatusV1(
            preflight_id=result.preflight_id,
            preflight_fingerprint=result.preflight_fingerprint,
            observed_at=now,
            lifecycle=lifecycle,
        )
        audit = _audit(result, lifecycle=lifecycle)
        return DeliveryActivationPreflightOperationResultV1(
            disposition=disposition,
            result=result,
            status=status,
            audit_evidence=audit,
            error=None,
        )

    @staticmethod
    def _failure(code: str, correlation_id: str) -> DeliveryActivationPreflightOperationResultV1:
        try:
            safe_correlation = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
        except ValueError:
            safe_correlation = "preflight-redacted"
        return DeliveryActivationPreflightOperationResultV1(
            disposition="unavailable" if code == "unavailable" else "rejected",
            result=None,
            status=None,
            audit_evidence=None,
            error=DeliveryActivationPreflightRedactedErrorV1(
                error_code=code, correlation_id=safe_correlation
            ),
        )

    def _server_now(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("trusted Core clock must return UTC")
        if value.microsecond:
            raise ValueError("trusted Core clock must return whole seconds")
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_delivery_activation_preflight_service(
    *,
    configuration: DeliveryActivationPreflightConfigurationV1,
    evidence_reader: DeliveryActivationPreflightEvidenceReader,
    store: DeliveryActivationPreflightStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> DeliveryActivationPreflightService:
    """Explicit construction only; production does not call this in v0.29 P2."""
    return DeliveryActivationPreflightService(
        configuration=configuration,
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        id_factory=id_factory,
    )


def _audit(
    result: DeliveryActivationPreflightResultV1,
    *,
    lifecycle: str,
) -> DeliveryActivationPreflightAuditEvidenceV1:
    raw = {
        "schema": "delivery-activation-preflight-audit-evidence-v1",
        "preflight_id": result.preflight_id,
        "preflight_fingerprint": result.preflight_fingerprint.model_dump(mode="json"),
        "delivery_preparation_id": result.delivery_preparation_id,
        "preparation_fingerprint": result.preparation_fingerprint.model_dump(mode="json"),
        "intake_request_id": result.linkage.intake_request_id,
        "delivery_attempt_id": result.linkage.delivery_attempt_id,
        "evaluated_at": result.evaluated_at,
        "expires_at": result.expires_at,
        "lifecycle": lifecycle,
        "decision": result.decision,
        "reason_codes": list(result.reason_codes),
        "provenance": "core_delivery_activation_preflight_v1",
        "delivery_activated": False,
        "delivery_authorized": False,
        "execution_authorized": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw).model_dump(mode="json")
    return DeliveryActivationPreflightAuditEvidenceV1.model_validate(raw)


def _create_fingerprint(create: DeliveryActivationPreflightCreateV1) -> str:
    return hashlib.sha256(
        b"atlas:delivery-activation-preflight-create:v1\0" + _canonical(create)
    ).hexdigest()


def _canonical(value: object) -> bytes:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return unicodedata.normalize(
        "NFC",
        json.dumps(raw, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")),
    ).encode()
