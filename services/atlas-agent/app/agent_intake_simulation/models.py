"""Closed, pure models for the frozen Agent Intake Simulation v1 contract.

Accepted values are injected simulation evidence only.  This module performs no
I/O and grants no delivery, admission, execution, worker, mutation, or replay
authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    model_validator,
)

MAX_CREATE_BYTES = 40 * 1024
MAX_ENVELOPE_BYTES = 32 * 1024
MAX_RECORD_BYTES = 32 * 1024

_HEX64 = re.compile(r"[0-9a-f]{64}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC_SECOND = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class StrictContractError(ValueError):
    """A wire value is outside the closed simulation contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _ascii_match(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not value.isascii() or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _hex64(value: str) -> str:
    return _ascii_match(value, _HEX64, "lowerhex[64]")


def _uuid4(value: str) -> str:
    return _ascii_match(value, _UUID4, "canonical UUIDv4")


def _utc_second(value: str) -> str:
    _ascii_match(value, _UTC_SECOND, "UtcSecond")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("invalid UtcSecond") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("invalid UtcSecond")
    return value


def _identity(value: str) -> str:
    return _ascii_match(value, _IDENTITY, "operator/correlation identity")


def _visible_ascii(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value.encode()) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("idempotency key is out of bounds")
    return value


CanonicalUuid4 = Annotated[str, AfterValidator(_uuid4)]
LowerHex64 = Annotated[str, AfterValidator(_hex64)]
UtcSecond = Annotated[str, AfterValidator(_utc_second)]
OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]


def _tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


EmptyArray = Annotated[tuple[()], BeforeValidator(_tuple)]


class FingerprintV1(ContractModel):
    algorithm: Literal["sha256"]
    canonicalization: Literal["atlas-jcs-nfc-v1"]
    value: LowerHex64


class InstallationDispatchRecipientV1(ContractModel):
    service: Literal["atlas-agent"] = "atlas-agent"
    intake_contract: Literal["agent-installation-dispatch-intake-v1"] = (
        "agent-installation-dispatch-intake-v1"
    )


class InstallationDispatchLinkageV1(ContractModel):
    candidate_record_id: CanonicalUuid4
    candidate_envelope_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    approval_intent_id: CanonicalUuid4
    approval_intent_fingerprint: FingerprintV1
    agent_request_id: CanonicalUuid4
    agent_request_fingerprint: FingerprintV1
    agent_validation_fingerprint: FingerprintV1
    agent_evidence_fingerprint: FingerprintV1
    destination_fingerprint: LowerHex64
    source_plan_fingerprint: FingerprintV1
    artifact_policy_fingerprint: FingerprintV1
    execution_request_id: CanonicalUuid4
    execution_request_fingerprint: FingerprintV1


class InstallationDispatchEnvelopeV1(ContractModel):
    schema: Literal["installation-dispatch-envelope-v1"] = "installation-dispatch-envelope-v1"
    dispatch_envelope_id: CanonicalUuid4
    prepared_at: UtcSecond
    valid_until: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["handoff-only"] = "handoff-only"
    recipient: InstallationDispatchRecipientV1
    linkage: InstallationDispatchLinkageV1
    statement: Literal["core_prepared_non_executing_agent_handoff"] = (
        "core_prepared_non_executing_agent_handoff"
    )
    delivery_authorized: Literal[False] = False
    agent_admission_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False
    dispatch_envelope_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_envelope(self) -> InstallationDispatchEnvelopeV1:
        prepared = _instant(self.prepared_at)
        valid_until = _instant(self.valid_until)
        if valid_until <= prepared:
            raise ValueError("dispatch envelope has no validity window")
        if valid_until > prepared + timedelta(seconds=60):
            raise ValueError("dispatch envelope exceeds 60-second lifetime")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_ENVELOPE_BYTES:
            raise ValueError("dispatch envelope exceeds 32 KiB")
        return self


