"""Pure immutable models for dormant Core-to-Agent delivery wiring v1.

This module performs no I/O and has no send capability.  Every value is
preparation or injected-response evidence and grants no execution or mutation
authority.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    model_validator,
)

from app.installation_dispatch_handoff.contract import (
    FingerprintV1,
    InstallationDispatchEnvelopeV1,
    InstallationDispatchLinkageV1,
    dispatch_envelope_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 1024
MAX_CONFIGURATION_BYTES = 16 * 1024
MAX_REQUEST_BYTES = 64 * 1024
MAX_PREPARATION_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class StrictContractError(ValueError):
    """A value is outside the frozen closed contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid canonical identity")
    return value


def _visible_ascii(value: str) -> str:
    if not value.isascii() or not 1 <= len(value.encode()) <= 128 or any(
        not 0x21 <= ord(character) <= 0x7E for character in value
    ):
        raise ValueError("idempotency key is out of bounds")
    return value


def _dns_name(value: str) -> str:
    if (
        not value.isascii()
        or value != value.lower()
        or not 1 <= len(value) <= 253
        or value in {"localhost", "localhost.localdomain"}
        or value.endswith(".")
        or any(_DNS_LABEL.fullmatch(label) is None for label in value.split("."))
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


CanonicalOperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]
CanonicalInternalDnsName = Annotated[str, AfterValidator(_dns_name)]
CanonicalAbsoluteFilePath = Annotated[str, AfterValidator(_absolute_file)]


def _tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


EmptyArray = Annotated[tuple[()], BeforeValidator(_tuple)]


