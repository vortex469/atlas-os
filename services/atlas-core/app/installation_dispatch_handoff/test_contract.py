from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_dispatch_handoff.contract import (
    AgentInstallationDispatchAdmissionV1,
    AgentInstallationDispatchIntakeV1,
    InstallationDispatchAuditEvidenceV1,
    InstallationDispatchErrorV1,
    InstallationDispatchHandoffCreateV1,
    InstallationDispatchIdempotencyV1,
    StrictContractError,
    build_dispatch_envelope,
    create_fingerprint,
    dispatch_envelope_fingerprint,
    dispatch_envelope_state,
    parse_create_json,
    validate_agent_intake,
)
from app.installation_execution_request.contract import build_execution_request
from app.installation_execution_request.test_contract import CORE_ID, chain

DISPATCH_ID = "00000000-0000-4000-8000-000000000401"
PREPARED_AT = "2026-08-27T12:00:01Z"


def upstream(tmp_path: Path):
    candidate, intent, execution_create = chain(tmp_path)
    request = build_execution_request(
        owner_id="operator-a",
        execution_request_id=CORE_ID,
        recorded_at="2026-08-27T12:00:00Z",
        envelope=candidate,
        approval_intent=intent,
        create=execution_create,
    )
    create = InstallationDispatchHandoffCreateV1(execution_request_id=CORE_ID)
    return candidate, intent, request, create


def built(tmp_path: Path):
    candidate, intent, request, create = upstream(tmp_path)
    envelope = build_dispatch_envelope(
        owner_id="operator-a",
        dispatch_envelope_id=DISPATCH_ID,
        prepared_at=PREPARED_AT,
        create=create,
        candidate_envelope=candidate,
        approval_intent=intent,
        execution_request=request,
    )
    return envelope, create


def test_valid_envelope_and_intake_are_closed_immutable_and_inert(tmp_path: Path) -> None:
    envelope, create = built(tmp_path)
    assert envelope.dispatch_envelope_fingerprint == dispatch_envelope_fingerprint(
        owner_id="operator-a", envelope=envelope
    )
    assert envelope.linkage.execution_request_id == create.execution_request_id
    assert dispatch_envelope_state(envelope, now=envelope.prepared_at) == "prepared"
    assert dispatch_envelope_state(envelope, now=envelope.valid_until) == "expired"
    assert not any(
        (
            envelope.delivery_authorized,
            envelope.agent_admission_authorized,
            envelope.execution_authorized,
            envelope.mutation_authorized,
            envelope.replay_allowed,
        )
    )
    with pytest.raises(ValidationError):
        envelope.mode = "deliver"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        type(envelope).model_validate({**envelope.model_dump(), "endpoint": "x"})

    intake = AgentInstallationDispatchIntakeV1(envelope=envelope)
    admission = validate_agent_intake(
        intake, owner_id="operator-a", evaluated_at="2026-08-27T12:00:02Z"
    )
    assert admission.status == "valid_but_not_admitted"
    assert admission.reason_codes == ()
    assert not any(
        (
            admission.delivery_accepted,
            admission.execution_admitted,
            admission.worker_allowed,
            admission.mutation_allowed,
            admission.replay_allowed,
        )
    )


def test_create_parser_rejects_duplicate_unknown_and_oversize() -> None:
    payload = json.dumps(
        InstallationDispatchHandoffCreateV1(
            execution_request_id=CORE_ID
        ).model_dump(mode="json")
    )
    assert parse_create_json(payload).execution_request_id == CORE_ID
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"execution_request_id":"' + CORE_ID + '"}')
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"command":"install"}')
    with pytest.raises(StrictContractError):
        parse_create_json(b" " * 1025)


def test_missing_or_changed_fingerprints_fail(tmp_path: Path) -> None:
    envelope, _ = built(tmp_path)
    raw = envelope.model_dump(mode="json")
    del raw["linkage"]["agent_evidence_fingerprint"]
    with pytest.raises(ValidationError):
        type(envelope).model_validate(raw)
    raw = envelope.model_dump(mode="json")
    raw["dispatch_envelope_fingerprint"]["value"] = "0" * 64
    tampered = type(envelope).model_validate(raw)
    with pytest.raises(ValueError, match="fingerprint"):
        validate_agent_intake(
            AgentInstallationDispatchIntakeV1(envelope=tampered),
            owner_id="operator-a",
            evaluated_at="2026-08-27T12:00:02Z",
        )


