"""Closed, pure models for Agent Live Intake Admission v1.

This module performs no I/O and grants only durable evidence admission.  It
contains no route, service, credential reader, transport, worker, or execution
integration.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.real_agent_intake_boundary.models import (
    AgentInstallationIntakeRequestV1,
    CanonicalOperatorId,
    CanonicalUuid4,
    CorrelationId,
    FingerprintV1,
    UtcSecond,
    request_fingerprint,
)

MAX_FRESHNESS_SECONDS = 30
MAX_REQUEST_BYTES = 64 * 1024
MAX_ENVELOPE_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 32 * 1024
MAX_RECORD_BYTES = 128 * 1024
AUTHENTICATED_CORE_PRINCIPAL = "atlas-core/install-intake-v1"
AUTHENTICATED_CORE_PERMISSION = "installation_intake:create"
INTAKE_PATH = "/api/v1/internal/installation-intake"

_VISIBLE_ASCII = re.compile(r"[\x21-\x7e]{1,128}")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class StrictContractError(ValueError):
    """A JSON value is outside the closed v0.32 contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _visible_ascii(value: str) -> str:
    if not value.isascii() or _VISIBLE_ASCII.fullmatch(value) is None:
        raise ValueError("idempotency key is out of bounds")
    return value


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid source identity")
    return value


def _dns(value: str) -> str:
    if (
        not value.isascii()
        or value != value.lower()
        or not 1 <= len(value) <= 253
        or value in {"localhost", "localhost.localdomain"}
        or value.endswith(".")
        or any(_DNS_LABEL.fullmatch(part) is None for part in value.split("."))
    ):
        raise ValueError("invalid canonical internal DNS name")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError("IP literals are prohibited")


def _absolute_file(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value.encode()) <= 4096
        or "\x00" in value
        or value.startswith("~")
        or "$" in value
        or not value.startswith("/")
        or "//" in value
    ):
        raise ValueError("invalid canonical absolute file path")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {".", ".."} for part in path.parts):
        raise ValueError("invalid canonical absolute file path")
    return value


IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]
SourceIdentity = Annotated[str, AfterValidator(_identity)]
CanonicalInternalDnsName = Annotated[str, AfterValidator(_dns)]
CanonicalAbsoluteFilePath = Annotated[str, AfterValidator(_absolute_file)]


class AgentLiveIntakeLinkageV1(ContractModel):
    candidate_record_id: CanonicalUuid4
    candidate_envelope_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    approval_intent_id: CanonicalUuid4
    approval_intent_fingerprint: FingerprintV1
    agent_request_id: CanonicalUuid4
    agent_request_fingerprint: FingerprintV1
    agent_validation_fingerprint: FingerprintV1
    agent_audit_evidence_fingerprint: FingerprintV1
    destination_fingerprint: FingerprintV1
    source_plan_fingerprint: FingerprintV1
    artifact_policy_fingerprint: FingerprintV1
    execution_request_id: CanonicalUuid4
    execution_request_fingerprint: FingerprintV1
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    simulation_request_id: CanonicalUuid4
    intake_record_id: CanonicalUuid4
    intake_record_fingerprint: FingerprintV1
    intake_simulation_evidence_fingerprint: FingerprintV1
    simulated_delivery_id: CanonicalUuid4
    simulated_delivery_fingerprint: FingerprintV1
    delivery_record_fingerprint: FingerprintV1
    simulated_delivery_evidence_fingerprint: FingerprintV1
    simulated_acknowledgement_id: CanonicalUuid4
    simulated_acknowledgement_fingerprint: FingerprintV1
    simulated_acknowledgement_evidence_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    dormant_preparation_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    enablement_id: CanonicalUuid4
    enablement_fingerprint: FingerprintV1


