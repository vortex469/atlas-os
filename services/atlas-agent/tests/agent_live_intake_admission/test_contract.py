from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from app.agent_live_intake_admission.contract import (
    AgentLiveIntakeAcknowledgementV1,
    AgentLiveIntakeAdmissionV1,
    AgentLiveIntakeAuditEvidenceV1,
    AgentLiveIntakeAuthenticationContextV1,
    AgentLiveIntakeAuthenticationReferenceV1,
    AgentLiveIntakeAuthenticationResultV1,
    AgentLiveIntakeEnvelopeV1,
    AgentLiveIntakeIdempotencyV1,
    AgentLiveIntakeLinkageV1,
    AgentLiveIntakeReceiptV1,
    AgentLiveIntakeRedactedErrorV1,
    AgentLiveIntakeResultV1,
    AgentLiveIntakeSendAttemptV1,
    AgentLiveIntakeSourceV1,
    AgentLiveIntakeStatusV1,
    StrictContractError,
    acknowledgement_fingerprint,
    admission_fingerprint,
    admission_lifecycle,
    attempt_fingerprint,
    audit_evidence_fingerprint,
    envelope_fingerprint,
    idempotency_key_fingerprint,
    linkage_fingerprint,
    operator_fingerprint,
    parse_envelope_json,
    record_fingerprint,
    request_body_fingerprint,
    validate_admission_input,
)
from app.real_agent_intake_boundary.models import (
    AgentInstallationIntakeRequestV1,
    dispatch_envelope_fingerprint,
    request_fingerprint,
)
from pydantic import ValidationError

OPERATOR = "operator-a"
CREATED = "2026-08-29T12:00:20Z"
RECEIVED = "2026-08-29T12:00:25Z"
EXPIRES = "2026-08-29T12:00:50Z"
ATTEMPT_ID = "00000000-0000-4000-8000-000000003101"
ADMISSION_ID = "00000000-0000-4000-8000-000000003201"
ACK_ID = "00000000-0000-4000-8000-000000003202"


def fp(character: str) -> dict[str, str]:
    return {"algorithm": "sha256", "canonicalization": "atlas-jcs-nfc-v1", "value": character * 64}