def _port(value: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= 65535:
        raise ValueError("invalid endpoint port")
    return value


class DormantAgentIntakeEndpointV1(ContractModel):
    scheme: Literal["https"] = "https"
    host: CanonicalInternalDnsName
    port: Annotated[int, AfterValidator(lambda value: _port(value))]
    path: Literal["/api/v1/internal/installation-intake"] = (
        "/api/v1/internal/installation-intake"
    )
    tls_server_name: CanonicalInternalDnsName
    ca_bundle_file: CanonicalAbsoluteFilePath
    connect_timeout_ms: Literal[1000] = 1000
    response_timeout_ms: Literal[5000] = 5000
    follow_redirects: Literal[False] = False
    proxy_allowed: Literal[False] = False
    forwarded_ingress_allowed: Literal[False] = False

    @model_validator(mode="after")
    def matching_server_name(self) -> DormantAgentIntakeEndpointV1:
        if self.tls_server_name != self.host:
            raise ValueError("TLS server name must equal endpoint host")
        return self

class DormantAgentIntakeAuthenticationReferenceV1(ContractModel):
    scheme: Literal["Bearer"] = "Bearer"
    principal: Literal["atlas-core/install-intake-v1"] = (
        "atlas-core/install-intake-v1"
    )
    authorization: Literal["installation_intake:create"] = (
        "installation_intake:create"
    )
    credential_source: Literal["mode-0400-file"] = "mode-0400-file"
    credential_file: CanonicalAbsoluteFilePath
    required_file_mode: Literal["0400"] = "0400"
    maximum_credential_bytes: Literal[4096] = 4096


class DormantAgentIntakeDeliveryConfigurationV1(ContractModel):
    schema: Literal["dormant-agent-intake-delivery-configuration-v1"] = (
        "dormant-agent-intake-delivery-configuration-v1"
    )
    enabled: Literal[False] = False
    mode: Literal["prepare-and-validate-only"] = "prepare-and-validate-only"
    endpoint: DormantAgentIntakeEndpointV1
    authentication: DormantAgentIntakeAuthenticationReferenceV1
    agent_route_registered: Literal[False] = False
    production_transport_registered: Literal[False] = False
    production_delivery_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class CoreAgentIntakeDeliveryCreateV1(ContractModel):
    schema: Literal["core-agent-intake-delivery-create-v1"] = (
        "core-agent-intake-delivery-create-v1"
    )
    dispatch_envelope_id: CanonicalUuid4
    intake_record_id: CanonicalUuid4
    simulated_delivery_id: CanonicalUuid4
    simulated_acknowledgement_id: CanonicalUuid4

    @model_validator(mode="after")
    def bounded_create(self) -> CoreAgentIntakeDeliveryCreateV1:
        if len(_canonical(self)) > MAX_CREATE_BYTES:
            raise ValueError("delivery create exceeds 1 KiB")
        return self


class AgentInstallationIntakeRecipientV1(ContractModel):
    service: Literal["atlas-agent"] = "atlas-agent"
    intake_contract: Literal["agent-installation-intake-v1"] = (
        "agent-installation-intake-v1"
    )


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
        if self.request_fingerprint != request_fingerprint(self):
            raise ValueError("request fingerprint mismatch")
        if len(_canonical(self)) > MAX_REQUEST_BYTES:
            raise ValueError("real intake request exceeds 64 KiB")
        return self


class CoreAgentIntakeDeliveryPreparationSourceV1(ContractModel):
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
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


class CoreAgentIntakeDeliveryEvidenceContextV1(ContractModel):
    """Injected owner-scoped evidence; it is never caller or network input."""

    operator_id: CanonicalOperatorId
    envelope: InstallationDispatchEnvelopeV1
    simulation_request_id: CanonicalUuid4
    source: CoreAgentIntakeDeliveryPreparationSourceV1
    intake_record_observed_at: UtcSecond
    simulated_acknowledged_at: UtcSecond
    existing_admission_id: CanonicalUuid4 | None = None
    existing_admission_fingerprint: FingerprintV1 | None = None
    existing_acknowledgement_fingerprint: FingerprintV1 | None = None
    default_enabled: Literal[False] = False
    production_delivery_observed: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_context(self) -> CoreAgentIntakeDeliveryEvidenceContextV1:
        existing = (
            self.existing_admission_id,
            self.existing_admission_fingerprint,
            self.existing_acknowledgement_fingerprint,
        )
        if any(value is not None for value in existing) and not all(
            value is not None for value in existing
        ):
            raise ValueError("existing v0.27 evidence must be complete")
        if (
            self.source.dispatch_envelope_id != self.envelope.dispatch_envelope_id
            or self.source.dispatch_envelope_fingerprint
            != self.envelope.dispatch_envelope_fingerprint
        ):
            raise ValueError("evidence context envelope mismatch")
        return self


class CoreAgentIntakeDeliveryPreparationV1(ContractModel):
    schema: Literal["core-agent-intake-delivery-preparation-v1"] = (
        "core-agent-intake-delivery-preparation-v1"
    )
    delivery_preparation_id: CanonicalUuid4
    prepared_at: UtcSecond
    valid_until: UtcSecond
    endpoint_fingerprint: FingerprintV1
    request: AgentInstallationIntakeRequestV1
    source: CoreAgentIntakeDeliveryPreparationSourceV1
    lifecycle_at_preparation: Literal["prepared_dormant"] = "prepared_dormant"
    status: Literal["not_sent"] = "not_sent"
    statement: Literal["core_prepared_agent_intake_delivery_wiring_only"] = (
        "core_prepared_agent_intake_delivery_wiring_only"
    )
    default_enabled: Literal[False] = False
    network_attempted: Literal[False] = False
    delivery_authorized: Literal[False] = False
    delivery_received: Literal[False] = False
    evidence_admission_granted: Literal[False] = False
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    preparation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_preparation(self) -> CoreAgentIntakeDeliveryPreparationV1:
        request = self.request
        source = self.source
        if self.prepared_at != request.sent_at or self.valid_until != request.expires_at:
            raise ValueError("preparation and request time mismatch")
        if source.dispatch_envelope_id != request.envelope.dispatch_envelope_id:
            raise ValueError("dispatch envelope ID mismatch")
        if source.dispatch_envelope_fingerprint != request.envelope.dispatch_envelope_fingerprint:
            raise ValueError("dispatch envelope fingerprint mismatch")
        prior = request.prior_evidence
        if (
            source.intake_record_id != prior.intake_simulation.intake_record_id
            or source.intake_record_fingerprint
            != prior.intake_simulation.intake_record_fingerprint
            or source.simulated_delivery_id
            != prior.simulated_delivery.simulated_delivery_id
            or source.simulated_delivery_fingerprint
            != prior.simulated_delivery.simulated_delivery_fingerprint
            or source.delivery_record_fingerprint
            != prior.simulated_delivery.delivery_record_fingerprint
            or source.simulated_acknowledgement_id
            != prior.simulated_delivery.acknowledgement_id
            or source.simulated_acknowledgement_fingerprint
            != prior.simulated_delivery.acknowledgement_fingerprint
        ):
            raise ValueError("prior evidence linkage mismatch")
        if len(_canonical(self)) > MAX_PREPARATION_BYTES:
            raise ValueError("preparation exceeds 96 KiB")
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
    def bounded_admission(self) -> AgentInstallationIntakeAdmissionV1:
        if not _instant(self.received_at) < _instant(self.valid_until):
            raise ValueError("admission is not current")
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
            raise ValueError("rejected result must contain one sanitized reason")
        if self.reason_code in ("unauthenticated", "unauthorized") and self.intake_request_id:
            raise ValueError("authentication rejection must redact request ID")
        return self


class AgentInstallationIntakeAcknowledgementV1(ContractModel):
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
    def exact_fingerprint(self) -> AgentInstallationIntakeAcknowledgementV1:
        if self.acknowledgement_fingerprint != acknowledgement_fingerprint(self):
            raise ValueError("acknowledgement fingerprint mismatch")
        return self


DeliveryValidationCodeV1 = Literal[
    "malformed",
    "request_mismatch",
    "delivery_attempt_mismatch",
    "ownership_mismatch",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "freshness_mismatch",
    "authority_mismatch",
    "replay_conflict",
    "unavailable",
]


class CoreAgentIntakeDeliveryResponseValidationV1(ContractModel):
    schema: Literal["core-agent-intake-delivery-response-validation-v1"] = (
        "core-agent-intake-delivery-response-validation-v1"
    )
    delivery_preparation_id: CanonicalUuid4
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    validated_at: UtcSecond
    outcome: Literal["valid_admission_evidence", "valid_rejection", "invalid"]
    agent_result: AgentInstallationIntakeResultV1 | None
    admission_fingerprint: FingerprintV1 | None
    acknowledgement_fingerprint: FingerprintV1 | None
    reason_code: DeliveryValidationCodeV1 | None
    source_was_injected: Literal[True] = True
    production_delivery_observed: Literal[False] = False
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    validation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_validation(self) -> CoreAgentIntakeDeliveryResponseValidationV1:
        admitted = self.outcome == "valid_admission_evidence"
        rejected = self.outcome == "valid_rejection"
        if admitted and not (
            self.agent_result
            and self.agent_result.outcome == "admitted_for_evidence_only"
            and self.admission_fingerprint
            and self.acknowledgement_fingerprint
            and self.reason_code is None
        ):
            raise ValueError("admission validation is incomplete")
        if rejected and not (
            self.agent_result
            and self.agent_result.outcome == "rejected"
            and self.admission_fingerprint is None
            and self.acknowledgement_fingerprint is None
            and self.reason_code is None
        ):
            raise ValueError("rejection validation is inconsistent")
        if self.outcome == "invalid" and not (
            self.agent_result is None
            and self.admission_fingerprint is None
            and self.acknowledgement_fingerprint is None
            and self.reason_code is not None
        ):
            raise ValueError("invalid validation must be redacted")
        return self


class CoreAgentIntakeDeliveryIdempotencyV1(ContractModel):
    operator_id: CanonicalOperatorId
    operation: Literal["core_agent_intake_delivery:prepare"] = (
        "core_agent_intake_delivery:prepare"
    )
    key: IdempotencyKey
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    delivery_attempt_id: CanonicalUuid4
    source: CoreAgentIntakeDeliveryPreparationSourceV1
    reservation_permanent: Literal[True] = True
    exact_retry_only: Literal[True] = True
    replay_allowed: Literal[False] = False


class CoreAgentIntakeDeliveryAuditEvidenceV1(ContractModel):
    schema: Literal["core-agent-intake-delivery-audit-evidence-v1"] = (
        "core-agent-intake-delivery-audit-evidence-v1"
    )
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    delivery_attempt_id: CanonicalUuid4
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    prepared_at: UtcSecond
    valid_until: UtcSecond
    validated_at: UtcSecond
    lifecycle: Literal["disabled", "prepared_dormant", "expired", "unavailable"]
    status: Literal["not_sent"] = "not_sent"
    provenance: Literal["core_dormant_agent_intake_delivery_wiring_only"] = (
        "core_dormant_agent_intake_delivery_wiring_only"
    )
    default_enabled: Literal[False] = False
    network_attempted: Literal[False] = False
    delivery_authorized: Literal[False] = False
    delivery_received: Literal[False] = False
    evidence_admission_granted: Literal[False] = False
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_fingerprint(self) -> CoreAgentIntakeDeliveryAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        return self


class CoreAgentIntakeDeliveryRedactedErrorV1(ContractModel):
    schema: Literal["core-agent-intake-delivery-error-v1"] = (
        "core-agent-intake-delivery-error-v1"
    )
    error_code: DeliveryValidationCodeV1
    correlation_id: CorrelationId
    delivery_preparation_id: CanonicalUuid4 | None = None
    preparation_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True


class CoreAgentIntakeDeliveryPreparationResultV1(ContractModel):
    disposition: Literal["prepared_dormant", "exact_replay", "rejected", "unavailable"]
    preparation: CoreAgentIntakeDeliveryPreparationV1 | None
    error: CoreAgentIntakeDeliveryRedactedErrorV1 | None
    audit_evidence: CoreAgentIntakeDeliveryAuditEvidenceV1 | None = None
    default_enabled: Literal[False] = False
    network_attempted: Literal[False] = False
    agent_invoked: Literal[False] = False
    execution_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self) -> CoreAgentIntakeDeliveryPreparationResultV1:
        success = self.disposition in ("prepared_dormant", "exact_replay")
        if success != (self.preparation is not None and self.error is None):
            raise ValueError("result disposition and values disagree")
        if not success and (self.preparation is not None or self.error is None):
            raise ValueError("failed result must contain one redacted error")
        return self