def test_ownership_linkage_staleness_and_expiry_fail_closed(tmp_path: Path) -> None:
    candidate, intent, request, create = upstream(tmp_path)
    arguments = {
        "owner_id": "operator-a",
        "dispatch_envelope_id": DISPATCH_ID,
        "prepared_at": PREPARED_AT,
        "create": create,
        "candidate_envelope": candidate,
        "approval_intent": intent,
        "execution_request": request,
    }
    with pytest.raises(ValueError, match="ownership|fingerprint"):
        build_dispatch_envelope(**{**arguments, "owner_id": "operator-b"})
    wrong = InstallationDispatchHandoffCreateV1(
        execution_request_id="00000000-0000-4000-8000-000000000402"
    )
    with pytest.raises(ValueError, match="linkage"):
        build_dispatch_envelope(**{**arguments, "create": wrong})
    with pytest.raises(ValueError, match="precedes"):
        build_dispatch_envelope(
            **{**arguments, "prepared_at": "2026-08-27T11:59:59Z"}
        )
    with pytest.raises(ValueError, match="current"):
        build_dispatch_envelope(
            **{**arguments, "prepared_at": request.valid_until}
        )


def test_upstream_fingerprint_and_linkage_tampering_fail(tmp_path: Path) -> None:
    candidate, intent, request, create = upstream(tmp_path)
    raw = request.model_dump(mode="json")
    raw["execution_request_fingerprint"]["value"] = "0" * 64
    tampered = type(request).model_validate(raw)
    with pytest.raises(ValueError, match="fingerprint"):
        build_dispatch_envelope(
            owner_id="operator-a",
            dispatch_envelope_id=DISPATCH_ID,
            prepared_at=PREPARED_AT,
            create=create,
            candidate_envelope=candidate,
            approval_intent=intent,
            execution_request=tampered,
        )
    raw = request.model_dump(mode="json")
    raw["linkage"]["approval_intent_fingerprint"]["value"] = "0" * 64
    raw["execution_request_fingerprint"] = (
        # Re-signing the owner-bound record must not permit upstream substitution.
        request.execution_request_fingerprint.model_dump(mode="json")
    )
    changed = type(request).model_validate(raw)
    with pytest.raises(ValueError, match="fingerprint|linkage"):
        build_dispatch_envelope(
            owner_id="operator-a",
            dispatch_envelope_id=DISPATCH_ID,
            prepared_at=PREPARED_AT,
            create=create,
            candidate_envelope=candidate,
            approval_intent=intent,
            execution_request=changed,
        )


def test_redacted_audit_idempotency_and_authority_shapes(tmp_path: Path) -> None:
    envelope, create = built(tmp_path)
    error = InstallationDispatchErrorV1(
        error_code="proof_mismatch", correlation_id="corr-1"
    )
    assert error.redacted is True
    assert set(error.model_dump()) == {
        "schema",
        "error_code",
        "correlation_id",
        "dispatch_envelope_id",
        "dispatch_envelope_fingerprint",
        "redacted",
    }
    evidence = InstallationDispatchAuditEvidenceV1(
        dispatch_envelope_id=envelope.dispatch_envelope_id,
        dispatch_envelope_fingerprint=envelope.dispatch_envelope_fingerprint,
        prepared_at=envelope.prepared_at,
        valid_until=envelope.valid_until,
        lifecycle="prepared",
    )
    assert evidence.evidence_provenance == "core_prepared_not_delivered"
    assert not evidence.delivered and not evidence.work_started
    reservation = InstallationDispatchIdempotencyV1(
        owner_id="operator-a",
        key="retry-1",
        create_fingerprint=create_fingerprint(create),
        execution_request_id=create.execution_request_id,
    )
    assert reservation.replay_allowed is False
    with pytest.raises(ValidationError):
        InstallationDispatchIdempotencyV1.model_validate(
            {**reservation.model_dump(), "replay_allowed": True}
        )


def test_fingerprints_are_domain_separated_owner_bound_and_deterministic(
    tmp_path: Path,
) -> None:
    envelope, create = built(tmp_path)
    assert dispatch_envelope_fingerprint(
        owner_id="operator-a", envelope=envelope
    ) == dispatch_envelope_fingerprint(owner_id="operator-a", envelope=envelope)
    assert dispatch_envelope_fingerprint(
        owner_id="operator-a", envelope=envelope
    ) != dispatch_envelope_fingerprint(owner_id="operator-b", envelope=envelope)
    assert create_fingerprint(create) != envelope.dispatch_envelope_fingerprint

    intake = AgentInstallationDispatchIntakeV1(envelope=envelope)
    admission = validate_agent_intake(
        intake, owner_id="operator-a", evaluated_at="2026-08-27T12:00:02Z"
    )
    assert admission == AgentInstallationDispatchAdmissionV1.model_validate(
        admission.model_dump(mode="python")
    )


def test_contract_has_no_forbidden_imports_or_calls() -> None:
    source = Path(__file__).with_name("contract.py").read_text()
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imports.isdisjoint(
        {
            "asyncio",
            "docker",
            "httpx",
            "requests",
            "socket",
            "subprocess",
            "app.clients",
            "app.workflows",
        }
    )
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint({"exec", "eval", "open", "compile", "__import__"})