class AgentLiveIntakeSendAttemptV1(ContractModel):
    schema: Literal["live-delivery-send-attempt-v1"] = "live-delivery-send-attempt-v1"
    send_attempt_id: CanonicalUuid4
    created_at: UtcSecond
    expires_at: UtcSecond
    operator_id: CanonicalOperatorId
    linkage: AgentLiveIntakeLinkageV1
    endpoint_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    request_body_fingerprint: FingerprintV1
    lifecycle_at_creation: Literal["reserved"] = "reserved"
    default_enabled: Literal[False] = False
    network_attempted: Literal[False] = False
    evidence_only: Literal[True] = True
    execution_requested: Literal[False] = False
    installation_requested: Literal[False] = False
    mutation_requested: Literal[False] = False
    replay_allowed: Literal[False] = False
    attempt_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_attempt(self) -> AgentLiveIntakeSendAttemptV1:
        created, expires = _instant(self.created_at), _instant(self.expires_at)
        if not created < expires <= created + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("attempt exceeds inherited 30-second freshness")
        if self.linkage.intake_request_id == self.send_attempt_id:
            raise ValueError("attempt and intake identities must be distinct")
        if self.attempt_fingerprint != attempt_fingerprint(self):
            raise ValueError("attempt fingerprint mismatch")
        return self


class AgentLiveIntakeEnvelopeV1(ContractModel):
    schema: Literal["agent-live-intake-envelope-v1"] = "agent-live-intake-envelope-v1"
    send_attempt: AgentLiveIntakeSendAttemptV1
    intake_request: AgentInstallationIntakeRequestV1
    request_fingerprint: FingerprintV1
    request_body_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    endpoint_fingerprint: FingerprintV1
    content_type: Literal["application/json"] = "application/json"
    credential_reference_only: Literal[True] = True
    credential_material_present: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0
    evidence_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    envelope_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_envelope(self) -> AgentLiveIntakeEnvelopeV1:
        attempt, request = self.send_attempt, self.intake_request
        body = _canonical(request)
        if len(body) > MAX_REQUEST_BYTES or len(_canonical(self)) > MAX_ENVELOPE_BYTES:
            raise ValueError("live intake body or envelope exceeds bounds")
        if request.request_fingerprint != request_fingerprint(request):
            raise ValueError("embedded request fingerprint mismatch")
        if self.request_fingerprint != request.request_fingerprint:
            raise ValueError("request fingerprint mismatch")
        if self.request_body_fingerprint != request_body_fingerprint(body):
            raise ValueError("request body fingerprint mismatch")
        if attempt.request_fingerprint != self.request_fingerprint or attempt.request_body_fingerprint != self.request_body_fingerprint:
            raise ValueError("attempt request binding mismatch")
        if attempt.endpoint_fingerprint != self.endpoint_fingerprint:
            raise ValueError("endpoint fingerprint mismatch")
        if request.operator_assertion.operator_id != attempt.operator_id:
            raise ValueError("operator ownership mismatch")
        if request.intake_request_id != attempt.linkage.intake_request_id or request.delivery_attempt_id != attempt.linkage.delivery_attempt_id:
            raise ValueError("v0.27 request linkage mismatch")
        if request.envelope.dispatch_envelope_id != attempt.linkage.dispatch_envelope_id or request.envelope.dispatch_envelope_fingerprint != attempt.linkage.dispatch_envelope_fingerprint:
            raise ValueError("dispatch linkage mismatch")
        if request.expires_at != attempt.expires_at or _instant(request.sent_at) < _instant(attempt.created_at):
            raise ValueError("attempt/request freshness mismatch")
        if self.envelope_fingerprint != envelope_fingerprint(self):
            raise ValueError("envelope fingerprint mismatch")
        return self


class AgentLiveIntakeAuthenticationReferenceV1(ContractModel):
    scheme: Literal["Bearer"] = "Bearer"
    principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] = AUTHENTICATED_CORE_PRINCIPAL
    permission: Literal[AUTHENTICATED_CORE_PERMISSION] = AUTHENTICATED_CORE_PERMISSION
    credential_source: Literal["mode-0400-file"] = "mode-0400-file"
    credential_file: CanonicalAbsoluteFilePath
    required_file_mode: Literal["0400"] = "0400"
    maximum_credential_bytes: Literal[4096] = 4096


