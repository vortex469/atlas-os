"""Closed, immutable v0.33 inert-delivery receipt models and pure validation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.dormant_agent_intake_delivery_wiring.contract import (
    AgentInstallationIntakeRequestV1,
)
from app.dormant_agent_intake_delivery_wiring.contract import (
    request_fingerprint as intake_request_fingerprint,
)
from app.installation_dispatch_handoff.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.live_delivery_send_boundary.contract import (
    LiveDeliverySendAttemptV1,
    LiveDeliverySendLinkageV1,
    attempt_fingerprint,
)

MAX_FRESHNESS_SECONDS = 30
MAX_AGENT_REQUEST_BYTES = 64 * 1024
MAX_AGENT_ENVELOPE_BYTES = 128 * 1024
MAX_AGENT_RESPONSE_BYTES = 32 * 1024
MAX_REQUEST_BYTES = 160 * 1024
MAX_VERIFICATION_BYTES = 160 * 1024
MAX_RECEIPT_BYTES = 192 * 1024
MAX_AUDIT_BYTES = 64 * 1024
MAX_JSON_NESTING = 32
AGENT_PRINCIPAL = "atlas-core/install-intake-v1"
AGENT_PERMISSION = "installation_intake:create"
AGENT_PATH = "/api/v1/internal/installation-intake"

_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_VISIBLE_ASCII = re.compile(r"[\x21-\x7e]{1,128}")


class StrictContractError(ValueError):
    """Input was outside the closed v0.33 contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid canonical identity")
    return value


def _visible_ascii(value: str) -> str:
    if not value.isascii() or _VISIBLE_ASCII.fullmatch(value) is None:
        raise ValueError("idempotency key is out of bounds")
    return value


OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _canonical(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    _closed_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _closed_value(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_JSON_NESTING:
        raise ValueError("JSON nesting exceeds bound")
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise ValueError("strings must be NFC")
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _closed_value(key, depth=depth + 1)
            _closed_value(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _closed_value(item, depth=depth + 1)
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError("unsupported JSON value")


def _fingerprint(domain: str, value: Any) -> FingerprintV1:
    payload = value if isinstance(value, bytes) else _canonical(value)
    digest = hashlib.sha256(domain.encode() + b"\0" + payload).hexdigest()
    return FingerprintV1(
        algorithm="sha256",
        canonicalization="atlas-jcs-nfc-v1",
        value=digest,
    )


def _without(value: Any, field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


class _AuthorityFlags(ContractModel):
    evidence_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class AgentLiveIntakeEnvelopeCopyV1(_AuthorityFlags):
    """Exact Core-local copy of the frozen v0.32 wire envelope."""

    schema: Literal["agent-live-intake-envelope-v1"] = (
        "agent-live-intake-envelope-v1"
    )
    send_attempt: LiveDeliverySendAttemptV1
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
    envelope_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_envelope(self) -> AgentLiveIntakeEnvelopeCopyV1:
        request_body = _canonical(self.intake_request)
        if len(request_body) > MAX_AGENT_REQUEST_BYTES:
            raise ValueError("Agent request exceeds 64 KiB")
        if self.intake_request.request_fingerprint != intake_request_fingerprint(
            self.intake_request
        ):
            raise ValueError("embedded intake request fingerprint mismatch")
        if self.request_fingerprint != self.intake_request.request_fingerprint:
            raise ValueError("request fingerprint mismatch")
        if self.request_body_fingerprint != request_body_fingerprint(request_body):
            raise ValueError("request body fingerprint mismatch")
        if (
            self.send_attempt.request_fingerprint != self.request_fingerprint
            or self.send_attempt.request_body_fingerprint
            != self.request_body_fingerprint
            or self.send_attempt.endpoint_fingerprint != self.endpoint_fingerprint
        ):
            raise ValueError("attempt envelope binding mismatch")
        if self.send_attempt.attempt_fingerprint != attempt_fingerprint(
            self.send_attempt, operator_id=self.send_attempt.operator_id
        ):
            raise ValueError("attempt fingerprint mismatch")
        if (
            self.intake_request.operator_assertion.operator_id
            != self.send_attempt.operator_id
            or self.intake_request.intake_request_id
            != self.send_attempt.linkage.intake_request_id
            or self.intake_request.delivery_attempt_id
            != self.send_attempt.linkage.delivery_attempt_id
        ):
            raise ValueError("Agent envelope ownership or linkage mismatch")
        if self.intake_request.expires_at != self.send_attempt.expires_at:
            raise ValueError("Agent envelope expiry mismatch")
        if self.envelope_fingerprint != agent_envelope_fingerprint(self):
            raise ValueError("Agent envelope fingerprint mismatch")
        if len(_canonical(self)) > MAX_AGENT_ENVELOPE_BYTES:
            raise ValueError("Agent envelope exceeds 128 KiB")
        return self


class AgentLiveIntakeAdmissionCopyV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-admission-v1"] = (
        "agent-live-intake-admission-v1"
    )
    admission_id: CanonicalUuid4
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    delivery_attempt_id: CanonicalUuid4
    received_at: UtcSecond
    valid_until: UtcSecond
    operator_id: OperatorId
    linkage: LiveDeliverySendLinkageV1
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    statement: Literal["agent_admitted_authenticated_live_delivery_evidence_only"] = (
        "agent_admitted_authenticated_live_delivery_evidence_only"
    )
    delivery_received: Literal[True] = True
    evidence_admission_granted: Literal[True] = True
    admission_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_admission(self) -> AgentLiveIntakeAdmissionCopyV1:
        if not _instant(self.received_at) < _instant(self.valid_until):
            raise ValueError("Agent admission is expired")
        if (
            self.intake_request_id != self.linkage.intake_request_id
            or self.delivery_attempt_id != self.linkage.delivery_attempt_id
        ):
            raise ValueError("Agent admission linkage mismatch")
        if self.admission_fingerprint != agent_admission_fingerprint(self):
            raise ValueError("Agent admission fingerprint mismatch")
        return self


class AgentLiveIntakeAcknowledgementCopyV1(_AuthorityFlags):
    schema: Literal["agent-live-intake-acknowledgement-v1"] = (
        "agent-live-intake-acknowledgement-v1"
    )
    acknowledgement_id: CanonicalUuid4
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    received_at: UtcSecond
    valid_until: UtcSecond
    status: Literal["admitted_for_evidence_only"] = "admitted_for_evidence_only"
    provenance: Literal["authenticated_core_live_intake_evidence_only"] = (
        "authenticated_core_live_intake_evidence_only"
    )
    acknowledgement_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_acknowledgement(self) -> AgentLiveIntakeAcknowledgementCopyV1:
        if not _instant(self.received_at) < _instant(self.valid_until):
            raise ValueError("Agent acknowledgement is expired")
        if self.acknowledgement_fingerprint != agent_acknowledgement_fingerprint(
            self
        ):
            raise ValueError("Agent acknowledgement fingerprint mismatch")
        return self


class AgentLiveIntakeResultCopyV1(ContractModel):
    schema: Literal["agent-live-intake-result-v1"] = "agent-live-intake-result-v1"
    send_attempt_id: CanonicalUuid4 | None
    intake_request_id: CanonicalUuid4 | None
    outcome: Literal["admitted_for_evidence_only", "rejected"]
    admission: AgentLiveIntakeAdmissionCopyV1 | None
    acknowledgement: AgentLiveIntakeAcknowledgementCopyV1 | None
    reason_code: Literal[
        "unauthenticated",
        "unauthorized",
        "malformed",
        "not_current",
        "ownership_mismatch",
        "request_mismatch",
        "attempt_mismatch",
        "linkage_mismatch",
        "fingerprint_mismatch",
        "replay_conflict",
        "quota_exceeded",
        "unavailable",
    ] | None

    @model_validator(mode="after")
    def exact_result(self) -> AgentLiveIntakeResultCopyV1:
        admitted = self.outcome == "admitted_for_evidence_only"
        if admitted != (
            self.admission is not None
            and self.acknowledgement is not None
            and self.reason_code is None
        ):
            raise ValueError("Agent result shape mismatch")
        if (
            admitted
            and self.admission
            and self.acknowledgement
            and not (
                self.send_attempt_id
                == self.admission.send_attempt_id
                == self.acknowledgement.send_attempt_id
                and self.intake_request_id
                == self.admission.intake_request_id
                == self.acknowledgement.intake_request_id
                and self.acknowledgement.admission_id == self.admission.admission_id
                and self.acknowledgement.admission_fingerprint
                == self.admission.admission_fingerprint
            )
        ):
            raise ValueError("Agent result binding mismatch")
        if self.reason_code in {"unauthenticated", "unauthorized"} and (
            self.send_attempt_id is not None or self.intake_request_id is not None
        ):
            raise ValueError("authentication rejection must redact identities")
        if len(_canonical(self)) > MAX_AGENT_RESPONSE_BYTES:
            raise ValueError("Agent result exceeds 32 KiB")
        return self


class AgentAdmissionReceiptAuthenticityV1(ContractModel):
    schema: Literal["agent-admission-receipt-authenticity-v1"] = (
        "agent-admission-receipt-authenticity-v1"
    )
    authenticated_principal: Literal[AGENT_PRINCIPAL] = AGENT_PRINCIPAL
    permission: Literal[AGENT_PERMISSION] = AGENT_PERMISSION
    source_scheme: Literal["https"] = "https"
    source_path: Literal[AGENT_PATH] = AGENT_PATH
    source_identity_fingerprint: FingerprintV1
    endpoint_fingerprint: FingerprintV1
    credential_reference_fingerprint: FingerprintV1
    authenticated_agent_response: Literal[True] = True
    credential_reference_only: Literal[True] = True
    credential_material_present: Literal[False] = False
    agent_receipt_exported: Literal[False] = False
    agent_receipt_atomicity_relied_upon: Literal[True] = True


class AgentAdmissionReceiptCopyV1(_AuthorityFlags):
    """Authenticated v0.32 admission/ack copy, not an Agent store export."""

    schema: Literal["agent-admission-receipt-copy-v1"] = (
        "agent-admission-receipt-copy-v1"
    )
    result: AgentLiveIntakeResultCopyV1
    authenticity: AgentAdmissionReceiptAuthenticityV1
    copied_at: UtcSecond
    copy_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_copy(self) -> AgentAdmissionReceiptCopyV1:
        if self.result.outcome != "admitted_for_evidence_only":
            raise ValueError("only admitted Agent evidence may be copied")
        if self.copy_fingerprint != agent_receipt_copy_fingerprint(self):
            raise ValueError("Agent receipt copy fingerprint mismatch")
        return self


class EndToEndInertDeliveryRequestV1(_AuthorityFlags):
    schema: Literal["end-to-end-inert-delivery-request-v1"] = (
        "end-to-end-inert-delivery-request-v1"
    )
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope: AgentLiveIntakeEnvelopeCopyV1
    endpoint_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    requested_at: UtcSecond
    expires_at: UtcSecond
    content_type: Literal["application/json"] = "application/json"
    maximum_response_bytes: Literal[32768] = 32768
    default_enabled: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0
    request_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_request(self) -> EndToEndInertDeliveryRequestV1:
        attempt = self.envelope.send_attempt
        requested, expires = _instant(self.requested_at), _instant(self.expires_at)
        created = _instant(attempt.created_at)
        if not created <= requested < expires <= created + timedelta(
            seconds=MAX_FRESHNESS_SECONDS
        ):
            raise ValueError("request exceeds inherited 30-second freshness")
        if not (
            self.send_attempt_id == attempt.send_attempt_id
            and self.attempt_fingerprint == attempt.attempt_fingerprint
            and self.endpoint_fingerprint == self.envelope.endpoint_fingerprint
            and self.expires_at == attempt.expires_at
        ):
            raise ValueError("request attempt or endpoint mismatch")
        if self.request_fingerprint != request_fingerprint(self):
            raise ValueError("end-to-end request fingerprint mismatch")
        if len(_canonical(self)) > MAX_REQUEST_BYTES:
            raise ValueError("end-to-end request exceeds 160 KiB")
        return self


class EndToEndInertDeliveryLinkageV1(LiveDeliverySendLinkageV1):
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    v031_send_receipt_fingerprint: FingerprintV1
    v032_envelope_fingerprint: FingerprintV1
    v032_agent_result_fingerprint: FingerprintV1
    v032_admission_id: CanonicalUuid4
    v032_admission_fingerprint: FingerprintV1
    v032_acknowledgement_id: CanonicalUuid4
    v032_acknowledgement_fingerprint: FingerprintV1
    v032_agent_receipt_exported: Literal[False] = False
    v032_agent_receipt_atomicity_relied_upon: Literal[True] = True


class EndToEndInertDeliveryVerificationV1(_AuthorityFlags):
    schema: Literal["end-to-end-inert-delivery-verification-v1"] = (
        "end-to-end-inert-delivery-verification-v1"
    )
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    response_body_fingerprint: FingerprintV1
    agent_result_fingerprint: FingerprintV1
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    acknowledgement_id: CanonicalUuid4
    acknowledgement_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    operator_id: OperatorId
    linkage_fingerprint: FingerprintV1
    verified_at: UtcSecond
    valid_until: UtcSecond
    authenticated_agent_response: Literal[True] = True
    agent_persistence_claimed_by_core: Literal[False] = False
    verification_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_verification(self) -> EndToEndInertDeliveryVerificationV1:
        if not _instant(self.verified_at) < _instant(self.valid_until):
            raise ValueError("receipt verification is stale or expired")
        if self.verification_fingerprint != verification_fingerprint(self):
            raise ValueError("verification fingerprint mismatch")
        if len(_canonical(self)) > MAX_VERIFICATION_BYTES:
            raise ValueError("verification exceeds 160 KiB")
        return self


class EndToEndInertDeliveryReceiptV1(_AuthorityFlags):
    schema: Literal["end-to-end-inert-delivery-receipt-v1"] = (
        "end-to-end-inert-delivery-receipt-v1"
    )
    receipt_id: CanonicalUuid4
    operator_id: OperatorId
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    prior_send_receipt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    verification: EndToEndInertDeliveryVerificationV1
    agent_receipt_copy: AgentAdmissionReceiptCopyV1
    linkage: EndToEndInertDeliveryLinkageV1
    received_at: UtcSecond
    valid_until: UtcSecond
    lifecycle_at_creation: Literal["verified_inert_receipt"] = (
        "verified_inert_receipt"
    )
    default_enabled: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0
    receipt_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_receipt(self) -> EndToEndInertDeliveryReceiptV1:
        verification = self.verification
        result = self.agent_receipt_copy.result
        admission = result.admission
        acknowledgement = result.acknowledgement
        if admission is None or acknowledgement is None:
            raise ValueError("Agent receipt evidence is incomplete")
        if not (
            self.operator_id == verification.operator_id == admission.operator_id
            and self.send_attempt_id
            == verification.send_attempt_id
            == admission.send_attempt_id
            and self.attempt_fingerprint
            == verification.attempt_fingerprint
            == admission.attempt_fingerprint
            and self.envelope_fingerprint
            == verification.envelope_fingerprint
            == admission.envelope_fingerprint
            and self.valid_until
            == verification.valid_until
            == admission.valid_until
            == acknowledgement.valid_until
        ):
            raise ValueError("receipt ownership, attempt, or freshness mismatch")
        expected_linkage = {
            **admission.linkage.model_dump(mode="json"),
            "send_attempt_id": self.send_attempt_id,
            "attempt_fingerprint": self.attempt_fingerprint.model_dump(mode="json"),
            "v031_send_receipt_fingerprint": (
                self.prior_send_receipt_fingerprint.model_dump(mode="json")
            ),
            "v032_envelope_fingerprint": self.envelope_fingerprint.model_dump(
                mode="json"
            ),
            "v032_agent_result_fingerprint": agent_result_fingerprint(
                result
            ).model_dump(mode="json"),
            "v032_admission_id": admission.admission_id,
            "v032_admission_fingerprint": admission.admission_fingerprint.model_dump(
                mode="json"
            ),
            "v032_acknowledgement_id": acknowledgement.acknowledgement_id,
            "v032_acknowledgement_fingerprint": (
                acknowledgement.acknowledgement_fingerprint.model_dump(mode="json")
            ),
            "v032_agent_receipt_exported": False,
            "v032_agent_receipt_atomicity_relied_upon": True,
        }
        if self.linkage.model_dump(mode="json") != expected_linkage:
            raise ValueError("complete v0.20-v0.32 linkage mismatch")
        if verification.linkage_fingerprint != linkage_fingerprint(self.linkage):
            raise ValueError("verification linkage fingerprint mismatch")
        if verification.agent_result_fingerprint != agent_result_fingerprint(result):
            raise ValueError("verification result fingerprint mismatch")
        if not (
            verification.admission_id == admission.admission_id
            and verification.admission_fingerprint == admission.admission_fingerprint
            and verification.acknowledgement_id
            == acknowledgement.acknowledgement_id
            and verification.acknowledgement_fingerprint
            == acknowledgement.acknowledgement_fingerprint
            and verification.intake_request_id == admission.intake_request_id
        ):
            raise ValueError("verification Agent receipt binding mismatch")
        received = _instant(self.received_at)
        valid_until = _instant(self.valid_until)
        if not _instant(admission.received_at) <= received <= _instant(
            verification.verified_at
        ) < valid_until:
            raise ValueError("receipt chronology or expiry mismatch")
        if self.receipt_fingerprint != receipt_fingerprint(self):
            raise ValueError("receipt fingerprint mismatch")
        if len(_canonical(self)) > MAX_RECEIPT_BYTES:
            raise ValueError("receipt exceeds 192 KiB")
        return self


EndToEndInertDeliveryLifecycleV1 = Literal[
    "disabled",
    "reserved",
    "sending",
    "agent_admitted",
    "verified_inert_receipt",
    "rejected",
    "ambiguous",
    "expired",
    "unavailable",
]


class EndToEndInertDeliveryStatusV1(_AuthorityFlags):
    schema: Literal["end-to-end-inert-delivery-status-v1"] = (
        "end-to-end-inert-delivery-status-v1"
    )
    receipt_id: CanonicalUuid4
    send_attempt_id: CanonicalUuid4
    operator_id: OperatorId
    observed_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: EndToEndInertDeliveryLifecycleV1
    default_enabled: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0


class EndToEndInertDeliveryIdempotencyV1(ContractModel):
    operator_id: OperatorId
    key: IdempotencyKey
    idempotency_key_fingerprint: FingerprintV1
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    receipt_id: CanonicalUuid4
    receipt_fingerprint: FingerprintV1
    reservation_permanent: Literal[True] = True
    exact_duplicate_only: Literal[True] = True
    network_on_exact_duplicate: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_idempotency(self) -> EndToEndInertDeliveryIdempotencyV1:
        if self.idempotency_key_fingerprint != idempotency_key_fingerprint(
            self.operator_id, self.key
        ):
            raise ValueError("idempotency fingerprint mismatch")
        return self


class EndToEndInertDeliveryRedactedErrorV1(_AuthorityFlags):
    schema: Literal["end-to-end-inert-delivery-error-v1"] = (
        "end-to-end-inert-delivery-error-v1"
    )
    error_code: Literal[
        "malformed",
        "unauthenticated",
        "unauthorized",
        "not_found",
        "not_current",
        "expired",
        "ownership_mismatch",
        "linkage_mismatch",
        "fingerprint_mismatch",
        "already_reserved",
        "transport_unavailable",
        "agent_rejected",
        "response_invalid",
        "ambiguous",
        "quota_exceeded",
        "unavailable",
    ]
    safe_message: Literal["Inert delivery receipt evidence is unavailable."] = (
        "Inert delivery receipt evidence is unavailable."
    )
    correlation_id: CorrelationId
    send_attempt_id: CanonicalUuid4 | None = None
    attempt_fingerprint: FingerprintV1 | None = None
    receipt_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True
    retryable: Literal[False] = False

    @model_validator(mode="after")
    def redact_authentication(self) -> EndToEndInertDeliveryRedactedErrorV1:
        if self.error_code in {"unauthenticated", "unauthorized"} and any(
            value is not None
            for value in (
                self.send_attempt_id,
                self.attempt_fingerprint,
                self.receipt_fingerprint,
            )
        ):
            raise ValueError("authentication errors must redact identities")
        return self


class EndToEndInertDeliveryAuditEvidenceV1(_AuthorityFlags):
    schema: Literal["end-to-end-inert-delivery-audit-evidence-v1"] = (
        "end-to-end-inert-delivery-audit-evidence-v1"
    )
    receipt_id: CanonicalUuid4
    receipt_fingerprint: FingerprintV1
    verification_fingerprint: FingerprintV1
    send_attempt_id: CanonicalUuid4
    attempt_fingerprint: FingerprintV1
    prior_send_receipt_fingerprint: FingerprintV1
    envelope_fingerprint: FingerprintV1
    agent_result_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    acknowledgement_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1
    endpoint_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    operator_fingerprint: FingerprintV1
    correlation_id: CorrelationId
    requested_at: UtcSecond
    received_at: UtcSecond
    completed_at: UtcSecond
    lifecycle: Literal["verified_inert_receipt", "expired", "unavailable"]
    outcome: Literal["verified_inert_receipt"] = "verified_inert_receipt"
    default_enabled: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_audit(self) -> EndToEndInertDeliveryAuditEvidenceV1:
        if not (
            _instant(self.requested_at)
            <= _instant(self.received_at)
            <= _instant(self.completed_at)
        ):
            raise ValueError("audit chronology mismatch")
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        if len(_canonical(self)) > MAX_AUDIT_BYTES:
            raise ValueError("audit evidence exceeds 64 KiB")
        return self


class EndToEndInertDeliveryResultV1(_AuthorityFlags):
    disposition: Literal[
        "verified_inert_receipt",
        "exact_duplicate",
        "rejected",
        "ambiguous",
        "unavailable",
    ]
    receipt: EndToEndInertDeliveryReceiptV1 | None
    verification: EndToEndInertDeliveryVerificationV1 | None
    agent_receipt_copy: AgentAdmissionReceiptCopyV1 | None
    status: EndToEndInertDeliveryStatusV1 | None
    audit_evidence: EndToEndInertDeliveryAuditEvidenceV1 | None
    error: EndToEndInertDeliveryRedactedErrorV1 | None
    default_enabled: Literal[False] = False
    one_shot_only: Literal[True] = True
    automatic_retries: Literal[0] = 0

    @model_validator(mode="after")
    def exact_result(self) -> EndToEndInertDeliveryResultV1:
        success = self.disposition in {
            "verified_inert_receipt",
            "exact_duplicate",
        }
        evidence = (
            self.receipt,
            self.verification,
            self.agent_receipt_copy,
            self.status,
            self.audit_evidence,
        )
        if success != (all(value is not None for value in evidence) and self.error is None):
            raise ValueError("result disposition and evidence disagree")
        if not success and (any(value is not None for value in evidence) or self.error is None):
            raise ValueError("failed result must contain only a redacted error")
        return self


def request_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:end-to-end-inert-delivery-request:v1",
        _without(value, "request_fingerprint"),
    )


def verification_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:end-to-end-inert-delivery-verification:v1",
        _without(value, "verification_fingerprint"),
    )


def receipt_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:end-to-end-inert-delivery-receipt:v1",
        _without(value, "receipt_fingerprint"),
    )


