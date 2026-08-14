"""Tests for the approval engine."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.approval.engine import ApprovalEngine, ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
    CommitApprovalMetadata,
    OperationalApprovalMetadata,
    VerificationApprovalCheck,
    VerificationApprovalEnvironment,
)
from app.approval.repository import ApprovalRepository


def operational_approval_request() -> ApprovalRequest:
    now = datetime(2026, 8, 14, tzinfo=UTC)
    return ApprovalRequest(
        identifier="approval-operational-workflow-1",
        checkpoint_id="operational-action-1",
        title="Approve exact operational action",
        requested_tool="atlas-agent-operational-contract",
        requested_command=(),
        rationale="Approve the immutable semantic request.",
        workflow_id="workflow-1",
        purpose=ApprovalPurpose.OPERATIONAL_ACTION,
        operational_metadata=OperationalApprovalMetadata(
            action_request_id="operational-action-1",
            action_request_digest="operational-action-request-digest-v1:" + "a" * 64,
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:" + "b" * 64,
            operational_plan_fingerprint="operational-plan-fingerprint-v1:" + "c" * 64,
            provider_id="proxmox",
            resource_id="qemu/101",
            resource_type="qemu",
            target_fingerprint="operational-target-v1:" + "d" * 64,
            target_version="1",
            operation_intent="restart-service",
            disruption_scope="one service interruption",
            verification_digest="operational-verification-digest-v1:" + "e" * 64,
            generated_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
    )


def test_operational_approval_accepts_only_typed_non_executable_metadata() -> None:
    request = operational_approval_request()
    result = ApprovalEngine().evaluate(
        ApprovalDecision(request=request, status=ApprovalStatus.PENDING)
    )
    assert result.decision.request == request
    assert result.decision.request.requested_command == ()


def test_operational_metadata_is_rejected_on_repository_approval() -> None:
    request = operational_approval_request()
    with pytest.raises(ApprovalValidationError, match="Only operational"):
        ApprovalEngine().evaluate(
            ApprovalDecision(
                request=ApprovalRequest(
                    identifier=request.identifier,
                    checkpoint_id=request.checkpoint_id,
                    title=request.title,
                    requested_tool="codex",
                    requested_command=("codex",),
                    rationale=request.rationale,
                    purpose=ApprovalPurpose.IMPLEMENTATION,
                    operational_metadata=request.operational_metadata,
                ),
                status=ApprovalStatus.PENDING,
            )
        )


def test_expired_operational_approval_is_rejected() -> None:
    request = operational_approval_request()
    with pytest.raises(ApprovalValidationError, match="expired"):
        ApprovalEngine(clock=lambda: request.operational_metadata.expires_at).evaluate(  # type: ignore[union-attr]
            ApprovalDecision(
                request=request,
                status=ApprovalStatus.APPROVED,
                reviewer="operator",
            )
        )


def test_pending_decision_accepted_without_reviewer():
    """Test that pending decisions are accepted without a reviewer."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING,
        reviewer=None
    )

    result = engine.evaluate(decision)
    assert result.decision.status == ApprovalStatus.PENDING
    assert result.decision.reviewer is None


def test_approved_decision_accepted_with_reviewer():
    """Test that approved decisions are accepted with a reviewer."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.APPROVED,
        reviewer="test-reviewer"
    )

    result = engine.evaluate(decision)
    assert result.decision.status == ApprovalStatus.APPROVED
    assert result.decision.reviewer == "test-reviewer"


def test_rejected_decision_accepted_with_reviewer_and_reason():
    """Test that rejected decisions are accepted with a reviewer and reason."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.REJECTED,
        reviewer="test-reviewer",
        reason="test reason"
    )

    result = engine.evaluate(decision)
    assert result.decision.status == ApprovalStatus.REJECTED
    assert result.decision.reviewer == "test-reviewer"
    assert result.decision.reason == "test reason"


def test_request_string_fields_normalized():
    """Test that request string fields are normalized with strip()."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="  test-req  ",
        checkpoint_id="  test-checkpoint  ",
        title="  Test Title  ",
        requested_tool="  test-tool  ",
        requested_command=("echo hello",),
        rationale="  test rationale  "
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    result = engine.evaluate(decision)
    assert result.decision.request.identifier == "test-req"
    assert result.decision.request.checkpoint_id == "test-checkpoint"
    assert result.decision.request.title == "Test Title"
    assert result.decision.request.requested_tool == "test-tool"
    assert result.decision.request.rationale == "test rationale"


def test_reviewer_and_reason_normalized():
    """Test that reviewer and reason are normalized with strip()."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.APPROVED,
        reviewer="  test-reviewer  ",
        reason="  test reason  "
    )

    result = engine.evaluate(decision)
    assert result.decision.reviewer == "test-reviewer"
    assert result.decision.reason == "test reason"