class AgentLiveIntakeSourceV1(ContractModel):
    scheme: Literal["https"] = "https"
    host: CanonicalInternalDnsName
    path: Literal[INTAKE_PATH] = INTAKE_PATH
    principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] = AUTHENTICATED_CORE_PRINCIPAL
    forwarded_ingress: Literal[False] = False
    proxy_used: Literal[False] = False


class AgentLiveIntakeAuthenticationContextV1(ContractModel):
    authenticated_principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] = AUTHENTICATED_CORE_PRINCIPAL
    permission: Literal[AUTHENTICATED_CORE_PERMISSION] = AUTHENTICATED_CORE_PERMISSION
    internal_https: Literal[True] = True
    credential_authenticated: Literal[True] = True
    source: AgentLiveIntakeSourceV1
    credential_reference: AgentLiveIntakeAuthenticationReferenceV1
    credential_material_present: Literal[False] = False


class AgentLiveIntakeAuthenticationResultV1(ContractModel):
    schema: Literal["agent-live-intake-authentication-result-v1"] = "agent-live-intake-authentication-result-v1"
    outcome: Literal["authenticated", "rejected"]
    principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] | None
    permission: Literal[AUTHENTICATED_CORE_PERMISSION] | None
    source_identity: SourceIdentity | None
    credential_reference_fingerprint: FingerprintV1 | None
    redacted: Literal[True] = True
    credential_material_present: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self) -> AgentLiveIntakeAuthenticationResultV1:
        authenticated = self.outcome == "authenticated"
        values = (self.principal, self.permission, self.source_identity, self.credential_reference_fingerprint)
        if (authenticated and not all(values)) or (not authenticated and any(value is not None for value in values)):
            raise ValueError("authentication result shape mismatch")
        return self


class _AuthorityFlags(ContractModel):
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class AgentLiveIntakeAdmissionV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-admission-v1"] = "agent-live-intake-admission-v1"
    admission_id: CanonicalUuid4
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    delivery_attempt_id: CanonicalUuid4
    received_at: UtcSecond
    valid_until: UtcSecond
    operator_id: CanonicalOperatorId
    linkage: AgentLiveIntakeLinkageV1
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    statement: Literal["agent_admitted_authenticated_live_delivery_evidence_only"] = "agent_admitted_authenticated_live_delivery_evidence_only"
    delivery_received: Literal[True] = True
    evidence_admission_granted: Literal[True] = True
    admission_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_admission(self) -> AgentLiveIntakeAdmissionV1:
        if not _instant(self.received_at) < _instant(self.valid_until):
            raise ValueError("admission is expired")
        if self.intake_request_id != self.linkage.intake_request_id or self.delivery_attempt_id != self.linkage.delivery_attempt_id:
            raise ValueError("admission linkage mismatch")
        if self.admission_fingerprint != admission_fingerprint(self):
            raise ValueError("admission fingerprint mismatch")
        return self


class AgentLiveIntakeAcknowledgementV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-acknowledgement-v1"] = "agent-live-intake-acknowledgement-v1"
    acknowledgement_id: CanonicalUuid4
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    received_at: UtcSecond
    valid_until: UtcSecond
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    provenance: Literal["authenticated_core_live_intake_evidence_only"] = "authenticated_core_live_intake_evidence_only"
    acknowledgement_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_ack(self) -> AgentLiveIntakeAcknowledgementV1:
        if not _instant(self.received_at) < _instant(self.valid_until):
            raise ValueError("acknowledgement is expired")
        if self.acknowledgement_fingerprint != acknowledgement_fingerprint(self):
            raise ValueError("acknowledgement fingerprint mismatch")
        return self


AgentLiveIntakeRejectionCodeV1 = Literal[
    "unauthenticated", "unauthorized", "malformed", "not_current",
    "ownership_mismatch", "request_mismatch", "attempt_mismatch",
    "linkage_mismatch", "fingerprint_mismatch", "replay_conflict",
    "quota_exceeded", "unavailable",
]


