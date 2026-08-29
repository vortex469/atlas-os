from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.dormant_agent_intake_delivery_wiring.contract import (
    acknowledgement_fingerprint,
)
from app.dormant_agent_intake_delivery_wiring.test_contract import (
    admitted_validation,
    preparation,
)
from app.live_delivery_send_boundary.contract import (
    AgentInstallationIntakeAcknowledgementV1,
    LiveDeliveryAuthenticationReferenceV1,
    LiveDeliveryEndpointV1,
    LiveDeliverySendAuditEvidenceV1,
    LiveDeliverySendCreateV1,
    LiveDeliverySendEvidenceV1,
    LiveDeliverySendIdempotencyV1,
    LiveDeliverySendLinkageV1,
    LiveDeliverySendReceiptV1,
    LiveDeliverySendRedactedErrorV1,
    LiveDeliveryTransportConfigurationV1,
    StrictContractError,
    attempt_fingerprint,
    audit_evidence_fingerprint,
    create_send_attempt,
    idempotency_key_fingerprint,
    parse_create_json,
    receipt_fingerprint,
    send_lifecycle,
    validate_send_attempt,
)
from app.operator_controlled_delivery_enablement.test_contract import OPERATOR, _record

ATTEMPT_ID = "00000000-0000-4000-8000-000000000b01"
CREATED_AT = "2026-08-27T12:00:14Z"


def _configuration(*, enabled: bool = True):
    return LiveDeliveryTransportConfigurationV1(
        enabled=enabled,
        endpoint=LiveDeliveryEndpointV1(
            host="atlas-agent.internal",
            port=8443,
            tls_server_name="atlas-agent.internal",
            ca_bundle_file="/run/atlas/agent-intake-ca.pem",
        ),
        authentication=LiveDeliveryAuthenticationReferenceV1(
            credential_file="/run/secrets/atlas-agent-intake-token"
        ),
    )


def _evidence(tmp_path: Path, *, owner: str = OPERATOR, at: str = CREATED_AT):
    enablement = _record(tmp_path)
    prepared = preparation(tmp_path)
    linkage = LiveDeliverySendLinkageV1(
        **enablement.linkage.model_dump(mode="python"),
        enablement_id=enablement.enablement_id,
        enablement_fingerprint=enablement.enablement_fingerprint,
    )
    return LiveDeliverySendEvidenceV1(
        operator_id=owner,
        authenticated_operator_id=owner,
        resolved_at=at,
        enablement=enablement,
        preparation=prepared,
        linkage=linkage,
    )


def _create(evidence):
    return LiveDeliverySendCreateV1(
        enablement_id=evidence.enablement.enablement_id,
        enablement_fingerprint=evidence.enablement.enablement_fingerprint,
        delivery_preparation_id=evidence.preparation.delivery_preparation_id,
        preparation_fingerprint=evidence.preparation.preparation_fingerprint,
    )


def _attempt(tmp_path: Path):
    evidence = _evidence(tmp_path)
    return create_send_attempt(
        _create(evidence), evidence=evidence, configuration=_configuration(),
        send_attempt_id=ATTEMPT_ID, created_at=CREATED_AT,
        idempotency_key="send-once",
    )


def test_closed_request_duplicate_unknown_and_bounds(tmp_path: Path) -> None:
    create = _create(_evidence(tmp_path))
    payload = json.dumps(create.model_dump(mode="json"))
    assert parse_create_json(payload) == create
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"schema":"duplicate"}')
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"execute":true}')
    with pytest.raises(StrictContractError):
        parse_create_json(b" " * 2049)


