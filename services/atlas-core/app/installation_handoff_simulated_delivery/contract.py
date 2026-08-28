"""Pure, immutable models for the frozen Simulated Handoff Delivery v1 contract.

The values in this module are evidence of an in-process simulation only.  They
perform no I/O and grant no delivery, admission, execution, or mutation authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.installation_dispatch_handoff.contract import (
    FingerprintV1,
    InstallationDispatchEnvelopeV1,
    dispatch_envelope_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_DELIVERY_BYTES = 48 * 1024
MAX_ACKNOWLEDGEMENT_BYTES = 16 * 1024
MAX_RECORD_BYTES = 16 * 1024

_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class StrictContractError(ValueError):
    """A wire value is outside the closed delivery contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid operator/correlation identity")
    return value


def _visible_ascii(value: str) -> str:
    if not value.isascii() or not 1 <= len(value.encode()) <= 128 or any(
        not 0x21 <= ord(character) <= 0x7E for character in value
    ):
        raise ValueError("idempotency key is out of bounds")
    return value


OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]


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
        prepared = _instant(self.envelope.prepared_at)
        dispatched = _instant(self.dispatched_at)
        if not prepared <= dispatched < _instant(self.valid_until):
            raise ValueError("delivery time is outside envelope validity")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_DELIVERY_BYTES:
            raise ValueError("simulated delivery exceeds 48 KiB")
        return self


class InstallationHandoffSimulatedDeliveryRecordV1(ContractModel):
    schema: Literal["installation-handoff-simulated-delivery-record-v1"] = (
        "installation-handoff-simulated-delivery-record-v1"
    )
    simulated_delivery_id: CanonicalUuid4
    simulation_request_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    simulated_delivery_fingerprint: FingerprintV1
    dispatched_at: UtcSecond
    valid_until: UtcSecond
    lifecycle_basis: Literal["simulation_attempt_recorded"] = "simulation_attempt_recorded"
    delivery_mode: Literal["in_process_simulation"] = "in_process_simulation"
    live_delivery_claimed: Literal[False] = False
    agent_admission_claimed: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False
    delivery_record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def bounded_record(self) -> InstallationHandoffSimulatedDeliveryRecordV1:
        if not _instant(self.dispatched_at) < _instant(self.valid_until):
            raise ValueError("delivery record is not current")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_RECORD_BYTES:
            raise ValueError("delivery record exceeds 16 KiB")
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
    def bounded_acknowledgement(self) -> AgentInstallationHandoffSimulatedAcknowledgementV1:
        if not _instant(self.acknowledged_at) < _instant(self.valid_until):
            raise ValueError("acknowledgement is not current")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_ACKNOWLEDGEMENT_BYTES:
            raise ValueError("acknowledgement exceeds 16 KiB")
        return self


DeliveryLifecycle = Literal[
    "pending_acknowledgement",
    "simulated_acknowledged",
    "expired_unacknowledged",
    "expired_acknowledged",
]

SimulatedDeliveryErrorCode = Literal[
    "malformed", "not_current", "ownership_mismatch", "delivery_mismatch",
    "envelope_mismatch", "linkage_mismatch", "recipient_mismatch",
    "intake_mismatch", "replay_conflict", "quota_exceeded", "unavailable",
]


class InstallationHandoffSimulatedDeliveryErrorV1(ContractModel):
    schema: Literal["installation-handoff-simulated-delivery-error-v1"] = (
        "installation-handoff-simulated-delivery-error-v1"
    )
    error_code: SimulatedDeliveryErrorCode
    correlation_id: CorrelationId
    simulated_delivery_id: CanonicalUuid4 | None = None
    simulation_request_id: CanonicalUuid4 | None = None
    dispatch_envelope_id: CanonicalUuid4 | None = None
    redacted: Literal[True] = True


class InstallationHandoffSimulatedDeliveryIdempotencyV1(ContractModel):
    operator_id: OperatorId
    operation: Literal["create-installation-handoff-simulated-delivery"] = (
        "create-installation-handoff-simulated-delivery"
    )
    key: IdempotencyKey
    simulated_delivery_id: CanonicalUuid4
    simulated_delivery_fingerprint: FingerprintV1
    simulation_request_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    replay_allowed: Literal[False] = False


class InstallationHandoffSimulatedDeliveryAuditEvidenceV1(ContractModel):
    schema: Literal["installation-handoff-simulated-delivery-audit-evidence-v1"] = (
        "installation-handoff-simulated-delivery-audit-evidence-v1"
    )
    simulated_delivery_id: CanonicalUuid4
    simulation_request_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    simulated_delivery_fingerprint: FingerprintV1
    delivery_record_fingerprint: FingerprintV1
    acknowledgement_id: CanonicalUuid4 | None = None
    acknowledgement_fingerprint: FingerprintV1 | None = None
    dispatched_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: DeliveryLifecycle
    status: Literal["simulation_only"] = "simulation_only"
    capability_status: Literal["unsupported"] = "unsupported"
    default_enabled: Literal[False] = False
    simulation_only: Literal[True] = True
    live_delivery_claimed: Literal[False] = False
    delivery_received: Literal[False] = False
    agent_admission_claimed: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evidence(self) -> InstallationHandoffSimulatedDeliveryAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        if (self.acknowledgement_id is None) != (
            self.acknowledgement_fingerprint is None
        ):
            raise ValueError("acknowledgement evidence must be complete")
        acknowledged = self.lifecycle in (
            "simulated_acknowledged",
            "expired_acknowledged",
        )
        if acknowledged != (self.acknowledgement_id is not None):
            raise ValueError("lifecycle and acknowledgement evidence disagree")
        return self