class AgentLiveIntakeResultV1(ContractModel):
    schema: Literal["agent-live-intake-result-v1"] = "agent-live-intake-result-v1"
    send_attempt_id: CanonicalUuid4 | None
    intake_request_id: CanonicalUuid4 | None
    outcome: Literal["admitted_for_evidence_only", "rejected"]
    admission: AgentLiveIntakeAdmissionV1 | None
    acknowledgement: AgentLiveIntakeAcknowledgementV1 | None
    reason_code: AgentLiveIntakeRejectionCodeV1 | None

    @model_validator(mode="after")
    def exact_result(self) -> AgentLiveIntakeResultV1:
        admitted = self.outcome == "admitted_for_evidence_only"
        if admitted != (self.admission is not None and self.acknowledgement is not None and self.reason_code is None):
            raise ValueError("result outcome shape mismatch")
        if admitted and self.admission and self.acknowledgement:
            if self.send_attempt_id != self.admission.send_attempt_id or self.send_attempt_id != self.acknowledgement.send_attempt_id:
                raise ValueError("result attempt mismatch")
            if self.intake_request_id != self.admission.intake_request_id or self.intake_request_id != self.acknowledgement.intake_request_id:
                raise ValueError("result request mismatch")
            if self.acknowledgement.admission_id != self.admission.admission_id or self.acknowledgement.admission_fingerprint != self.admission.admission_fingerprint:
                raise ValueError("result admission mismatch")
        if self.reason_code in {"unauthenticated", "unauthorized"} and (self.send_attempt_id is not None or self.intake_request_id is not None):
            raise ValueError("authentication rejection must redact identities")
        if len(_canonical(self)) > MAX_RESPONSE_BYTES:
            raise ValueError("live intake response exceeds 32 KiB")
        return self


class AgentLiveIntakeRedactedErrorV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-error-v1"] = "agent-live-intake-error-v1"
    error_code: AgentLiveIntakeRejectionCodeV1
    safe_message: Literal["Agent live intake evidence is unavailable."] = "Agent live intake evidence is unavailable."
    correlation_id: CorrelationId
    send_attempt_id: CanonicalUuid4 | None = None
    attempt_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True
    retryable: Literal[False] = False

    @model_validator(mode="after")
    def redact_auth_failures(self) -> AgentLiveIntakeRedactedErrorV1:
        if self.error_code in {"unauthenticated", "unauthorized"} and (self.send_attempt_id is not None or self.attempt_fingerprint is not None):
            raise ValueError("authentication failure must redact identities")
        return self


class AgentLiveIntakeIdempotencyV1(ContractModel):
    authenticated_principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] = AUTHENTICATED_CORE_PRINCIPAL
    operator_id: CanonicalOperatorId
    operation: Literal[AUTHENTICATED_CORE_PERMISSION] = AUTHENTICATED_CORE_PERMISSION
    key: IdempotencyKey
    idempotency_key_fingerprint: FingerprintV1
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    enablement_id: CanonicalUuid4
    preflight_id: CanonicalUuid4
    delivery_preparation_id: CanonicalUuid4
    intake_request_id: CanonicalUuid4
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    reservation_permanent: Literal[True] = True
    exact_duplicate_only: Literal[True] = True
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_key(self) -> AgentLiveIntakeIdempotencyV1:
        if self.idempotency_key_fingerprint != idempotency_key_fingerprint(self.operator_id, self.key):
            raise ValueError("idempotency fingerprint mismatch")
        return self


AgentLiveIntakeLifecycleV1 = Literal[
    "disabled", "received", "admitted_for_evidence_only", "rejected", "expired", "unavailable"
]


class AgentLiveIntakeStatusV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-status-v1"] = "agent-live-intake-status-v1"
    admission_id: CanonicalUuid4
    send_attempt_id: CanonicalUuid4
    operator_id: CanonicalOperatorId
    observed_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: AgentLiveIntakeLifecycleV1
    default_enabled: Literal[False] = False
    evidence_only: Literal[True] = True