def test_requested_command_order_preserved():
    """Test that requested_command order is preserved."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo first", "echo second", "echo third"),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    result = engine.evaluate(decision)
    assert result.decision.request.requested_command == ("echo first", "echo second", "echo third")


def test_blank_identifier_rejected():
    """Test that blank identifier is rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="   ",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request identifier cannot be blank"):
        engine.evaluate(decision)


def test_blank_checkpoint_id_rejected():
    """Test that blank checkpoint_id is rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="   ",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request checkpoint_id cannot be blank"):
        engine.evaluate(decision)


def test_blank_title_rejected():
    """Test that blank title is rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="   ",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request title cannot be blank"):
        engine.evaluate(decision)


def test_blank_requested_tool_rejected():
    """Test that blank requested_tool is rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="   ",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request requested_tool cannot be blank"):
        engine.evaluate(decision)


def test_blank_rationale_rejected():
    """Test that blank rationale is rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="   "
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request rationale cannot be blank"):
        engine.evaluate(decision)


def test_empty_requested_command_rejected():
    """Test that empty requested_command is rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=(),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request requested_command must contain at least one item"):
        engine.evaluate(decision)


def test_blank_requested_command_item_rejected():
    """Test that blank requested_command items are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello", "   "),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING
    )

    with pytest.raises(ApprovalValidationError, match="Approval request requested_command items cannot be blank"):
        engine.evaluate(decision)


def test_pending_decision_with_reviewer_rejected():
    """Test that pending decisions with reviewer are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING,
        reviewer="test-reviewer"
    )

    with pytest.raises(ApprovalValidationError, match="Pending decisions must not have a reviewer"):
        engine.evaluate(decision)


def test_approved_decision_without_reviewer_rejected():
    """Test that approved decisions without reviewer are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.APPROVED
    )

    with pytest.raises(ApprovalValidationError, match="Approved decisions must have a nonblank reviewer"):
        engine.evaluate(decision)


def test_approved_decision_with_blank_reviewer_rejected():
    """Test that approved decisions with blank reviewer are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.APPROVED,
        reviewer="   "
    )

    with pytest.raises(ApprovalValidationError, match="Approved decisions must have a nonblank reviewer"):
        engine.evaluate(decision)


def test_rejected_decision_without_reviewer_rejected():
    """Test that rejected decisions without reviewer are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.REJECTED
    )

    with pytest.raises(ApprovalValidationError, match="Rejected decisions must have a nonblank reviewer"):
        engine.evaluate(decision)


