from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from app.install_container_contract import (
    AgentInstallContainerErrorV1,
    AgentInstallContainerRequestV1,
    ApprovalProofFactsV1,
    CandidateProofFactsV1,
    InstallContainerValidationService,
    NoReplayEvidenceV1,
    ReasonCode,
    ValidationFactsV1,
    validate_install_container_json,
    validate_install_container_request,
)
from test_install_container_contract_models import request_dict


def valid_inputs():
    request = AgentInstallContainerRequestV1.model_validate(request_dict())
    candidate = CandidateProofFactsV1(
        operator_id="operator-1",
        active=True,
        candidate_record_id=request.approval.candidate_record_id,
        candidate_envelope_fingerprint=request.approval.candidate_envelope_fingerprint,
        admission_fingerprint=request.approval.admission_fingerprint,
        candidate_record_fingerprint=request.approval.candidate_record_fingerprint,
        subject=request.subject,
        source_plan_fingerprint=request.artifact.source_plan_fingerprint,
        source_repository_path=request.artifact.source_repository_path,
        source_service=request.artifact.source_service,
        source_content_digest=request.artifact.source_content_digest,
    )
    approval = ApprovalProofFactsV1(
        operator_id="operator-1",
        approval_intent_id=request.approval.approval_intent_id,
        approval_intent_fingerprint=request.approval.approval_intent_fingerprint,
        candidate_record_id=request.approval.candidate_record_id,
        candidate_envelope_fingerprint=request.approval.candidate_envelope_fingerprint,
        admission_fingerprint=request.approval.admission_fingerprint,
        candidate_record_fingerprint=request.approval.candidate_record_fingerprint,
    )
    facts = ValidationFactsV1(
        authenticated_operator_id="operator-1",
        candidate=candidate,
        approval=approval,
        current_destination_fingerprint=request.subject.destination_fingerprint,
        replay=NoReplayEvidenceV1("fresh"),
    )
    return request, facts


def test_valid_request_is_deterministic_unsupported_and_non_authorizing() -> None:
    request, facts = valid_inputs()
    first = validate_install_container_request(
        request, facts=facts, validated_at="2026-08-28T12:01:00Z"
    )
    second = validate_install_container_request(
        request, facts=facts, validated_at="2026-08-28T12:01:00Z"
    )
    assert first == second
    assert first.status == "valid_but_unsupported"
    assert first.reason_codes == ()
    assert not first.execution_supported
    assert not first.dispatch_allowed
    assert not first.mutation_allowed
    assert not first.replay_allowed
    assert first.evidence.evidence_fingerprint == second.evidence.evidence_fingerprint


def test_local_service_composes_injected_facts_and_returns_closed_evidence() -> None:
    request, facts = valid_inputs()
    service = InstallContainerValidationService(
        facts=facts,
        validated_at="2026-08-28T12:01:00Z",
    )

    result = service.validate(
        json.dumps(request.model_dump(mode="json")),
        correlation_id="local-validation-1",
    )

    assert result.status == "valid_but_unsupported"
    assert result.reason_codes == ()
    assert result.evidence.request_id == request.request_id
    assert result.execution_supported is False
    assert result.dispatch_allowed is False
    assert result.mutation_allowed is False
    assert result.replay_allowed is False


