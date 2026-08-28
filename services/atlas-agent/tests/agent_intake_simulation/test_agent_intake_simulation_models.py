from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest
from app.agent_intake_simulation import (
    AgentInstallationIntakeSimulationAuditEvidenceV1,
    AgentInstallationIntakeSimulationCreateV1,
    AgentInstallationIntakeSimulationErrorV1,
    AgentInstallationIntakeSimulationIdempotencyV1,
    AgentInstallationIntakeSimulationResultV1,
    StrictContractError,
    audit_evidence_fingerprint,
    dispatch_envelope_fingerprint,
    intake_record_fingerprint,
    parse_simulation_create_json,
    simulation_create_fingerprint,
    simulation_lifecycle,
    validate_simulated_intake,
)
from pydantic import ValidationError

OPERATOR = "operator-a"
REQUEST_ID = "00000000-0000-4000-8000-000000000501"
RECORD_ID = "00000000-0000-4000-8000-000000000502"
DISPATCH_ID = "00000000-0000-4000-8000-000000000401"


def fp(character: str) -> dict[str, str]:
    return {
        "algorithm": "sha256",
        "canonicalization": "atlas-jcs-nfc-v1",
        "value": character * 64,
    }


def envelope_dict() -> dict[str, object]:
    raw: dict[str, object] = {
        "schema": "installation-dispatch-envelope-v1",
        "dispatch_envelope_id": DISPATCH_ID,
        "prepared_at": "2026-08-28T12:00:00Z",
        "valid_until": "2026-08-28T12:01:00Z",
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


def create_dict() -> dict[str, object]:
    return {
        "schema": "agent-installation-intake-simulation-create-v1",
        "simulation_request_id": REQUEST_ID,
        "envelope": envelope_dict(),
    }


def validation():
    create = AgentInstallationIntakeSimulationCreateV1.model_validate(create_dict())
    return validate_simulated_intake(
        create,
        operator_id=OPERATOR,
        observed_at="2026-08-28T12:00:10Z",
        intake_record_id=RECORD_ID,
    )


def test_closed_duplicate_unknown_and_immutable_simulated_intake() -> None:
    raw = create_dict()
    create = parse_simulation_create_json(json.dumps(raw))
    with pytest.raises(ValidationError):
        create.simulation_request_id = RECORD_ID  # type: ignore[misc]
    with pytest.raises(StrictContractError):
        parse_simulation_create_json(json.dumps({**raw, "command": "install"}))
    payload = json.dumps(raw)
    with pytest.raises(StrictContractError):
        parse_simulation_create_json(payload[:-1] + ',"schema":"duplicate"}')

    result = validation()
    record = result.record
    assert record.linkage == create.envelope.linkage
    assert record.valid_until == "2026-08-28T12:00:40Z"
    assert record.intake_record_fingerprint == intake_record_fingerprint(
        operator_id=OPERATOR, record=record
    )
    assert simulation_lifecycle(record, now=record.observed_at) == "simulated"
    assert simulation_lifecycle(record, now=record.valid_until) == "expired"


def test_missing_invalid_fingerprints_and_linkage_fail() -> None:
    for field in (
        "candidate_envelope_fingerprint",
        "approval_intent_fingerprint",
        "agent_request_fingerprint",
        "agent_validation_fingerprint",
        "agent_evidence_fingerprint",
        "execution_request_fingerprint",
    ):
        raw = create_dict()
        del raw["envelope"]["linkage"][field]  # type: ignore[index]
        with pytest.raises(ValidationError):
            AgentInstallationIntakeSimulationCreateV1.model_validate(raw)
    raw = create_dict()
    raw["envelope"]["linkage"]["destination_fingerprint"] = "x" * 64  # type: ignore[index]
    with pytest.raises(ValidationError):
        AgentInstallationIntakeSimulationCreateV1.model_validate(raw)


def test_ownership_tampering_and_freshness_fail_closed() -> None:
    create = AgentInstallationIntakeSimulationCreateV1.model_validate(create_dict())
    with pytest.raises(ValueError, match="ownership|fingerprint"):
        validate_simulated_intake(
            create,
            operator_id="operator-b",
            observed_at="2026-08-28T12:00:10Z",
            intake_record_id=RECORD_ID,
        )
    with pytest.raises(ValueError, match="precedes"):
        validate_simulated_intake(
            create,
            operator_id=OPERATOR,
            observed_at="2026-08-28T11:59:59Z",
            intake_record_id=RECORD_ID,
        )
    with pytest.raises(ValueError, match="not current"):
        validate_simulated_intake(
            create,
            operator_id=OPERATOR,
            observed_at="2026-08-28T12:01:00Z",
            intake_record_id=RECORD_ID,
        )
    tampered = deepcopy(create_dict())
    tampered["envelope"]["linkage"]["execution_request_id"] = REQUEST_ID  # type: ignore[index]
    changed = AgentInstallationIntakeSimulationCreateV1.model_validate(tampered)
    with pytest.raises(ValueError, match="fingerprint"):
        validate_simulated_intake(
            changed,
            operator_id=OPERATOR,
            observed_at="2026-08-28T12:00:10Z",
            intake_record_id=RECORD_ID,
        )


def test_default_disabled_simulation_only_authority_and_result_shapes() -> None:
    result = validation()
    assert result.capability_status == "unsupported"
    assert result.default_enabled is False and result.simulation_only is True
    assert not any(
        (
            result.delivery_received,
            result.live_admission_granted,
            result.execution_authorized,
            result.worker_allowed,
            result.mutation_allowed,
            result.replay_allowed,
        )
    )
    schema = type(result).model_json_schema()["properties"]
    for field in (
        "default_enabled",
        "delivery_received",
        "live_admission_granted",
        "execution_authorized",
        "worker_allowed",
        "mutation_allowed",
        "replay_allowed",
    ):
        assert schema[field]["const"] is False
    wrapped = AgentInstallationIntakeSimulationResultV1(
        disposition="simulated", validation=result, error=None
    )
    assert wrapped.worker_invoked is False


def test_redacted_error_audit_and_no_replay_shapes() -> None:
    error = AgentInstallationIntakeSimulationErrorV1(
        error_code="linkage_mismatch", correlation_id="simulation-1"
    )
    dumped = error.model_dump(mode="json")
    assert dumped["redacted"] is True
    assert set(dumped) == {
        "schema",
        "error_code",
        "correlation_id",
        "simulation_request_id",
        "dispatch_envelope_id",
        "dispatch_envelope_fingerprint",
        "redacted",
    }
    record = validation().record
    raw = {
        "schema": "agent-installation-intake-simulation-audit-evidence-v1",
        "intake_record_id": record.intake_record_id,
        "simulation_request_id": record.simulation_request_id,
        "dispatch_envelope_id": record.source.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": record.source.dispatch_envelope_fingerprint,
        "linkage": record.linkage,
        "intake_record_fingerprint": record.intake_record_fingerprint,
        "observed_at": record.observed_at,
        "valid_until": record.valid_until,
        "lifecycle": "simulated",
        "status": "simulated_valid",
        "evidence_provenance": "agent_simulated_not_received",
        "delivery_received": False,
        "live_admission_granted": False,
        "execution_authorized": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw)
    evidence = AgentInstallationIntakeSimulationAuditEvidenceV1.model_validate(raw)
    assert evidence.evidence_provenance == "agent_simulated_not_received"
    reservation = AgentInstallationIntakeSimulationIdempotencyV1(
        operator_id=OPERATOR,
        key="retry-1",
        create_fingerprint=simulation_create_fingerprint(
            AgentInstallationIntakeSimulationCreateV1.model_validate(create_dict())
        ),
        simulation_request_id=REQUEST_ID,
        dispatch_envelope_id=DISPATCH_ID,
        dispatch_envelope_fingerprint=record.source.dispatch_envelope_fingerprint,
        intake_record_fingerprint=record.intake_record_fingerprint,
    )
    assert reservation.replay_allowed is False
    with pytest.raises(ValidationError):
        type(reservation).model_validate({**reservation.model_dump(), "replay_allowed": True})


def test_fingerprints_are_deterministic_domain_separated_and_owner_bound() -> None:
    create = AgentInstallationIntakeSimulationCreateV1.model_validate(create_dict())
    assert simulation_create_fingerprint(create) == simulation_create_fingerprint(create)
    assert simulation_create_fingerprint(create) != create.envelope.dispatch_envelope_fingerprint
    record = validation().record
    assert intake_record_fingerprint(
        operator_id=OPERATOR, record=record
    ) != intake_record_fingerprint(operator_id="operator-b", record=record)


def test_contract_has_no_forbidden_imports_calls_or_production_consumers() -> None:
    root = Path(__file__).parents[2] / "app"
    contract_root = root / "agent_intake_simulation"
    tree = ast.parse((contract_root / "models.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported.isdisjoint(
        {"asyncio", "docker", "podman", "socket", "subprocess", "requests", "httpx"}
    )
    forbidden_calls = {"exec", "eval", "open", "system", "run", "Popen"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    calls |= {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert calls.isdisjoint(forbidden_calls)
    consumers = []
    for path in root.rglob("*.py"):
        if contract_root in path.parents:
            continue
        if "agent_intake_simulation" in path.read_text(encoding="utf-8"):
            consumers.append(path.relative_to(root))
    assert consumers == []
