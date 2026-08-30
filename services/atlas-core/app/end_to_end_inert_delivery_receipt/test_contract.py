from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.dormant_agent_intake_delivery_wiring.contract import (
    AgentInstallationIntakeRequestV1,
)
from app.dormant_agent_intake_delivery_wiring.contract import (
    request_fingerprint as intake_request_fingerprint,
)
from app.end_to_end_inert_delivery_receipt import contract
from app.end_to_end_inert_delivery_receipt.contract import (
    AgentAdmissionReceiptAuthenticityV1,
    AgentAdmissionReceiptCopyV1,
    AgentLiveIntakeAcknowledgementCopyV1,
    AgentLiveIntakeAdmissionCopyV1,
    AgentLiveIntakeEnvelopeCopyV1,
    AgentLiveIntakeResultCopyV1,
    EndToEndInertDeliveryAuditEvidenceV1,
    EndToEndInertDeliveryIdempotencyV1,
    EndToEndInertDeliveryLinkageV1,
    EndToEndInertDeliveryReceiptV1,
    EndToEndInertDeliveryRedactedErrorV1,
    EndToEndInertDeliveryRequestV1,
    EndToEndInertDeliveryResultV1,
    EndToEndInertDeliveryStatusV1,
    EndToEndInertDeliveryVerificationV1,
    StrictContractError,
    agent_acknowledgement_fingerprint,
    agent_admission_fingerprint,
    agent_envelope_fingerprint,
    agent_receipt_copy_fingerprint,
    agent_result_fingerprint,
    audit_evidence_fingerprint,
    idempotency_key_fingerprint,
    linkage_fingerprint,
    operator_fingerprint,
    parse_agent_result_json,
    parse_request_json,
    receipt_fingerprint,
    request_fingerprint,
    response_body_fingerprint,
    verification_fingerprint,
)
from app.installation_dispatch_handoff.contract import (
    InstallationDispatchEnvelopeV1,
    dispatch_envelope_fingerprint,
)
from app.live_delivery_send_boundary.contract import (
    LiveDeliverySendAttemptV1,
    attempt_fingerprint,
    body_fingerprint,
)
from app.live_delivery_send_boundary.test_contract import (
    CREATED_AT,
    _attempt,
)
from app.operator_controlled_delivery_enablement.test_contract import OPERATOR

RECEIVED_AT = "2026-08-27T12:00:15Z"
VERIFIED_AT = "2026-08-27T12:00:16Z"
ADMISSION_ID = "00000000-0000-4000-8000-000000000c01"
ACK_ID = "00000000-0000-4000-8000-000000000c02"
RECEIPT_ID = "00000000-0000-4000-8000-000000000c03"


def _fp(character: str):
    from app.installation_dispatch_handoff.contract import FingerprintV1

    return FingerprintV1(
        algorithm="sha256",
        canonicalization="atlas-jcs-nfc-v1",
        value=character * 64,
    )