def test_local_service_redacts_malformed_input() -> None:
    _, facts = valid_inputs()
    service = InstallContainerValidationService(
        facts=facts,
        validated_at="2026-08-28T12:01:00Z",
    )

    result = service.validate(
        '{"token":"do-not-echo","token":"still-secret"}',
        correlation_id="local-validation-2",
    )

    assert isinstance(result, AgentInstallContainerErrorV1)
    assert result.redacted is True
    assert "secret" not in json.dumps(result.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("missing_candidate", ReasonCode.CANDIDATE_PROOF_MISSING),
        ("inactive", ReasonCode.CANDIDATE_NOT_ACTIVE),
        ("candidate_fingerprint", ReasonCode.CANDIDATE_PROOF_MISMATCH),
        ("missing_approval", ReasonCode.APPROVAL_PROOF_MISSING),
        ("foreign_operator", ReasonCode.APPROVAL_PROOF_MISMATCH),
        ("destination", ReasonCode.DESTINATION_IDENTITY_MISMATCH),
        ("source", ReasonCode.ARTIFACT_SOURCE_MISMATCH),
    ],
)
def test_invalid_proofs_operator_and_lineage_fail_closed(change, reason) -> None:
    request, facts = valid_inputs()
    if change == "missing_candidate":
        facts = replace(facts, candidate=None)
    elif change == "inactive":
        facts = replace(facts, candidate=replace(facts.candidate, active=False))
    elif change == "candidate_fingerprint":
        facts = replace(
            facts,
            candidate=replace(
                facts.candidate,
                candidate_record_fingerprint=request.approval.admission_fingerprint,
            ),
        )
    elif change == "missing_approval":
        facts = replace(facts, approval=None)
    elif change == "foreign_operator":
        facts = replace(facts, approval=replace(facts.approval, operator_id="operator-2"))
    elif change == "destination":
        facts = replace(facts, current_destination_fingerprint="2" * 64)
    else:
        facts = replace(
            facts,
            candidate=replace(facts.candidate, source_service="other-service"),
        )
    result = validate_install_container_request(
        request, facts=facts, validated_at="2026-08-28T12:01:00Z"
    )
    assert result.status == "rejected"
    assert reason in result.reason_codes
    assert result.evidence.reason_codes == result.reason_codes


def test_expiry_and_no_replay_evidence_are_terminal() -> None:
    request, facts = valid_inputs()
    expired = validate_install_container_request(
        request, facts=facts, validated_at="2026-08-28T12:05:00Z"
    )
    assert expired.reason_codes == (ReasonCode.REQUEST_NOT_CURRENT,)

    ambiguous = validate_install_container_request(
        request,
        facts=replace(facts, replay=NoReplayEvidenceV1("ambiguous")),
        validated_at="2026-08-28T12:01:00Z",
    )
    assert ambiguous.reason_codes == (ReasonCode.REQUEST_REPLAY_OR_DUPLICATE,)

    duplicate = validate_install_container_request(
        request,
        facts=replace(facts, replay=NoReplayEvidenceV1("exact_duplicate", expired)),
        validated_at="2026-08-28T12:01:00Z",
    )
    assert duplicate is expired


def test_malformed_artifact_and_hostile_input_return_only_redacted_error() -> None:
    _, facts = valid_inputs()
    hostile = request_dict()
    hostile["artifact"]["environment"] = ["TOKEN=secret-value"]
    payload = json.dumps(hostile)
    result = validate_install_container_json(
        payload,
        facts=facts,
        validated_at="2026-08-28T12:01:00Z",
        correlation_id="validation-1",
    )
    assert isinstance(result, AgentInstallContainerErrorV1)
    assert result.redacted is True
    dumped = json.dumps(result.model_dump(mode="json"))
    assert "secret-value" not in dumped
    assert set(result.model_dump()) == {
        "schema", "reason_code", "request_id", "request_fingerprint",
        "correlation_id", "redacted",
    }


def test_validation_has_no_runtime_network_process_or_filesystem_side_effects(
    monkeypatch, tmp_path: Path
) -> None:
    request, facts = valid_inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("side-effect boundary was called")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    before = tuple(tmp_path.iterdir())
    result = validate_install_container_request(
        request, facts=facts, validated_at="2026-08-28T12:01:00Z"
    )
    assert result.status == "valid_but_unsupported"
    assert tuple(tmp_path.iterdir()) == before


def test_replay_evidence_shape_rejects_missing_or_unexpected_original() -> None:
    request, facts = valid_inputs()
    validation = validate_install_container_request(
        request, facts=facts, validated_at="2026-08-28T12:01:00Z"
    )
    with pytest.raises(ValueError):
        NoReplayEvidenceV1("exact_duplicate")
    with pytest.raises(ValueError):
        NoReplayEvidenceV1("fresh", validation)
    with pytest.raises(ValueError):
        NoReplayEvidenceV1("retry")
