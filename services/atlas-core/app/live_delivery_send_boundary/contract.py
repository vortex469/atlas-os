"""Pure closed v0.31 live-send models; no I/O, route, service, or transport."""

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

from app.dormant_agent_intake_delivery_wiring.contract import (
    AgentInstallationIntakeAcknowledgementV1,
    AgentInstallationIntakeAdmissionV1,
    AgentInstallationIntakeRequestV1,
    AgentInstallationIntakeResultV1,
    CoreAgentIntakeDeliveryPreparationV1,
    DormantAgentIntakeEndpointV1,
    acknowledgement_fingerprint,
    admission_fingerprint,
    endpoint_fingerprint,
    preparation_fingerprint,
    request_fingerprint,
)
from app.installation_dispatch_handoff.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.operator_controlled_delivery_enablement.contract import (
    OperatorControlledDeliveryEnablementRecordV1,
    validate_enablement_record,
)

MAX_CREATE_BYTES = 2048
MAX_CONFIGURATION_BYTES = 16 * 1024
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 32 * 1024
MAX_TRANSPORT_ENVELOPE_BYTES = 96 * 1024
MAX_ATTEMPT_BYTES = 128 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_AUDIT_EVIDENCE_BYTES = 32 * 1024
MAX_FRESHNESS_SECONDS = 30
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class StrictContractError(ValueError):
    pass


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
    if (not value.isascii() or value != value.lower() or not 1 <= len(value) <= 253
            or value in {"localhost", "localhost.localdomain"} or value.endswith(".")
            or any(_DNS_LABEL.fullmatch(label) is None for label in value.split("."))):
        raise ValueError("invalid canonical internal DNS name")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError("IP literals are prohibited")


def _absolute_file(value: str) -> str:
    if (not value.isascii() or not 1 <= len(value.encode()) <= 4096 or "\x00" in value
            or value.startswith("~") or "$" in value or not value.startswith("/")
            or "//" in value):
        raise ValueError("invalid canonical absolute file path")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {".", ".."} for part in path.parts):
        raise ValueError("invalid canonical absolute file path")
    return value


OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]
CanonicalInternalDnsName = Annotated[str, AfterValidator(_dns_name)]
CanonicalAbsoluteFilePath = Annotated[str, AfterValidator(_absolute_file)]


class LiveDeliverySendCreateV1(ContractModel):
    schema: Literal["live-delivery-send-create-v1"] = "live-delivery-send-create-v1"
    enablement_id: CanonicalUuid4
    enablement_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def bounded(self):
        if len(_canonical(self)) > MAX_CREATE_BYTES:
            raise ValueError("live delivery send create exceeds 2 KiB")
        return self


class LiveDeliveryEndpointV1(ContractModel):
    scheme: Literal["https"] = "https"
    host: CanonicalInternalDnsName
    port: Annotated[int, AfterValidator(lambda value: _port(value))]
    path: Literal["/api/v1/internal/installation-intake"] = "/api/v1/internal/installation-intake"
    tls_server_name: CanonicalInternalDnsName
    ca_bundle_file: CanonicalAbsoluteFilePath
    connect_timeout_ms: Literal[1000] = 1000
    response_timeout_ms: Literal[5000] = 5000
    follow_redirects: Literal[False] = False
    proxy_allowed: Literal[False] = False
    forwarded_ingress_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_endpoint(self):
        if self.tls_server_name != self.host:
            raise ValueError("TLS server name must equal endpoint host")
        return self


class LiveDeliveryAuthenticationReferenceV1(ContractModel):
    scheme: Literal["Bearer"] = "Bearer"
    principal: Literal["atlas-core/install-intake-v1"] = "atlas-core/install-intake-v1"
    authorization: Literal["installation_intake:create"] = "installation_intake:create"
    credential_source: Literal["mode-0400-file"] = "mode-0400-file"
    credential_file: CanonicalAbsoluteFilePath
    required_file_mode: Literal["0400"] = "0400"
    maximum_credential_bytes: Literal[4096] = 4096