class AgentInstallationIntakeSimulationCreateV1(ContractModel):
    schema: Literal["agent-installation-intake-simulation-create-v1"] = (
        "agent-installation-intake-simulation-create-v1"
    )
    simulation_request_id: CanonicalUuid4
    envelope: InstallationDispatchEnvelopeV1

    @model_validator(mode="after")
    def bounded_create(self) -> AgentInstallationIntakeSimulationCreateV1:
        if len(_canonical(self.model_dump(mode="json"))) > MAX_CREATE_BYTES:
            raise ValueError("simulation create exceeds 40 KiB")
        return self


class AgentInstallationIntakeSimulationSourceV1(ContractModel):
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1


SimulationLifecycle = Literal["simulated", "expired"]


class AgentInstallationIntakeSimulationV1(ContractModel):
    schema: Literal["agent-installation-intake-simulation-v1"] = (
        "agent-installation-intake-simulation-v1"
    )
    intake_record_id: CanonicalUuid4
    simulation_request_id: CanonicalUuid4
    observed_at: UtcSecond
    valid_until: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["simulation-only"] = "simulation-only"
    source: AgentInstallationIntakeSimulationSourceV1
    linkage: InstallationDispatchLinkageV1
    status: Literal["simulated_valid"] = "simulated_valid"
    reason_codes: EmptyArray
    statement: Literal["agent_validated_injected_handoff_without_admission"] = (
        "agent_validated_injected_handoff_without_admission"
    )
    delivery_received: Literal[False] = False
    live_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    intake_record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_record(self) -> AgentInstallationIntakeSimulationV1:
        observed = _instant(self.observed_at)
        valid_until = _instant(self.valid_until)
        if not observed < valid_until <= observed + timedelta(seconds=30):
            raise ValueError("simulation record validity is out of bounds")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_RECORD_BYTES:
            raise ValueError("simulation record exceeds 32 KiB")
        return self


SimulationErrorCode = Literal[
    "malformed",
    "not_current",
    "ownership_mismatch",
    "envelope_mismatch",
    "linkage_mismatch",
    "recipient_mismatch",
    "replay_conflict",
    "quota_exceeded",
    "unavailable",
]


class AgentInstallationIntakeSimulationErrorV1(ContractModel):
    schema: Literal["agent-installation-intake-simulation-error-v1"] = (
        "agent-installation-intake-simulation-error-v1"
    )
    error_code: SimulationErrorCode
    correlation_id: CorrelationId
    simulation_request_id: CanonicalUuid4 | None = None
    dispatch_envelope_id: CanonicalUuid4 | None = None
    dispatch_envelope_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True


class AgentInstallationIntakeSimulationAuditEvidenceV1(ContractModel):
    schema: Literal["agent-installation-intake-simulation-audit-evidence-v1"] = (
        "agent-installation-intake-simulation-audit-evidence-v1"
    )
    intake_record_id: CanonicalUuid4
    simulation_request_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    linkage: InstallationDispatchLinkageV1
    intake_record_fingerprint: FingerprintV1
    observed_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: SimulationLifecycle
    status: Literal["simulated_valid"] = "simulated_valid"
    evidence_provenance: Literal["agent_simulated_not_received"] = (
        "agent_simulated_not_received"
    )
    delivery_received: Literal[False] = False
    live_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evidence(self) -> AgentInstallationIntakeSimulationAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        return self


class AgentInstallationIntakeSimulationIdempotencyV1(ContractModel):
    operator_id: OperatorId
    operation: Literal["create-agent-installation-intake-simulation"] = (
        "create-agent-installation-intake-simulation"
    )
    key: IdempotencyKey
    create_fingerprint: FingerprintV1
    simulation_request_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    intake_record_fingerprint: FingerprintV1
    replay_allowed: Literal[False] = False