def test_valid_immutable_attempt_envelope_and_agent_contracts(tmp_path: Path) -> None:
    attempt, envelope = _attempt(tmp_path)
    assert validate_send_attempt(attempt, operator_id=OPERATOR) == attempt
    assert envelope.request.mode == "intake-evidence-only"
    assert envelope.credential_reference_only and not envelope.credential_material_present
    assert attempt.default_enabled is False and attempt.evidence_only
    assert not any((attempt.network_attempted, attempt.execution_requested,
                    attempt.installation_requested, attempt.mutation_requested,
                    attempt.replay_allowed))
    _, validation = admitted_validation(tmp_path)
    result = validation.agent_result
    assert result is not None and result.admission is not None
    admission = result.admission
    ack_raw = {
        "schema": "agent-installation-intake-acknowledgement-v1",
        "admission_id": admission.admission_id,
        "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
        "intake_request_id": admission.intake_request_id,
        "received_at": admission.received_at,
        "valid_until": admission.valid_until,
        "status": "admitted_for_evidence_only",
        "provenance": "authenticated_core_intake_evidence_only",
        "execution_admission_granted": False, "execution_authorized": False,
        "worker_allowed": False, "mutation_allowed": False, "replay_allowed": False,
    }
    ack_raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(ack_raw).model_dump(mode="json")
    assert AgentInstallationIntakeAcknowledgementV1.model_validate(ack_raw).status == "admitted_for_evidence_only"
    with pytest.raises(ValidationError):
        attempt.network_attempted = True  # type: ignore[misc]