class LiveDeliveryTransportConfigurationV1(ContractModel):
    schema: Literal["live-delivery-transport-configuration-v1"] = "live-delivery-transport-configuration-v1"
    enabled: bool = False
    endpoint: LiveDeliveryEndpointV1
    authentication: LiveDeliveryAuthenticationReferenceV1
    maximum_request_bytes: Literal[65536] = 65536
    maximum_response_bytes: Literal[32768] = 32768
    maximum_redirects: Literal[0] = 0
    automatic_retries: Literal[0] = 0
    one_shot_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bounded(self):
        if len(_canonical(self)) > MAX_CONFIGURATION_BYTES:
            raise ValueError("live delivery configuration exceeds 16 KiB")
        return self


class LiveDeliverySendLinkageV1(ContractModel):
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


class LiveDeliverySendEvidenceV1(ContractModel):
    operator_id: OperatorId
    authenticated_operator_id: OperatorId
    authentication_verified: Literal[True] = True
    create_authorized: Literal[True] = True
    resolved_at: UtcSecond
    enablement: OperatorControlledDeliveryEnablementRecordV1
    preparation: CoreAgentIntakeDeliveryPreparationV1
    linkage: LiveDeliverySendLinkageV1
    source_was_owner_scoped_local_readers: Literal[True] = True
    current_revalidation_succeeded: Literal[True] = True
    existing_live_send: Literal[False] = False
    credential_material_loaded: Literal[False] = False
    network_attempted: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_owner_and_linkage(self):
        if self.operator_id != self.authenticated_operator_id:
            raise ValueError("ownership mismatch")
        validate_enablement_record(self.enablement, operator_id=self.operator_id)
        _validate_preparation(self.preparation, operator_id=self.operator_id)
        expected = {**self.enablement.linkage.model_dump(mode="json"),
                    "enablement_id": self.enablement.enablement_id,
                    "enablement_fingerprint": self.enablement.enablement_fingerprint.model_dump(mode="json")}
        if self.linkage.model_dump(mode="json") != expected:
            raise ValueError("complete v0.20-v0.30 linkage mismatch")
        if (self.preparation.delivery_preparation_id != self.enablement.delivery_preparation_id
                or self.preparation.preparation_fingerprint != self.enablement.preparation_fingerprint):
            raise ValueError("enablement preparation mismatch")
        return self


class LiveDeliveryTransportEnvelopeV1(ContractModel):
    schema: Literal["live-delivery-transport-envelope-v1"] = "live-delivery-transport-envelope-v1"
    send_attempt_id: CanonicalUuid4
    endpoint_fingerprint: FingerprintV1
    request: AgentInstallationIntakeRequestV1
    request_fingerprint: FingerprintV1
    request_body_fingerprint: FingerprintV1
    content_type: Literal["application/json"] = "application/json"
    content_length: int
    idempotency_key_fingerprint: FingerprintV1
    authorization_scheme: Literal["Bearer"] = "Bearer"
    credential_reference_only: Literal[True] = True
    credential_material_present: Literal[False] = False
    automatic_retries: Literal[0] = 0
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_envelope(self):
        body = _canonical(self.request)
        if self.request_fingerprint != request_fingerprint(self.request):
            raise ValueError("request fingerprint mismatch")
        if self.request_body_fingerprint != body_fingerprint(body):
            raise ValueError("request body fingerprint mismatch")
        if self.content_length != len(body) or not 0 < self.content_length <= MAX_REQUEST_BYTES:
            raise ValueError("request body length mismatch")
        if len(_canonical(self)) > MAX_TRANSPORT_ENVELOPE_BYTES:
            raise ValueError("transport envelope exceeds 96 KiB")
        return self