def audit_evidence_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:end-to-end-inert-delivery-audit-evidence:v1",
        _without(value, "evidence_fingerprint"),
    )


def agent_envelope_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:agent-live-intake-envelope:v1",
        _without(value, "envelope_fingerprint"),
    )


def agent_admission_fingerprint(value: Any) -> FingerprintV1:
    raw = _without(value, "admission_fingerprint")
    return _fingerprint(
        "atlas:agent-live-intake-admission:v1",
        {"operator_id": raw["operator_id"], "admission": raw},
    )


def agent_acknowledgement_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:agent-live-intake-acknowledgement:v1",
        _without(value, "acknowledgement_fingerprint"),
    )


def agent_result_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint("atlas:agent-live-intake-result:v1", value)


def agent_receipt_copy_fingerprint(value: Any) -> FingerprintV1:
    return _fingerprint(
        "atlas:agent-admission-receipt-copy:v1",
        _without(value, "copy_fingerprint"),
    )


def response_body_fingerprint(value: bytes) -> FingerprintV1:
    return _fingerprint("atlas:live-delivery-body:v1", value)


def request_body_fingerprint(value: bytes) -> FingerprintV1:
    return _fingerprint(
        "atlas:live-delivery-send-request-body:v1", {"hex": value.hex()}
    )


