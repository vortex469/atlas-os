"""Tests for the approval engine."""

import pytest

from app.approval.engine import ApprovalEngine, ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
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
