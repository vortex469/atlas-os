"""Explicitly constructed no-send client for dormant delivery preparation."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, TypeAdapter

from .contract import (
    MAX_RESPONSE_BYTES,
    AgentInstallationIntakePriorEvidenceV1,
    AgentInstallationIntakeRequestV1,
    CoreAgentIntakeDeliveryAuditEvidenceV1,
    CoreAgentIntakeDeliveryCreateV1,
    CoreAgentIntakeDeliveryEvidenceContextV1,
    CoreAgentIntakeDeliveryPreparationResultV1,
    CoreAgentIntakeDeliveryPreparationV1,
    CoreAgentIntakeDeliveryRedactedErrorV1,
    CoreAgentIntakeDeliveryResponseValidationV1,
    CorrelationId,
    DormantAgentIntakeDeliveryConfigurationV1,
    IdempotencyKey,
    audit_evidence_fingerprint,
    endpoint_fingerprint,
    preparation_fingerprint,
    request_fingerprint,
    validate_delivery_response,
)
from .store import (
    DormantAgentIntakeDeliveryPreparationStore,
    DormantDeliveryStoreError,
)


class DormantDeliveryEvidenceReader(Protocol):
    """Resolve exact owned released evidence without network access."""

    def resolve(
        self, *, operator_id: str, create: CoreAgentIntakeDeliveryCreateV1
    ) -> CoreAgentIntakeDeliveryEvidenceContextV1: ...


class DormantAgentIntakeDeliveryClient:
    """Prepare evidence only; deliberately exposes no send or transport API."""

    def __init__(
        self,
        *,
        configuration: DormantAgentIntakeDeliveryConfigurationV1,
        evidence_reader: DormantDeliveryEvidenceReader,
        preparation_store: DormantAgentIntakeDeliveryPreparationStore,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> None:
        self._configuration = DormantAgentIntakeDeliveryConfigurationV1.model_validate(
            configuration.model_dump(mode="python")
        )
        self._evidence_reader = evidence_reader
        self._preparation_store = preparation_store
        self._clock = clock
        self._id_factory = id_factory

    @property
    def configuration(self) -> DormantAgentIntakeDeliveryConfigurationV1:
        return self._configuration

    def prepare(
        self,
        create: CoreAgentIntakeDeliveryCreateV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> CoreAgentIntakeDeliveryPreparationResultV1:
        try:
            exact_key = TypeAdapter(IdempotencyKey).validate_python(
                idempotency_key, strict=True
            )
            exact_correlation = TypeAdapter(CorrelationId).validate_python(
                correlation_id, strict=True
            )
            exact_create = CoreAgentIntakeDeliveryCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            create_fp = _create_fingerprint(exact_create)
            reserved = self._preparation_store.resolve_reservation(
                operator_id=authenticated_operator_id,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                dispatch_envelope_id=exact_create.dispatch_envelope_id,
            )
            if reserved is not None:
                return CoreAgentIntakeDeliveryPreparationResultV1(
                    disposition="exact_replay",
                    preparation=reserved,
                    error=None,
                    audit_evidence=_audit(
                        reserved, validated_at=reserved.prepared_at
                    ),
                )
            context = CoreAgentIntakeDeliveryEvidenceContextV1.model_validate(
                self._evidence_reader.resolve(
                    operator_id=authenticated_operator_id, create=exact_create
                ).model_dump(mode="python")
            )
            now = self._server_now()
            preparation = self._assemble(
                create=exact_create,
                context=context,
                operator_id=authenticated_operator_id,
                prepared_at=now,
            )
            stored, created = self._preparation_store.reserve(
                operator_id=authenticated_operator_id,
                idempotency_key=exact_key,
                create_fingerprint=create_fp,
                preparation=preparation,
            )
            audit = _audit(stored, validated_at=stored.prepared_at)
            return CoreAgentIntakeDeliveryPreparationResultV1(
                disposition="prepared_dormant" if created else "exact_replay",
                preparation=stored,
                error=None,
                audit_evidence=audit,
            )
        except DormantDeliveryStoreError as error:
            return self._error(
                "replay_conflict" if error.code == "replay_conflict" else "unavailable",
                exact_correlation,
            )
        except ValueError:
            return self._error("linkage_mismatch", correlation_id)
        except Exception:  # noqa: BLE001 - injected dependency failures stay redacted
            return self._error("unavailable", correlation_id)

    def get_preparation(
        self, *, authenticated_operator_id: str, delivery_preparation_id: str
    ) -> CoreAgentIntakeDeliveryPreparationV1:
        return self._preparation_store.get(
            operator_id=authenticated_operator_id,
            delivery_preparation_id=delivery_preparation_id,
        )

    def validate_response(
        self,
        validation: CoreAgentIntakeDeliveryResponseValidationV1,
        *,
        preparation: CoreAgentIntakeDeliveryPreparationV1,
        authenticated_operator_id: str,
    ) -> CoreAgentIntakeDeliveryResponseValidationV1:
        if (
            validation.agent_result is not None
            and len(validation.agent_result.model_dump_json().encode())
            > MAX_RESPONSE_BYTES
        ):
            raise ValueError("injected response exceeds 64 KiB")
        return validate_delivery_response(
            validation,
            preparation=preparation,
            operator_id=authenticated_operator_id,
        )

    def _assemble(
        self,
        *,
        create: CoreAgentIntakeDeliveryCreateV1,
        context: CoreAgentIntakeDeliveryEvidenceContextV1,
        operator_id: str,
        prepared_at: str,
    ) -> CoreAgentIntakeDeliveryPreparationV1:
        if context.operator_id != operator_id:
            raise ValueError("ownership mismatch")
        source = context.source
        if (
            create.dispatch_envelope_id != source.dispatch_envelope_id
            or create.intake_record_id != source.intake_record_id
            or create.simulated_delivery_id != source.simulated_delivery_id
            or create.simulated_acknowledgement_id
            != source.simulated_acknowledgement_id
        ):
            raise ValueError("create linkage mismatch")
        if context.existing_admission_id is not None:
            raise ValueError("v0.27 admission already exists")
        now = _instant(prepared_at)
        envelope = context.envelope
        if not _instant(envelope.prepared_at) <= now < _instant(envelope.valid_until):
            raise ValueError("dispatch envelope is not current")
        if (
            _instant(context.intake_record_observed_at) > now
            or _instant(context.simulated_acknowledged_at) > now
        ):
            raise ValueError("evidence postdates preparation")

        request_raw = {
            "schema": "agent-installation-intake-request-v1",
            "intake_request_id": self._id_factory(),
            "delivery_attempt_id": self._id_factory(),
            "sent_at": prepared_at,
            "expires_at": envelope.valid_until,
            "operation": "install-container",
            "mode": "intake-evidence-only",
            "sender": "atlas-core",
            "recipient": {
                "service": "atlas-agent",
                "intake_contract": "agent-installation-intake-v1",
            },
            "operator_assertion": {
                "operator_id": operator_id,
                "asserted_by": "atlas-core",
            },
            "envelope": envelope.model_dump(mode="json"),
            "prior_evidence": AgentInstallationIntakePriorEvidenceV1(
                intake_simulation={
                    "simulation_request_id": context.simulation_request_id,
                    "intake_record_id": source.intake_record_id,
                    "intake_record_fingerprint": source.intake_record_fingerprint,
                },
                simulated_delivery={
                    "simulated_delivery_id": source.simulated_delivery_id,
                    "simulated_delivery_fingerprint": source.simulated_delivery_fingerprint,
                    "delivery_record_fingerprint": source.delivery_record_fingerprint,
                    "acknowledgement_id": source.simulated_acknowledgement_id,
                    "acknowledgement_fingerprint": source.simulated_acknowledgement_fingerprint,
                },
            ).model_dump(mode="json"),
            "delivery_authorized": True,
            "evidence_admission_requested": True,
            "execution_authorized": False,
            "worker_allowed": False,
            "mutation_allowed": False,
            "replay_allowed": False,
        }
        request_raw["request_fingerprint"] = request_fingerprint(request_raw).model_dump(
            mode="json"
        )
        request = AgentInstallationIntakeRequestV1.model_validate(request_raw)
        raw = {
            "schema": "core-agent-intake-delivery-preparation-v1",
            "delivery_preparation_id": self._id_factory(),
            "prepared_at": prepared_at,
            "valid_until": envelope.valid_until,
            "endpoint_fingerprint": endpoint_fingerprint(
                self._configuration.endpoint
            ).model_dump(mode="json"),
            "request": request.model_dump(mode="json"),
            "source": source.model_dump(mode="json"),
            "lifecycle_at_preparation": "prepared_dormant",
            "status": "not_sent",
            "statement": "core_prepared_agent_intake_delivery_wiring_only",
            "default_enabled": False,
            "network_attempted": False,
            "delivery_authorized": False,
            "delivery_received": False,
            "evidence_admission_granted": False,
            "execution_admission_granted": False,
            "execution_authorized": False,
            "worker_allowed": False,
            "mutation_allowed": False,
            "replay_allowed": False,
        }
        raw["preparation_fingerprint"] = preparation_fingerprint(
            operator_id=operator_id, preparation=raw
        ).model_dump(mode="json")
        return CoreAgentIntakeDeliveryPreparationV1.model_validate(raw)

    def _server_now(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("trusted Core clock must return UTC")
        if value.microsecond:
            raise ValueError("trusted Core clock must return whole seconds")
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _error(code: str, correlation_id: str) -> CoreAgentIntakeDeliveryPreparationResultV1:
        return CoreAgentIntakeDeliveryPreparationResultV1(
            disposition="unavailable" if code == "unavailable" else "rejected",
            preparation=None,
            error=CoreAgentIntakeDeliveryRedactedErrorV1(
                error_code=code, correlation_id=correlation_id
            ),
            audit_evidence=None,
        )


def create_dormant_agent_intake_delivery_client(
    *,
    configuration: DormantAgentIntakeDeliveryConfigurationV1,
    evidence_reader: DormantDeliveryEvidenceReader,
    preparation_store: DormantAgentIntakeDeliveryPreparationStore,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> DormantAgentIntakeDeliveryClient:
    """Construct the no-send client explicitly; production never calls this."""
    return DormantAgentIntakeDeliveryClient(
        configuration=configuration,
        evidence_reader=evidence_reader,
        preparation_store=preparation_store,
        clock=clock,
        id_factory=id_factory,
    )


def _audit(
    preparation: CoreAgentIntakeDeliveryPreparationV1, *, validated_at: str
) -> CoreAgentIntakeDeliveryAuditEvidenceV1:
    raw = {
        "schema": "core-agent-intake-delivery-audit-evidence-v1",
        "delivery_preparation_id": preparation.delivery_preparation_id,
        "preparation_fingerprint": preparation.preparation_fingerprint.model_dump(
            mode="json"
        ),
        "intake_request_id": preparation.request.intake_request_id,
        "request_fingerprint": preparation.request.request_fingerprint.model_dump(
            mode="json"
        ),
        "delivery_attempt_id": preparation.request.delivery_attempt_id,
        "dispatch_envelope_id": preparation.source.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": preparation.source.dispatch_envelope_fingerprint.model_dump(
            mode="json"
        ),
        "prepared_at": preparation.prepared_at,
        "valid_until": preparation.valid_until,
        "validated_at": validated_at,
        "lifecycle": "disabled",
        "status": "not_sent",
        "provenance": "core_dormant_agent_intake_delivery_wiring_only",
        "default_enabled": False,
        "network_attempted": False,
        "delivery_authorized": False,
        "delivery_received": False,
        "evidence_admission_granted": False,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw).model_dump(
        mode="json"
    )
    return CoreAgentIntakeDeliveryAuditEvidenceV1.model_validate(raw)


def _create_fingerprint(create: CoreAgentIntakeDeliveryCreateV1) -> str:
    encoded = _canonical(create).decode()
    return hashlib.sha256(
        b"atlas:core-agent-intake-delivery-create:v1\0" + encoded.encode()
    ).hexdigest()


def _canonical(value: object) -> bytes:
    def normalize(item: object) -> object:
        if isinstance(item, BaseModel):
            return normalize(item.model_dump(mode="json"))
        if isinstance(item, str):
            if item != unicodedata.normalize("NFC", item):
                raise ValueError("strings must be NFC")
            return item
        if isinstance(item, bool) or item is None:
            return item
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, list | tuple):
            return [normalize(child) for child in item]
        raise TypeError("value is outside canonical domain")

    return json.dumps(
        normalize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