class AgentInstallationIntakeSimulationValidationV1(ContractModel):
    schema: Literal["agent-installation-intake-simulation-validation-v1"] = (
        "agent-installation-intake-simulation-validation-v1"
    )
    observed_at: UtcSecond
    status: Literal["simulated_valid"] = "simulated_valid"
    reason_codes: EmptyArray
    capability_status: Literal["unsupported"] = "unsupported"
    default_enabled: Literal[False] = False
    simulation_only: Literal[True] = True
    delivery_received: Literal[False] = False
    live_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    record: AgentInstallationIntakeSimulationV1
    validation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_validation(self) -> AgentInstallationIntakeSimulationValidationV1:
        if self.observed_at != self.record.observed_at:
            raise ValueError("validation and record observation mismatch")
        if self.validation_fingerprint != validation_fingerprint(self):
            raise ValueError("validation fingerprint mismatch")
        return self


class AgentInstallationIntakeSimulationResultV1(ContractModel):
    disposition: Literal["simulated", "exact_replay", "rejected", "unavailable"]
    validation: AgentInstallationIntakeSimulationValidationV1 | None
    error: AgentInstallationIntakeSimulationErrorV1 | None
    delivery_attempted: Literal[False] = False
    live_admission_attempted: Literal[False] = False
    worker_invoked: Literal[False] = False
    mutation_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self) -> AgentInstallationIntakeSimulationResultV1:
        success = self.disposition in ("simulated", "exact_replay")
        if success != (self.validation is not None and self.error is None):
            raise ValueError("result disposition and value disagree")
        if not success and (self.validation is not None or self.error is None):
            raise ValueError("failed result must contain only a redacted error")
        if self.disposition == "unavailable" and self.error and self.error.error_code != "unavailable":
            raise ValueError("unavailable result requires unavailable error")
        return self


def parse_simulation_create_json(
    payload: bytes | str,
) -> AgentInstallationIntakeSimulationCreateV1:
    """Parse one bounded JSON object, rejecting duplicate and unknown keys."""
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > MAX_CREATE_BYTES:
        raise StrictContractError("malformed")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StrictContractError("malformed")
            result[key] = value
        return result

    try:
        decoded = json.loads(encoded.decode("utf-8"), object_pairs_hook=reject_duplicates)
        if not isinstance(decoded, dict):
            raise StrictContractError("malformed")
        return AgentInstallationIntakeSimulationCreateV1.model_validate(decoded)
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("malformed") from error


def validate_simulated_intake(
    create: AgentInstallationIntakeSimulationCreateV1,
    *,
    operator_id: str,
    observed_at: str,
    intake_record_id: str,
) -> AgentInstallationIntakeSimulationValidationV1:
    """Validate injected bytes and return immutable, non-authorizing evidence."""
    exact = AgentInstallationIntakeSimulationCreateV1.model_validate(
        create.model_dump(mode="python")
    )
    _identity(operator_id)
    _uuid4(intake_record_id)
    _utc_second(observed_at)
    envelope = exact.envelope
    if envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(
        operator_id=operator_id, envelope=envelope
    ):
        raise ValueError("ownership or envelope fingerprint mismatch")
    observed = _instant(observed_at)
    prepared = _instant(envelope.prepared_at)
    upstream_deadline = _instant(envelope.valid_until)
    if observed < prepared:
        raise ValueError("observation precedes source preparation")
    if observed >= upstream_deadline:
        raise ValueError("source envelope is not current")
    valid_until = min(upstream_deadline, observed + timedelta(seconds=30))
    raw: dict[str, Any] = {
        "schema": "agent-installation-intake-simulation-v1",
        "intake_record_id": intake_record_id,
        "simulation_request_id": exact.simulation_request_id,
        "observed_at": observed_at,
        "valid_until": _format(valid_until),
        "operation": "install-container",
        "mode": "simulation-only",
        "source": {
            "dispatch_envelope_id": envelope.dispatch_envelope_id,
            "dispatch_envelope_fingerprint": envelope.dispatch_envelope_fingerprint.model_dump(
                mode="json"
            ),
        },
        "linkage": envelope.linkage.model_dump(mode="json"),
        "status": "simulated_valid",
        "reason_codes": [],
        "statement": "agent_validated_injected_handoff_without_admission",
        "delivery_received": False,
        "live_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["intake_record_fingerprint"] = intake_record_fingerprint(
        operator_id=operator_id, record=raw
    ).model_dump(mode="json")
    record = AgentInstallationIntakeSimulationV1.model_validate(raw)
    validation_raw: dict[str, Any] = {
        "schema": "agent-installation-intake-simulation-validation-v1",
        "observed_at": observed_at,
        "status": "simulated_valid",
        "reason_codes": [],
        "capability_status": "unsupported",
        "default_enabled": False,
        "simulation_only": True,
        "delivery_received": False,
        "live_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
        "record": record.model_dump(mode="json"),
    }
    validation_raw["validation_fingerprint"] = validation_fingerprint(
        validation_raw
    ).model_dump(mode="json")
    return AgentInstallationIntakeSimulationValidationV1.model_validate(validation_raw)


