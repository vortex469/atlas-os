from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from app.agent_intake_simulation.models import dispatch_envelope_fingerprint
from app.real_agent_intake_boundary import (
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeEvidenceContextV1,
    AgentInstallationIntakeRedactedErrorV1,
    AgentInstallationIntakeRequestV1,
    AgentInstallationIntakeResultV1,
    StrictContractError,
    admission_fingerprint,
    intake_lifecycle,
    parse_intake_request_json,
    request_fingerprint,
    validate_real_intake,
)
from pydantic import ValidationError

OPERATOR = "operator-a"


def fp(character: str) -> dict[str, str]:
    return {
        "algorithm": "sha256",
        "canonicalization": "atlas-jcs-nfc-v1",
        "value": character * 64,
    }


def envelope_dict() -> dict[str, object]:
    raw: dict[str, object] = {
        "schema": "installation-dispatch-envelope-v1",
        "dispatch_envelope_id": "00000000-0000-4000-8000-000000000401",
        "prepared_at": "2026-08-29T12:00:00Z",
        "valid_until": "2026-08-29T12:01:00Z",
        "operation": "install-container",
        "mode": "handoff-only",
        "recipient": {
            "service": "atlas-agent",
            "intake_contract": "agent-installation-dispatch-intake-v1",
        },
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
    raw["dispatch_envelope_fingerprint"] = dispatch_envelope_fingerprint(
        operator_id=OPERATOR, envelope=raw
    ).model_dump(mode="json")
    return raw


def prior_evidence() -> dict[str, object]:
    return {
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
    }


def request_dict() -> dict[str, object]:
    raw: dict[str, object] = {
        "schema": "agent-installation-intake-request-v1",
        "intake_request_id": "00000000-0000-4000-8000-000000000701",
        "delivery_attempt_id": "00000000-0000-4000-8000-000000000702",
        "sent_at": "2026-08-29T12:00:20Z",
        "expires_at": "2026-08-29T12:01:00Z",
        "operation": "install-container",
        "mode": "intake-evidence-only",
        "sender": "atlas-core",
        "recipient": {
            "service": "atlas-agent",
            "intake_contract": "agent-installation-intake-v1",
        },
        "operator_assertion": {"operator_id": OPERATOR, "asserted_by": "atlas-core"},
        "envelope": envelope_dict(),
        "prior_evidence": prior_evidence(),
        "delivery_authorized": True,
        "evidence_admission_requested": True,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["request_fingerprint"] = request_fingerprint(raw).model_dump(mode="json")
    return raw


def contexts(request: AgentInstallationIntakeRequestV1):
    auth = AgentInstallationIntakeAuthenticationContextV1()
    evidence = AgentInstallationIntakeEvidenceContextV1(
        operator_id=OPERATOR,
        linkage=request.envelope.linkage,
        prior_evidence=request.prior_evidence,
        intake_record_observed_at="2026-08-29T12:00:10Z",
        acknowledgement_acknowledged_at="2026-08-29T12:00:12Z",
    )
    return auth, evidence


def validation():
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    auth, evidence = contexts(request)
    return validate_real_intake(
        request,
        authentication=auth,
        evidence=evidence,
        received_at="2026-08-29T12:00:25Z",
        admission_id="00000000-0000-4000-8000-000000000703",
    )


def test_closed_duplicate_unknown_immutable_and_valid_model() -> None:
    raw = request_dict()
    request = parse_intake_request_json(json.dumps(raw))
    with pytest.raises(ValidationError):
        request.sender = "other"  # type: ignore[misc]
    with pytest.raises(StrictContractError):
        parse_intake_request_json(json.dumps({**raw, "command": "install"}))
    payload = json.dumps(raw)
    with pytest.raises(StrictContractError):
        parse_intake_request_json(payload[:-1] + ',"schema":"duplicate"}')
    result = validation()
    assert result.capability_status == "unsupported"
    assert result.default_enabled is False and result.evidence_only is True
    assert result.admission.linkage == request.envelope.linkage
    assert result.admission.prior_evidence == request.prior_evidence
    assert result.admission.received_at == "2026-08-29T12:00:25Z"
    assert result.admission.admission_fingerprint == admission_fingerprint(
        operator_id=OPERATOR, admission=result.admission
    )


def test_missing_fingerprints_ownership_linkage_and_evidence_mismatch() -> None:
    for path in (
        ("envelope", "linkage", "candidate_record_fingerprint"),
        ("envelope", "linkage", "approval_intent_fingerprint"),
        ("envelope", "linkage", "agent_validation_fingerprint"),
        ("envelope", "linkage", "execution_request_fingerprint"),
        ("prior_evidence", "intake_simulation", "intake_record_fingerprint"),
        ("prior_evidence", "simulated_delivery", "delivery_record_fingerprint"),
        ("prior_evidence", "simulated_delivery", "acknowledgement_fingerprint"),
    ):
        raw = request_dict()
        del raw[path[0]][path[1]][path[2]]  # type: ignore[index]
        with pytest.raises(ValidationError):
            AgentInstallationIntakeRequestV1.model_validate(raw)
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    auth, evidence = contexts(request)
    foreign = evidence.model_copy(update={"operator_id": "operator-b"})
    with pytest.raises(ValueError, match="ownership"):
        validate_real_intake(
            request,
            authentication=auth,
            evidence=foreign,
            received_at="2026-08-29T12:00:25Z",
            admission_id="00000000-0000-4000-8000-000000000703",
        )
    changed_raw = request_dict()
    changed_raw["envelope"]["linkage"]["execution_request_id"] = (  # type: ignore[index]
        "00000000-0000-4000-8000-000000000299"
    )
    changed = AgentInstallationIntakeRequestV1.model_validate(changed_raw)
    with pytest.raises(ValueError, match="request fingerprint"):
        validate_real_intake(
            changed,
            authentication=auth,
            evidence=evidence,
            received_at="2026-08-29T12:00:25Z",
            admission_id="00000000-0000-4000-8000-000000000703",
        )


def test_auth_shape_freshness_expiry_and_lifecycle() -> None:
    with pytest.raises(ValidationError):
        AgentInstallationIntakeAuthenticationContextV1.model_validate(
            {"authenticated_principal": "atlas-core", "permission": "admin"}
        )
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    auth, evidence = contexts(request)
    for received in ("2026-08-29T12:00:31Z", "2026-08-29T12:01:00Z"):
        with pytest.raises(ValueError, match="window|current"):
            validate_real_intake(
                request,
                authentication=auth,
                evidence=evidence,
                received_at=received,
                admission_id="00000000-0000-4000-8000-000000000703",
            )
    admission = validation().admission
    assert intake_lifecycle(admission, now=admission.received_at) == "admitted"
    assert intake_lifecycle(admission, now=admission.valid_until) == "expired"


def test_fixed_authority_redaction_result_and_domain_separation() -> None:
    result = validation()
    schema = type(result).model_json_schema()["properties"]
    for field in (
        "default_enabled",
        "execution_admission_granted",
        "execution_authorized",
        "worker_allowed",
        "mutation_allowed",
        "replay_allowed",
    ):
        assert schema[field]["const"] is False
    error = AgentInstallationIntakeRedactedErrorV1(
        error_code="unauthenticated",
        correlation_id="intake-1",
        authenticated_sender_class="unknown",
    )
    assert error.redacted is True and error.intake_request_id is None
    rejected = AgentInstallationIntakeResultV1(
        intake_request_id=None,
        outcome="rejected",
        admission=None,
        reason_code="unauthenticated",
    )
    assert rejected.reason_code == "unauthenticated"
    request = AgentInstallationIntakeRequestV1.model_validate(request_dict())
    assert request_fingerprint(request) == request_fingerprint(request)
    assert request.request_fingerprint != result.admission.admission_fingerprint
    with pytest.raises(ValueError, match="principal"):
        request_fingerprint(request, authenticated_core_principal="other")


def test_no_forbidden_imports_calls_or_production_wiring() -> None:
    root = Path(__file__).parents[2] / "app"
    package = root / "real_agent_intake_boundary"
    tree = ast.parse((package / "models.py").read_text(encoding="utf-8"))
    imports = {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports |= {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports.isdisjoint(
        {"asyncio", "docker", "podman", "socket", "subprocess", "requests", "httpx"}
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert calls.isdisjoint({"exec", "eval", "open", "system", "run", "Popen"})
    consumers = []
    for path in root.rglob("*.py"):
        if package in path.parents:
            continue
        if "real_agent_intake_boundary" in path.read_text(encoding="utf-8"):
            consumers.append(path.relative_to(root))
    assert consumers == []
