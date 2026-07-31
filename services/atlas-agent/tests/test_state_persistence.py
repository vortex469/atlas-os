"""Tests for file-backed Atlas Agent state persistence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
    CommitApprovalMetadata,
)
from app.approval.repository import ApprovalRepository
from app.context.models import ActionHistoryContext, ActionHistoryEntry, AgentContext
from app.execution.models import EnvironmentVariable
from app.model_providers.models import ModelResponse
from app.persistence.snapshot import (
    AgentStatePersistenceCoordinator,
    StatePersistenceError,
)
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitRequest
from app.review.models import ReviewReport, ReviewStatus
from app.verification.models import (
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowRequest, WorkflowSession, WorkflowSessionState
from app.workflow.state import WorkflowStateStore


def checkpoint() -> RoadmapCheckpoint:
    return RoadmapCheckpoint(
        identifier="A15.1",
        title="File-backed recovery",
        goal="Recover workflow state.",
        affected_files=(Path("app/workflow/engine.py"),),
        required_tests=("pytest",),
    )


def plan(root: Path) -> ImplementationPlan:
    return ImplementationPlan(
        checkpoint_id="A15.1",
        title="File-backed recovery",
        goal="Recover workflow state.",
        repository_root=root,
        branch="feature/atlas-agent",
        head_commit="abc123",
        scope_items=(),
        affected_files=(Path("app/workflow/engine.py"),),
        required_tests=("pytest",),
        risks=(),
    )


def request(root: Path, *, env_value: str = "secret-token") -> WorkflowRequest:
    return WorkflowRequest(
        checkpoint=checkpoint(),
        repository_root=root,
        execution_identifier="execution-a15",
        execution_argv=("codex", "implement"),
        execution_workdir=root,
        verification_checks=(
            VerificationCheck(
                identifier="pytest",
                argv=("python", "-m", "pytest"),
                working_directory=root,
                environment=(
                    EnvironmentVariable(name="ATLAS_TEST_SECRET", value=env_value),
                ),
            ),
        ),
        review_identifier="review-a15",
    )


def session(
    root: Path,
    state: WorkflowSessionState,
    *,
    identifier: str = "workflow-a15",
) -> WorkflowSession:
    return WorkflowSession(
        identifier=identifier,
        request=request(root),
        plan=plan(root),
        state=state,
    )


def approval_request(
    workflow_id: str,
    purpose: ApprovalPurpose,
    *,
    root: Path,
    fingerprint: str = "a" * 64,
) -> ApprovalRequest:
    if purpose is ApprovalPurpose.IMPLEMENTATION:
        return ApprovalRequest(
            identifier=f"approval-{workflow_id}",
            workflow_id=workflow_id,
            checkpoint_id="A15.1",
            title="Approve implementation",
            requested_tool="codex",
            requested_command=("codex", "implement"),
            requested_working_directory=root,
            rationale="Approve implementation.",
        )
    if purpose is ApprovalPurpose.VERIFICATION:
        return ApprovalRequest(
            identifier=f"approval-verification-{workflow_id}",
            workflow_id=workflow_id,
            checkpoint_id="A15.1",
            title="Approve verification",
            requested_tool="verification",
            requested_command=("verification-suite", "pytest"),
            requested_working_directory=root,
            rationale="Approve verification.",
            purpose=ApprovalPurpose.VERIFICATION,
        )
    return ApprovalRequest(
        identifier=f"approval-commit-{workflow_id}",
        workflow_id=workflow_id,
        checkpoint_id="A15.1",
        title="Approve commit",
        requested_tool="git",
        requested_command=("git-commit", "app/workflow/engine.py"),
        requested_working_directory=root,
        rationale="Approve commit.",
        purpose=ApprovalPurpose.COMMIT,
        commit_metadata=None,
    )


def coordinator(
    state_dir: Path,
    workflow_state: WorkflowStateStore | None = None,
    approvals: ApprovalRepository | None = None,
) -> AgentStatePersistenceCoordinator:
    return AgentStatePersistenceCoordinator(
        state_dir=state_dir,
        workflow_state=workflow_state or WorkflowStateStore(),
        approval_repository=approvals or ApprovalRepository(),
    )


def test_missing_snapshot_starts_empty(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)

    persistence.initialize()

    assert workflow_state.get_sprint() is None
    assert approvals.get_pending_requests() == []


def test_full_workflow_and_approval_round_trip_redacts_env(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    stored_session = session(tmp_path, WorkflowSessionState.AWAITING_APPROVAL)
    approval = approval_request(
        stored_session.identifier,
        ApprovalPurpose.IMPLEMENTATION,
        root=tmp_path,
    )

    persistence.mutate_aggregate(
        lambda workflow, approval_repo: (
            workflow.create_session(stored_session),
            approval_repo.save_request(approval),
        )
    )

    raw_json = persistence.snapshot_path.read_text()
    assert "secret-token" not in raw_json
    assert "value_sha256" in raw_json
    assert json.loads(raw_json) == json.loads(raw_json)

    recovered_workflow = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered = coordinator(tmp_path, recovered_workflow, recovered_approvals)
    recovered.initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session == replace(
        stored_session,
        request=replace(
            stored_session.request,
            verification_checks=(
                replace(
                    stored_session.request.verification_checks[0],
                    environment=(
                        EnvironmentVariable(
                            name="ATLAS_TEST_SECRET",
                            value="",
                            value_digest=sha256(b"secret-token").hexdigest(),
                            redacted=True,
                        ),
                    ),
                ),
            ),
        ),
    )
    assert recovered_approvals.get_request(approval.identifier) is not None


def test_action_history_context_round_trips_in_workflow_snapshot(
    tmp_path: Path,
) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    timestamp = datetime(2026, 7, 31, 16, 0, tzinfo=timezone.utc)
    context = AgentContext(
        atlas="atlas",
        assistant="orion",
        engine="atlas-core",
        release="test",
        services={},
        action_history=ActionHistoryContext(
            entries=(
                ActionHistoryEntry(
                    identifier="entry-1",
                    provider_id="docker",
                    provider_name="Docker",
                    action_id="restart-container",
                    action_label="Restart Container",
                    status="failed",
                    success=False,
                    message="Container restart failed after bounded timeout.",
                    confirmed=True,
                    destructive=True,
                    parameter_names=("container",),
                    request_id="request-1",
                    started_at=timestamp,
                    completed_at=timestamp,
                    duration_ms=12.5,
                ),
            ),
        ),
    )
    stored_session = replace(
        session(tmp_path, WorkflowSessionState.COMPLETED),
        context=context,
    )
    persistence.mutate_workflow(lambda workflow: workflow.create_session(stored_session))

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.context == context


def test_review_analysis_round_trips_in_workflow_snapshot(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    persistence = coordinator(tmp_path, workflow_state, ApprovalRepository())
    persistence.initialize()
    analysis = ModelResponse(
        text="Advisory review analysis.",
        model="test-model",
        provider_id="test-provider",
    )
    stored_session = replace(
        session(tmp_path, WorkflowSessionState.AWAITING_COMMIT_APPROVAL),
        review_report=ReviewReport(
            request_id="review-a15",
            checkpoint_id="A15.1",
            status=ReviewStatus.APPROVED,
            findings=(),
            recommendations=(),
        ),
        review_analysis=analysis,
        commit_request=CommitRequest(
            repository_root=tmp_path,
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            paths=(Path("app/workflow/engine.py"),),
            message="feat(agent): workflow recovery",
        ),
        reviewed_files=(Path("app/workflow/engine.py"),),
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        reviewed_content_fingerprint="a" * 64,
    )
    approval = approval_request(
        stored_session.identifier,
        ApprovalPurpose.COMMIT,
        root=tmp_path,
    )
    approval = replace(
        approval,
        commit_metadata=CommitApprovalMetadata(
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            reviewed_files=(Path("app/workflow/engine.py"),),
            reviewed_content_fingerprint="a" * 64,
            commit_message="feat(agent): workflow recovery",
        ),
    )

    persistence.mutate_aggregate(
        lambda workflow, approvals: (
            workflow.create_session(stored_session),
            approvals.save_request(approval),
        )
    )

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.review_analysis == analysis


def test_old_snapshot_without_review_analysis_loads_none(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    persistence = coordinator(tmp_path, workflow_state, ApprovalRepository())
    persistence.initialize()
    stored_session = session(tmp_path, WorkflowSessionState.COMPLETED)
    persistence.mutate_workflow(lambda workflow: workflow.create_session(stored_session))
    payload = json.loads(persistence.snapshot_path.read_text())
    del payload["workflow_state"]["sessions"][stored_session.identifier]["review_analysis"]
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.review_analysis is None


def test_claimed_state_recovers_to_blocked_and_persists(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    claimed = session(tmp_path, WorkflowSessionState.EXECUTING)
    persistence.mutate_workflow(lambda workflow: workflow.create_session(claimed))

    recovered_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered = coordinator(tmp_path, recovered_state, recovered_approvals)
    recovered.initialize()

    recovered_session = recovered_state.get_session(claimed.identifier)
    assert recovered_session is not None
    assert recovered_session.state is WorkflowSessionState.BLOCKED
    assert recovered_session.blocked_reason == "implementation interrupted by process restart"
    persisted = json.loads(recovered.snapshot_path.read_text())
    assert persisted["workflow_state"]["sessions"][claimed.identifier]["state"] == "blocked"


def test_pending_approved_rejected_and_standalone_approvals_recover(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    standalone = ApprovalRequest(
        identifier="approval-standalone",
        checkpoint_id="A15.1",
        title="Standalone",
        requested_tool="tool",
        requested_command=("tool",),
        rationale="Standalone approval.",
    )
    rejected = ApprovalRequest(
        identifier="approval-standalone-rejected",
        checkpoint_id="A15.1",
        title="Standalone rejected",
        requested_tool="tool",
        requested_command=("tool",),
        rationale="Standalone approval.",
    )
    persistence.mutate_approval(
        lambda repo: (
            repo.save_request(standalone),
            repo.save_request(rejected),
            repo.update_decision(
                standalone.identifier,
                ApprovalDecision(
                    request=standalone,
                    status=ApprovalStatus.APPROVED,
                ),
            ),
            repo.update_decision(
                rejected.identifier,
                ApprovalDecision(
                    request=rejected,
                    status=ApprovalStatus.REJECTED,
                ),
            ),
        )
    )

    recovered_approvals = ApprovalRepository()
    recovered = coordinator(tmp_path, WorkflowStateStore(), recovered_approvals)
    recovered.initialize()

    assert recovered_approvals.get_request(standalone.identifier).approved is True
    assert recovered_approvals.get_request(rejected.identifier).decision.status is ApprovalStatus.REJECTED
    assert recovered_approvals.update_decision(
        standalone.identifier,
        ApprovalDecision(request=standalone, status=ApprovalStatus.REJECTED),
    ) is False


def test_waiting_workflow_without_approval_fails_startup(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    workflow_state.create_session(session(tmp_path, WorkflowSessionState.AWAITING_APPROVAL))
    payload = persistence._encode_payload(workflow_state.export_snapshot(), {})
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path).initialize()


def test_corrupt_and_unsupported_snapshots_fail_startup(tmp_path: Path) -> None:
    path = tmp_path / "atlas-agent-state.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path).initialize()

    path.write_text(
        json.dumps(
            {
                "application": "atlas-agent",
                "schema_version": 999,
                "workflow_state": {"sessions": {}, "sprint": None, "verification": None, "review": None},
                "approvals": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path).initialize()


def test_failed_persistence_leaves_live_and_durable_state_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    baseline = session(tmp_path, WorkflowSessionState.BLOCKED, identifier="baseline")
    persistence.mutate_workflow(lambda workflow: workflow.create_session(baseline))
    before = persistence.snapshot_path.read_text()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("app.persistence.snapshot.os.replace", fail_replace)
    with pytest.raises(StatePersistenceError):
        persistence.mutate_workflow(
            lambda workflow: workflow.create_session(
                session(tmp_path, WorkflowSessionState.BLOCKED, identifier="new")
            )
        )

    assert workflow_state.get_session("new") is None
    assert persistence.snapshot_path.read_text() == before


def test_rehydrate_matching_env_permits_verification_without_persisting_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_TEST_SECRET", "secret-token")
    check = VerificationCheck(
        identifier="pytest",
        argv=("python", "-m", "pytest"),
        working_directory=tmp_path,
        environment=(
            EnvironmentVariable(
                name="ATLAS_TEST_SECRET",
                value="",
                value_digest=sha256(b"secret-token").hexdigest(),
                redacted=True,
            ),
        ),
    )

    rehydrated = WorkflowEngine._rehydrate_verification_checks((check,))

    assert rehydrated[0].environment[0].value == "secret-token"
    assert rehydrated[0].environment[0].redacted is False


def test_missing_or_mismatched_rehydrated_env_blocks_before_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = VerificationCheck(
        identifier="pytest",
        argv=("python", "-m", "pytest"),
        working_directory=tmp_path,
        environment=(
            EnvironmentVariable(
                name="ATLAS_TEST_SECRET",
                value="",
                value_digest=sha256(b"secret-token").hexdigest(),
                redacted=True,
            ),
        ),
    )

    monkeypatch.delenv("ATLAS_TEST_SECRET", raising=False)
    with pytest.raises(ValueError, match="unavailable"):
        WorkflowEngine._rehydrate_verification_checks((check,))

    monkeypatch.setenv("ATLAS_TEST_SECRET", "different")
    with pytest.raises(ValueError, match="digest mismatch"):
        WorkflowEngine._rehydrate_verification_checks((check,))


def test_commit_waiting_requires_matching_commit_metadata(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    commit_request = CommitRequest(
        repository_root=tmp_path,
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        paths=(Path("app/workflow/engine.py"),),
        message="feat(agent): file-backed recovery",
    )
    waiting = replace(
        session(tmp_path, WorkflowSessionState.AWAITING_COMMIT_APPROVAL),
        commit_request=commit_request,
        reviewed_files=(Path("app/workflow/engine.py"),),
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        reviewed_content_fingerprint="a" * 64,
    )
    bad_approval = approval_request(
        waiting.identifier,
        ApprovalPurpose.COMMIT,
        root=tmp_path,
        fingerprint="b" * 64,
    )

    with pytest.raises(StatePersistenceError):
        persistence.mutate_aggregate(
            lambda workflow, repo: (
                workflow.create_session(waiting),
                repo.save_request(bad_approval),
            )
        )

    assert workflow_state.get_session(waiting.identifier) is None


def test_workflow_reports_round_trip(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    workflow_state.publish_verification(
        VerificationReport(
            repository_root=tmp_path,
            results=(),
            status=VerificationStatus.PASSED,
            duration_seconds=1.0,
        )
    )
    workflow_state.publish_review(
        ReviewReport(
            request_id="review-a15",
            checkpoint_id="A15.1",
            status=ReviewStatus.APPROVED,
            findings=(),
            recommendations=(),
        )
    )
    workflow_state.create_session(session(tmp_path, WorkflowSessionState.COMPLETED))
    persistence.persist_current_state()

    recovered = WorkflowStateStore()
    coordinator(tmp_path, recovered, ApprovalRepository()).initialize()

    assert recovered.get_verification().status is VerificationStatus.PASSED
    assert recovered.get_review().status is ReviewStatus.APPROVED
    assert recovered.get_session("workflow-a15").state is WorkflowSessionState.COMPLETED


def test_failed_validation_leaves_live_state_unchanged(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()

    with pytest.raises(StatePersistenceError):
        persistence.mutate_workflow(
            lambda workflow: workflow.create_session(
                session(tmp_path, WorkflowSessionState.AWAITING_APPROVAL)
            )
        )

    assert workflow_state.get_session("workflow-a15") is None
