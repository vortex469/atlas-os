"""Closed, pure models for the frozen Real Agent Intake Boundary v1 contract.

This module performs no I/O.  Its admissions are evidence only and grant no
execution, worker, provider, repository, runtime, guest, or mutation authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    model_validator,
)

MAX_REQUEST_BYTES = 64 * 1024
MAX_ADMISSION_BYTES = 32 * 1024
AUTHENTICATED_CORE_PRINCIPAL = "atlas-core/install-intake-v1"
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_VISIBLE_ASCII = re.compile(r"[\x21-\x7e]{1,128}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC_SECOND = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


class StrictContractError(ValueError):
    """A wire value is outside the closed real-intake contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid canonical operator/correlation identity")
    return value


def _visible_ascii(value: str) -> str:
    if not value.isascii() or _VISIBLE_ASCII.fullmatch(value) is None:
        raise ValueError("idempotency key is out of bounds")
    return value


CanonicalOperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]


def _ascii_match(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not value.isascii() or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _uuid4(value: str) -> str:
    return _ascii_match(value, _UUID4, "canonical UUIDv4")


def _hex64(value: str) -> str:
    return _ascii_match(value, _HEX64, "lowerhex[64]")


def _utc_second(value: str) -> str:
    _ascii_match(value, _UTC_SECOND, "UtcSecond")
    parsed = _instant(value)
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("invalid UtcSecond")
    return value


CanonicalUuid4 = Annotated[str, AfterValidator(_uuid4)]
LowerHex64 = Annotated[str, AfterValidator(_hex64)]
UtcSecond = Annotated[str, AfterValidator(_utc_second)]


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
        if not prepared < valid_until:
            raise ValueError("dispatch envelope has no validity window")
        if (valid_until - prepared).total_seconds() > 60:
            raise ValueError("dispatch envelope exceeds 60-second lifetime")
        return self


class AgentInstallationIntakeRecipientV1(ContractModel):
    service: Literal["atlas-agent"] = "atlas-agent"
    intake_contract: Literal["agent-installation-intake-v1"] = "agent-installation-intake-v1"


class AgentInstallationIntakeOperatorAssertionV1(ContractModel):
    operator_id: CanonicalOperatorId
    asserted_by: Literal["atlas-core"] = "atlas-core"


class PriorIntakeEvidenceV1(ContractModel):
    simulation_request_id: CanonicalUuid4
    intake_record_id: CanonicalUuid4
    intake_record_fingerprint: FingerprintV1


class AgentInstallationIntakeSimulatedDeliveryEvidenceV1(ContractModel):
    simulated_delivery_id: CanonicalUuid4
    simulated_delivery_fingerprint: FingerprintV1
    delivery_record_fingerprint: FingerprintV1
    acknowledgement_id: CanonicalUuid4
    acknowledgement_fingerprint: FingerprintV1


class AgentInstallationIntakePriorEvidenceV1(ContractModel):
    intake_simulation: PriorIntakeEvidenceV1
    simulated_delivery: AgentInstallationIntakeSimulatedDeliveryEvidenceV1


class AgentInstallationIntakeRequestV1(ContractModel):
    schema: Literal["agent-installation-intake-request-v1"] = (
        "agent-installation-intake-request-v1"
    )
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    sent_at: UtcSecond
    expires_at: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["intake-evidence-only"] = "intake-evidence-only"
    sender: Literal["atlas-core"] = "atlas-core"
    recipient: AgentInstallationIntakeRecipientV1
    operator_assertion: AgentInstallationIntakeOperatorAssertionV1
    envelope: InstallationDispatchEnvelopeV1
    prior_evidence: AgentInstallationIntakePriorEvidenceV1
    delivery_authorized: Literal[True] = True
    evidence_admission_requested: Literal[True] = True
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    request_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_request(self) -> AgentInstallationIntakeRequestV1:
        prepared = _instant(self.envelope.prepared_at)
        sent = _instant(self.sent_at)
        expires = _instant(self.expires_at)
        if self.expires_at != self.envelope.valid_until:
            raise ValueError("request expiry must equal envelope expiry")
        if not prepared <= sent < expires:
            raise ValueError("request time is outside envelope validity")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_REQUEST_BYTES:
            raise ValueError("real intake request exceeds 64 KiB")
        return self


class AgentInstallationIntakeAdmissionSourceV1(ContractModel):
    request_fingerprint: FingerprintV1
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1


class AgentInstallationIntakeAdmissionV1(ContractModel):
    schema: Literal["agent-installation-intake-admission-v1"] = (
        "agent-installation-intake-admission-v1"
    )
    admission_id: CanonicalUuid4
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    received_at: UtcSecond
    valid_until: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["intake-evidence-only"] = "intake-evidence-only"
    authenticated_sender: Literal["atlas-core/install-intake-v1"] = (
        "atlas-core/install-intake-v1"
    )
    source: AgentInstallationIntakeAdmissionSourceV1
    linkage: InstallationDispatchLinkageV1
    prior_evidence: AgentInstallationIntakePriorEvidenceV1
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    reason_codes: EmptyArray
    statement: Literal[
        "agent_accepted_authenticated_handoff_for_intake_evidence_only"
    ] = "agent_accepted_authenticated_handoff_for_intake_evidence_only"
    delivery_received: Literal[True] = True
    evidence_admission_granted: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    admission_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_admission(self) -> AgentInstallationIntakeAdmissionV1:
        if not _instant(self.received_at) < _instant(self.valid_until):
            raise ValueError("admission is not current")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_ADMISSION_BYTES:
            raise ValueError("real intake admission exceeds 32 KiB")
        return self


IntakeRejectionCodeV1 = Literal[
    "unauthenticated",
    "unauthorized",
    "malformed",
    "not_current",
    "ownership_mismatch",
    "request_mismatch",
    "envelope_mismatch",
    "linkage_mismatch",
    "simulation_evidence_mismatch",
    "delivery_evidence_mismatch",
    "recipient_mismatch",
    "replay_conflict",
    "quota_exceeded",
    "unavailable",
]


class AgentInstallationIntakeResultV1(ContractModel):
    schema: Literal["agent-installation-intake-result-v1"] = (
        "agent-installation-intake-result-v1"
    )
    intake_request_id: CanonicalUuid4 | None
    outcome: Literal["admitted_for_evidence_only", "rejected"]
    admission: AgentInstallationIntakeAdmissionV1 | None
    reason_code: IntakeRejectionCodeV1 | None

    @model_validator(mode="after")
    def exact_result(self) -> AgentInstallationIntakeResultV1:
        admitted = self.outcome == "admitted_for_evidence_only"
        if admitted != (self.admission is not None and self.reason_code is None):
            raise ValueError("result outcome and values disagree")
        if admitted and self.admission and self.intake_request_id != self.admission.intake_request_id:
            raise ValueError("result and admission request IDs disagree")
        if not admitted and (self.admission is not None or self.reason_code is None):
            raise ValueError("rejected result must contain only one sanitized reason")
        if self.reason_code in ("unauthenticated", "unauthorized") and self.intake_request_id is not None:
            raise ValueError("authentication rejection must redact request ID")
        return self


class AgentInstallationIntakeAuthenticationContextV1(ContractModel):
    """Injected authentication result; never accepted from the request body."""

    authenticated_principal: Literal["atlas-core/install-intake-v1"] = (
        "atlas-core/install-intake-v1"
    )
    permission: Literal["installation_intake:create"] = "installation_intake:create"
    internal_https: Literal[True] = True
    credential_authenticated: Literal[True] = True


class AgentInstallationIntakeEvidenceContextV1(ContractModel):
    """Agent-owned v0.25/v0.26 evidence projected for pure equality checks."""

    operator_id: CanonicalOperatorId
    linkage: InstallationDispatchLinkageV1
    prior_evidence: AgentInstallationIntakePriorEvidenceV1
    intake_record_observed_at: UtcSecond
    acknowledgement_acknowledged_at: UtcSecond
    intake_statement: Literal["agent_validated_injected_handoff_without_admission"] = (
        "agent_validated_injected_handoff_without_admission"
    )
    acknowledgement_provenance: Literal["agent_simulated_not_received"] = (
        "agent_simulated_not_received"
    )
    delivery_received: Literal[False] = False
    live_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class AgentInstallationIntakeIdempotencyV1(ContractModel):
    authenticated_principal: Literal["atlas-core/install-intake-v1"] = AUTHENTICATED_CORE_PRINCIPAL
    operator_id: CanonicalOperatorId
    operation: Literal["installation_intake:create"] = "installation_intake:create"
    key: IdempotencyKey
    intake_request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    delivery_attempt_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    prior_evidence: AgentInstallationIntakePriorEvidenceV1
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    reservation_permanent: Literal[True] = True
    exact_retry_only: Literal[True] = True
    replay_allowed: Literal[False] = False


class AgentInstallationIntakeAcknowledgementV1(ContractModel):
    """Closed evidence-only acknowledgement projection of one admission."""

    schema: Literal["agent-installation-intake-acknowledgement-v1"] = (
        "agent-installation-intake-acknowledgement-v1"
    )
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    received_at: UtcSecond
    valid_until: UtcSecond
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    provenance: Literal["authenticated_core_intake_evidence_only"] = (
        "authenticated_core_intake_evidence_only"
    )
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    acknowledgement_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def fingerprint_matches(self) -> AgentInstallationIntakeAcknowledgementV1:
        if self.acknowledgement_fingerprint != acknowledgement_fingerprint(self):
            raise ValueError("acknowledgement fingerprint mismatch")
        return self


class AgentInstallationIntakeAuditEvidenceV1(ContractModel):
    schema: Literal["agent-installation-intake-audit-evidence-v1"] = (
        "agent-installation-intake-audit-evidence-v1"
    )
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    prior_evidence: AgentInstallationIntakePriorEvidenceV1
    received_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: Literal["admitted", "expired", "unavailable"]
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    provenance: Literal["authenticated_core_intake_evidence_only"] = (
        "authenticated_core_intake_evidence_only"
    )
    default_enabled: Literal[False] = False
    evidence_only: Literal[True] = True
    delivery_received: Literal[True] = True
    evidence_admission_granted: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def fingerprint_matches(self) -> AgentInstallationIntakeAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        return self


class AgentInstallationIntakeRedactedErrorV1(ContractModel):
    schema: Literal["agent-installation-intake-error-v1"] = (
        "agent-installation-intake-error-v1"
    )
    error_code: IntakeRejectionCodeV1
    correlation_id: CorrelationId
    authenticated_sender_class: Literal["atlas-core", "unknown"]
    intake_request_id: CanonicalUuid4 | None = None
    request_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True

    @model_validator(mode="after")
    def redact_authentication_failures(self) -> AgentInstallationIntakeRedactedErrorV1:
        if self.error_code in ("unauthenticated", "unauthorized") and (
            self.intake_request_id is not None or self.request_fingerprint is not None
        ):
            raise ValueError("authentication error must redact request identity")
        return self


class AgentInstallationIntakeValidationV1(ContractModel):
    schema: Literal["agent-installation-intake-validation-v1"] = (
        "agent-installation-intake-validation-v1"
    )
    validated_at: UtcSecond
    status: Literal["valid_for_evidence_only"] = "valid_for_evidence_only"
    reason_codes: EmptyArray
    capability_status: Literal["unsupported"] = "unsupported"
    default_enabled: Literal[False] = False
    evidence_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    admission: AgentInstallationIntakeAdmissionV1
    validation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_validation(self) -> AgentInstallationIntakeValidationV1:
        if self.validated_at != self.admission.received_at:
            raise ValueError("validation and admission time disagree")
        if self.validation_fingerprint != validation_fingerprint(self):
            raise ValueError("validation fingerprint mismatch")
        return self


def parse_intake_request_json(payload: bytes | str) -> AgentInstallationIntakeRequestV1:
    """Parse one bounded object while rejecting duplicate and unknown keys."""
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > MAX_REQUEST_BYTES:
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
        return AgentInstallationIntakeRequestV1.model_validate(decoded)
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("malformed") from error


def validate_real_intake(
    request: AgentInstallationIntakeRequestV1,
    *,
    authentication: AgentInstallationIntakeAuthenticationContextV1,
    evidence: AgentInstallationIntakeEvidenceContextV1,
    received_at: str,
    admission_id: str,
) -> AgentInstallationIntakeValidationV1:
    """Purely validate and derive immutable evidence-only admission models."""
    exact = AgentInstallationIntakeRequestV1.model_validate(request.model_dump(mode="python"))
    auth = AgentInstallationIntakeAuthenticationContextV1.model_validate(
        authentication.model_dump(mode="python")
    )
    local = AgentInstallationIntakeEvidenceContextV1.model_validate(
        evidence.model_dump(mode="python")
    )
    _ = auth
    _identity(exact.operator_assertion.operator_id)
    received = _instant(received_at)
    sent = _instant(exact.sent_at)
    expires = _instant(exact.expires_at)
    if exact.request_fingerprint != request_fingerprint(exact):
        raise ValueError("request fingerprint mismatch")
    if exact.envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(
        operator_id=exact.operator_assertion.operator_id, envelope=exact.envelope
    ):
        raise ValueError("ownership or envelope fingerprint mismatch")
    if local.operator_id != exact.operator_assertion.operator_id:
        raise ValueError("ownership mismatch")
    if local.linkage != exact.envelope.linkage:
        raise ValueError("linkage mismatch")
    if local.prior_evidence.intake_simulation != exact.prior_evidence.intake_simulation:
        raise ValueError("simulation evidence mismatch")
    if local.prior_evidence.simulated_delivery != exact.prior_evidence.simulated_delivery:
        raise ValueError("delivery evidence mismatch")
    if received < sent:
        raise ValueError("receipt precedes send time")
    if received >= expires:
        raise ValueError("request is not current")
    if (received - sent).total_seconds() > 10:
        raise ValueError("request exceeded 10-second delivery window")
    if _instant(local.intake_record_observed_at) > sent:
        raise ValueError("simulation evidence postdates request")
    if _instant(local.acknowledgement_acknowledged_at) > sent:
        raise ValueError("delivery evidence postdates request")
    raw: dict[str, Any] = {
        "schema": "agent-installation-intake-admission-v1",
        "admission_id": admission_id,
        "intake_request_id": exact.intake_request_id,
        "delivery_attempt_id": exact.delivery_attempt_id,
        "received_at": received_at,
        "valid_until": exact.expires_at,
        "operation": "install-container",
        "mode": "intake-evidence-only",
        "authenticated_sender": AUTHENTICATED_CORE_PRINCIPAL,
        "source": {
            "request_fingerprint": exact.request_fingerprint.model_dump(mode="json"),
            "dispatch_envelope_id": exact.envelope.dispatch_envelope_id,
            "dispatch_envelope_fingerprint": exact.envelope.dispatch_envelope_fingerprint.model_dump(mode="json"),
        },
        "linkage": exact.envelope.linkage.model_dump(mode="json"),
        "prior_evidence": exact.prior_evidence.model_dump(mode="json"),
        "status": "admitted_for_evidence_only",
        "reason_codes": [],
        "statement": "agent_accepted_authenticated_handoff_for_intake_evidence_only",
        "delivery_received": True,
        "evidence_admission_granted": True,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["admission_fingerprint"] = admission_fingerprint(
        operator_id=local.operator_id, admission=raw
    ).model_dump(mode="json")
    admission = AgentInstallationIntakeAdmissionV1.model_validate(raw)
    validation_raw: dict[str, Any] = {
        "schema": "agent-installation-intake-validation-v1",
        "validated_at": received_at,
        "status": "valid_for_evidence_only",
        "reason_codes": [],
        "capability_status": "unsupported",
        "default_enabled": False,
        "evidence_only": True,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
        "admission": admission.model_dump(mode="json"),
    }
    validation_raw["validation_fingerprint"] = validation_fingerprint(
        validation_raw
    ).model_dump(mode="json")
    return AgentInstallationIntakeValidationV1.model_validate(validation_raw)


def intake_lifecycle(
    admission: AgentInstallationIntakeAdmissionV1, *, now: str
) -> Literal["admitted", "expired"]:
    exact = AgentInstallationIntakeAdmissionV1.model_validate(
        admission.model_dump(mode="python")
    )
    instant = _instant(now)
    if instant < _instant(exact.received_at):
        raise ValueError("lifecycle instant precedes admission")
    return "admitted" if instant < _instant(exact.valid_until) else "expired"


def dispatch_envelope_fingerprint(
    *, operator_id: str, envelope: InstallationDispatchEnvelopeV1 | dict[str, Any]
) -> FingerprintV1:
    _identity(operator_id)
    raw = envelope.model_dump(mode="json") if isinstance(envelope, BaseModel) else dict(envelope)
    raw.pop("dispatch_envelope_fingerprint", None)
    return _fingerprint(
        "atlas:installation-dispatch-envelope:v1",
        {"owner_id": operator_id, "envelope": raw},
    )


def request_fingerprint(
    request: AgentInstallationIntakeRequestV1 | dict[str, Any],
    *, authenticated_core_principal: str = AUTHENTICATED_CORE_PRINCIPAL,
) -> FingerprintV1:
    if authenticated_core_principal != AUTHENTICATED_CORE_PRINCIPAL:
        raise ValueError("unsupported authenticated Core principal")
    raw = request.model_dump(mode="json") if isinstance(request, BaseModel) else dict(request)
    raw.pop("request_fingerprint", None)
    return _fingerprint(
        "atlas:agent-installation-intake-request:v1",
        {"authenticated_core_principal": authenticated_core_principal, "request": raw},
    )


def admission_fingerprint(
    *, operator_id: str, admission: AgentInstallationIntakeAdmissionV1 | dict[str, Any]
) -> FingerprintV1:
    _identity(operator_id)
    raw = admission.model_dump(mode="json") if isinstance(admission, BaseModel) else dict(admission)
    raw.pop("admission_fingerprint", None)
    return _fingerprint(
        "atlas:agent-installation-intake-admission:v1",
        {"operator_id": operator_id, "admission": raw},
    )


def acknowledgement_fingerprint(
    acknowledgement: AgentInstallationIntakeAcknowledgementV1 | dict[str, Any],
) -> FingerprintV1:
    raw = acknowledgement.model_dump(mode="json") if isinstance(acknowledgement, BaseModel) else dict(acknowledgement)
    raw.pop("acknowledgement_fingerprint", None)
    return _fingerprint("atlas:agent-installation-intake-acknowledgement:v1", raw)


def audit_evidence_fingerprint(
    evidence: AgentInstallationIntakeAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    raw = evidence.model_dump(mode="json") if isinstance(evidence, BaseModel) else dict(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:agent-installation-intake-audit-evidence:v1", raw)


def validation_fingerprint(
    validation: AgentInstallationIntakeValidationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = validation.model_dump(mode="json") if isinstance(validation, BaseModel) else dict(validation)
    raw.pop("validation_fingerprint", None)
    return _fingerprint("atlas:agent-installation-intake-validation:v1", raw)


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
            result: dict[str, object] = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON keys must be strings")
                normalize(key)
                result[key] = normalize(child)
            return result
        if isinstance(item, list | tuple):
            return [normalize(child) for child in item]
        raise TypeError("value is outside canonical domain")

    return json.dumps(
        normalize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