def linkage_fingerprint(value: EndToEndInertDeliveryLinkageV1) -> FingerprintV1:
    return _fingerprint("atlas:end-to-end-inert-delivery-linkage:v1", value)


def idempotency_key_fingerprint(operator_id: str, key: str) -> FingerprintV1:
    exact_key = _visible_ascii(key)
    return _fingerprint(
        "atlas:end-to-end-inert-delivery-idempotency-key:v1",
        {"operator_id": _identity(operator_id), "idempotency_key": exact_key},
    )


def operator_fingerprint(operator_id: str) -> FingerprintV1:
    return _fingerprint(
        "atlas:end-to-end-inert-delivery-operator:v1",
        {"operator_id": _identity(operator_id)},
    )


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictContractError("duplicate JSON member")
        value[key] = item
    return value


def _parse_closed_json(body: bytes, *, maximum: int) -> Any:
    if not 0 < len(body) <= maximum:
        raise StrictContractError("JSON body is out of bounds")
    try:
        value = json.loads(body, object_pairs_hook=_reject_duplicates)
        _closed_value(value)
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("invalid closed JSON") from error
    return value


def parse_request_json(body: bytes) -> EndToEndInertDeliveryRequestV1:
    try:
        return EndToEndInertDeliveryRequestV1.model_validate(
            _parse_closed_json(body, maximum=MAX_REQUEST_BYTES)
        )
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("invalid inert delivery request") from error


def parse_agent_result_json(body: bytes) -> AgentLiveIntakeResultCopyV1:
    try:
        return AgentLiveIntakeResultCopyV1.model_validate(
            _parse_closed_json(body, maximum=MAX_AGENT_RESPONSE_BYTES)
        )
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("invalid Agent admission result") from error
