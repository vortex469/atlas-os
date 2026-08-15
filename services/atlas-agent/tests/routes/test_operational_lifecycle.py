"""Workflow-scoped unified operational lifecycle read tests."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.core_client.exceptions import AtlasCoreConnectionError
from app.core_client.models import (
    CoreOperationalLifecycleRead,
    CoreOperationalLifecycleTransition,
)
from app.routes.workflow import WorkflowOperationalLifecycleResponse
from app.workflow.models import OperationalExecutionReference, OperationalExecutionStage
from tests.routes.test_workflow import (
    candidate_workflow_session,
    make_client,
    save_candidate_workflow,
)
from tests.test_operational_execution import _approval, _session


def test_agent_lifecycle_contract_contains_only_sanitized_fields() -> None:
    fields = set(WorkflowOperationalLifecycleResponse.model_fields)
    forbidden_fragments = {
        "authorization",
        "cookie",
        "csrf",
        "credential",
        "bearer_token",
        "vmgenid",
        "identity_token",
        "native_payload",
        "command",
        "environment",
        "exception",
        "traceback",
        "worker",
        "sandbox",
    }

    assert not {
        field
        for field in fields
        if any(fragment in field for fragment in forbidden_fragments)
    }


def test_repository_workflow_lifecycle_is_not_applicable(tmp_path, monkeypatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    save_candidate_workflow(container, candidate_workflow_session(tmp_path))

    response = client.get(
        "/api/v1/agent/workflows/workflow-123/operational-lifecycle"
    )

    assert response.status_code == 200
    assert response.json()["applicable"] is False
    assert response.json()["availability"] == "not_applicable"


def test_repository_recovery_diagnostic_is_typed_not_applicable(
    tmp_path, monkeypatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    save_candidate_workflow(container, candidate_workflow_session(tmp_path))
    container.core_client.get_operational_lifecycle_read = AsyncMock()

    response = client.get(
        "/api/v1/agent/workflows/workflow-123/recovery-diagnostic"
    )

    assert response.status_code == 200
    assert response.json()["applicable"] is False
    assert response.json()["controlled_reason"] == "not_applicable"
    container.core_client.get_operational_lifecycle_read.assert_not_called()

    bundle = client.get(
        "/api/v1/agent/workflows/workflow-123/support-bundle"
    )
    assert bundle.status_code == 200
    assert bundle.json()["applicable"] is False
    assert bundle.json()["diagnostic"]["controlled_reason"] == "not_applicable"
    container.core_client.get_operational_lifecycle_read.assert_not_called()


def test_workflow_history_filter_returns_only_operational_effect(tmp_path, monkeypatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    save_candidate_workflow(container, candidate_workflow_session(tmp_path))
    operational = _session()
    container.workflow_state.create_session(operational)

    response = client.get(
        "/api/v1/agent/workflows",
        params={"effect_kind": "operational_action", "limit": 10},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["workflow_id"] == operational.identifier
    assert response.json()["items"][0]["effect_kind"] == "operational_action"


def test_completed_operational_lifecycle_preserves_owner_states(tmp_path, monkeypatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    session = _session()
    action = session.operational_action_request
    assert action is not None
    now = datetime.now(UTC)
    session = replace(
        session,
        operational_execution_reference=OperationalExecutionReference(
            request_id=action.request_id,
            request_digest=action.request_digest,
            stage=OperationalExecutionStage.VERIFIED,
            dispatch_status="succeeded",
            ledger_state="verified",
            provider_operation_id="UPID:sanitized",
            verification_status="succeeded",
            submitted_at=now,
            last_observed_at=now,
            terminal=True,
        ),
    )
    container.workflow_state.create_session(session)
    approval = _approval(session)
    container.approval_repository.replace_snapshot(
        {approval.decision.request.identifier: approval}
    )
    container.core_client.get_operational_lifecycle_read = AsyncMock(
        return_value=CoreOperationalLifecycleRead(
            request_id=action.request_id,
            request_digest=action.request_digest,
            ledger_state="verified",
            transitions=(
                CoreOperationalLifecycleTransition(
                    sequence=1, state="claimed", occurred_at=now
                ),
                CoreOperationalLifecycleTransition(
                    sequence=2, state="dispatching", occurred_at=now
                ),
                CoreOperationalLifecycleTransition(
                    sequence=3, state="verified", occurred_at=now
                ),
            ),
            transition_sequence_valid=True,
            barrier_crossed=True,
            barrier_crossing_count=1,
            provider_operation_captured=True,
            provider_operation_capture_count=1,
            dispatch_status="succeeded",
            provider_operation_reference="UPID:sanitized",
            dispatch_started_at=now,
            dispatch_completed_at=now,
            verification_status="succeeded",
            observed_target_fingerprint=action.target_fingerprint,
            observed_state="running",
            observed_health="running",
            verification_started_at=now,
            verification_completed_at=now,
            verification_deadline=action.expires_at,
            terminal=True,
            controlled_reason=None,
        )
    )

    response = client.get(
        f"/api/v1/agent/workflows/{session.identifier}/operational-lifecycle"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["consistency_status"] == "consistent"
    assert body["agent_execution_stage"] == "verified"
    assert body["core_record_state"] == "verified"
    assert body["barrier_crossing_count"] == 1
    assert body["provider_operation_capture_count"] == 1
    assert body["transition_sequence_valid"] is True
    assert [item["state"] for item in body["transitions"]] == [
        "claimed",
        "dispatching",
        "verified",
    ]
    assert body["action_approval"]["actionable"] is False
    assert "vmgenid" not in response.text
    assert "Authorization" not in response.text


def test_core_failure_is_controlled_partial_state(tmp_path, monkeypatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    session = _session()
    action = session.operational_action_request
    assert action is not None
    now = datetime.now(UTC)
    session = replace(
        session,
        operational_execution_reference=OperationalExecutionReference(
            request_id=action.request_id,
            request_digest=action.request_digest,
            stage=OperationalExecutionStage.VERIFICATION_PENDING,
            dispatch_status="succeeded",
            ledger_state="verifying",
            provider_operation_id="UPID:sanitized",
            verification_status=None,
            submitted_at=now,
            last_observed_at=now,
            terminal=False,
        ),
    )
    container.workflow_state.create_session(session)
    container.core_client.get_operational_lifecycle_read = AsyncMock(
        side_effect=AtlasCoreConnectionError("secret native exception")
    )

    response = client.get(
        f"/api/v1/agent/workflows/{session.identifier}/operational-lifecycle"
    )

    assert response.status_code == 200
    assert response.json()["availability"] == "unavailable"
    assert response.json()["controlled_reason"] == "core_lifecycle_unavailable"
    assert "secret native exception" not in response.text


def test_approved_request_not_submitted_has_no_fabricated_core_record(
    tmp_path, monkeypatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    session = _session()
    container.workflow_state.create_session(session)
    container.core_client.get_operational_lifecycle_read = AsyncMock()

    response = client.get(
        f"/api/v1/agent/workflows/{session.identifier}/operational-lifecycle"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "agent_only"
    assert body["controlled_reason"] == "not_submitted"
    assert body["core_record_state"] is None
    container.core_client.get_operational_lifecycle_read.assert_not_called()


def test_submission_outcome_unknown_with_no_core_record_remains_distinct(
    tmp_path, monkeypatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    session = _session()
    action = session.operational_action_request
    assert action is not None
    now = datetime.now(UTC)
    session = replace(
        session,
        operational_execution_reference=OperationalExecutionReference(
            request_id=action.request_id,
            request_digest=action.request_digest,
            stage=OperationalExecutionStage.SUBMISSION_OUTCOME_UNKNOWN,
            dispatch_status=None,
            ledger_state=None,
            provider_operation_id=None,
            verification_status=None,
            submitted_at=now,
            last_observed_at=now,
            terminal=False,
            controlled_reason="submission_outcome_unknown",
        ),
    )
    container.workflow_state.create_session(session)
    container.core_client.get_operational_lifecycle_read = AsyncMock(return_value=None)

    response = client.get(
        f"/api/v1/agent/workflows/{session.identifier}/operational-lifecycle"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_execution_stage"] == "submission_outcome_unknown"
    assert body["controlled_reason"] == "submission_outcome_unknown"
    assert body["terminal"] is False


def test_recovery_diagnostic_missing_core_is_read_only(tmp_path, monkeypatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    session = _session()
    action = session.operational_action_request
    assert action is not None
    now = datetime.now(UTC)
    session = replace(
        session,
        operational_execution_reference=OperationalExecutionReference(
            request_id=action.request_id,
            request_digest=action.request_digest,
            stage=OperationalExecutionStage.DISPATCH_PENDING,
            dispatch_status=None,
            ledger_state=None,
            provider_operation_id=None,
            verification_status=None,
            submitted_at=now,
            last_observed_at=now,
            terminal=False,
        ),
    )
    container.workflow_state.create_session(session)
    before = container.workflow_state.get_session(session.identifier)
    container.core_client.get_operational_lifecycle_read = AsyncMock(return_value=None)

    response = client.get(
        f"/api/v1/agent/workflows/{session.identifier}/recovery-diagnostic"
    )

    assert response.status_code == 200
    assert response.json()["diagnostic_status"] == "attention_required"
    assert response.json()["controlled_reason"] == "missing_core_record"
    assert container.workflow_state.get_session(session.identifier) == before
    container.core_client.get_operational_lifecycle_read.assert_awaited_once_with(
        action.request_id
    )


def test_support_bundle_core_unavailable_is_sanitized_and_read_only(
    tmp_path, monkeypatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    session = _session()
    action = session.operational_action_request
    assert action is not None
    now = datetime.now(UTC)
    session = replace(
        session,
        operational_execution_reference=OperationalExecutionReference(
            request_id=action.request_id,
            request_digest=action.request_digest,
            stage=OperationalExecutionStage.VERIFICATION_PENDING,
            dispatch_status="succeeded",
            ledger_state="verifying",
            provider_operation_id="UPID:sanitized",
            verification_status=None,
            submitted_at=now,
            last_observed_at=now,
            terminal=False,
            audit_events=("authenticated_dispatch_submitted", "unsafe exception text"),
        ),
    )
    container.workflow_state.create_session(session)
    before = container.workflow_state.get_session(session.identifier)
    container.core_client.get_operational_lifecycle_read = AsyncMock(
        side_effect=AtlasCoreConnectionError("secret native exception")
    )

    response = client.get(
        f"/api/v1/agent/workflows/{session.identifier}/support-bundle"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["schema_version"] == "atlas-operational-support-bundle-v1"
    assert body["diagnostic"]["diagnostic_status"] == "unavailable"
    assert body["lifecycle"]["availability"] == "unavailable"
    assert body["audit_refs"] == [
        {"event_type": "authenticated_dispatch_submitted"}
    ]
    assert "secret native exception" not in response.text
    assert "unsafe exception text" not in response.text
    assert container.workflow_state.get_session(session.identifier) == before
    container.core_client.get_operational_lifecycle_read.assert_awaited_once_with(
        action.request_id
    )