def simulation_lifecycle(
    record: AgentInstallationIntakeSimulationV1, *, now: str
) -> SimulationLifecycle:
    exact = AgentInstallationIntakeSimulationV1.model_validate(record.model_dump(mode="python"))
    instant = _instant(_utc_second(now))
    if instant < _instant(exact.observed_at):
        raise ValueError("lifecycle instant precedes observation")
    return "simulated" if instant < _instant(exact.valid_until) else "expired"


def dispatch_envelope_fingerprint(
    *, operator_id: str, envelope: InstallationDispatchEnvelopeV1 | dict[str, Any]
) -> FingerprintV1:
    raw = envelope.model_dump(mode="json") if isinstance(envelope, BaseModel) else dict(envelope)
    raw.pop("dispatch_envelope_fingerprint", None)
    return _fingerprint(
        "atlas:installation-dispatch-envelope:v1",
        {"owner_id": operator_id, "envelope": raw},
    )


def simulation_create_fingerprint(
    create: AgentInstallationIntakeSimulationCreateV1,
) -> FingerprintV1:
    return _fingerprint(
        "atlas:agent-installation-intake-simulation-create:v1",
        create.model_dump(mode="json"),
    )


def intake_record_fingerprint(
    *, operator_id: str, record: AgentInstallationIntakeSimulationV1 | dict[str, Any]
) -> FingerprintV1:
    raw = record.model_dump(mode="json") if isinstance(record, BaseModel) else dict(record)
    raw.pop("intake_record_fingerprint", None)
    return _fingerprint(
        "atlas:agent-installation-intake-simulation:v1",
        {"operator_id": operator_id, "record": raw},
    )


def audit_evidence_fingerprint(
    evidence: AgentInstallationIntakeSimulationAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    raw = evidence.model_dump(mode="json") if isinstance(evidence, BaseModel) else dict(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:agent-installation-intake-simulation-audit-evidence:v1", raw)


def validation_fingerprint(
    validation: AgentInstallationIntakeSimulationValidationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = validation.model_dump(mode="json") if isinstance(validation, BaseModel) else dict(validation)
    raw.pop("validation_fingerprint", None)
    return _fingerprint("atlas:agent-installation-intake-simulation-validation:v1", raw)


def _canonical(value: object) -> bytes:
    def normalize(item: object) -> object:
        if isinstance(item, BaseModel):
            return normalize(item.model_dump(mode="json"))
        if isinstance(item, str):
            if item != unicodedata.normalize("NFC", item):
                raise ValueError("strings must be NFC")
            return item
        elif isinstance(item, bool) or item is None:
            return item
        elif isinstance(item, int | float):
            raise TypeError("JSON numbers are prohibited")
        elif isinstance(item, dict):
            result: dict[str, object] = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON keys must be strings")
                normalize(key)
                result[key] = normalize(child)
            return result
        elif isinstance(item, list | tuple):
            return [normalize(child) for child in item]
        else:
            raise TypeError("value is outside canonical domain")

    normalized = normalize(value)
    return json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _format(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
