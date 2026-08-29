"""Pure closed models for the v0.29 delivery-activation preflight.

This module only validates injected local evidence.  It has no service, store,
route, transport, credential, Agent, process, or mutation capability.
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

from app.dormant_agent_intake_delivery_wiring.contract import (
    CoreAgentIntakeDeliveryPreparationV1,
    preparation_fingerprint,
)
from app.installation_dispatch_handoff.contract import (
    FingerprintV1,
    dispatch_envelope_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 1024
MAX_RESULT_BYTES = 96 * 1024
MAX_AUDIT_EVIDENCE_BYTES = 16 * 1024
MAX_FRESHNESS_SECONDS = 30
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


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


OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
IdempotencyKey = Annotated[str, AfterValidator(_visible_ascii)]


def _tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


PreflightReasonCodeV1 = Literal[
    "preflight_feature_disabled",
    "preparation_not_found",
    "preparation_fingerprint_mismatch",
    "ownership_mismatch",
    "linkage_mismatch",
    "upstream_fingerprint_mismatch",
    "upstream_state_invalid",
    "preparation_not_dormant",
    "already_admitted",
    "expired",
    "clock_invalid",
    "authority_mismatch",
    "evidence_unavailable",
    "evidence_corrupt",
    "replay_conflict",
]
_REASON_ORDER = {
    reason: index
    for index, reason in enumerate(
        (
            "preflight_feature_disabled", "preparation_not_found",
            "preparation_fingerprint_mismatch", "ownership_mismatch",
            "linkage_mismatch", "upstream_fingerprint_mismatch",
            "upstream_state_invalid", "preparation_not_dormant",
            "already_admitted", "expired", "clock_invalid",
            "authority_mismatch", "evidence_unavailable", "evidence_corrupt",
            "replay_conflict",
        )
    )
}
ReasonCodes = Annotated[tuple[PreflightReasonCodeV1, ...], BeforeValidator(_tuple)]


class DeliveryActivationPreflightCreateV1(ContractModel):
    schema: Literal["delivery-activation-preflight-create-v1"] = (
        "delivery-activation-preflight-create-v1"
    )
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def bounded(self) -> DeliveryActivationPreflightCreateV1:
        if len(_canonical(self)) > MAX_CREATE_BYTES:
            raise ValueError("preflight create exceeds 1 KiB")
        return self


class DeliveryActivationPreflightAuthenticationExpectationV1(ContractModel):
    identity_source: Literal["authenticated_core_session_principal"] = (
        "authenticated_core_session_principal"
    )
    create_authorization: Literal["installation_delivery_preflight:create"] = (
        "installation_delivery_preflight:create"
    )
    read_authorization: Literal["installation_delivery_preflight:read"] = (
        "installation_delivery_preflight:read"
    )
    csrf_required: Literal[True] = True
    same_origin_required: Literal[True] = True
    caller_supplied_operator_allowed: Literal[False] = False
    service_credentials_accepted: Literal[False] = False


class DeliveryActivationPreflightConfigurationV1(ContractModel):
    schema: Literal["delivery-activation-preflight-configuration-v1"] = (
        "delivery-activation-preflight-configuration-v1"
    )
    enabled: bool = False
    mode: Literal["local-evidence-preflight-only"] = "local-evidence-preflight-only"
    authentication: DeliveryActivationPreflightAuthenticationExpectationV1 = (
        DeliveryActivationPreflightAuthenticationExpectationV1()
    )
    agent_contact_allowed: Literal[False] = False
    credential_loading_allowed: Literal[False] = False
    production_transport_registered: Literal[False] = False
    delivery_activation_allowed: Literal[False] = False
    execution_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False


class DeliveryActivationPreflightLinkageV1(ContractModel):
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


class DeliveryActivationPreflightLifecycleInputsV1(ContractModel):
    candidate_state: Literal["active"] = "active"
    approval_intent_state: Literal["recorded"] = "recorded"
    agent_validation_status: Literal["valid_but_unsupported"] = "valid_but_unsupported"
    execution_request_state: Literal["recorded"] = "recorded"
    dispatch_handoff_state: Literal["prepared"] = "prepared"
    preparation_lifecycle: Literal["prepared_dormant"] = "prepared_dormant"
    preparation_status: Literal["not_sent"] = "not_sent"
    existing_agent_admission: Literal[False] = False
    evidence_complete: Literal[True] = True


class DeliveryActivationPreflightEvidenceV1(ContractModel):
    """Injected, owner-scoped local evidence resolved by a later P2 service."""

    operator_id: OperatorId
    authenticated_operator_id: OperatorId
    authentication_verified: Literal[True] = True
    create_authorized: Literal[True] = True
    resolved_at: UtcSecond
    preparation: CoreAgentIntakeDeliveryPreparationV1
    linkage: DeliveryActivationPreflightLinkageV1
    lifecycle: DeliveryActivationPreflightLifecycleInputsV1
    source_was_owner_scoped_local_readers: Literal[True] = True
    credentials_loaded: Literal[False] = False
    agent_contacted: Literal[False] = False
    production_transport_registered: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_owner_and_linkage(self) -> DeliveryActivationPreflightEvidenceV1:
        if self.operator_id != self.authenticated_operator_id:
            raise ValueError("ownership mismatch")
        _validate_linkage(self.operator_id, self.preparation, self.linkage)
        return self


class DeliveryActivationPreflightResultV1(ContractModel):
    schema: Literal["delivery-activation-preflight-result-v1"] = (
        "delivery-activation-preflight-result-v1"
    )
    preflight_id: CanonicalUuid4
    evaluated_at: UtcSecond
    expires_at: UtcSecond
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    endpoint_fingerprint: FingerprintV1
    linkage: DeliveryActivationPreflightLinkageV1
    decision: Literal["eligible_for_later_activation", "ineligible"]
    reason_codes: ReasonCodes
    lifecycle_at_evaluation: Literal["eligible", "ineligible"]
    statement: Literal["local_evidence_preflight_only_no_delivery_activation"] = (
        "local_evidence_preflight_only_no_delivery_activation"
    )
    source: Literal["core_delivery_activation_preflight_v1"] = (
        "core_delivery_activation_preflight_v1"
    )
    default_enabled: Literal[False] = False
    agent_contacted: Literal[False] = False
    credentials_loaded: Literal[False] = False
    production_transport_registered: Literal[False] = False
    delivery_activated: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    preflight_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_result(self) -> DeliveryActivationPreflightResultV1:
        eligible = self.decision == "eligible_for_later_activation"
        if eligible != (self.lifecycle_at_evaluation == "eligible"):
            raise ValueError("decision and lifecycle disagree")
        if eligible != (not self.reason_codes):
            raise ValueError("eligible results alone have no reason codes")
        if tuple(sorted(set(self.reason_codes), key=_REASON_ORDER.__getitem__)) != self.reason_codes:
            raise ValueError("reason codes must be sorted and duplicate-free")
        evaluated, expires = _instant(self.evaluated_at), _instant(self.expires_at)
        if eligible and not evaluated < expires <= evaluated + timedelta(seconds=30):
            raise ValueError("eligible result freshness exceeds 30 seconds")
        if not eligible and expires != evaluated:
            raise ValueError("ineligible result must be immediately terminal")
        if len(_canonical(self)) > MAX_RESULT_BYTES:
            raise ValueError("preflight result exceeds 96 KiB")
        return self


class DeliveryActivationPreflightStatusV1(ContractModel):
    schema: Literal["delivery-activation-preflight-status-v1"] = (
        "delivery-activation-preflight-status-v1"
    )
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    observed_at: UtcSecond
    lifecycle: Literal["eligible", "expired", "ineligible", "unavailable"]
    delivery_activated: Literal[False] = False
    delivery_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False


class DeliveryActivationPreflightIdempotencyV1(ContractModel):
    operator_id: OperatorId
    operation: Literal["delivery_activation_preflight:create"] = (
        "delivery_activation_preflight:create"
    )
    key: IdempotencyKey
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    reservation_permanent: Literal[True] = True
    exact_retry_only: Literal[True] = True
    replay_allowed: Literal[False] = False


class DeliveryActivationPreflightAuditEvidenceV1(ContractModel):
    schema: Literal["delivery-activation-preflight-audit-evidence-v1"] = (
        "delivery-activation-preflight-audit-evidence-v1"
    )
    preflight_id: CanonicalUuid4
    preflight_fingerprint: FingerprintV1
    delivery_preparation_id: CanonicalUuid4
    preparation_fingerprint: FingerprintV1
    intake_request_id: CanonicalUuid4
    delivery_attempt_id: CanonicalUuid4
    evaluated_at: UtcSecond
    expires_at: UtcSecond
    lifecycle: Literal["eligible", "expired", "ineligible", "unavailable"]
    decision: Literal["eligible_for_later_activation", "ineligible"]
    reason_codes: ReasonCodes
    provenance: Literal["core_delivery_activation_preflight_v1"] = (
        "core_delivery_activation_preflight_v1"
    )
    delivery_activated: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evidence(self) -> DeliveryActivationPreflightAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        if len(_canonical(self)) > MAX_AUDIT_EVIDENCE_BYTES:
            raise ValueError("audit evidence exceeds 16 KiB")
        return self


PreflightErrorCodeV1 = Literal[
    "malformed", "not_found", "unauthenticated", "unauthorized",
    "linkage_mismatch", "fingerprint_mismatch", "not_current",
    "replay_conflict", "unavailable",
]


class DeliveryActivationPreflightRedactedErrorV1(ContractModel):
    schema: Literal["delivery-activation-preflight-error-v1"] = (
        "delivery-activation-preflight-error-v1"
    )
    error_code: PreflightErrorCodeV1
    correlation_id: CorrelationId
    delivery_preparation_id: CanonicalUuid4 | None = None
    preparation_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True


def evaluate_delivery_activation_preflight(
    create: DeliveryActivationPreflightCreateV1,
    *,
    evidence: DeliveryActivationPreflightEvidenceV1,
    configuration: DeliveryActivationPreflightConfigurationV1,
    preflight_id: str,
    evaluated_at: str,
) -> DeliveryActivationPreflightResultV1:
    """Derive one non-authorizing result from already-resolved local evidence."""
    exact_create = DeliveryActivationPreflightCreateV1.model_validate(
        create.model_dump(mode="python")
    )
    exact = DeliveryActivationPreflightEvidenceV1.model_validate(
        evidence.model_dump(mode="python")
    )
    now = _instant(evaluated_at)
    prepared = exact.preparation
    if exact_create.delivery_preparation_id != prepared.delivery_preparation_id:
        raise ValueError("preparation identity mismatch")
    if exact_create.preparation_fingerprint != prepared.preparation_fingerprint:
        raise ValueError("preparation fingerprint mismatch")
    if _instant(exact.resolved_at) != now:
        raise ValueError("evidence resolution time mismatch")
    if now < _instant(prepared.prepared_at):
        raise ValueError("clock invalid")

    reasons: list[PreflightReasonCodeV1] = []
    if not configuration.enabled:
        reasons.append("preflight_feature_disabled")
    if now - _instant(prepared.prepared_at) > timedelta(seconds=MAX_FRESHNESS_SECONDS):
        reasons.append("expired")
    if now >= _instant(prepared.valid_until):
        reasons.append("expired")
    if exact.lifecycle.existing_agent_admission:
        reasons.append("already_admitted")
    reasons = sorted(set(reasons), key=_REASON_ORDER.__getitem__)
    eligible = not reasons
    expires = min(_instant(prepared.valid_until), now + timedelta(seconds=30))
    if eligible and expires <= now:
        raise ValueError("eligible preflight has no freshness window")
    raw: dict[str, Any] = {
        "schema": "delivery-activation-preflight-result-v1",
        "preflight_id": preflight_id,
        "evaluated_at": _format(now),
        "expires_at": _format(expires if eligible else now),
        "delivery_preparation_id": prepared.delivery_preparation_id,
        "preparation_fingerprint": prepared.preparation_fingerprint.model_dump(mode="json"),
        "endpoint_fingerprint": prepared.endpoint_fingerprint.model_dump(mode="json"),
        "linkage": exact.linkage.model_dump(mode="json"),
        "decision": "eligible_for_later_activation" if eligible else "ineligible",
        "reason_codes": reasons,
        "lifecycle_at_evaluation": "eligible" if eligible else "ineligible",
        "statement": "local_evidence_preflight_only_no_delivery_activation",
        "source": "core_delivery_activation_preflight_v1",
        "default_enabled": False,
        "agent_contacted": False,
        "credentials_loaded": False,
        "production_transport_registered": False,
        "delivery_activated": False,
        "delivery_authorized": False,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["preflight_fingerprint"] = preflight_fingerprint(
        raw, operator_id=exact.operator_id
    ).model_dump(mode="json")
    return validate_preflight_result(
        DeliveryActivationPreflightResultV1.model_validate(raw),
        operator_id=exact.operator_id,
    )


def validate_preflight_result(
    result: DeliveryActivationPreflightResultV1, *, operator_id: str
) -> DeliveryActivationPreflightResultV1:
    """Reparse and verify the owner-domain result fingerprint."""
    exact = DeliveryActivationPreflightResultV1.model_validate(
        result.model_dump(mode="python")
    )
    if exact.preflight_fingerprint != preflight_fingerprint(
        exact, operator_id=operator_id
    ):
        raise ValueError("preflight fingerprint mismatch")
    return exact


def preflight_lifecycle(
    result: DeliveryActivationPreflightResultV1, *, now: str
) -> Literal["eligible", "expired", "ineligible"]:
    instant = _instant(now)
    if instant < _instant(result.evaluated_at):
        raise ValueError("lifecycle instant precedes evaluation")
    if result.decision == "ineligible":
        return "ineligible"
    return "eligible" if instant < _instant(result.expires_at) else "expired"


def preflight_fingerprint(
    result: DeliveryActivationPreflightResultV1 | dict[str, Any],
    *,
    operator_id: str | None = None,
) -> FingerprintV1:
    raw = _raw(result)
    raw.pop("preflight_fingerprint", None)
    owner = operator_id
    if owner is None:
        raise ValueError("operator_id is required for owner-bound fingerprint")
    return _fingerprint(
        "atlas:delivery-activation-preflight-result:v1",
        {"operator_id": _identity(owner), "result": raw},
    )


def audit_evidence_fingerprint(
    evidence: DeliveryActivationPreflightAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    raw = _raw(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:delivery-activation-preflight-audit-evidence:v1", raw)


def parse_create_json(payload: str | bytes) -> DeliveryActivationPreflightCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("preflight create exceeds 1 KiB")
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicates)
        return DeliveryActivationPreflightCreateV1.model_validate(value)
    except StrictContractError:
        raise
    except Exception as exc:
        raise StrictContractError("invalid preflight create") from exc


def _validate_linkage(
    operator_id: str,
    preparation: CoreAgentIntakeDeliveryPreparationV1,
    linkage: DeliveryActivationPreflightLinkageV1,
) -> None:
    envelope = preparation.request.envelope
    source = preparation.source
    upstream = envelope.linkage
    if preparation.preparation_fingerprint != preparation_fingerprint(
        operator_id=operator_id, preparation=preparation
    ):
        raise ValueError("preparation fingerprint mismatch")
    if envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(
        owner_id=operator_id, envelope=envelope
    ):
        raise ValueError("ownership or dispatch fingerprint mismatch")
    expected = (
        upstream.candidate_record_id, upstream.candidate_envelope_fingerprint,
        upstream.candidate_record_fingerprint, upstream.approval_intent_id,
        upstream.approval_intent_fingerprint, upstream.agent_request_id,
        upstream.agent_request_fingerprint, upstream.agent_validation_fingerprint,
        upstream.agent_evidence_fingerprint, upstream.destination_fingerprint,
        upstream.source_plan_fingerprint, upstream.artifact_policy_fingerprint,
        upstream.execution_request_id, upstream.execution_request_fingerprint,
        envelope.dispatch_envelope_id, envelope.dispatch_envelope_fingerprint,
        preparation.request.prior_evidence.intake_simulation.simulation_request_id,
        source.intake_record_id, source.intake_record_fingerprint,
        source.intake_simulation_evidence_fingerprint, source.simulated_delivery_id,
        source.simulated_delivery_fingerprint, source.delivery_record_fingerprint,
        source.simulated_delivery_evidence_fingerprint,
        source.simulated_acknowledgement_id,
        source.simulated_acknowledgement_fingerprint,
        source.simulated_acknowledgement_evidence_fingerprint,
        preparation.request.intake_request_id, preparation.request.delivery_attempt_id,
        preparation.preparation_fingerprint,
    )
    actual = tuple(
        getattr(linkage, field_name)
        for field_name in DeliveryActivationPreflightLinkageV1.model_fields
    )
    normalized_expected = tuple(
        value if isinstance(value, FingerprintV1) else (
            FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=value)
            if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
            else value
        )
        for value in expected
    )
    if actual != normalized_expected:
        raise ValueError("complete v0.20-v0.28 linkage mismatch")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictContractError("duplicate JSON member")
        value[key] = item
    return value


def _raw(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)


def _canonical(value: object) -> bytes:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    normalized = unicodedata.normalize("NFC", json.dumps(
        raw, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ))
    return normalized.encode()


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0) or parsed.microsecond:
        raise ValueError("timestamp must be whole-second UTC")
    return parsed.astimezone(UTC)


def _format(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [name for name in globals() if name.startswith("DeliveryActivationPreflight")]
__all__ += [
    "MAX_FRESHNESS_SECONDS", "StrictContractError", "audit_evidence_fingerprint",
    "evaluate_delivery_activation_preflight", "parse_create_json",
    "preflight_fingerprint", "preflight_lifecycle", "validate_preflight_result",
]
