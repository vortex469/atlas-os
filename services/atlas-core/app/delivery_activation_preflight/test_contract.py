from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.delivery_activation_preflight.contract import (
    DeliveryActivationPreflightAuditEvidenceV1,
    DeliveryActivationPreflightConfigurationV1,
    DeliveryActivationPreflightCreateV1,
    DeliveryActivationPreflightEvidenceV1,
    DeliveryActivationPreflightIdempotencyV1,
    DeliveryActivationPreflightLifecycleInputsV1,
    DeliveryActivationPreflightLinkageV1,
    DeliveryActivationPreflightRedactedErrorV1,
    StrictContractError,
    audit_evidence_fingerprint,
    evaluate_delivery_activation_preflight,
    parse_create_json,
    preflight_fingerprint,
    preflight_lifecycle,
    validate_preflight_result,
)
from app.dormant_agent_intake_delivery_wiring.test_contract import OPERATOR, preparation
from app.installation_dispatch_handoff.contract import FingerprintV1

PREFLIGHT_ID = "00000000-0000-4000-8000-000000000901"
EVALUATED_AT = "2026-08-27T12:00:12Z"


def _fingerprint(value: str) -> FingerprintV1:
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=value
    )


def _linkage(value) -> DeliveryActivationPreflightLinkageV1:
    envelope = value.request.envelope
    upstream, source = envelope.linkage, value.source
    return DeliveryActivationPreflightLinkageV1(
        candidate_record_id=upstream.candidate_record_id,
        candidate_envelope_fingerprint=upstream.candidate_envelope_fingerprint,
        candidate_record_fingerprint=upstream.candidate_record_fingerprint,
        approval_intent_id=upstream.approval_intent_id,
        approval_intent_fingerprint=upstream.approval_intent_fingerprint,
        agent_request_id=upstream.agent_request_id,
        agent_request_fingerprint=upstream.agent_request_fingerprint,
        agent_validation_fingerprint=upstream.agent_validation_fingerprint,
        agent_audit_evidence_fingerprint=upstream.agent_evidence_fingerprint,
        destination_fingerprint=_fingerprint(upstream.destination_fingerprint),
        source_plan_fingerprint=upstream.source_plan_fingerprint,
        artifact_policy_fingerprint=upstream.artifact_policy_fingerprint,
        execution_request_id=upstream.execution_request_id,
        execution_request_fingerprint=upstream.execution_request_fingerprint,
        dispatch_envelope_id=envelope.dispatch_envelope_id,
        dispatch_envelope_fingerprint=envelope.dispatch_envelope_fingerprint,
        simulation_request_id=value.request.prior_evidence.intake_simulation.simulation_request_id,
        intake_record_id=source.intake_record_id,
        intake_record_fingerprint=source.intake_record_fingerprint,
        intake_simulation_evidence_fingerprint=source.intake_simulation_evidence_fingerprint,
        simulated_delivery_id=source.simulated_delivery_id,
        simulated_delivery_fingerprint=source.simulated_delivery_fingerprint,
        delivery_record_fingerprint=source.delivery_record_fingerprint,
        simulated_delivery_evidence_fingerprint=source.simulated_delivery_evidence_fingerprint,
        simulated_acknowledgement_id=source.simulated_acknowledgement_id,
        simulated_acknowledgement_fingerprint=source.simulated_acknowledgement_fingerprint,
        simulated_acknowledgement_evidence_fingerprint=source.simulated_acknowledgement_evidence_fingerprint,
        intake_request_id=value.request.intake_request_id,
        delivery_attempt_id=value.request.delivery_attempt_id,
        dormant_preparation_fingerprint=value.preparation_fingerprint,
    )


def _evidence(tmp_path: Path, *, at: str = EVALUATED_AT, owner: str = OPERATOR):
    value = preparation(tmp_path)
    return DeliveryActivationPreflightEvidenceV1(
        operator_id=owner,
        authenticated_operator_id=owner,
        resolved_at=at,
        preparation=value,
        linkage=_linkage(value),
        lifecycle=DeliveryActivationPreflightLifecycleInputsV1(),
    )


def _create(evidence: DeliveryActivationPreflightEvidenceV1):
    return DeliveryActivationPreflightCreateV1(
        delivery_preparation_id=evidence.preparation.delivery_preparation_id,
        preparation_fingerprint=evidence.preparation.preparation_fingerprint,
    )


def _result(tmp_path: Path, *, enabled: bool = True, at: str = EVALUATED_AT):
    evidence = _evidence(tmp_path, at=at)
    return evaluate_delivery_activation_preflight(
        _create(evidence), evidence=evidence,
        configuration=DeliveryActivationPreflightConfigurationV1(enabled=enabled),
        preflight_id=PREFLIGHT_ID, evaluated_at=at,
    )


def test_closed_schemas_duplicate_unknown_and_body_bound(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    payload = json.dumps(_create(evidence).model_dump(mode="json"))
    assert parse_create_json(payload) == _create(evidence)
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"schema":"duplicate"}')
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"activate":true}')
    with pytest.raises(StrictContractError):
        parse_create_json(b" " * 1025)
    with pytest.raises(ValidationError):
        DeliveryActivationPreflightConfigurationV1(enabled=False, transport=True)  # type: ignore[call-arg]