class LiveDeliverySendAttemptV1(ContractModel):
    schema: Literal["live-delivery-send-attempt-v1"] = "live-delivery-send-attempt-v1"
    send_attempt_id: CanonicalUuid4
    created_at: UtcSecond
    expires_at: UtcSecond
    operator_id: OperatorId
    linkage: LiveDeliverySendLinkageV1
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
    def exact_attempt(self):
        created, expires = _instant(self.created_at), _instant(self.expires_at)
        if not created < expires <= created + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("attempt exceeds inherited 30-second freshness")
        if len(_canonical(self)) > MAX_ATTEMPT_BYTES:
            raise ValueError("attempt exceeds 128 KiB")
        return self


LiveDeliverySendLifecycleV1 = Literal["reserved", "sending", "admitted_evidence_only", "rejected", "ambiguous", "expired", "unavailable"]


class LiveDeliverySendRedactedErrorV1(ContractModel):
    schema: Literal["live-delivery-send-error-v1"] = "live-delivery-send-error-v1"
    error_code: Literal["malformed", "unauthenticated", "unauthorized", "not_found", "not_current", "expired", "linkage_mismatch", "fingerprint_mismatch", "already_reserved", "rate_limited", "transport_unavailable", "agent_rejected", "response_invalid", "ambiguous", "unavailable"]
    safe_message: Literal["Live delivery send evidence is unavailable."] = "Live delivery send evidence is unavailable."
    correlation_id: CorrelationId
    send_attempt_id: CanonicalUuid4 | None = None
    attempt_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True
    retryable: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class LiveDeliverySendReceiptV1(ContractModel):
    schema: Literal["live-delivery-send-receipt-v1"] = "live-delivery-send-receipt-v1"
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    completed_at: UtcSecond
    lifecycle: Literal["admitted_evidence_only", "rejected", "ambiguous"]
    http_status_class: Literal["2xx", "4xx", "5xx", "none"]
    response_fingerprint: FingerprintV1 | None
    admission_fingerprint: FingerprintV1 | None
    acknowledgement_fingerprint: FingerprintV1 | None
    agent_audit_evidence_fingerprint: FingerprintV1 | None
    redacted_error: LiveDeliverySendRedactedErrorV1 | None
    agent_contacted: Literal[True] = True
    evidence_admitted: bool
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    receipt_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_receipt(self):
        evidence = (self.response_fingerprint, self.admission_fingerprint,
                    self.acknowledgement_fingerprint, self.agent_audit_evidence_fingerprint)
        admitted = self.lifecycle == "admitted_evidence_only"
        if admitted != (self.evidence_admitted and all(value is not None for value in evidence)):
            raise ValueError("receipt admission evidence mismatch")
        if admitted and (self.http_status_class != "2xx" or self.redacted_error is not None):
            raise ValueError("admitted receipt transport mismatch")
        if self.lifecycle == "ambiguous" and (self.evidence_admitted
                or any(value is not None for value in evidence) or self.redacted_error is None
                or self.redacted_error.error_code != "ambiguous"):
            raise ValueError("ambiguous receipt must contain no affirmative evidence")
        if self.lifecycle == "rejected" and (self.evidence_admitted or self.redacted_error is None):
            raise ValueError("rejected receipt requires one redacted error")
        if self.receipt_fingerprint != receipt_fingerprint(self):
            raise ValueError("receipt fingerprint mismatch")
        if len(_canonical(self)) > MAX_RECEIPT_BYTES:
            raise ValueError("receipt exceeds 64 KiB")
        return self


class LiveDeliverySendStatusV1(ContractModel):
    schema: Literal["live-delivery-send-status-v1"] = "live-delivery-send-status-v1"
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    observed_at: UtcSecond
    lifecycle: LiveDeliverySendLifecycleV1
    evidence_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class LiveDeliverySendIdempotencyV1(ContractModel):
    operator_id: OperatorId
    operation: Literal["live_delivery_send:create"] = "live_delivery_send:create"
    key: IdempotencyKey
    enablement_id: CanonicalUuid4
    enablement_fingerprint: FingerprintV1
    preflight_id: CanonicalUuid4
    preparation_id: CanonicalUuid4
    request_id: CanonicalUuid4
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    reservation_before_io: Literal[True] = True
    reservation_permanent: Literal[True] = True
    exact_retry_zero_io: Literal[True] = True
    ambiguity_terminal: Literal[True] = True
    expiry_releases_reservation: Literal[False] = False
    replay_allowed: Literal[False] = False