def _json_bytes(value) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _evidence(tmp_path: Path):
    attempt, transport_envelope = _attempt(tmp_path)
    intake_raw = transport_envelope.request.model_dump(mode="json")
    dispatch_raw = intake_raw["envelope"]
    dispatch_raw["valid_until"] = attempt.expires_at
    dispatch_raw["dispatch_envelope_fingerprint"] = dispatch_envelope_fingerprint(
        owner_id=OPERATOR, envelope=dispatch_raw
    ).model_dump(mode="json")
    intake_raw["envelope"] = InstallationDispatchEnvelopeV1.model_validate(
        dispatch_raw
    ).model_dump(mode="json")
    intake_raw["sent_at"] = attempt.created_at
    intake_raw["expires_at"] = attempt.expires_at
    intake_raw["request_fingerprint"] = intake_request_fingerprint(
        intake_raw
    ).model_dump(mode="json")
    intake_request = AgentInstallationIntakeRequestV1.model_validate(intake_raw)
    attempt_raw = attempt.model_dump(mode="json")
    attempt_raw["linkage"]["dispatch_envelope_fingerprint"] = dispatch_raw[
        "dispatch_envelope_fingerprint"
    ]
    attempt_raw["request_fingerprint"] = intake_request.request_fingerprint.model_dump(
        mode="json"
    )
    attempt_raw["request_body_fingerprint"] = body_fingerprint(
        _json_bytes(intake_request)
    ).model_dump(mode="json")
    attempt_raw["attempt_fingerprint"] = attempt_fingerprint(
        attempt_raw, operator_id=attempt.operator_id
    ).model_dump(mode="json")
    attempt = LiveDeliverySendAttemptV1.model_validate(attempt_raw)
    envelope_seed = AgentLiveIntakeEnvelopeCopyV1.model_construct(
        send_attempt=attempt,
        intake_request=intake_request,
        request_fingerprint=attempt.request_fingerprint,
        request_body_fingerprint=attempt.request_body_fingerprint,
        idempotency_key_fingerprint=_fp("1"),
        endpoint_fingerprint=attempt.endpoint_fingerprint,
        envelope_fingerprint=_fp("0"),
    )
    envelope = AgentLiveIntakeEnvelopeCopyV1.model_validate(
        envelope_seed.model_copy(
            update={"envelope_fingerprint": agent_envelope_fingerprint(envelope_seed)}
        )
    )

    admission_seed = AgentLiveIntakeAdmissionCopyV1.model_construct(
        admission_id=ADMISSION_ID,
        send_attempt_id=attempt.send_attempt_id,
        attempt_fingerprint=attempt.attempt_fingerprint,
        envelope_fingerprint=envelope.envelope_fingerprint,
        intake_request_id=attempt.linkage.intake_request_id,
        request_fingerprint=attempt.request_fingerprint,
        delivery_attempt_id=attempt.linkage.delivery_attempt_id,
        received_at=RECEIVED_AT,
        valid_until=attempt.expires_at,
        operator_id=OPERATOR,
        linkage=attempt.linkage,
        admission_fingerprint=_fp("0"),
    )
    admission = AgentLiveIntakeAdmissionCopyV1.model_validate(
        admission_seed.model_copy(
            update={
                "admission_fingerprint": agent_admission_fingerprint(admission_seed)
            }
        )
    )
    acknowledgement_seed = AgentLiveIntakeAcknowledgementCopyV1.model_construct(
        acknowledgement_id=ACK_ID,
        admission_id=admission.admission_id,
        admission_fingerprint=admission.admission_fingerprint,
        send_attempt_id=attempt.send_attempt_id,
        attempt_fingerprint=attempt.attempt_fingerprint,
        intake_request_id=attempt.linkage.intake_request_id,
        received_at=RECEIVED_AT,
        valid_until=attempt.expires_at,
        acknowledgement_fingerprint=_fp("0"),
    )
    acknowledgement = AgentLiveIntakeAcknowledgementCopyV1.model_validate(
        acknowledgement_seed.model_copy(
            update={
                "acknowledgement_fingerprint": (
                    agent_acknowledgement_fingerprint(acknowledgement_seed)
                )
            }
        )
    )
    result = AgentLiveIntakeResultCopyV1(
        send_attempt_id=attempt.send_attempt_id,
        intake_request_id=attempt.linkage.intake_request_id,
        outcome="admitted_for_evidence_only",
        admission=admission,
        acknowledgement=acknowledgement,
        reason_code=None,
    )
    authenticity = AgentAdmissionReceiptAuthenticityV1(
        source_identity_fingerprint=_fp("2"),
        endpoint_fingerprint=attempt.endpoint_fingerprint,
        credential_reference_fingerprint=_fp("3"),
    )
    copy_seed = AgentAdmissionReceiptCopyV1.model_construct(
        result=result,
        authenticity=authenticity,
        copied_at=VERIFIED_AT,
        copy_fingerprint=_fp("0"),
    )
    receipt_copy = AgentAdmissionReceiptCopyV1.model_validate(
        copy_seed.model_copy(
            update={"copy_fingerprint": agent_receipt_copy_fingerprint(copy_seed)}
        )
    )
    request_seed = EndToEndInertDeliveryRequestV1.model_construct(
        send_attempt_id=attempt.send_attempt_id,
        attempt_fingerprint=attempt.attempt_fingerprint,
        envelope=envelope,
        endpoint_fingerprint=attempt.endpoint_fingerprint,
        idempotency_key_fingerprint=_fp("1"),
        requested_at=CREATED_AT,
        expires_at=attempt.expires_at,
        request_fingerprint=_fp("0"),
    )
    request = EndToEndInertDeliveryRequestV1.model_validate(
        request_seed.model_copy(
            update={"request_fingerprint": request_fingerprint(request_seed)}
        )
    )
    prior_receipt_fp = _fp("4")
    result_fp = agent_result_fingerprint(result)
    linkage = EndToEndInertDeliveryLinkageV1(
        **attempt.linkage.model_dump(mode="python"),
        send_attempt_id=attempt.send_attempt_id,
        attempt_fingerprint=attempt.attempt_fingerprint,
        v031_send_receipt_fingerprint=prior_receipt_fp,
        v032_envelope_fingerprint=envelope.envelope_fingerprint,
        v032_agent_result_fingerprint=result_fp,
        v032_admission_id=admission.admission_id,
        v032_admission_fingerprint=admission.admission_fingerprint,
        v032_acknowledgement_id=acknowledgement.acknowledgement_id,
        v032_acknowledgement_fingerprint=(
            acknowledgement.acknowledgement_fingerprint
        ),
    )
    verification_seed = EndToEndInertDeliveryVerificationV1.model_construct(
        send_attempt_id=attempt.send_attempt_id,
        attempt_fingerprint=attempt.attempt_fingerprint,
        envelope_fingerprint=envelope.envelope_fingerprint,
        request_fingerprint=request.request_fingerprint,
        response_body_fingerprint=response_body_fingerprint(_json_bytes(result)),
        agent_result_fingerprint=result_fp,
        admission_id=admission.admission_id,
        admission_fingerprint=admission.admission_fingerprint,
        acknowledgement_id=acknowledgement.acknowledgement_id,
        acknowledgement_fingerprint=acknowledgement.acknowledgement_fingerprint,
        intake_request_id=attempt.linkage.intake_request_id,
        operator_id=OPERATOR,
        linkage_fingerprint=linkage_fingerprint(linkage),
        verified_at=VERIFIED_AT,
        valid_until=attempt.expires_at,
        verification_fingerprint=_fp("0"),
    )
    verification = EndToEndInertDeliveryVerificationV1.model_validate(
        verification_seed.model_copy(
            update={
                "verification_fingerprint": verification_fingerprint(
                    verification_seed
                )
            }
        )
    )
    receipt_seed = EndToEndInertDeliveryReceiptV1.model_construct(
        receipt_id=RECEIPT_ID,
        operator_id=OPERATOR,
        send_attempt_id=attempt.send_attempt_id,
        attempt_fingerprint=attempt.attempt_fingerprint,
        prior_send_receipt_fingerprint=prior_receipt_fp,
        envelope_fingerprint=envelope.envelope_fingerprint,
        verification=verification,
        agent_receipt_copy=receipt_copy,
        linkage=linkage,
        received_at=RECEIVED_AT,
        valid_until=attempt.expires_at,
        receipt_fingerprint=_fp("0"),
    )
    receipt = EndToEndInertDeliveryReceiptV1.model_validate(
        receipt_seed.model_copy(
            update={"receipt_fingerprint": receipt_fingerprint(receipt_seed)}
        )
    )
    return request, receipt_copy, verification, linkage, receipt


