"""Explicitly constructed Core-local v0.30 enablement evidence service."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, TypeAdapter

from .contract import (
    CONFIRMATION,
    CorrelationId,
    IdempotencyKey,
    OperatorControlledDeliveryEnablementAuditEvidenceV1,
    OperatorControlledDeliveryEnablementConfigurationV1,
    OperatorControlledDeliveryEnablementCreateV1,
    OperatorControlledDeliveryEnablementEvidenceV1,
    OperatorControlledDeliveryEnablementOperationResultV1,
    OperatorControlledDeliveryEnablementRedactedErrorV1,
    OperatorControlledDeliveryEnablementStatusV1,
    OperatorId,
    audit_evidence_fingerprint,
    create_delivery_enablement_record,
    enablement_lifecycle,
)
from .store import (
    OperatorControlledDeliveryEnablementStore,
    OperatorControlledDeliveryEnablementStoreError,
)


class OperatorControlledDeliveryEnablementEvidenceReader(Protocol):
    """Resolve the exact owner-scoped local chain without network access."""

    def resolve(
        self,
        *,
        operator_id: str,
        create: OperatorControlledDeliveryEnablementCreateV1,
    ) -> OperatorControlledDeliveryEnablementEvidenceV1: ...


class OperatorControlledDeliveryEnablementService:
    """Create/read enablement evidence; exposes no send or activation method."""

    def __init__(
        self,
        *,
        configuration: OperatorControlledDeliveryEnablementConfigurationV1,
        evidence_reader: OperatorControlledDeliveryEnablementEvidenceReader,
        store: OperatorControlledDeliveryEnablementStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._configuration = (
            OperatorControlledDeliveryEnablementConfigurationV1.model_validate(
                configuration.model_dump(mode="python")
            )
        )
        self._evidence_reader = evidence_reader
        self._store = store
        self._clock = clock
        self._id_factory = id_factory

    @property
    def configuration(self) -> OperatorControlledDeliveryEnablementConfigurationV1:
        return self._configuration

    def create(
        self,
        create: OperatorControlledDeliveryEnablementCreateV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperatorControlledDeliveryEnablementOperationResultV1:
        safe_correlation = correlation_id
        try:
            exact_key = TypeAdapter(IdempotencyKey).validate_python(
                idempotency_key, strict=True
            )
            safe_correlation = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
            exact_operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            exact_create = OperatorControlledDeliveryEnablementCreateV1.model_validate(
                create.model_dump(mode="python")
            )
        except Exception:  # noqa: BLE001 - parsing details are closed
            code = (
                "confirmation_mismatch"
                if getattr(create, "confirmation", None) != CONFIRMATION
                else "malformed"
            )
            return self._failure(code, safe_correlation)

        try:
            create_fp = _create_fingerprint(exact_create)
            reserved = self._store.resolve_reservation(
                operator_id=exact_operator,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                preflight_id=exact_create.preflight_id,
                preflight_fingerprint=exact_create.preflight_fingerprint.value,
            )
            if reserved is not None:
                return self._success(
                    reserved, disposition="exact_replay", now=reserved.enabled_at
                )
            if not self._configuration.enabled:
                return self._failure("not_current", safe_correlation)
            now = self._server_now()
            evidence = OperatorControlledDeliveryEnablementEvidenceV1.model_validate(
                self._evidence_reader.resolve(
                    operator_id=exact_operator, create=exact_create
                ).model_dump(mode="python")
            )
            if (
                evidence.operator_id != exact_operator
                or evidence.authenticated_operator_id != exact_operator
                or evidence.resolved_at != now
            ):
                raise ValueError("authenticated owner or trusted instant mismatch")
            record = create_delivery_enablement_record(
                exact_create,
                evidence=evidence,
                configuration=self._configuration,
                enablement_id=self._id_factory(),
                enabled_at=now,
            )
            stored, created = self._store.reserve(
                operator_id=exact_operator,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                record=record,
            )
            return self._success(
                stored,
                disposition="created" if created else "exact_replay",
                now=stored.enabled_at,
            )
        except OperatorControlledDeliveryEnablementStoreError as error:
            code = (
                error.code
                if error.code in {"replay_conflict", "quota_exceeded"}
                else "unavailable"
            )
            return self._failure(code, safe_correlation)
        except ValueError as error:
            message = str(error)
            code = "not_current" if any(
                marker in message for marker in ("stale", "expired", "not eligible")
            ) else "linkage_mismatch"
            return self._failure(code, safe_correlation)
        except Exception:  # noqa: BLE001 - injected failures are redacted
            return self._failure("unavailable", safe_correlation)

    def get(
        self,
        *,
        authenticated_operator_id: str,
        enablement_id: str,
        correlation_id: str,
    ) -> OperatorControlledDeliveryEnablementOperationResultV1:
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
            exact_operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            record = self._store.get(
                operator_id=exact_operator, enablement_id=enablement_id
            )
            now = self._server_now()
            if enablement_lifecycle(record, now=now) == "enabled":
                create = OperatorControlledDeliveryEnablementCreateV1(
                    preflight_id=record.preflight_id,
                    preflight_fingerprint=record.preflight_fingerprint,
                    confirmation=CONFIRMATION,
                )
                evidence = OperatorControlledDeliveryEnablementEvidenceV1.model_validate(
                    self._evidence_reader.resolve(
                        operator_id=exact_operator, create=create
                    ).model_dump(mode="python")
                )
                if (
                    evidence.operator_id != exact_operator
                    or evidence.authenticated_operator_id != exact_operator
                    or evidence.resolved_at != now
                    or evidence.linkage != record.linkage
                ):
                    raise ValueError("current evidence revalidation mismatch")
            return self._success(record, disposition="exact_replay", now=now)
        except OperatorControlledDeliveryEnablementStoreError as error:
            return self._failure(
                "not_found" if error.code == "not_found" else "unavailable",
                correlation_id,
            )
        except Exception:  # noqa: BLE001 - all read failures are redacted
            return self._failure("unavailable", correlation_id)

    def list(
        self, *, authenticated_operator_id: str, correlation_id: str
    ) -> tuple[OperatorControlledDeliveryEnablementOperationResultV1, ...]:
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
            exact_operator = TypeAdapter(OperatorId).validate_python(
                authenticated_operator_id, strict=True
            )
            records = self._store.list_owned(operator_id=exact_operator)
        except Exception:  # noqa: BLE001 - store details remain redacted
            return (self._failure("unavailable", correlation_id),)
        return tuple(
            self.get(
                authenticated_operator_id=exact_operator,
                enablement_id=record.enablement_id,
                correlation_id=correlation_id,
            )
            for record in records
        )

    @staticmethod
    def _success(record, *, disposition: str, now: str):
        lifecycle = enablement_lifecycle(record, now=now)
        status = OperatorControlledDeliveryEnablementStatusV1(
            enablement_id=record.enablement_id,
            enablement_fingerprint=record.enablement_fingerprint,
            observed_at=now,
            lifecycle=lifecycle,
        )
        return OperatorControlledDeliveryEnablementOperationResultV1(
            disposition=disposition,
            record=record,
            status=status,
            audit_evidence=_audit(record, lifecycle=lifecycle),
            error=None,
        )

    @staticmethod
    def _failure(code: str, correlation_id: str):
        try:
            safe = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
        except ValueError:
            safe = "enablement-redacted"
        return OperatorControlledDeliveryEnablementOperationResultV1(
            disposition="unavailable" if code == "unavailable" else "rejected",
            record=None,
            status=None,
            audit_evidence=None,
            error=OperatorControlledDeliveryEnablementRedactedErrorV1(
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


def create_operator_controlled_delivery_enablement_service(
    *,
    configuration: OperatorControlledDeliveryEnablementConfigurationV1,
    evidence_reader: OperatorControlledDeliveryEnablementEvidenceReader,
    store: OperatorControlledDeliveryEnablementStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> OperatorControlledDeliveryEnablementService:
    """Explicit construction only; production does not call this in P2."""
    return OperatorControlledDeliveryEnablementService(
        configuration=configuration,
        evidence_reader=evidence_reader,
        store=store,
        clock=clock,
        id_factory=id_factory,
    )


def _audit(record, *, lifecycle: str):
    raw = {
        "schema": "operator-controlled-delivery-enablement-audit-evidence-v1",
        "enablement_id": record.enablement_id,
        "enablement_fingerprint": record.enablement_fingerprint.model_dump(mode="json"),
        "preflight_id": record.preflight_id,
        "preflight_fingerprint": record.preflight_fingerprint.model_dump(mode="json"),
        "delivery_preparation_id": record.delivery_preparation_id,
        "preparation_fingerprint": record.preparation_fingerprint.model_dump(mode="json"),
        "enabled_at": record.enabled_at,
        "expires_at": record.expires_at,
        "lifecycle": lifecycle,
        "status": record.status_at_creation,
        "confirmation": record.confirmation,
        "provenance": "core_operator_controlled_delivery_enablement_v1",
        "delivery_activated": False,
        "delivery_sent": False,
        "delivery_authorized": False,
        "execution_authorized": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw).model_dump(
        mode="json"
    )
    return OperatorControlledDeliveryEnablementAuditEvidenceV1.model_validate(raw)


def _create_fingerprint(create) -> str:
    return hashlib.sha256(
        b"atlas:operator-controlled-delivery-enablement-create:v1\0"
        + _canonical(create)
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