class LiveDeliverySendAuditEvidenceV1(ContractModel):
    schema: Literal["live-delivery-send-audit-evidence-v1"] = "live-delivery-send-audit-evidence-v1"
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    correlation_id: CorrelationId
    idempotency_key_fingerprint: FingerprintV1
    endpoint_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    receipt_fingerprint: FingerprintV1 | None
    created_at: UtcSecond
    completed_at: UtcSecond | None
    lifecycle: LiveDeliverySendLifecycleV1
    agent_disposition: Literal["not_contacted", "admitted_for_evidence_only", "rejected", "unknown"]
    evidence_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_audit(self):
        terminal = self.lifecycle in {"admitted_evidence_only", "rejected", "ambiguous"}
        if terminal != (self.completed_at is not None):
            raise ValueError("audit lifecycle and completion disagree")
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        if len(_canonical(self)) > MAX_AUDIT_EVIDENCE_BYTES:
            raise ValueError("audit evidence exceeds 32 KiB")
        return self


class LiveDeliverySendOperationResultV1(ContractModel):
    disposition: Literal["reserved", "exact_replay", "rejected", "unavailable"]
    attempt: LiveDeliverySendAttemptV1 | None
    receipt: LiveDeliverySendReceiptV1 | None
    status: LiveDeliverySendStatusV1 | None
    audit_evidence: LiveDeliverySendAuditEvidenceV1 | None
    error: LiveDeliverySendRedactedErrorV1 | None
    default_enabled: Literal[False] = False
    network_attempted: Literal[False] = False
    one_shot_only: Literal[True] = True
    execution_attempted: Literal[False] = False
    installation_attempted: Literal[False] = False
    worker_attempted: Literal[False] = False
    workflow_attempted: Literal[False] = False
    deployment_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self):
        success = self.disposition in {"reserved", "exact_replay"}
        if success != (
            self.attempt is not None
            and self.status is not None
            and self.audit_evidence is not None
            and self.error is None
        ):
            raise ValueError("operation disposition and values disagree")
        if success and self.receipt is not None:
            raise ValueError("P2 reservation result cannot contain a receipt")
        if not success and any(
            value is not None
            for value in (self.attempt, self.receipt, self.status, self.audit_evidence)
        ):
            raise ValueError("failed operation cannot contain evidence")
        if not success and self.error is None:
            raise ValueError("failed operation requires one redacted error")
        return self


class LiveDeliverySendTransportResultV1(ContractModel):
    """Closed outcome of the single P3 transport opportunity."""

    disposition: Literal[
        "admitted_evidence_only", "rejected", "ambiguous", "exact_replay", "unavailable"
    ]
    attempt: LiveDeliverySendAttemptV1 | None
    receipt: LiveDeliverySendReceiptV1 | None
    agent_result: AgentInstallationIntakeResultV1 | None
    acknowledgement: AgentInstallationIntakeAcknowledgementV1 | None
    audit_evidence: LiveDeliverySendAuditEvidenceV1 | None
    error: LiveDeliverySendRedactedErrorV1 | None
    default_enabled: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0
    execution_attempted: Literal[False] = False
    installation_attempted: Literal[False] = False
    worker_attempted: Literal[False] = False
    workflow_attempted: Literal[False] = False
    deployment_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_transport_result(self):
        has_evidence = self.attempt is not None and self.audit_evidence is not None
        terminal = self.receipt is not None
        if terminal != has_evidence:
            raise ValueError("transport disposition and terminal evidence disagree")
        if self.disposition in {"admitted_evidence_only", "ambiguous", "exact_replay"} and not terminal:
            raise ValueError("transport disposition requires terminal evidence")
        if not terminal and (
            any(value is not None for value in (
                self.attempt, self.receipt, self.agent_result,
                self.acknowledgement, self.audit_evidence,
            )) or self.error is None
        ):
            raise ValueError("precondition result must be redacted")
        admitted = self.receipt is not None and self.receipt.lifecycle == "admitted_evidence_only"
        if admitted != (self.agent_result is not None and self.acknowledgement is not None):
            raise ValueError("admitted transport evidence is incomplete")
        if terminal and self.error != self.receipt.redacted_error:
            raise ValueError("transport and receipt errors disagree")
        return self