def _audit(request, receipt, verification, linkage):
    admission = receipt.agent_receipt_copy.result.admission
    acknowledgement = receipt.agent_receipt_copy.result.acknowledgement
    assert admission is not None and acknowledgement is not None
    seed = EndToEndInertDeliveryAuditEvidenceV1.model_construct(
        receipt_id=receipt.receipt_id,
        receipt_fingerprint=receipt.receipt_fingerprint,
        verification_fingerprint=verification.verification_fingerprint,
        send_attempt_id=receipt.send_attempt_id,
        attempt_fingerprint=receipt.attempt_fingerprint,
        prior_send_receipt_fingerprint=receipt.prior_send_receipt_fingerprint,
        envelope_fingerprint=receipt.envelope_fingerprint,
        agent_result_fingerprint=verification.agent_result_fingerprint,
        admission_fingerprint=admission.admission_fingerprint,
        acknowledgement_fingerprint=acknowledgement.acknowledgement_fingerprint,
        linkage_fingerprint=linkage_fingerprint(linkage),
        endpoint_fingerprint=request.endpoint_fingerprint,
        idempotency_key_fingerprint=request.idempotency_key_fingerprint,
        operator_fingerprint=operator_fingerprint(receipt.operator_id),
        correlation_id="receipt-1",
        requested_at=request.requested_at,
        received_at=receipt.received_at,
        completed_at=verification.verified_at,
        lifecycle="verified_inert_receipt",
        evidence_fingerprint=_fp("0"),
    )
    return EndToEndInertDeliveryAuditEvidenceV1.model_validate(
        seed.model_copy(
            update={"evidence_fingerprint": audit_evidence_fingerprint(seed)}
        )
    )


def test_closed_json_duplicate_unknown_and_immutable(tmp_path: Path) -> None:
    request, receipt_copy, _, _, _ = _evidence(tmp_path)
    payload = _json_bytes(request)
    assert parse_request_json(payload) == request
    with pytest.raises(StrictContractError, match="duplicate"):
        parse_request_json(payload[:-1] + b',"schema":"duplicate"}')
    raw = request.model_dump(mode="json") | {"execute": True}
    with pytest.raises(StrictContractError):
        parse_request_json(_json_bytes(raw))
    assert parse_agent_result_json(_json_bytes(receipt_copy.result)) == (
        receipt_copy.result
    )
    with pytest.raises(ValidationError):
        request.default_enabled = True  # type: ignore[misc]