def test_valid_request_result_are_immutable_and_non_activating(tmp_path: Path) -> None:
    value = _result(tmp_path)
    assert value.decision == "eligible_for_later_activation"
    assert preflight_lifecycle(value, now=value.evaluated_at) == "eligible"
    assert preflight_lifecycle(value, now=value.expires_at) == "expired"
    assert not any((value.default_enabled, value.agent_contacted, value.credentials_loaded,
                    value.production_transport_registered, value.delivery_activated,
                    value.delivery_authorized, value.execution_admission_granted,
                    value.execution_authorized, value.worker_allowed,
                    value.mutation_allowed, value.replay_allowed))
    with pytest.raises(ValidationError):
        value.delivery_activated = True  # type: ignore[misc]


def test_missing_invalid_fingerprints_and_owner_linkage_mismatch(tmp_path: Path) -> None:
    value = _result(tmp_path)
    raw = value.model_dump(mode="json")
    del raw["preflight_fingerprint"]
    with pytest.raises(ValidationError):
        type(value).model_validate(raw)
    raw = value.model_dump(mode="json")
    raw["preflight_fingerprint"]["value"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        validate_preflight_result(type(value).model_validate(raw), operator_id=OPERATOR)
    with pytest.raises(ValueError, match="ownership|fingerprint"):
        _evidence(tmp_path, owner="operator-b")
    evidence = _evidence(tmp_path)
    changed = evidence.model_dump(mode="json")
    changed["linkage"]["intake_request_id"] = "00000000-0000-4000-8000-000000000999"
    with pytest.raises(ValueError, match="linkage"):
        DeliveryActivationPreflightEvidenceV1.model_validate(changed)


def test_stale_expired_and_default_disabled(tmp_path: Path) -> None:
    stale = _result(tmp_path, at="2026-08-27T12:00:33Z")
    assert stale.decision == "ineligible" and stale.reason_codes == ("expired",)
    expired = _result(tmp_path, at="2026-08-27T12:01:01Z")
    assert expired.decision == "ineligible" and "expired" in expired.reason_codes
    disabled = _result(tmp_path, enabled=False)
    assert disabled.reason_codes == ("preflight_feature_disabled",)
    assert disabled.expires_at == disabled.evaluated_at


def test_redacted_error_idempotency_audit_and_determinism(tmp_path: Path) -> None:
    value = _result(tmp_path)
    assert value.preflight_fingerprint == preflight_fingerprint(value, operator_id=OPERATOR)
    assert preflight_fingerprint(value, operator_id=OPERATOR) != preflight_fingerprint(
        value, operator_id="operator-b"
    )
    error = DeliveryActivationPreflightRedactedErrorV1(
        error_code="unavailable", correlation_id="preflight-1"
    )
    assert error.redacted and "detail" not in error.model_dump()
    reservation = DeliveryActivationPreflightIdempotencyV1(
        operator_id=OPERATOR, key="one-key",
        delivery_preparation_id=value.delivery_preparation_id,
        preparation_fingerprint=value.preparation_fingerprint,
        intake_request_id=value.linkage.intake_request_id,
        delivery_attempt_id=value.linkage.delivery_attempt_id,
        preflight_id=value.preflight_id,
        preflight_fingerprint=value.preflight_fingerprint,
    )
    assert reservation.reservation_permanent and not reservation.replay_allowed
    audit_raw = {
        "schema": "delivery-activation-preflight-audit-evidence-v1",
        "preflight_id": value.preflight_id,
        "preflight_fingerprint": value.preflight_fingerprint.model_dump(mode="json"),
        "delivery_preparation_id": value.delivery_preparation_id,
        "preparation_fingerprint": value.preparation_fingerprint.model_dump(mode="json"),
        "intake_request_id": value.linkage.intake_request_id,
        "delivery_attempt_id": value.linkage.delivery_attempt_id,
        "evaluated_at": value.evaluated_at, "expires_at": value.expires_at,
        "lifecycle": "eligible", "decision": value.decision, "reason_codes": [],
        "provenance": "core_delivery_activation_preflight_v1",
        "delivery_activated": False, "delivery_authorized": False,
        "execution_authorized": False, "mutation_allowed": False,
        "replay_allowed": False,
    }
    audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(audit_raw).model_dump(mode="json")
    audit = DeliveryActivationPreflightAuditEvidenceV1.model_validate(audit_raw)
    assert audit.evidence_fingerprint == audit_evidence_fingerprint(audit)


def test_contract_has_no_forbidden_imports_or_calls() -> None:
    tree = ast.parse(Path(__file__).with_name("contract.py").read_text())
    forbidden = {"httpx", "requests", "socket", "subprocess", "docker", "podman"}
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports.isdisjoint(forbidden)
    calls = {getattr(node.func, "id", "") for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert calls.isdisjoint({"open", "exec", "eval", "system", "run", "Popen"})