def create_send_attempt(create, *, evidence, configuration, send_attempt_id: str,
                        created_at: str, idempotency_key: str):
    exact_create = LiveDeliverySendCreateV1.model_validate(create.model_dump(mode="python"))
    exact = LiveDeliverySendEvidenceV1.model_validate(evidence.model_dump(mode="python"))
    config = LiveDeliveryTransportConfigurationV1.model_validate(configuration.model_dump(mode="python"))
    if not config.enabled:
        raise ValueError("live delivery send is default-disabled")
    pairs = ((exact_create.enablement_id, exact.enablement.enablement_id),
             (exact_create.enablement_fingerprint, exact.enablement.enablement_fingerprint),
             (exact_create.delivery_preparation_id, exact.preparation.delivery_preparation_id),
             (exact_create.preparation_fingerprint, exact.preparation.preparation_fingerprint))
    if any(left != right for left, right in pairs):
        raise ValueError("send create linkage mismatch")
    now, resolved = _instant(created_at), _instant(exact.resolved_at)
    enabled, expires = _instant(exact.enablement.enabled_at), _instant(exact.enablement.expires_at)
    if resolved != now or not enabled <= now < expires:
        raise ValueError("enablement is stale or expired")
    if expires > enabled + timedelta(seconds=MAX_FRESHNESS_SECONDS):
        raise ValueError("enablement exceeds inherited 30-second freshness")
    endpoint_fp = endpoint_fingerprint(DormantAgentIntakeEndpointV1.model_validate(config.endpoint.model_dump(mode="python")))
    if exact.preparation.endpoint_fingerprint != endpoint_fp:
        raise ValueError("endpoint fingerprint mismatch")
    request, body = exact.preparation.request, _canonical(exact.preparation.request)
    key_fp = idempotency_key_fingerprint(operator_id=exact.operator_id, idempotency_key=idempotency_key)
    envelope = LiveDeliveryTransportEnvelopeV1(
        send_attempt_id=send_attempt_id, endpoint_fingerprint=endpoint_fp, request=request,
        request_fingerprint=request.request_fingerprint, request_body_fingerprint=body_fingerprint(body),
        content_length=len(body), idempotency_key_fingerprint=key_fp)
    raw: dict[str, Any] = {
        "schema": "live-delivery-send-attempt-v1", "send_attempt_id": send_attempt_id,
        "created_at": _format(now), "expires_at": exact.enablement.expires_at,
        "operator_id": exact.operator_id, "linkage": exact.linkage.model_dump(mode="json"),
        "endpoint_fingerprint": endpoint_fp.model_dump(mode="json"),
        "request_fingerprint": request.request_fingerprint.model_dump(mode="json"),
        "request_body_fingerprint": body_fingerprint(body).model_dump(mode="json"),
        "lifecycle_at_creation": "reserved", "default_enabled": False,
        "network_attempted": False, "evidence_only": True, "execution_requested": False,
        "installation_requested": False, "mutation_requested": False, "replay_allowed": False}
    raw["attempt_fingerprint"] = attempt_fingerprint(raw, operator_id=exact.operator_id).model_dump(mode="json")
    return LiveDeliverySendAttemptV1.model_validate(raw), envelope


def validate_send_attempt(attempt, *, operator_id: str):
    exact = LiveDeliverySendAttemptV1.model_validate(attempt.model_dump(mode="python"))
    if exact.operator_id != _identity(operator_id):
        raise ValueError("ownership mismatch")
    if exact.attempt_fingerprint != attempt_fingerprint(exact, operator_id=operator_id):
        raise ValueError("attempt fingerprint mismatch")
    return exact