def test_valid_request_verification_receipt_result_and_audit(tmp_path: Path) -> None:
    request, receipt_copy, verification, linkage, receipt = _evidence(tmp_path)
    audit = _audit(request, receipt, verification, linkage)
    status = EndToEndInertDeliveryStatusV1(
        receipt_id=receipt.receipt_id,
        send_attempt_id=receipt.send_attempt_id,
        operator_id=receipt.operator_id,
        observed_at=verification.verified_at,
        valid_until=receipt.valid_until,
        lifecycle="verified_inert_receipt",
    )
    operation = EndToEndInertDeliveryResultV1(
        disposition="verified_inert_receipt",
        receipt=receipt,
        verification=verification,
        agent_receipt_copy=receipt_copy,
        status=status,
        audit_evidence=audit,
        error=None,
    )
    assert operation.receipt == receipt
    assert receipt.linkage == linkage
    assert receipt_copy.authenticity.agent_receipt_exported is False
    assert receipt_copy.authenticity.agent_receipt_atomicity_relied_upon is True


@pytest.mark.parametrize(
    "target,field",
    (("request", "request_fingerprint"), ("verification", "verification_fingerprint"),
     ("receipt", "receipt_fingerprint")),
)
def test_invalid_or_missing_fingerprints_fail_closed(
    tmp_path: Path, target: str, field: str
) -> None:
    request, _, verification, _, receipt = _evidence(tmp_path)
    value = {"request": request, "verification": verification, "receipt": receipt}[target]
    raw = value.model_dump(mode="json")
    raw[field] = _fp("f").model_dump(mode="json")
    with pytest.raises(ValueError, match="fingerprint"):
        type(value).model_validate(raw)
    raw.pop(field)
    with pytest.raises(ValidationError):
        type(value).model_validate(raw)


def test_ownership_and_complete_linkage_mismatch_fail(tmp_path: Path) -> None:
    _, _, _, _, receipt = _evidence(tmp_path)
    raw = receipt.model_dump(mode="json")
    raw["operator_id"] = "operator-b"
    raw["receipt_fingerprint"] = receipt_fingerprint(raw).model_dump(mode="json")
    with pytest.raises(ValueError, match="ownership"):
        EndToEndInertDeliveryReceiptV1.model_validate(raw)
    raw = receipt.model_dump(mode="json")
    raw["linkage"]["approval_intent_fingerprint"]["value"] = "e" * 64
    raw["receipt_fingerprint"] = receipt_fingerprint(raw).model_dump(mode="json")
    with pytest.raises(ValueError, match="linkage"):
        EndToEndInertDeliveryReceiptV1.model_validate(raw)


def test_stale_and_expired_inputs_fail(tmp_path: Path) -> None:
    request, _, verification, _, _ = _evidence(tmp_path)
    raw = request.model_dump(mode="json")
    raw["requested_at"] = raw["expires_at"]
    raw["request_fingerprint"] = request_fingerprint(raw).model_dump(mode="json")
    with pytest.raises(ValueError, match="30-second|freshness"):
        EndToEndInertDeliveryRequestV1.model_validate(raw)
    raw = verification.model_dump(mode="json")
    raw["verified_at"] = raw["valid_until"]
    raw["verification_fingerprint"] = verification_fingerprint(raw).model_dump(
        mode="json"
    )
    with pytest.raises(ValueError, match="stale|expired"):
        EndToEndInertDeliveryVerificationV1.model_validate(raw)


def test_agent_receipt_authenticity_and_source_metadata_are_exact(
    tmp_path: Path,
) -> None:
    _, receipt_copy, _, _, _ = _evidence(tmp_path)
    for field, value in (
        ("source_scheme", "http"),
        ("source_path", "/alternate"),
        ("authenticated_principal", "operator"),
        ("credential_material_present", True),
        ("agent_receipt_exported", True),
    ):
        raw = receipt_copy.authenticity.model_dump(mode="json")
        raw[field] = value
        with pytest.raises(ValidationError):
            AgentAdmissionReceiptAuthenticityV1.model_validate(raw)
    result_raw = receipt_copy.result.model_dump(mode="json")
    result_raw["acknowledgement"]["admission_id"] = ACK_ID
    result_raw["acknowledgement"]["acknowledgement_fingerprint"] = (
        agent_acknowledgement_fingerprint(result_raw["acknowledgement"])
        .model_dump(mode="json")
    )
    with pytest.raises(ValueError, match="binding"):
        AgentLiveIntakeResultCopyV1.model_validate(result_raw)