class AgentLiveIntakeAuditEvidenceV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-audit-evidence-v1"] = "agent-live-intake-audit-evidence-v1"
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    acknowledgement_fingerprint: FingerprintV1
    record_fingerprint: FingerprintV1
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1
    authenticated_principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] = AUTHENTICATED_CORE_PRINCIPAL
    permission: Literal[AUTHENTICATED_CORE_PERMISSION] = AUTHENTICATED_CORE_PERMISSION
    operator_fingerprint: FingerprintV1
    correlation_id: CorrelationId
    received_at: UtcSecond
    completed_at: UtcSecond
    lifecycle: Literal["admitted_for_evidence_only", "expired", "unavailable"]
    outcome: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    default_enabled: Literal[False] = False
    evidence_only: Literal[True] = True
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_audit(self) -> AgentLiveIntakeAuditEvidenceV1:
        if _instant(self.completed_at) < _instant(self.received_at):
            raise ValueError("audit completion precedes receipt")
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        return self


class AgentLiveIntakeReceiptV1(_AuthorityFlags):
    """Agent-owned durable admission record; not the downstream Core receipt."""

    schema: Literal["agent-live-intake-record-v1"] = "agent-live-intake-record-v1"
    admission: AgentLiveIntakeAdmissionV1
    acknowledgement: AgentLiveIntakeAcknowledgementV1
    authenticated_principal: Literal[AUTHENTICATED_CORE_PRINCIPAL] = AUTHENTICATED_CORE_PRINCIPAL
    permission: Literal[AUTHENTICATED_CORE_PERMISSION] = AUTHENTICATED_CORE_PERMISSION
    credential_reference_fingerprint: FingerprintV1
    lifecycle_at_creation: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    default_enabled: Literal[False] = False
    evidence_only: Literal[True] = True
    record_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_record(self) -> AgentLiveIntakeReceiptV1:
        if self.acknowledgement.admission_id != self.admission.admission_id or self.acknowledgement.admission_fingerprint != self.admission.admission_fingerprint:
            raise ValueError("record admission mismatch")
        if self.acknowledgement.send_attempt_id != self.admission.send_attempt_id:
            raise ValueError("record attempt mismatch")
        if self.record_fingerprint != record_fingerprint(self):
            raise ValueError("record fingerprint mismatch")
        if len(_canonical(self)) > MAX_RECORD_BYTES:
            raise ValueError("live intake record exceeds 128 KiB")
        return self


AgentLiveIntakeRecordV1 = AgentLiveIntakeReceiptV1


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _canonical(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def _fingerprint(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + (_canonical(value) if not isinstance(value, bytes) else value)).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest)