def request() -> AgentInstallationIntakeRequestV1:
    dispatch: dict[str, object] = {
        "schema": "installation-dispatch-envelope-v1",
        "dispatch_envelope_id": "00000000-0000-4000-8000-000000000401",
        "prepared_at": "2026-08-29T12:00:00Z",
        "valid_until": EXPIRES,
        "operation": "install-container",
        "mode": "handoff-only",
        "recipient": {"service": "atlas-agent", "intake_contract": "agent-installation-dispatch-intake-v1"},
        "linkage": {
            "candidate_record_id": "00000000-0000-4000-8000-000000000201",
            "candidate_envelope_fingerprint": fp("1"),
            "admission_fingerprint": fp("2"),
            "candidate_record_fingerprint": fp("3"),
            "approval_intent_id": "00000000-0000-4000-8000-000000000211",
            "approval_intent_fingerprint": fp("4"),
            "agent_request_id": "00000000-0000-4000-8000-000000000221",
            "agent_request_fingerprint": fp("5"),
            "agent_validation_fingerprint": fp("6"),
            "agent_evidence_fingerprint": fp("7"),
            "destination_fingerprint": "8" * 64,
            "source_plan_fingerprint": fp("9"),
            "artifact_policy_fingerprint": fp("a"),
            "execution_request_id": "00000000-0000-4000-8000-000000000231",
            "execution_request_fingerprint": fp("b"),
        },
        "statement": "core_prepared_non_executing_agent_handoff",
        "delivery_authorized": False,
        "agent_admission_authorized": False,
        "execution_authorized": False,
        "mutation_authorized": False,
        "replay_allowed": False,
    }
    dispatch["dispatch_envelope_fingerprint"] = dispatch_envelope_fingerprint(
        operator_id=OPERATOR, envelope=dispatch
    ).model_dump(mode="json")
    raw: dict[str, object] = {
        "schema": "agent-installation-intake-request-v1",
        "intake_request_id": "00000000-0000-4000-8000-000000000701",
        "delivery_attempt_id": "00000000-0000-4000-8000-000000000702",
        "sent_at": CREATED,
        "expires_at": EXPIRES,
        "operation": "install-container",
        "mode": "intake-evidence-only",
        "sender": "atlas-core",
        "recipient": {"service": "atlas-agent", "intake_contract": "agent-installation-intake-v1"},
        "operator_assertion": {"operator_id": OPERATOR, "asserted_by": "atlas-core"},
        "envelope": dispatch,
        "prior_evidence": {
            "intake_simulation": {
                "simulation_request_id": "00000000-0000-4000-8000-000000000501",
                "intake_record_id": "00000000-0000-4000-8000-000000000502",
                "intake_record_fingerprint": fp("c"),
            },
            "simulated_delivery": {
                "simulated_delivery_id": "00000000-0000-4000-8000-000000000601",
                "simulated_delivery_fingerprint": fp("d"),
                "delivery_record_fingerprint": fp("e"),
                "acknowledgement_id": "00000000-0000-4000-8000-000000000603",
                "acknowledgement_fingerprint": fp("f"),
            },
        },
        "delivery_authorized": True,
        "evidence_admission_requested": True,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["request_fingerprint"] = request_fingerprint(raw).model_dump(mode="json")
    return AgentInstallationIntakeRequestV1.model_validate(raw)


def linkage(req: AgentInstallationIntakeRequestV1) -> AgentLiveIntakeLinkageV1:
    dispatch = req.envelope
    prior = req.prior_evidence
    return AgentLiveIntakeLinkageV1(
        candidate_record_id=dispatch.linkage.candidate_record_id,
        candidate_envelope_fingerprint=dispatch.linkage.candidate_envelope_fingerprint,
        candidate_record_fingerprint=dispatch.linkage.candidate_record_fingerprint,
        approval_intent_id=dispatch.linkage.approval_intent_id,
        approval_intent_fingerprint=dispatch.linkage.approval_intent_fingerprint,
        agent_request_id=dispatch.linkage.agent_request_id,
        agent_request_fingerprint=dispatch.linkage.agent_request_fingerprint,
        agent_validation_fingerprint=dispatch.linkage.agent_validation_fingerprint,
        agent_audit_evidence_fingerprint=fp("1"),
        destination_fingerprint=fp("2"),
        source_plan_fingerprint=dispatch.linkage.source_plan_fingerprint,
        artifact_policy_fingerprint=dispatch.linkage.artifact_policy_fingerprint,
        execution_request_id=dispatch.linkage.execution_request_id,
        execution_request_fingerprint=dispatch.linkage.execution_request_fingerprint,
        dispatch_envelope_id=dispatch.dispatch_envelope_id,
        dispatch_envelope_fingerprint=dispatch.dispatch_envelope_fingerprint,
        simulation_request_id=prior.intake_simulation.simulation_request_id,
        intake_record_id=prior.intake_simulation.intake_record_id,
        intake_record_fingerprint=prior.intake_simulation.intake_record_fingerprint,
        intake_simulation_evidence_fingerprint=fp("3"),
        simulated_delivery_id=prior.simulated_delivery.simulated_delivery_id,
        simulated_delivery_fingerprint=prior.simulated_delivery.simulated_delivery_fingerprint,
        delivery_record_fingerprint=prior.simulated_delivery.delivery_record_fingerprint,
        simulated_delivery_evidence_fingerprint=fp("4"),
        simulated_acknowledgement_id=prior.simulated_delivery.acknowledgement_id,
        simulated_acknowledgement_fingerprint=prior.simulated_delivery.acknowledgement_fingerprint,
        simulated_acknowledgement_evidence_fingerprint=fp("5"),
        intake_request_id=req.intake_request_id,
        delivery_attempt_id=req.delivery_attempt_id,
        dormant_preparation_fingerprint=fp("6"),
        delivery_preparation_id="00000000-0000-4000-8000-000000002801",
        preparation_fingerprint=fp("7"),
        preflight_id="00000000-0000-4000-8000-000000002901",
        preflight_fingerprint=fp("8"),
        enablement_id="00000000-0000-4000-8000-000000003001",
        enablement_fingerprint=fp("9"),
    )


def canonical(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")  # type: ignore[union-attr]
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def envelope() -> AgentLiveIntakeEnvelopeV1:
    req = request()
    body_fp = request_body_fingerprint(canonical(req))
    endpoint_fp = fp("a")
    attempt_raw = {
        "schema": "live-delivery-send-attempt-v1",
        "send_attempt_id": ATTEMPT_ID,
        "created_at": CREATED,
        "expires_at": EXPIRES,
        "operator_id": OPERATOR,
        "linkage": linkage(req).model_dump(mode="json"),
        "endpoint_fingerprint": endpoint_fp,
        "request_fingerprint": req.request_fingerprint.model_dump(mode="json"),
        "request_body_fingerprint": body_fp.model_dump(mode="json"),
        "lifecycle_at_creation": "reserved",
        "default_enabled": False,
        "network_attempted": False,
        "evidence_only": True,
        "execution_requested": False,
        "installation_requested": False,
        "mutation_requested": False,
        "replay_allowed": False,
    }
    attempt_raw["attempt_fingerprint"] = attempt_fingerprint(attempt_raw).model_dump(mode="json")
    attempt = AgentLiveIntakeSendAttemptV1.model_validate(attempt_raw)
    raw = {
        "schema": "agent-live-intake-envelope-v1",
        "send_attempt": attempt.model_dump(mode="json"),
        "intake_request": req.model_dump(mode="json"),
        "request_fingerprint": req.request_fingerprint.model_dump(mode="json"),
        "request_body_fingerprint": body_fp.model_dump(mode="json"),
        "idempotency_key_fingerprint": idempotency_key_fingerprint(OPERATOR, "send-once").model_dump(mode="json"),
        "endpoint_fingerprint": endpoint_fp,
        "content_type": "application/json",
        "credential_reference_only": True,
        "credential_material_present": False,
        "one_shot_only": True,
        "automatic_retries": 0,
        "evidence_only": True,
        "execution_authorized": False,
        "installation_allowed": False,
        "worker_allowed": False,
        "workflow_allowed": False,
        "deployment_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["envelope_fingerprint"] = envelope_fingerprint(raw).model_dump(mode="json")
    return AgentLiveIntakeEnvelopeV1.model_validate(raw)


def admission(env: AgentLiveIntakeEnvelopeV1) -> AgentLiveIntakeAdmissionV1:
    raw = {
        "schema": "agent-live-intake-admission-v1",
        "admission_id": ADMISSION_ID,
        "send_attempt_id": env.send_attempt.send_attempt_id,
        "attempt_fingerprint": env.send_attempt.attempt_fingerprint.model_dump(mode="json"),
        "envelope_fingerprint": env.envelope_fingerprint.model_dump(mode="json"),
        "intake_request_id": env.intake_request.intake_request_id,
        "request_fingerprint": env.request_fingerprint.model_dump(mode="json"),
        "delivery_attempt_id": env.intake_request.delivery_attempt_id,
        "received_at": RECEIVED,
        "valid_until": EXPIRES,
        "operator_id": OPERATOR,
        "linkage": env.send_attempt.linkage.model_dump(mode="json"),
        "status": "admitted_for_evidence_only",
        "statement": "agent_admitted_authenticated_live_delivery_evidence_only",
        "delivery_received": True,
        "evidence_admission_granted": True,
        "execution_admission_granted": False,
        "execution_authorized": False,
        "installation_allowed": False,
        "worker_allowed": False,
        "workflow_allowed": False,
        "deployment_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["admission_fingerprint"] = admission_fingerprint(raw).model_dump(mode="json")
    return AgentLiveIntakeAdmissionV1.model_validate(raw)


def acknowledgement(item: AgentLiveIntakeAdmissionV1) -> AgentLiveIntakeAcknowledgementV1:
    raw = {
        "schema": "agent-live-intake-acknowledgement-v1",
        "acknowledgement_id": ACK_ID,
        "admission_id": item.admission_id,
        "admission_fingerprint": item.admission_fingerprint.model_dump(mode="json"),
        "send_attempt_id": item.send_attempt_id,
        "attempt_fingerprint": item.attempt_fingerprint.model_dump(mode="json"),
        "intake_request_id": item.intake_request_id,
        "received_at": item.received_at,
        "valid_until": item.valid_until,
        "status": "admitted_for_evidence_only",
        "provenance": "authenticated_core_live_intake_evidence_only",
        "execution_admission_granted": False,
        "execution_authorized": False,
        "installation_allowed": False,
        "worker_allowed": False,
        "workflow_allowed": False,
        "deployment_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(raw).model_dump(mode="json")
    return AgentLiveIntakeAcknowledgementV1.model_validate(raw)


def test_valid_closed_immutable_envelope_admission_ack_result_and_receipt() -> None:
    env = envelope()
    item = admission(env)
    ack = acknowledgement(item)
    result = AgentLiveIntakeResultV1(
        send_attempt_id=item.send_attempt_id,
        intake_request_id=item.intake_request_id,
        outcome="admitted_for_evidence_only",
        admission=item,
        acknowledgement=ack,
        reason_code=None,
    )
    record_raw = {
        "admission": item.model_dump(mode="json"),
        "acknowledgement": ack.model_dump(mode="json"),
        "credential_reference_fingerprint": fp("b"),
    }
    record_raw["record_fingerprint"] = record_fingerprint(record_raw).model_dump(mode="json")
    record = AgentLiveIntakeReceiptV1.model_validate(record_raw)
    assert result.outcome == record.lifecycle_at_creation == "admitted_for_evidence_only"
    assert record.default_enabled is False and record.evidence_only
    with pytest.raises(ValidationError):
        item.status = "executing"  # type: ignore[misc]


def test_closed_json_duplicate_unknown_and_bounds() -> None:
    env = envelope()
    payload = canonical(env)
    assert parse_envelope_json(payload) == env
    with pytest.raises(StrictContractError):
        parse_envelope_json(payload[:-1] + b',"schema":"duplicate"}')
    with pytest.raises(StrictContractError):
        parse_envelope_json(payload[:-1] + b',"execute":true}')
    with pytest.raises(StrictContractError):
        parse_envelope_json(b" " * (128 * 1024 + 1))


def test_fingerprints_owner_linkage_and_freshness_fail_closed() -> None:
    env = envelope()
    raw = env.model_dump(mode="json")
    raw["envelope_fingerprint"] = fp("0")
    with pytest.raises(ValueError, match="fingerprint"):
        AgentLiveIntakeEnvelopeV1.model_validate(raw)
    raw = env.model_dump(mode="json")
    raw["send_attempt"]["operator_id"] = "operator-b"
    raw["send_attempt"]["attempt_fingerprint"] = attempt_fingerprint(raw["send_attempt"]).model_dump(mode="json")
    raw["envelope_fingerprint"] = envelope_fingerprint(raw).model_dump(mode="json")
    with pytest.raises(ValueError, match="ownership"):
        AgentLiveIntakeEnvelopeV1.model_validate(raw)
    with pytest.raises(ValueError, match="ownership"):
        validate_admission_input(env, operator_id="operator-b", received_at=RECEIVED, endpoint_fingerprint_value=env.endpoint_fingerprint)
    with pytest.raises(ValueError, match="stale|expired"):
        validate_admission_input(env, operator_id=OPERATOR, received_at=EXPIRES, endpoint_fingerprint_value=env.endpoint_fingerprint)
    assert validate_admission_input(env, operator_id=OPERATOR, received_at=RECEIVED, endpoint_fingerprint_value=env.endpoint_fingerprint) == env


def test_authentication_source_and_redaction_shapes() -> None:
    reference = AgentLiveIntakeAuthenticationReferenceV1(credential_file="/run/secrets/atlas-agent-intake-token")
    source = AgentLiveIntakeSourceV1(host="atlas-agent.internal")
    context = AgentLiveIntakeAuthenticationContextV1(source=source, credential_reference=reference)
    assert context.internal_https and not context.credential_material_present
    auth = AgentLiveIntakeAuthenticationResultV1(
        outcome="authenticated",
        principal="atlas-core/install-intake-v1",
        permission="installation_intake:create",
        source_identity="atlas-core.internal",
        credential_reference_fingerprint=fp("c"),
    )
    assert auth.redacted
    for bad in ("relative", "/run/../secret", "/run//secret"):
        with pytest.raises(ValidationError):
            AgentLiveIntakeAuthenticationReferenceV1(credential_file=bad)
    for bad in ("http", "127.0.0.1", "localhost"):
        with pytest.raises(ValidationError):
            AgentLiveIntakeSourceV1(**({"scheme": bad, "host": "agent.internal"} if bad == "http" else {"host": bad}))
    with pytest.raises(ValidationError):
        AgentLiveIntakeAuthenticationResultV1(outcome="rejected", principal="atlas-core/install-intake-v1", permission=None, source_identity=None, credential_reference_fingerprint=None)
    error = AgentLiveIntakeRedactedErrorV1(error_code="unavailable", correlation_id="intake-1")
    assert error.redacted and not error.retryable and "secret" not in error.model_dump_json()


def test_idempotency_status_audit_and_fixed_false_authority() -> None:
    env = envelope()
    item = admission(env)
    ack = acknowledgement(item)
    reservation = AgentLiveIntakeIdempotencyV1(
        operator_id=OPERATOR,
        key="send-once",
        idempotency_key_fingerprint=idempotency_key_fingerprint(OPERATOR, "send-once"),
        send_attempt_id=item.send_attempt_id,
        attempt_fingerprint=item.attempt_fingerprint,
        envelope_fingerprint=item.envelope_fingerprint,
        enablement_id=item.linkage.enablement_id,
        preflight_id=item.linkage.preflight_id,
        delivery_preparation_id=item.linkage.delivery_preparation_id,
        intake_request_id=item.intake_request_id,
        admission_id=item.admission_id,
        admission_fingerprint=item.admission_fingerprint,
    )
    assert reservation.reservation_permanent and reservation.exact_duplicate_only and not reservation.replay_allowed
    status = AgentLiveIntakeStatusV1(admission_id=item.admission_id, send_attempt_id=item.send_attempt_id, operator_id=OPERATOR, observed_at=RECEIVED, valid_until=EXPIRES, lifecycle="admitted_for_evidence_only")
    assert status.default_enabled is False and not status.execution_authorized
    assert admission_lifecycle(item, observed_at=RECEIVED) == "admitted_for_evidence_only"
    assert admission_lifecycle(item, observed_at=EXPIRES) == "expired"
    audit_raw = {
        "admission_id": item.admission_id,
        "admission_fingerprint": item.admission_fingerprint.model_dump(mode="json"),
        "acknowledgement_fingerprint": ack.acknowledgement_fingerprint.model_dump(mode="json"),
        "record_fingerprint": fp("d"),
        "send_attempt_id": item.send_attempt_id,
        "attempt_fingerprint": item.attempt_fingerprint.model_dump(mode="json"),
        "envelope_fingerprint": item.envelope_fingerprint.model_dump(mode="json"),
        "request_fingerprint": item.request_fingerprint.model_dump(mode="json"),
        "linkage_fingerprint": linkage_fingerprint(item.linkage).model_dump(mode="json"),
        "operator_fingerprint": operator_fingerprint(OPERATOR).model_dump(mode="json"),
        "correlation_id": "intake-1",
        "received_at": RECEIVED,
        "completed_at": RECEIVED,
        "lifecycle": "admitted_for_evidence_only",
    }
    audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(audit_raw).model_dump(mode="json")
    audit = AgentLiveIntakeAuditEvidenceV1.model_validate(audit_raw)
    assert audit.evidence_fingerprint == audit_evidence_fingerprint(audit)
    changed = reservation.model_dump(mode="json")
    changed["replay_allowed"] = True
    with pytest.raises(ValidationError):
        AgentLiveIntakeIdempotencyV1.model_validate(changed)


def test_no_forbidden_runtime_imports_or_calls() -> None:
    source = Path("services/atlas-agent/app/agent_live_intake_admission/contract.py").read_text()
    tree = ast.parse(source)
    forbidden = {"subprocess", "docker", "podman", "socket", "requests", "httpx", "workflow", "worker"}
    imported = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported & forbidden
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "system", "run", "Popen"}