def validate_delivery_preparation(
    preparation: CoreAgentIntakeDeliveryPreparationV1,
    *,
    operator_id: str,
    configuration: DormantAgentIntakeDeliveryConfigurationV1,
    validated_at: str,
) -> Literal["disabled", "prepared_dormant", "expired"]:
    """Purely validate ownership, endpoint, linkage, and freshness."""
    exact = CoreAgentIntakeDeliveryPreparationV1.model_validate(
        preparation.model_dump(mode="python")
    )
    owner = _identity(operator_id)
    now = _instant(validated_at)
    if exact.endpoint_fingerprint != endpoint_fingerprint(configuration.endpoint):
        raise ValueError("endpoint fingerprint mismatch")
    if exact.request.envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(
        owner_id=owner, envelope=exact.request.envelope
    ):
        raise ValueError("ownership or dispatch envelope fingerprint mismatch")
    if exact.request.operator_assertion.operator_id != owner:
        raise ValueError("ownership mismatch")
    if exact.preparation_fingerprint != preparation_fingerprint(
        operator_id=owner, preparation=exact
    ):
        raise ValueError("preparation fingerprint mismatch")
    if now < _instant(exact.prepared_at):
        raise ValueError("validation time precedes preparation")
    if configuration.enabled is False:
        return "expired" if now >= _instant(exact.valid_until) else "disabled"
    raise ValueError("unsupported enabled configuration")


