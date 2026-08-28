"""Pure Agent-side models for v0.26 simulated handoff acknowledgement."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.agent_intake_simulation.models import (
    CanonicalUuid4,
    FingerprintV1,
    InstallationDispatchEnvelopeV1,
    UtcSecond,
    dispatch_envelope_fingerprint,
    intake_record_fingerprint,
)

MAX_DELIVERY_BYTES = 48 * 1024
MAX_ACKNOWLEDGEMENT_BYTES = 16 * 1024
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid correlation identity")
    return value


CorrelationId = Annotated[str, AfterValidator(_identity)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstallationHandoffSimulatedDeliveryRecipientV1(ContractModel):
    service: Literal["atlas-agent"] = "atlas-agent"
    intake_contract: Literal["agent-installation-intake-simulation-v1"] = (
        "agent-installation-intake-simulation-v1"
    )


class InstallationHandoffSimulatedDeliveryV1(ContractModel):
    schema: Literal["installation-handoff-simulated-delivery-v1"] = (
        "installation-handoff-simulated-delivery-v1"
    )
    simulated_delivery_id: CanonicalUuid4
    simulation_request_id: CanonicalUuid4
    dispatched_at: UtcSecond
    valid_until: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["simulation-only"] = "simulation-only"
    sender: Literal["atlas-core"] = "atlas-core"
    recipient: InstallationHandoffSimulatedDeliveryRecipientV1
    envelope: InstallationDispatchEnvelopeV1
    delivery_authorized: Literal[False] = False
    live_admission_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    simulated_delivery_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_delivery(self) -> InstallationHandoffSimulatedDeliveryV1:
        if self.valid_until != self.envelope.valid_until:
            raise ValueError("delivery expiry must equal envelope expiry")
        if not _instant(self.envelope.prepared_at) <= _instant(self.dispatched_at) < _instant(self.valid_until):
            raise ValueError("delivery time is outside envelope validity")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_DELIVERY_BYTES:
            raise ValueError("simulated delivery exceeds 48 KiB")
        return self


class AgentInstallationHandoffSimulatedAcknowledgementSourceV1(ContractModel):
    simulated_delivery_id: CanonicalUuid4
    simulated_delivery_fingerprint: FingerprintV1
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1


class AgentInstallationHandoffSimulatedAcknowledgementIntakeV1(ContractModel):
    simulation_request_id: CanonicalUuid4
    intake_record_id: CanonicalUuid4
    intake_record_fingerprint: FingerprintV1


class AgentInstallationHandoffSimulatedAcknowledgementV1(ContractModel):
    schema: Literal["agent-installation-handoff-simulated-acknowledgement-v1"] = (
        "agent-installation-handoff-simulated-acknowledgement-v1"
    )
    acknowledgement_id: CanonicalUuid4
    acknowledged_at: UtcSecond
    valid_until: UtcSecond
    status: Literal["simulated_acknowledged"] = "simulated_acknowledged"
    provenance: Literal["agent_simulated_not_received"] = "agent_simulated_not_received"
    source: AgentInstallationHandoffSimulatedAcknowledgementSourceV1
    intake: AgentInstallationHandoffSimulatedAcknowledgementIntakeV1
    statement: Literal[
        "agent_acknowledged_simulated_handoff_without_live_receipt"
    ] = "agent_acknowledged_simulated_handoff_without_live_receipt"
    delivery_received: Literal[False] = False
    live_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    acknowledgement_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_acknowledgement(self) -> AgentInstallationHandoffSimulatedAcknowledgementV1:
        if not _instant(self.acknowledged_at) < _instant(self.valid_until):
            raise ValueError("acknowledgement is not current")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_ACKNOWLEDGEMENT_BYTES:
            raise ValueError("acknowledgement exceeds 16 KiB")
        return self


class AgentInstallationHandoffSimulatedAcknowledgementAuditEvidenceV1(ContractModel):
    schema: Literal[
        "agent-installation-handoff-simulated-acknowledgement-audit-evidence-v1"
    ] = "agent-installation-handoff-simulated-acknowledgement-audit-evidence-v1"
    acknowledgement_id: CanonicalUuid4
    acknowledgement_fingerprint: FingerprintV1
    simulated_delivery_id: CanonicalUuid4
    simulated_delivery_fingerprint: FingerprintV1
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    simulation_request_id: CanonicalUuid4
    intake_record_id: CanonicalUuid4
    intake_record_fingerprint: FingerprintV1
    acknowledged_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["simulated_acknowledged", "expired_acknowledged"]
    provenance: Literal["agent_simulated_not_received"] = "agent_simulated_not_received"
    capability_status: Literal["unsupported"] = "unsupported"
    default_enabled: Literal[False] = False
    simulation_only: Literal[True] = True
    delivery_received: Literal[False] = False
    live_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evidence(
        self,
    ) -> AgentInstallationHandoffSimulatedAcknowledgementAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        return self


class AgentInstallationHandoffSimulatedAcknowledgementErrorV1(ContractModel):
    schema: Literal["agent-installation-handoff-simulated-acknowledgement-error-v1"] = (
        "agent-installation-handoff-simulated-acknowledgement-error-v1"
    )
    error_code: Literal[
        "malformed", "not_current", "ownership_mismatch", "delivery_mismatch",
        "envelope_mismatch", "linkage_mismatch", "recipient_mismatch",
        "intake_mismatch", "replay_conflict", "quota_exceeded", "unavailable",
    ]
    correlation_id: CorrelationId
    simulated_delivery_id: CanonicalUuid4 | None = None
    acknowledgement_id: CanonicalUuid4 | None = None
    redacted: Literal[True] = True


class AgentInstallationHandoffSimulatedAcknowledgementResultV1(ContractModel):
    disposition: Literal["simulated", "exact_replay", "rejected", "unavailable"]
    acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1 | None
    error: AgentInstallationHandoffSimulatedAcknowledgementErrorV1 | None
    delivery_received: Literal[False] = False
    live_admission_attempted: Literal[False] = False
    execution_attempted: Literal[False] = False
    worker_invoked: Literal[False] = False
    mutation_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self) -> AgentInstallationHandoffSimulatedAcknowledgementResultV1:
        success = self.disposition in ("simulated", "exact_replay")
        if success != (self.acknowledgement is not None and self.error is None):
            raise ValueError("result disposition and value disagree")
        if not success and (self.acknowledgement is not None or self.error is None):
            raise ValueError("failed result must contain only a redacted error")
        if (
            self.disposition == "unavailable"
            and self.error
            and self.error.error_code != "unavailable"
        ):
            raise ValueError("unavailable result requires unavailable error")
        return self


def validate_simulated_delivery(delivery: InstallationHandoffSimulatedDeliveryV1, *, operator_id: str,
    observed_at: str) -> None:
    if delivery.envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(
        operator_id=operator_id, envelope=delivery.envelope
    ):
        raise ValueError("ownership or envelope fingerprint mismatch")
    if delivery.simulated_delivery_fingerprint != simulated_delivery_fingerprint(
        operator_id=operator_id, delivery=delivery
    ):
        raise ValueError("simulated delivery fingerprint mismatch")
    observed = _instant(observed_at)
    if observed < _instant(delivery.dispatched_at):
        raise ValueError("observation precedes delivery")
    if observed >= _instant(delivery.valid_until):
        raise ValueError("simulated delivery is not current")


def build_acknowledgement(*, operator_id: str, delivery: InstallationHandoffSimulatedDeliveryV1,
    intake_record: Any, acknowledgement_id: str) -> AgentInstallationHandoffSimulatedAcknowledgementV1:
    """Derive acknowledgement only from a complete, fingerprint-valid v0.25 record."""
    validate_simulated_delivery(delivery, operator_id=operator_id, observed_at=intake_record.observed_at)
    if intake_record.intake_record_fingerprint != intake_record_fingerprint(
        operator_id=operator_id, record=intake_record
    ):
        raise ValueError("intake record fingerprint mismatch")
    if (intake_record.simulation_request_id, intake_record.source.dispatch_envelope_id,
        intake_record.source.dispatch_envelope_fingerprint, intake_record.linkage) != (
        delivery.simulation_request_id, delivery.envelope.dispatch_envelope_id,
        delivery.envelope.dispatch_envelope_fingerprint, delivery.envelope.linkage):
        raise ValueError("intake linkage mismatch")
    raw: dict[str, Any] = {
        "schema": "agent-installation-handoff-simulated-acknowledgement-v1",
        "acknowledgement_id": acknowledgement_id, "acknowledged_at": intake_record.observed_at,
        "valid_until": intake_record.valid_until, "status": "simulated_acknowledged",
        "provenance": "agent_simulated_not_received",
        "source": {"simulated_delivery_id": delivery.simulated_delivery_id,
            "simulated_delivery_fingerprint": delivery.simulated_delivery_fingerprint.model_dump(mode="json"),
            "dispatch_envelope_id": delivery.envelope.dispatch_envelope_id,
            "dispatch_envelope_fingerprint": delivery.envelope.dispatch_envelope_fingerprint.model_dump(mode="json")},
        "intake": {"simulation_request_id": delivery.simulation_request_id,
            "intake_record_id": intake_record.intake_record_id,
            "intake_record_fingerprint": intake_record.intake_record_fingerprint.model_dump(mode="json")},
        "statement": "agent_acknowledged_simulated_handoff_without_live_receipt",
        "delivery_received": False, "live_admission_granted": False,
        "execution_authorized": False, "worker_allowed": False,
        "mutation_allowed": False, "replay_allowed": False,
    }
    raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(operator_id=operator_id, acknowledgement=raw).model_dump(mode="json")
    return AgentInstallationHandoffSimulatedAcknowledgementV1.model_validate(raw)


def acknowledgement_lifecycle(acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1, *, now: str) -> Literal["simulated_acknowledged", "expired_acknowledged"]:
    instant = _instant(now)
    if instant < _instant(acknowledgement.acknowledged_at):
        raise ValueError("lifecycle instant precedes acknowledgement")
    return "simulated_acknowledged" if instant < _instant(acknowledgement.valid_until) else "expired_acknowledged"


def derived_intake_idempotency_key(delivery: InstallationHandoffSimulatedDeliveryV1) -> str:
    return "v026:" + delivery.simulated_delivery_fingerprint.value


def simulated_delivery_fingerprint(*, operator_id: str, delivery: InstallationHandoffSimulatedDeliveryV1 | dict[str, Any]) -> FingerprintV1:
    raw = delivery.model_dump(mode="json") if isinstance(delivery, BaseModel) else dict(delivery)
    raw.pop("simulated_delivery_fingerprint", None)
    return _fingerprint("atlas:installation-handoff-simulated-delivery:v1", {"operator_id": operator_id, "delivery": raw})


def acknowledgement_fingerprint(*, operator_id: str, acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1 | dict[str, Any]) -> FingerprintV1:
    raw = acknowledgement.model_dump(mode="json") if isinstance(acknowledgement, BaseModel) else dict(acknowledgement)
    raw.pop("acknowledgement_fingerprint", None)
    return _fingerprint("atlas:agent-installation-handoff-simulated-acknowledgement:v1", {"operator_id": operator_id, "acknowledgement": raw})


def audit_evidence_fingerprint(evidence: AgentInstallationHandoffSimulatedAcknowledgementAuditEvidenceV1 | dict[str, Any]) -> FingerprintV1:
    raw = evidence.model_dump(mode="json") if isinstance(evidence, BaseModel) else dict(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:agent-installation-handoff-simulated-acknowledgement-audit-evidence:v1", raw)


def _canonical(value: object) -> bytes:
    def normalize(item: object) -> object:
        if isinstance(item, BaseModel): return normalize(item.model_dump(mode="json"))
        if isinstance(item, str):
            if item != unicodedata.normalize("NFC", item): raise ValueError("strings must be NFC")
            return item
        if isinstance(item, bool) or item is None: return item
        if isinstance(item, int | float): raise TypeError("JSON numbers are prohibited")
        if isinstance(item, dict): return {normalize(key): normalize(child) for key, child in item.items()}
        if isinstance(item, list | tuple): return [normalize(child) for child in item]
        raise TypeError("value is outside canonical domain")
    return json.dumps(normalize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1",
        value=hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest())


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