class InstallationHandoffSimulatedDeliveryResultV1(ContractModel):
    disposition: Literal["simulated", "exact_replay", "rejected", "unavailable"]
    record: InstallationHandoffSimulatedDeliveryRecordV1 | None
    acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1 | None
    error: InstallationHandoffSimulatedDeliveryErrorV1 | None
    live_delivery_attempted: Literal[False] = False
    execution_attempted: Literal[False] = False
    worker_invoked: Literal[False] = False
    mutation_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self) -> InstallationHandoffSimulatedDeliveryResultV1:
        success = self.disposition in ("simulated", "exact_replay")
        if success != (self.record is not None and self.acknowledgement is not None and self.error is None):
            raise ValueError("result disposition and value disagree")
        if not success and (self.record is not None or self.acknowledgement is not None or self.error is None):
            raise ValueError("failed result must contain only a redacted error")
        if self.disposition == "unavailable" and self.error and self.error.error_code != "unavailable":
            raise ValueError("unavailable result requires unavailable error")
        return self


def build_simulated_delivery(*, operator_id: str, simulated_delivery_id: str,
    simulation_request_id: str, dispatched_at: str,
    envelope: InstallationDispatchEnvelopeV1) -> InstallationHandoffSimulatedDeliveryV1:
    """Validate an owned v0.24 envelope and construct inert delivery evidence."""
    _identity(operator_id)
    exact = InstallationDispatchEnvelopeV1.model_validate(envelope.model_dump(mode="python"))
    if exact.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(owner_id=operator_id, envelope=exact):
        raise ValueError("ownership or envelope fingerprint mismatch")
    raw: dict[str, Any] = {
        "schema": "installation-handoff-simulated-delivery-v1",
        "simulated_delivery_id": simulated_delivery_id,
        "simulation_request_id": simulation_request_id,
        "dispatched_at": dispatched_at,
        "valid_until": exact.valid_until,
        "operation": "install-container", "mode": "simulation-only", "sender": "atlas-core",
        "recipient": {"service": "atlas-agent", "intake_contract": "agent-installation-intake-simulation-v1"},
        "envelope": exact.model_dump(mode="json"),
        "delivery_authorized": False, "live_admission_authorized": False,
        "execution_authorized": False, "worker_allowed": False,
        "mutation_allowed": False, "replay_allowed": False,
    }
    raw["simulated_delivery_fingerprint"] = simulated_delivery_fingerprint(operator_id=operator_id, delivery=raw).model_dump(mode="json")
    return InstallationHandoffSimulatedDeliveryV1.model_validate(raw)


def validate_simulated_delivery(delivery: InstallationHandoffSimulatedDeliveryV1, *, operator_id: str, now: str) -> None:
    exact = InstallationHandoffSimulatedDeliveryV1.model_validate(delivery.model_dump(mode="python"))
    observed = _instant(now)
    if observed < _instant(exact.dispatched_at):
        raise ValueError("observation precedes delivery")
    if observed >= _instant(exact.valid_until):
        raise ValueError("simulated delivery is not current")
    if exact.envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(owner_id=operator_id, envelope=exact.envelope):
        raise ValueError("ownership or envelope fingerprint mismatch")
    if exact.simulated_delivery_fingerprint != simulated_delivery_fingerprint(operator_id=operator_id, delivery=exact):
        raise ValueError("simulated delivery fingerprint mismatch")


def build_delivery_record(*, operator_id: str, delivery: InstallationHandoffSimulatedDeliveryV1) -> InstallationHandoffSimulatedDeliveryRecordV1:
    validate_simulated_delivery(delivery, operator_id=operator_id, now=delivery.dispatched_at)
    raw: dict[str, Any] = {
        "schema": "installation-handoff-simulated-delivery-record-v1",
        "simulated_delivery_id": delivery.simulated_delivery_id,
        "simulation_request_id": delivery.simulation_request_id,
        "dispatch_envelope_id": delivery.envelope.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": delivery.envelope.dispatch_envelope_fingerprint.model_dump(mode="json"),
        "simulated_delivery_fingerprint": delivery.simulated_delivery_fingerprint.model_dump(mode="json"),
        "dispatched_at": delivery.dispatched_at, "valid_until": delivery.valid_until,
        "lifecycle_basis": "simulation_attempt_recorded", "delivery_mode": "in_process_simulation",
        "live_delivery_claimed": False, "agent_admission_claimed": False,
        "execution_authorized": False, "mutation_authorized": False, "replay_allowed": False,
    }
    raw["delivery_record_fingerprint"] = delivery_record_fingerprint(operator_id=operator_id, record=raw).model_dump(mode="json")
    return InstallationHandoffSimulatedDeliveryRecordV1.model_validate(raw)