def test_rejected_decision_without_reason_rejected():
    """Test that rejected decisions without reason are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.REJECTED,
        reviewer="test-reviewer"
    )

    with pytest.raises(ApprovalValidationError, match="Rejected decisions must have a nonblank reason"):
        engine.evaluate(decision)


def test_rejected_decision_with_blank_reason_rejected():
    """Test that rejected decisions with blank reason are rejected."""
    engine = ApprovalEngine()

    request = ApprovalRequest(
        identifier="test-req",
        checkpoint_id="test-checkpoint",
        title="Test Title",
        requested_tool="test-tool",
        requested_command=("echo hello",),
        rationale="test rationale"
    )

    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.REJECTED,
        reviewer="test-reviewer",
        reason="   "
    )

    with pytest.raises(ApprovalValidationError, match="Rejected decisions must have a nonblank reason"):
        engine.evaluate(decision)


def test_verification_approval_preserves_ordered_normalized_metadata() -> None:
    request = ApprovalRequest(
        identifier=" approval-verification ",
        workflow_id=" workflow-a12-1 ",
        checkpoint_id=" A12.1 ",
        title=" Approve verification ",
        requested_tool=" verification ",
        requested_command=(" verification-suite ", " pytest "),
        requested_working_directory=Path("/workspace/atlas"),
        rationale=" Exact checks ",
        purpose=ApprovalPurpose.VERIFICATION,
        verification_checks=(
            VerificationApprovalCheck(
                identifier=" pytest ",
                command=(" python ", "-m", " pytest "),
                working_directory=Path("/workspace/atlas"),
                timeout_seconds=120,
                environment=(
                    VerificationApprovalEnvironment(
                        name=" ATLAS_ENV ",
                        value_digest="a" * 64,
                    ),
                ),
            ),
        ),
    )

    result = ApprovalEngine().evaluate(
        ApprovalDecision(request=request, status=ApprovalStatus.PENDING)
    )

    normalized = result.decision.request
    assert normalized.workflow_id == "workflow-a12-1"
    assert normalized.purpose is ApprovalPurpose.VERIFICATION
    assert normalized.verification_checks[0].command == (
        "python",
        "-m",
        "pytest",
    )
    assert normalized.verification_checks[0].environment[0].name == "ATLAS_ENV"


def test_verification_approval_rejects_invalid_digest() -> None:
    request = ApprovalRequest(
        identifier="approval-verification",
        workflow_id="workflow-a12-1",
        checkpoint_id="A12.1",
        title="Approve verification",
        requested_tool="verification",
        requested_command=("verification-suite", "pytest"),
        rationale="Exact checks",
        purpose=ApprovalPurpose.VERIFICATION,
        verification_checks=(
            VerificationApprovalCheck(
                identifier="pytest",
                command=("python", "-m", "pytest"),
                working_directory=Path("/workspace/atlas"),
                timeout_seconds=None,
                environment=(
                    VerificationApprovalEnvironment(
                        name="ATLAS_ENV",
                        value_digest="secret",
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(
        ApprovalValidationError,
        match="lowercase SHA-256",
    ):
        ApprovalEngine().evaluate(
            ApprovalDecision(request=request, status=ApprovalStatus.PENDING)
        )


def test_commit_approval_preserves_normalized_metadata() -> None:
    request = ApprovalRequest(
        identifier=" approval-commit ",
        workflow_id=" workflow-a12-2 ",
        checkpoint_id=" A12.2 ",
        title=" Approve commit ",
        requested_tool=" git ",
        requested_command=(" git-commit ", " app/workflow/engine.py "),
        requested_working_directory=Path("/workspace/atlas"),
        rationale=" Exact commit ",
        purpose=ApprovalPurpose.COMMIT,
        commit_metadata=CommitApprovalMetadata(
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            reviewed_files=(Path("app/workflow/engine.py"),),
            reviewed_content_fingerprint="a" * 64,
            commit_message="feat(agent): workflow automation",
        ),
    )

    result = ApprovalEngine().evaluate(
        ApprovalDecision(request=request, status=ApprovalStatus.PENDING)
    )

    normalized = result.decision.request
    assert normalized.workflow_id == "workflow-a12-2"
    assert normalized.purpose is ApprovalPurpose.COMMIT
    assert normalized.commit_metadata is not None
    assert normalized.commit_metadata.reviewed_files == (Path("app/workflow/engine.py"),)
    assert normalized.verification_checks == ()


@pytest.mark.parametrize(
    "approval_request",
    (
        ApprovalRequest(
            identifier="approval-commit",
            workflow_id="workflow-a12-2",
            checkpoint_id="A12.2",
            title="Approve commit",
            requested_tool="git",
            requested_command=("git-commit", "app/workflow/engine.py"),
            rationale="Exact commit",
            purpose=ApprovalPurpose.COMMIT,
        ),
        ApprovalRequest(
            identifier="approval-implementation",
            checkpoint_id="A12.2",
            title="Approve implementation",
            requested_tool="codex",
            requested_command=("codex", "implement"),
            rationale="Exact implementation",
            commit_metadata=CommitApprovalMetadata(
                expected_branch="feature/atlas-agent",
                expected_head="abc123",
                reviewed_files=(Path("app/workflow/engine.py"),),
                reviewed_content_fingerprint="a" * 64,
                commit_message="feat(agent): workflow automation",
            ),
        ),
    ),
)
def test_commit_approval_rejects_invalid_metadata_combinations(
    approval_request: ApprovalRequest,
) -> None:
    with pytest.raises(ApprovalValidationError):
        ApprovalEngine().evaluate(
            ApprovalDecision(request=approval_request, status=ApprovalStatus.PENDING)
        )


def test_repository_terminal_decision_is_immutable_under_concurrency() -> None:
    repository = ApprovalRepository()
    request = ApprovalRequest(
        identifier="approval-a12-1",
        checkpoint_id="A12.1",
        title="Approve implementation",
        requested_tool="codex",
        requested_command=("codex", "implement"),
        rationale="Exact implementation.",
    )
    repository.save_request(request)
    decisions = (
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="reviewer-a",
        ),
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.REJECTED,
            reviewer="reviewer-b",
            reason="Rejected.",
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda decision: repository.update_decision(
                    request.identifier,
                    decision,
                ),
                decisions,
            )
        )

    assert sorted(results) == [False, True]
    stored = repository.get_request(request.identifier)
    assert stored is not None
    assert stored.decision in decisions
    assert not repository.update_decision(
        request.identifier,
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="replacement",
        ),
    )