def preparation_lifecycle(
    preparation: CoreAgentIntakeDeliveryPreparationV1, *, now: str
) -> Literal["prepared_dormant", "expired"]:
    instant = _instant(now)
    if instant < _instant(preparation.prepared_at):
        raise ValueError("lifecycle instant precedes preparation")
    return "prepared_dormant" if instant < _instant(preparation.valid_until) else "expired"


def validate_delivery_response(
    validation: CoreAgentIntakeDeliveryResponseValidationV1,
    *,
    preparation: CoreAgentIntakeDeliveryPreparationV1,
    operator_id: str,
) -> CoreAgentIntakeDeliveryResponseValidationV1:
    """Validate one already-injected response without retrieving or sending it."""
    exact = CoreAgentIntakeDeliveryResponseValidationV1.model_validate(
        validation.model_dump(mode="python")
    )
    prepared = CoreAgentIntakeDeliveryPreparationV1.model_validate(
        preparation.model_dump(mode="python")
    )
    owner = _identity(operator_id)
    if (
        exact.delivery_preparation_id != prepared.delivery_preparation_id
        or exact.intake_request_id != prepared.request.intake_request_id
        or exact.delivery_attempt_id != prepared.request.delivery_attempt_id
    ):
        raise ValueError("response request identity mismatch")
    if exact.validation_fingerprint != response_validation_fingerprint(
        operator_id=owner, validation=exact
    ):
        raise ValueError("response validation fingerprint mismatch")
    result = exact.agent_result
    if exact.outcome == "valid_admission_evidence":
        if result is None or result.admission is None:
            raise ValueError("admission response is missing")
        admission = result.admission
        request = prepared.request
        if (
            admission.intake_request_id != request.intake_request_id
            or admission.delivery_attempt_id != request.delivery_attempt_id
            or admission.source.request_fingerprint != request.request_fingerprint
            or admission.source.dispatch_envelope_id
            != request.envelope.dispatch_envelope_id
            or admission.source.dispatch_envelope_fingerprint
            != request.envelope.dispatch_envelope_fingerprint
            or admission.linkage != request.envelope.linkage
            or admission.prior_evidence != request.prior_evidence
            or admission.valid_until != request.expires_at
        ):
            raise ValueError("admission linkage mismatch")
        expected_admission = admission_fingerprint(
            operator_id=owner, admission=admission
        )
        if admission.admission_fingerprint != expected_admission:
            raise ValueError("admission fingerprint mismatch")
        acknowledgement_raw: dict[str, Any] = {
            "schema": "agent-installation-intake-acknowledgement-v1",
            "admission_id": admission.admission_id,
            "admission_fingerprint": expected_admission.model_dump(mode="json"),
            "intake_request_id": admission.intake_request_id,
            "received_at": admission.received_at,
            "valid_until": admission.valid_until,
            "status": "admitted_for_evidence_only",
            "provenance": "authenticated_core_intake_evidence_only",
            "execution_admission_granted": False,
            "execution_authorized": False,
            "worker_allowed": False,
            "mutation_allowed": False,
            "replay_allowed": False,
        }
        expected_ack = acknowledgement_fingerprint(acknowledgement_raw)
        if (
            exact.admission_fingerprint != expected_admission
            or exact.acknowledgement_fingerprint != expected_ack
        ):
            raise ValueError("admission acknowledgement evidence mismatch")
    return exact