def validate_acknowledgement(*, operator_id: str, delivery: InstallationHandoffSimulatedDeliveryV1,
    acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1) -> None:
    validate_simulated_delivery(delivery, operator_id=operator_id, now=acknowledgement.acknowledged_at)
    source = acknowledgement.source
    if (source.simulated_delivery_id, source.simulated_delivery_fingerprint,
        source.dispatch_envelope_id, source.dispatch_envelope_fingerprint) != (
        delivery.simulated_delivery_id, delivery.simulated_delivery_fingerprint,
        delivery.envelope.dispatch_envelope_id, delivery.envelope.dispatch_envelope_fingerprint):
        raise ValueError("acknowledgement delivery linkage mismatch")
    if acknowledgement.intake.simulation_request_id != delivery.simulation_request_id:
        raise ValueError("acknowledgement intake linkage mismatch")
    if acknowledgement.valid_until > delivery.valid_until:
        raise ValueError("acknowledgement extends delivery expiry")
    if acknowledgement.acknowledgement_fingerprint != acknowledgement_fingerprint(operator_id=operator_id, acknowledgement=acknowledgement):
        raise ValueError("acknowledgement fingerprint mismatch")


def delivery_lifecycle(record: InstallationHandoffSimulatedDeliveryRecordV1, *, now: str,
    acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1 | None = None) -> DeliveryLifecycle:
    instant = _instant(now)
    if instant < _instant(record.dispatched_at):
        raise ValueError("lifecycle instant precedes delivery")
    acknowledged = acknowledgement is not None
    if acknowledged and acknowledgement.source.simulated_delivery_id != record.simulated_delivery_id:
        raise ValueError("acknowledgement delivery linkage mismatch")
    if instant >= _instant(record.valid_until):
        return "expired_acknowledged" if acknowledged else "expired_unacknowledged"
    return "simulated_acknowledged" if acknowledged else "pending_acknowledgement"


def simulated_delivery_fingerprint(*, operator_id: str, delivery: InstallationHandoffSimulatedDeliveryV1 | dict[str, Any]) -> FingerprintV1:
    raw = delivery.model_dump(mode="json") if isinstance(delivery, BaseModel) else dict(delivery)
    raw.pop("simulated_delivery_fingerprint", None)
    return _fingerprint("atlas:installation-handoff-simulated-delivery:v1", {"operator_id": operator_id, "delivery": raw})


def delivery_record_fingerprint(*, operator_id: str, record: InstallationHandoffSimulatedDeliveryRecordV1 | dict[str, Any]) -> FingerprintV1:
    raw = record.model_dump(mode="json") if isinstance(record, BaseModel) else dict(record)
    raw.pop("delivery_record_fingerprint", None)
    return _fingerprint("atlas:installation-handoff-simulated-delivery-record:v1", {"operator_id": operator_id, "record": raw})


def acknowledgement_fingerprint(*, operator_id: str, acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1 | dict[str, Any]) -> FingerprintV1:
    raw = acknowledgement.model_dump(mode="json") if isinstance(acknowledgement, BaseModel) else dict(acknowledgement)
    raw.pop("acknowledgement_fingerprint", None)
    return _fingerprint("atlas:agent-installation-handoff-simulated-acknowledgement:v1", {"operator_id": operator_id, "acknowledgement": raw})


def audit_evidence_fingerprint(evidence: InstallationHandoffSimulatedDeliveryAuditEvidenceV1 | dict[str, Any]) -> FingerprintV1:
    raw = evidence.model_dump(mode="json") if isinstance(evidence, BaseModel) else dict(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:installation-handoff-simulated-delivery-audit-evidence:v1", raw)


def derived_agent_idempotency_key(delivery: InstallationHandoffSimulatedDeliveryV1) -> str:
    return "v026:" + delivery.simulated_delivery_fingerprint.value


def parse_delivery_json(payload: bytes | str) -> InstallationHandoffSimulatedDeliveryV1:
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > MAX_DELIVERY_BYTES:
        raise StrictContractError("malformed")
    def closed(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StrictContractError("malformed")
            result[key] = value
        return result
    try:
        value = json.loads(encoded.decode("utf-8"), object_pairs_hook=closed)
        if not isinstance(value, dict):
            raise StrictContractError("malformed")
        return InstallationHandoffSimulatedDeliveryV1.model_validate(value)
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("malformed") from error


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
        if isinstance(item, int | float):
            raise TypeError("JSON numbers are prohibited")
        if isinstance(item, dict):
            return {normalize(key): normalize(child) for key, child in item.items()}
        if isinstance(item, list | tuple):
            return [normalize(child) for child in item]
        raise TypeError("value is outside canonical domain")
    return json.dumps(normalize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1",
        value=hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest())


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
