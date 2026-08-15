"""Deterministic read-only operational recovery diagnostic tests."""

from types import SimpleNamespace

import pytest
from app.workflow.recovery_diagnostic import project_recovery_diagnostic


def _facts(**overrides):
    values = {
        "applicable": True,
        "workflow_id": "workflow-1",
        "agent_execution_record_present": True,
        "core_record_present": True,
        "request_digest_match": True,
        "action_request_id": "request-1",
        "availability": "complete",
        "consistency_status": "consistent",
        "transition_sequence_valid": True,
        "barrier_crossed": True,
        "provider_operation_captured": True,
        "dispatch_status": "succeeded",
        "verification_status": "succeeded",
        "target_fingerprint": "fingerprint-1",
        "observed_target_fingerprint": "fingerprint-1",
        "observed_state": "running",
        "observed_health": "running",
        "agent_terminal": True,
        "terminal": True,
        "core_record_state": "verified",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_verified_terminal_workflow_is_healthy() -> None:
    result = project_recovery_diagnostic(_facts())

    assert result.diagnostic_status == "healthy"
    assert result.consistency == "consistent"
    assert result.controlled_reason is None
    assert result.safe_next_action == "none"
    assert result.verification_evidence.target_fingerprint_state == "unchanged"


@pytest.mark.parametrize(
    ("overrides", "status", "consistency", "reason", "action"),
    [
        (
            {"agent_terminal": False, "terminal": False, "core_record_state": "succeeded", "verification_status": None},
            "pending", "consistent", "verification_pending", "wait_for_verification",
        ),
        (
            {"agent_terminal": False, "terminal": False, "core_record_state": "verifying", "verification_status": None},
            "recovery_in_progress", "consistent", "verification_pending", "wait_for_verification",
        ),
        (
            {"availability": "unavailable", "core_record_present": False, "request_digest_match": None, "terminal": False, "agent_terminal": False},
            "unavailable", "core_unavailable", "core_unavailable", "restore_core_availability",
        ),
        (
            {"core_record_present": False, "request_digest_match": None, "terminal": False, "agent_terminal": False},
            "attention_required", "agent_only", "missing_core_record", "operator_review_required",
        ),
        (
            {"request_digest_match": False, "consistency_status": "mismatch"},
            "attention_required", "immutable_mismatch", "immutable_request_mismatch", "operator_review_required",
        ),
        (
            {"transition_sequence_valid": False},
            "attention_required", "transition_mismatch", "invalid_transition_sequence", "preserve_evidence",
        ),
        (
            {"agent_terminal": False},
            "attention_required", "terminal_mismatch", "terminal_state_disagreement", "operator_review_required",
        ),
        (
            {"dispatch_status": "outcome_unknown", "core_record_state": "outcome_unknown", "terminal": False, "agent_terminal": False, "verification_status": None},
            "outcome_uncertain", "consistent", "dispatch_outcome_unknown", "preserve_evidence",
        ),
        (
            {"verification_status": "verification_failed", "core_record_state": "verification_failed", "observed_health": "degraded"},
            "attention_required", "consistent", "verification_failed", "inspect_target_read_only",
        ),
        (
            {"verification_status": "target_replaced", "core_record_state": "target_replaced", "observed_target_fingerprint": "fingerprint-2"},
            "attention_required", "consistent", "target_replaced", "new_request_only_after_terminal",
        ),
    ],
)
def test_diagnostic_rules(overrides, status, consistency, reason, action) -> None:
    result = project_recovery_diagnostic(_facts(**overrides))

    assert result.diagnostic_status == status
    assert result.consistency == consistency
    assert result.controlled_reason == reason
    assert result.safe_next_action == action


def test_repository_workflow_is_typed_not_applicable() -> None:
    result = project_recovery_diagnostic(
        _facts(
            applicable=False,
            agent_execution_record_present=False,
            core_record_present=False,
            request_digest_match=None,
            action_request_id=None,
            barrier_crossed=False,
            provider_operation_captured=False,
            dispatch_status=None,
            verification_status=None,
            target_fingerprint=None,
            observed_target_fingerprint=None,
            agent_terminal=False,
            terminal=False,
            core_record_state=None,
        )
    )

    assert result.applicable is False
    assert result.controlled_reason == "not_applicable"
    assert result.verification_evidence.target_fingerprint_state == "not_applicable"


def test_diagnostic_contract_exposes_no_sensitive_or_executable_fields() -> None:
    result = project_recovery_diagnostic(_facts())
    payload = result.model_dump_json()
    forbidden = (
        "authorization", "cookie", "csrf", "credential", "token", "vmgenid",
        "native_payload", "command", "environment", "exception", "traceback",
        "worker", "sandbox",
    )

    assert not any(value in payload.lower() for value in forbidden)