def send_lifecycle(attempt, *, now: str, receipt=None, send_started: bool = False,
                   process_lost: bool = False, current_revalidation_succeeded: bool = True):
    observed = _instant(now)
    if observed < _instant(attempt.created_at):
        raise ValueError("lifecycle instant precedes reservation")
    if receipt is not None:
        if receipt.send_attempt_id != attempt.send_attempt_id:
            raise ValueError("receipt attempt mismatch")
        return receipt.lifecycle
    if process_lost or (send_started and observed >= _instant(attempt.expires_at)):
        return "ambiguous"
    if not current_revalidation_succeeded:
        return "unavailable"
    if observed >= _instant(attempt.expires_at):
        return "expired"
    return "sending" if send_started else "reserved"


def attempt_fingerprint(value, *, operator_id: str) -> FingerprintV1:
    raw = _raw(value); raw.pop("attempt_fingerprint", None)
    return _fingerprint("atlas:live-delivery-send-attempt:v1", {"operator_id": _identity(operator_id), "attempt": raw})


def receipt_fingerprint(value) -> FingerprintV1:
    raw = _raw(value); raw.pop("receipt_fingerprint", None)
    return _fingerprint("atlas:live-delivery-send-receipt:v1", raw)


def audit_evidence_fingerprint(value) -> FingerprintV1:
    raw = _raw(value); raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:live-delivery-send-audit-evidence:v1", raw)


def body_fingerprint(value: bytes) -> FingerprintV1:
    return _fingerprint("atlas:live-delivery-send-request-body:v1", {"hex": value.hex()})


def canonical_agent_request(value) -> bytes:
    exact = AgentInstallationIntakeRequestV1.model_validate(
        value.model_dump(mode="python")
    )
    return _canonical(exact)


def idempotency_key_fingerprint(*, operator_id: str, idempotency_key: str) -> FingerprintV1:
    return _fingerprint("atlas:live-delivery-send-idempotency-key:v1",
                        {"operator_id": _identity(operator_id), "key": _visible_ascii(idempotency_key)})


def agent_result_fingerprint(value) -> FingerprintV1:
    return _fingerprint("atlas:live-delivery-agent-result:v1", _raw(value))