def test_owner_linkage_fingerprint_and_freshness_fail_closed(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    changed = evidence.model_dump(mode="json")
    changed["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValueError, match="ownership"):
        LiveDeliverySendEvidenceV1.model_validate(changed)
    changed = evidence.model_dump(mode="json")
    changed["linkage"]["enablement_id"] = "00000000-0000-4000-8000-000000000b99"
    with pytest.raises(ValueError, match="linkage"):
        LiveDeliverySendEvidenceV1.model_validate(changed)
    attempt, _ = _attempt(tmp_path)
    raw = attempt.model_dump(mode="json")
    raw["attempt_fingerprint"]["value"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        validate_send_attempt(type(attempt).model_validate(raw), operator_id=OPERATOR)
    for at in ("2026-08-27T12:00:42Z", "2026-08-27T12:00:43Z"):
        stale = _evidence(tmp_path, at=at)
        with pytest.raises(ValueError, match="stale|expired"):
            create_send_attempt(
                _create(stale), evidence=stale, configuration=_configuration(),
                send_attempt_id=ATTEMPT_ID, created_at=at, idempotency_key="send-once",
            )


def test_endpoint_credential_shape_and_default_disabled(tmp_path: Path) -> None:
    for endpoint in (
        {"host": "127.0.0.1", "port": 8443, "tls_server_name": "127.0.0.1", "ca_bundle_file": "/ca.pem"},
        {"host": "agent.internal", "port": 8443, "tls_server_name": "other.internal", "ca_bundle_file": "/ca.pem"},
        {"host": "agent.internal", "port": 8443, "tls_server_name": "agent.internal", "ca_bundle_file": "relative.pem"},
    ):
        with pytest.raises(ValidationError):
            LiveDeliveryEndpointV1.model_validate(endpoint)
    with pytest.raises(ValidationError):
        LiveDeliveryAuthenticationReferenceV1(credential_file="/run/../secret")
    evidence = _evidence(tmp_path)
    with pytest.raises(ValueError, match="default-disabled"):
        create_send_attempt(
            _create(evidence), evidence=evidence, configuration=_configuration(enabled=False),
            send_attempt_id=ATTEMPT_ID, created_at=CREATED_AT, idempotency_key="send-once",
        )


def test_ambiguity_receipt_redaction_and_no_replay(tmp_path: Path) -> None:
    attempt, _ = _attempt(tmp_path)
    assert send_lifecycle(attempt, now=CREATED_AT) == "reserved"
    assert send_lifecycle(attempt, now=CREATED_AT, send_started=True) == "sending"
    assert send_lifecycle(attempt, now=CREATED_AT, process_lost=True) == "ambiguous"
    error = LiveDeliverySendRedactedErrorV1(error_code="ambiguous", correlation_id="send-1")
    raw = {
        "schema": "live-delivery-send-receipt-v1",
        "send_attempt_id": attempt.send_attempt_id,
        "attempt_fingerprint": attempt.attempt_fingerprint.model_dump(mode="json"),
        "completed_at": CREATED_AT, "lifecycle": "ambiguous", "http_status_class": "none",
        "response_fingerprint": None, "admission_fingerprint": None,
        "acknowledgement_fingerprint": None, "agent_audit_evidence_fingerprint": None,
        "redacted_error": error.model_dump(mode="json"), "agent_contacted": True,
        "evidence_admitted": False, "execution_admission_granted": False,
        "execution_authorized": False, "installation_allowed": False,
        "worker_allowed": False, "workflow_allowed": False, "deployment_allowed": False,
        "mutation_allowed": False, "replay_allowed": False,
    }
    raw["receipt_fingerprint"] = receipt_fingerprint(raw).model_dump(mode="json")
    receipt = LiveDeliverySendReceiptV1.model_validate(raw)
    assert receipt.lifecycle == "ambiguous" and not receipt.replay_allowed
    changed = raw | {"evidence_admitted": True}
    changed["receipt_fingerprint"] = receipt_fingerprint(changed).model_dump(mode="json")
    with pytest.raises(ValueError, match="ambiguous"):
        LiveDeliverySendReceiptV1.model_validate(changed)


def test_idempotency_audit_and_deterministic_fingerprints(tmp_path: Path) -> None:
    attempt, envelope = _attempt(tmp_path)
    assert attempt.attempt_fingerprint == attempt_fingerprint(attempt, operator_id=OPERATOR)
    key_fp = idempotency_key_fingerprint(operator_id=OPERATOR, idempotency_key="send-once")
    reservation = LiveDeliverySendIdempotencyV1(
        operator_id=OPERATOR, key="send-once", enablement_id=attempt.linkage.enablement_id,
        enablement_fingerprint=attempt.linkage.enablement_fingerprint,
        preflight_id=attempt.linkage.preflight_id,
        preparation_id=attempt.linkage.delivery_preparation_id,
        request_id=attempt.linkage.intake_request_id,
        send_attempt_id=attempt.send_attempt_id, attempt_fingerprint=attempt.attempt_fingerprint,
    )
    assert reservation.reservation_before_io and reservation.exact_retry_zero_io
    raw = {
        "schema": "live-delivery-send-audit-evidence-v1",
        "send_attempt_id": attempt.send_attempt_id,
        "attempt_fingerprint": attempt.attempt_fingerprint.model_dump(mode="json"),
        "correlation_id": "send-1", "idempotency_key_fingerprint": key_fp.model_dump(mode="json"),
        "endpoint_fingerprint": envelope.endpoint_fingerprint.model_dump(mode="json"),
        "request_fingerprint": attempt.request_fingerprint.model_dump(mode="json"),
        "receipt_fingerprint": None, "created_at": attempt.created_at, "completed_at": None,
        "lifecycle": "reserved", "agent_disposition": "not_contacted", "evidence_only": True,
        "execution_admission_granted": False, "execution_authorized": False,
        "installation_allowed": False, "worker_allowed": False, "workflow_allowed": False,
        "deployment_allowed": False, "mutation_allowed": False, "replay_allowed": False,
    }
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw).model_dump(mode="json")
    assert LiveDeliverySendAuditEvidenceV1.model_validate(raw).evidence_fingerprint == audit_evidence_fingerprint(raw)


def test_contract_has_no_forbidden_imports_or_calls() -> None:
    tree = ast.parse(Path(__file__).with_name("contract.py").read_text())
    forbidden = {"httpx", "requests", "socket", "ssl", "subprocess", "docker", "podman"}
    imports = {alias.name.split(".")[0] for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    calls = {getattr(node.func, "id", "") for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert imports.isdisjoint(forbidden)
    assert calls.isdisjoint({"open", "exec", "eval", "system", "run", "Popen"})
