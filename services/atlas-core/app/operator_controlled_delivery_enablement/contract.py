"""Pure closed v0.30 models; no service, I/O, transport, or execution."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.delivery_activation_preflight.contract import (
    DeliveryActivationPreflightResultV1,
    FingerprintV1,
    validate_preflight_result,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 1024
MAX_RECORD_BYTES = 96 * 1024
MAX_AUDIT_EVIDENCE_BYTES = 16 * 1024
MAX_PREFLIGHT_FRESHNESS_SECONDS = 30
CONFIRMATION = ("I enable this exact delivery for later consideration only. "
                "This does not send, install, or execute anything.")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


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
        not 0x21 <= ord(char) <= 0x7E for char in value
    ):
        raise ValueError("idempotency key is out of bounds")
    return value


OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]
OperatorConfirmationV1 = Literal[
    "I enable this exact delivery for later consideration only. This does not send, install, or execute anything."
]


class OperatorControlledDeliveryEnablementCreateV1(ContractModel):
    schema: Literal["operator-controlled-delivery-enablement-create-v1"] = "operator-controlled-delivery-enablement-create-v1"
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    confirmation: OperatorConfirmationV1

    @model_validator(mode="after")
    def bounded(self):
        if len(_canonical(self)) > MAX_CREATE_BYTES:
            raise ValueError("delivery enablement create exceeds 1 KiB")
        return self


class OperatorControlledDeliveryEnablementAuthenticationExpectationV1(ContractModel):
    identity_source: Literal["authenticated_core_session_principal"] = "authenticated_core_session_principal"
    create_authorization: Literal["installation_delivery_enablement:create"] = "installation_delivery_enablement:create"
    read_authorization: Literal["installation_delivery_enablement:read"] = "installation_delivery_enablement:read"
    csrf_required: Literal[True] = True
    trusted_https_origin_required: Literal[True] = True
    caller_supplied_operator_allowed: Literal[False] = False
    service_credentials_accepted: Literal[False] = False


class OperatorControlledDeliveryEnablementConfigurationV1(ContractModel):
    schema: Literal["operator-controlled-delivery-enablement-configuration-v1"] = "operator-controlled-delivery-enablement-configuration-v1"
    enabled: bool = False
    mode: Literal["local-operator-enablement-evidence-only"] = "local-operator-enablement-evidence-only"
    authentication: OperatorControlledDeliveryEnablementAuthenticationExpectationV1 = OperatorControlledDeliveryEnablementAuthenticationExpectationV1()
    agent_contact_allowed: Literal[False] = False
    credential_loading_allowed: Literal[False] = False
    production_transport_registered: Literal[False] = False
    delivery_activation_allowed: Literal[False] = False
    delivery_send_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    execution_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False


class OperatorControlledDeliveryEnablementLinkageV1(ContractModel):
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


class OperatorControlledDeliveryEnablementEvidenceV1(ContractModel):
    operator_id: OperatorId
    authenticated_operator_id: OperatorId
    authentication_verified: Literal[True] = True
    create_authorized: Literal[True] = True
    resolved_at: UtcSecond
    preflight: DeliveryActivationPreflightResultV1
    linkage: OperatorControlledDeliveryEnablementLinkageV1
    source_was_owner_scoped_local_readers: Literal[True] = True
    current_revalidation_succeeded: Literal[True] = True
    conflicting_agent_admission: Literal[False] = False
    credentials_loaded: Literal[False] = False
    agent_contacted: Literal[False] = False
    production_transport_registered: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_owner_and_linkage(self):
        if self.operator_id != self.authenticated_operator_id:
            raise ValueError("ownership mismatch")
        validate_preflight_result(self.preflight, operator_id=self.operator_id)
        expected = {**self.preflight.linkage.model_dump(mode="json"),
                    "delivery_preparation_id": self.preflight.delivery_preparation_id,
                    "preparation_fingerprint": self.preflight.preparation_fingerprint.model_dump(mode="json"),
                    "preflight_id": self.preflight.preflight_id,
                    "preflight_fingerprint": self.preflight.preflight_fingerprint.model_dump(mode="json")}
        if self.linkage.model_dump(mode="json") != expected:
            raise ValueError("complete v0.20-v0.29 linkage mismatch")
        return self


class OperatorControlledDeliveryEnablementRecordV1(ContractModel):
    schema: Literal["operator-controlled-delivery-enablement-record-v1"] = "operator-controlled-delivery-enablement-record-v1"
    enablement_id: CanonicalUuid4
    enabled_at: UtcSecond
    expires_at: UtcSecond
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    linkage: OperatorControlledDeliveryEnablementLinkageV1
    status_at_creation: Literal["operator_enabled_for_later_delivery_consideration"] = "operator_enabled_for_later_delivery_consideration"
    confirmation: OperatorConfirmationV1
    statement: Literal["operator_enablement_evidence_only_no_delivery_activation"] = "operator_enablement_evidence_only_no_delivery_activation"
    source: Literal["core_operator_controlled_delivery_enablement_v1"] = "core_operator_controlled_delivery_enablement_v1"
    default_enabled: Literal[False] = False
    operator_enabled: Literal[True] = True
    agent_contacted: Literal[False] = False
    credentials_loaded: Literal[False] = False
    production_transport_registered: Literal[False] = False
    delivery_activated: Literal[False] = False
    delivery_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    enablement_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_record(self):
        enabled, expires = _instant(self.enabled_at), _instant(self.expires_at)
        if not enabled < expires <= enabled + timedelta(seconds=30):
            raise ValueError("enablement freshness exceeds inherited 30 seconds")
        pairs = ((self.preflight_id, self.linkage.preflight_id),
                 (self.preflight_fingerprint, self.linkage.preflight_fingerprint),
                 (self.delivery_preparation_id, self.linkage.delivery_preparation_id),
                 (self.preparation_fingerprint, self.linkage.preparation_fingerprint))
        if any(left != right for left, right in pairs):
            raise ValueError("record linkage mismatch")
        if len(_canonical(self)) > MAX_RECORD_BYTES:
            raise ValueError("delivery enablement record exceeds 96 KiB")
        return self


EnablementLifecycleV1 = Literal["enabled", "expired", "unavailable"]


class OperatorControlledDeliveryEnablementStatusV1(ContractModel):
    schema: Literal["operator-controlled-delivery-enablement-status-v1"] = "operator-controlled-delivery-enablement-status-v1"
    enablement_id: CanonicalUuid4
    enablement_fingerprint: FingerprintV1
    observed_at: UtcSecond
    lifecycle: EnablementLifecycleV1
    operator_enabled: Literal[True] = True
    delivery_activated: Literal[False] = False
    delivery_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False


class OperatorControlledDeliveryEnablementIdempotencyV1(ContractModel):
    operator_id: OperatorId
    operation: Literal["operator_controlled_delivery_enablement:create"] = "operator_controlled_delivery_enablement:create"
    key: IdempotencyKey
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    enablement_id: CanonicalUuid4
    enablement_fingerprint: FingerprintV1
    reservation_permanent: Literal[True] = True
    exact_retry_only: Literal[True] = True
    expiry_releases_reservation: Literal[False] = False
    replay_allowed: Literal[False] = False


class OperatorControlledDeliveryEnablementAuditEvidenceV1(ContractModel):
    schema: Literal["operator-controlled-delivery-enablement-audit-evidence-v1"] = "operator-controlled-delivery-enablement-audit-evidence-v1"
    enablement_id: CanonicalUuid4
    enablement_fingerprint: FingerprintV1
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    enabled_at: UtcSecond
    expires_at: UtcSecond
    lifecycle: EnablementLifecycleV1
    status: Literal["operator_enabled_for_later_delivery_consideration"] = "operator_enabled_for_later_delivery_consideration"
    confirmation: OperatorConfirmationV1
    provenance: Literal["core_operator_controlled_delivery_enablement_v1"] = "core_operator_controlled_delivery_enablement_v1"
    delivery_activated: Literal[False] = False
    delivery_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_audit(self):
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        if len(_canonical(self)) > MAX_AUDIT_EVIDENCE_BYTES:
            raise ValueError("audit evidence exceeds 16 KiB")
        return self


EnablementErrorCodeV1 = Literal["malformed", "not_found", "unauthenticated", "unauthorized", "confirmation_mismatch", "linkage_mismatch", "fingerprint_mismatch", "preflight_not_eligible", "not_current", "replay_conflict", "quota_exceeded", "unavailable"]


class OperatorControlledDeliveryEnablementRedactedErrorV1(ContractModel):
    schema: Literal["operator-controlled-delivery-enablement-error-v1"] = "operator-controlled-delivery-enablement-error-v1"
    error_code: EnablementErrorCodeV1
    correlation_id: CorrelationId
    preflight_id: CanonicalUuid4 | None = None
    preflight_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True


class OperatorControlledDeliveryEnablementOperationResultV1(ContractModel):
    disposition: Literal["created", "exact_replay", "rejected", "unavailable"]
    record: OperatorControlledDeliveryEnablementRecordV1 | None
    status: OperatorControlledDeliveryEnablementStatusV1 | None
    audit_evidence: OperatorControlledDeliveryEnablementAuditEvidenceV1 | None
    error: OperatorControlledDeliveryEnablementRedactedErrorV1 | None
    default_enabled: Literal[False] = False
    agent_contacted: Literal[False] = False
    credentials_loaded: Literal[False] = False
    delivery_activated: Literal[False] = False
    delivery_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self):
        success = self.disposition in ("created", "exact_replay")
        affirmative = (self.record, self.status, self.audit_evidence)
        if success != (all(value is not None for value in affirmative) and self.error is None):
            raise ValueError("operation disposition and values disagree")
        if not success and (any(value is not None for value in affirmative) or self.error is None):
            raise ValueError("failed operation must contain one redacted error")
        if self.disposition == "unavailable" and self.error and self.error.error_code != "unavailable":
            raise ValueError("unavailable disposition requires unavailable error")
        return self


def create_delivery_enablement_record(create, *, evidence, configuration, enablement_id: str, enabled_at: str):
    exact_create = OperatorControlledDeliveryEnablementCreateV1.model_validate(create.model_dump(mode="python"))
    exact = OperatorControlledDeliveryEnablementEvidenceV1.model_validate(evidence.model_dump(mode="python"))
    if not configuration.enabled:
        raise ValueError("delivery enablement is default-disabled")
    preflight = exact.preflight
    if exact_create.preflight_id != preflight.preflight_id or exact_create.preflight_fingerprint != preflight.preflight_fingerprint:
        raise ValueError("preflight identity or fingerprint mismatch")
    if preflight.decision != "eligible_for_later_activation":
        raise ValueError("preflight is not eligible")
    now, evaluated, expires = _instant(enabled_at), _instant(preflight.evaluated_at), _instant(preflight.expires_at)
    if _instant(exact.resolved_at) != now:
        raise ValueError("evidence resolution time mismatch")
    if expires > evaluated + timedelta(seconds=30) or not evaluated <= now < expires:
        raise ValueError("preflight is stale or expired")
    raw: dict[str, Any] = {
        "schema": "operator-controlled-delivery-enablement-record-v1", "enablement_id": enablement_id,
        "enabled_at": _format(now), "expires_at": preflight.expires_at,
        "preflight_id": preflight.preflight_id, "preflight_fingerprint": preflight.preflight_fingerprint.model_dump(mode="json"),
        "delivery_preparation_id": preflight.delivery_preparation_id, "preparation_fingerprint": preflight.preparation_fingerprint.model_dump(mode="json"),
        "linkage": exact.linkage.model_dump(mode="json"), "status_at_creation": "operator_enabled_for_later_delivery_consideration",
        "confirmation": CONFIRMATION, "statement": "operator_enablement_evidence_only_no_delivery_activation",
        "source": "core_operator_controlled_delivery_enablement_v1", "default_enabled": False, "operator_enabled": True,
        "agent_contacted": False, "credentials_loaded": False, "production_transport_registered": False,
        "delivery_activated": False, "delivery_sent": False, "delivery_authorized": False,
        "execution_admission_granted": False, "execution_authorized": False, "dispatch_allowed": False,
        "worker_allowed": False, "workflow_allowed": False, "installation_allowed": False,
        "deployment_allowed": False, "mutation_allowed": False, "replay_allowed": False,
    }
    raw["enablement_fingerprint"] = enablement_fingerprint(raw, operator_id=exact.operator_id).model_dump(mode="json")
    return validate_enablement_record(OperatorControlledDeliveryEnablementRecordV1.model_validate(raw), operator_id=exact.operator_id)


def validate_enablement_record(record, *, operator_id: str):
    exact = OperatorControlledDeliveryEnablementRecordV1.model_validate(record.model_dump(mode="python"))
    if exact.enablement_fingerprint != enablement_fingerprint(exact, operator_id=operator_id):
        raise ValueError("enablement fingerprint mismatch")
    return exact


def enablement_lifecycle(record, *, now: str, current_revalidation_succeeded: bool = True) -> EnablementLifecycleV1:
    observed = _instant(now)
    if observed < _instant(record.enabled_at):
        raise ValueError("lifecycle instant precedes enablement")
    if observed >= _instant(record.expires_at):
        return "expired"
    return "enabled" if current_revalidation_succeeded else "unavailable"


def enablement_fingerprint(record, *, operator_id: str) -> FingerprintV1:
    raw = _raw(record); raw.pop("enablement_fingerprint", None)
    return _fingerprint("atlas:operator-controlled-delivery-enablement-record:v1", {"operator_id": _identity(operator_id), "record": raw})


def audit_evidence_fingerprint(evidence) -> FingerprintV1:
    raw = _raw(evidence); raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:operator-controlled-delivery-enablement-audit-evidence:v1", raw)


def parse_create_json(payload: str | bytes):
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("delivery enablement create exceeds 1 KiB")
    try:
        return OperatorControlledDeliveryEnablementCreateV1.model_validate(json.loads(raw, object_pairs_hook=_no_duplicates))
    except StrictContractError:
        raise
    except Exception as exc:
        raise StrictContractError("invalid delivery enablement create") from exc


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


__all__ = [name for name in globals() if name.startswith("OperatorControlledDeliveryEnablement")]
__all__ += ["CONFIRMATION", "StrictContractError", "audit_evidence_fingerprint", "create_delivery_enablement_record", "enablement_fingerprint", "enablement_lifecycle", "parse_create_json", "validate_enablement_record"]