def agent_audit_evidence_fingerprint(admission) -> FingerprintV1:
    exact = AgentInstallationIntakeAdmissionV1.model_validate(
        admission.model_dump(mode="python")
    )
    raw = {
        "schema": "agent-installation-intake-audit-evidence-v1",
        "admission_id": exact.admission_id,
        "admission_fingerprint": exact.admission_fingerprint.model_dump(mode="json"),
        "intake_request_id": exact.intake_request_id,
        "delivery_attempt_id": exact.delivery_attempt_id,
        "request_fingerprint": exact.source.request_fingerprint.model_dump(mode="json"),
        "dispatch_envelope_id": exact.source.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": exact.source.dispatch_envelope_fingerprint.model_dump(mode="json"),
        "prior_evidence": exact.prior_evidence.model_dump(mode="json"),
        "received_at": exact.received_at,
        "valid_until": exact.valid_until,
        "lifecycle": "admitted",
        "status": "admitted_for_evidence_only",
        "provenance": "authenticated_core_intake_evidence_only",
        "default_enabled": False,
        "evidence_only": True,
        "delivery_received": True,
        "evidence_admission_granted": True,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    return _fingerprint("atlas:agent-installation-intake-audit-evidence:v1", raw)


def parse_agent_result_json(payload: bytes) -> AgentInstallationIntakeResultV1:
    if not payload or len(payload) > MAX_RESPONSE_BYTES:
        raise StrictContractError("agent response is outside its bound")
    try:
        value = json.loads(payload, object_pairs_hook=_no_duplicates)
        return AgentInstallationIntakeResultV1.model_validate(value)
    except StrictContractError:
        raise
    except Exception as exc:
        raise StrictContractError("invalid agent response") from exc


def validate_agent_result(*, result, delivery_preparation_id: str, request,
                          operator_id: str, validated_at: str):
    exact = AgentInstallationIntakeResultV1.model_validate(
        result.model_dump(mode="python")
    )
    admitted = exact.outcome == "admitted_for_evidence_only"
    admission = exact.admission
    acknowledgement = None
    admission_fp = None
    if admitted:
        if admission is None:
            raise ValueError("missing admission")
        admission_fp = admission_fingerprint(operator_id=operator_id, admission=admission)
        acknowledgement_raw = {
            "schema": "agent-installation-intake-acknowledgement-v1",
            "admission_id": admission.admission_id,
            "admission_fingerprint": admission_fp.model_dump(mode="json"),
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
        acknowledgement_raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(
            acknowledgement_raw
        ).model_dump(mode="json")
        acknowledgement = AgentInstallationIntakeAcknowledgementV1.model_validate(
            acknowledgement_raw
        )
    exact_request = AgentInstallationIntakeRequestV1.model_validate(
        request.model_dump(mode="python")
    )
    _identity(operator_id)
    _identity(delivery_preparation_id)
    _instant(validated_at)
    if exact.intake_request_id not in {None, exact_request.intake_request_id}:
        raise ValueError("response request identity mismatch")
    if admission is not None and (
        admission.intake_request_id != exact_request.intake_request_id
        or admission.delivery_attempt_id != exact_request.delivery_attempt_id
        or admission.source.request_fingerprint != exact_request.request_fingerprint
        or admission.source.dispatch_envelope_id
        != exact_request.envelope.dispatch_envelope_id
        or admission.source.dispatch_envelope_fingerprint
        != exact_request.envelope.dispatch_envelope_fingerprint
        or admission.linkage != exact_request.envelope.linkage
        or admission.prior_evidence != exact_request.prior_evidence
        or admission.valid_until != exact_request.expires_at
        or admission.admission_fingerprint != admission_fp
    ):
        raise ValueError("admission linkage or fingerprint mismatch")
    return exact, acknowledgement


def parse_create_json(payload: str | bytes):
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("live delivery send create exceeds 2 KiB")
    try:
        return LiveDeliverySendCreateV1.model_validate(json.loads(raw, object_pairs_hook=_no_duplicates))
    except StrictContractError:
        raise
    except Exception as exc:
        raise StrictContractError("invalid live delivery send create") from exc


def _validate_preparation(value, *, operator_id: str) -> None:
    if value.request.operator_assertion.operator_id != operator_id:
        raise ValueError("preparation ownership mismatch")
    if value.request.request_fingerprint != request_fingerprint(value.request):
        raise ValueError("request fingerprint mismatch")
    if value.preparation_fingerprint != preparation_fingerprint(operator_id=operator_id, preparation=value):
        raise ValueError("preparation fingerprint mismatch")


def _port(value: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= 65535:
        raise ValueError("invalid endpoint port")
    return value


def _no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise StrictContractError("duplicate JSON member")
        value[key] = item
    return value


def _raw(value):
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)


def _canonical(value) -> bytes:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return unicodedata.normalize("NFC", json.dumps(raw, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))).encode()


def _fingerprint(domain: str, value) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest)


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0) or parsed.microsecond:
        raise ValueError("timestamp must be whole-second UTC")
    return parsed.astimezone(UTC)


def _format(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [name for name in globals() if name.startswith("LiveDelivery")]
__all__ += [
    "AgentInstallationIntakeAcknowledgementV1",
    "AgentInstallationIntakeAdmissionV1",
    "AgentInstallationIntakeRequestV1",
    "AgentInstallationIntakeResultV1",
    "StrictContractError",
    "agent_audit_evidence_fingerprint",
    "agent_result_fingerprint",
    "attempt_fingerprint",
    "audit_evidence_fingerprint",
    "body_fingerprint",
    "canonical_agent_request",
    "create_send_attempt",
    "idempotency_key_fingerprint",
    "parse_agent_result_json",
    "parse_create_json",
    "receipt_fingerprint",
    "send_lifecycle",
    "validate_agent_result",
    "validate_send_attempt",
]