def request_fingerprint(
    request: AgentInstallationIntakeRequestV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _raw(request)
    raw.pop("request_fingerprint", None)
    return _fingerprint(
        "atlas:agent-installation-intake-request:v1",
        {
            "authenticated_core_principal": "atlas-core/install-intake-v1",
            "request": raw,
        },
    )


def admission_fingerprint(
    *, operator_id: str, admission: AgentInstallationIntakeAdmissionV1 | dict[str, Any]
) -> FingerprintV1:
    raw = _raw(admission)
    raw.pop("admission_fingerprint", None)
    return _fingerprint(
        "atlas:agent-installation-intake-admission:v1",
        {"operator_id": _identity(operator_id), "admission": raw},
    )


def acknowledgement_fingerprint(
    acknowledgement: AgentInstallationIntakeAcknowledgementV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _raw(acknowledgement)
    raw.pop("acknowledgement_fingerprint", None)
    return _fingerprint("atlas:agent-installation-intake-acknowledgement:v1", raw)


def endpoint_fingerprint(endpoint: DormantAgentIntakeEndpointV1) -> FingerprintV1:
    return _fingerprint(
        "atlas:dormant-agent-intake-endpoint:v1", endpoint.model_dump(mode="json")
    )


def preparation_fingerprint(
    *, operator_id: str, preparation: CoreAgentIntakeDeliveryPreparationV1 | dict[str, Any]
) -> FingerprintV1:
    raw = _raw(preparation)
    raw.pop("preparation_fingerprint", None)
    return _fingerprint(
        "atlas:core-agent-intake-delivery-preparation:v1",
        {"operator_id": _identity(operator_id), "preparation": raw},
    )


def response_validation_fingerprint(
    *,
    operator_id: str,
    validation: CoreAgentIntakeDeliveryResponseValidationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _raw(validation)
    raw.pop("validation_fingerprint", None)
    return _fingerprint(
        "atlas:core-agent-intake-delivery-response-validation:v1",
        {"operator_id": _identity(operator_id), "validation": raw},
    )


def audit_evidence_fingerprint(
    evidence: CoreAgentIntakeDeliveryAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _raw(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:core-agent-intake-delivery-audit-evidence:v1", raw)


def parse_delivery_create_json(payload: bytes | str) -> CoreAgentIntakeDeliveryCreateV1:
    return _parse(payload, CoreAgentIntakeDeliveryCreateV1, MAX_CREATE_BYTES)


def parse_delivery_configuration_json(
    payload: bytes | str,
) -> DormantAgentIntakeDeliveryConfigurationV1:
    """Parse injected dormant configuration without reading referenced files."""
    return _parse(
        payload,
        DormantAgentIntakeDeliveryConfigurationV1,
        MAX_CONFIGURATION_BYTES,
    )


def parse_delivery_response_json(
    payload: bytes | str,
) -> AgentInstallationIntakeResultV1:
    return _parse(payload, AgentInstallationIntakeResultV1, MAX_RESPONSE_BYTES)


def _parse(payload: bytes | str, model: type[ContractModel], maximum: int):
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > maximum:
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
        return model.model_validate(decoded)
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("malformed") from error


def _raw(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)


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
        if isinstance(item, int):
            return item
        if isinstance(item, float):
            raise TypeError("JSON floating point values are prohibited")
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