def _without(value: Any, field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


def attempt_fingerprint(value: Any) -> FingerprintV1:
    raw = _without(value, "attempt_fingerprint")
    return _fingerprint("atlas:live-delivery-send-attempt:v1", {"operator_id": raw["operator_id"], "attempt": raw})


def envelope_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint("atlas:agent-live-intake-envelope:v1", _without(value, "envelope_fingerprint"))


def admission_fingerprint(value: Any) -> FingerprintV1:
    raw = _without(value, "admission_fingerprint")
    raw = {
        "schema": "agent-live-intake-admission-v1",
        "status": "admitted_for_evidence_only",
        "statement": "agent_admitted_authenticated_live_delivery_evidence_only",
        "delivery_received": True,
        "evidence_admission_granted": True,
        **_false_authority(),
        **raw,
    }
    return _fingerprint("atlas:agent-live-intake-admission:v1", {"operator_id": raw["operator_id"], "admission": raw})


def acknowledgement_fingerprint(value: Any) -> FingerprintV1:
    raw = _without(value, "acknowledgement_fingerprint")
    raw = {
        "schema": "agent-live-intake-acknowledgement-v1",
        "status": "admitted_for_evidence_only",
        "provenance": "authenticated_core_live_intake_evidence_only",
        **_false_authority(),
        **raw,
    }
    return _fingerprint("atlas:agent-live-intake-acknowledgement:v1", raw)


def record_fingerprint(value: Any) -> FingerprintV1:
    raw = _without(value, "record_fingerprint")
    raw = {
        "schema": "agent-live-intake-record-v1",
        "authenticated_principal": AUTHENTICATED_CORE_PRINCIPAL,
        "permission": AUTHENTICATED_CORE_PERMISSION,
        "lifecycle_at_creation": "admitted_for_evidence_only",
        "default_enabled": False,
        "evidence_only": True,
        **_false_authority(),
        **raw,
    }
    return _fingerprint("atlas:agent-live-intake-record:v1", raw)


def audit_evidence_fingerprint(value: Any) -> FingerprintV1:
    raw = _without(value, "evidence_fingerprint")
    raw = {
        "schema": "agent-live-intake-audit-evidence-v1",
        "authenticated_principal": AUTHENTICATED_CORE_PRINCIPAL,
        "permission": AUTHENTICATED_CORE_PERMISSION,
        "outcome": "admitted_for_evidence_only",
        "default_enabled": False,
        "evidence_only": True,
        **_false_authority(),
        **raw,
    }
    return _fingerprint("atlas:agent-live-intake-audit-evidence:v1", raw)


def _false_authority() -> dict[str, bool]:
    return {
        "execution_admission_granted": False,
        "execution_authorized": False,
        "installation_allowed": False,
        "worker_allowed": False,
        "workflow_allowed": False,
        "deployment_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }


def idempotency_key_fingerprint(operator_id: str, key: str) -> FingerprintV1:
    return _fingerprint("atlas:live-delivery-send-idempotency-key:v1", {"operator_id": operator_id, "key": key})


def request_body_fingerprint(value: bytes) -> FingerprintV1:
    return _fingerprint("atlas:live-delivery-send-request-body:v1", {"hex": value.hex()})


def linkage_fingerprint(value: AgentLiveIntakeLinkageV1) -> FingerprintV1:
    return _fingerprint("atlas:agent-live-intake-linkage:v1", value)


def operator_fingerprint(operator_id: str) -> FingerprintV1:
    return _fingerprint("atlas:agent-live-intake-operator:v1", operator_id)


def parse_envelope_json(payload: bytes | str) -> AgentLiveIntakeEnvelopeV1:
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > MAX_ENVELOPE_BYTES:
        raise StrictContractError("live intake envelope exceeds 128 KiB")

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise StrictContractError("duplicate JSON member")
            if unicodedata.normalize("NFC", key) != key:
                raise StrictContractError("non-canonical JSON member")
            result[key] = value
        return result

    try:
        decoded = json.loads(encoded, object_pairs_hook=closed_object, parse_constant=lambda _: (_ for _ in ()).throw(StrictContractError("non-finite number")))
        return AgentLiveIntakeEnvelopeV1.model_validate(decoded)
    except StrictContractError:
        raise
    except Exception as exc:
        raise StrictContractError("invalid live intake envelope") from exc


def validate_admission_input(envelope: AgentLiveIntakeEnvelopeV1, *, operator_id: str, received_at: str, endpoint_fingerprint_value: FingerprintV1) -> AgentLiveIntakeEnvelopeV1:
    if envelope.send_attempt.operator_id != operator_id:
        raise ValueError("operator ownership mismatch")
    if envelope.endpoint_fingerprint != endpoint_fingerprint_value:
        raise ValueError("server-owned endpoint mismatch")
    received = _instant(received_at)
    created, sent, expires = (_instant(envelope.send_attempt.created_at), _instant(envelope.intake_request.sent_at), _instant(envelope.send_attempt.expires_at))
    if not created <= sent <= received < expires or expires > created + timedelta(seconds=MAX_FRESHNESS_SECONDS):
        raise ValueError("live intake evidence is stale or expired")
    return envelope


def admission_lifecycle(admission: AgentLiveIntakeAdmissionV1, *, observed_at: str, available: bool = True) -> AgentLiveIntakeLifecycleV1:
    if not available:
        return "unavailable"
    if _instant(observed_at) >= _instant(admission.valid_until):
        return "expired"
    return "admitted_for_evidence_only"


__all__ = [name for name in globals() if name.startswith("AgentLiveIntake") or name.endswith("_fingerprint") or name in {"StrictContractError", "parse_envelope_json", "validate_admission_input", "admission_lifecycle"}]