def test_bounds_fail_closed(tmp_path: Path, monkeypatch) -> None:
    request, receipt_copy, _, _, receipt = _evidence(tmp_path)
    monkeypatch.setattr(contract, "MAX_AGENT_ENVELOPE_BYTES", 1)
    with pytest.raises(ValueError, match="128 KiB"):
        AgentLiveIntakeEnvelopeCopyV1.model_validate(
            request.envelope.model_dump(mode="json")
        )
    monkeypatch.setattr(contract, "MAX_AGENT_ENVELOPE_BYTES", 128 * 1024)
    monkeypatch.setattr(contract, "MAX_REQUEST_BYTES", 1)
    with pytest.raises(ValueError, match="160 KiB"):
        EndToEndInertDeliveryRequestV1.model_validate(request.model_dump(mode="json"))
    monkeypatch.setattr(contract, "MAX_AGENT_RESPONSE_BYTES", 1)
    with pytest.raises(ValueError, match="32 KiB"):
        AgentLiveIntakeResultCopyV1.model_validate(
            receipt_copy.result.model_dump(mode="json")
        )
    monkeypatch.setattr(contract, "MAX_AGENT_RESPONSE_BYTES", 32 * 1024)
    monkeypatch.setattr(contract, "MAX_RECEIPT_BYTES", 1)
    with pytest.raises(ValueError, match="192 KiB"):
        EndToEndInertDeliveryReceiptV1.model_validate(
            receipt.model_dump(mode="json")
        )


def test_no_replay_fixed_authority_and_redacted_error(tmp_path: Path) -> None:
    request, _, _, _, receipt = _evidence(tmp_path)
    idempotency = EndToEndInertDeliveryIdempotencyV1(
        operator_id=OPERATOR,
        key="receipt-once",
        idempotency_key_fingerprint=idempotency_key_fingerprint(
            OPERATOR, "receipt-once"
        ),
        send_attempt_id=receipt.send_attempt_id,
        attempt_fingerprint=receipt.attempt_fingerprint,
        envelope_fingerprint=receipt.envelope_fingerprint,
        receipt_id=receipt.receipt_id,
        receipt_fingerprint=receipt.receipt_fingerprint,
    )
    assert idempotency.reservation_permanent
    assert idempotency.exact_duplicate_only
    assert idempotency.network_on_exact_duplicate is False
    models = (request, receipt, receipt.verification, receipt.agent_receipt_copy)
    for value in models:
        raw = value.model_dump()
        assert raw["evidence_only"] is True
        for field in (
            "execution_admission_granted",
            "execution_authorized",
            "installation_allowed",
            "worker_allowed",
            "workflow_allowed",
            "deployment_allowed",
            "mutation_allowed",
            "replay_allowed",
        ):
            assert raw[field] is False
    error = EndToEndInertDeliveryRedactedErrorV1(
        error_code="ambiguous", correlation_id="receipt-1"
    )
    assert error.safe_message == "Inert delivery receipt evidence is unavailable."
    assert error.redacted and not error.retryable and not error.replay_allowed
    with pytest.raises(ValueError, match="redact"):
        EndToEndInertDeliveryRedactedErrorV1(
            error_code="unauthenticated",
            correlation_id="receipt-2",
            send_attempt_id=receipt.send_attempt_id,
        )


def test_domain_separated_fingerprints_are_deterministic(tmp_path: Path) -> None:
    request, _, verification, linkage, receipt = _evidence(tmp_path)
    assert request_fingerprint(request) == request_fingerprint(request)
    assert verification_fingerprint(verification) == verification.verification_fingerprint
    assert receipt_fingerprint(receipt) == receipt.receipt_fingerprint
    assert linkage_fingerprint(linkage) != receipt.receipt_fingerprint
    assert request.request_fingerprint != receipt.receipt_fingerprint


def test_contract_has_no_forbidden_imports_or_calls_and_agent_is_unchanged() -> None:
    path = Path(__file__).with_name("contract.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "httpx",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "docker",
        "podman",
        "os",
    }
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert imports.isdisjoint(forbidden)
    assert calls.isdisjoint({"open", "exec", "eval", "system", "run", "Popen"})
    repository_root = Path(__file__).parents[5]
    agent_package = (
        repository_root
        / "services"
        / "atlas-agent"
        / "app"
        / "agent_live_intake_admission"
    )
    assert not any("v0.33" in path.read_text(encoding="utf-8") for path in agent_package.glob("*.py"))
