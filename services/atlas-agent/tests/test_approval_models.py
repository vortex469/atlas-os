"""Tests for immutable approval models."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
)


def make_request() -> ApprovalRequest:
    return ApprovalRequest(
        identifier="approval-a12-1",
        checkpoint_id="A12.1",
        title="Run Atlas Agent verification",
        requested_tool="pytest",
        requested_command=("python", "-m", "pytest", "-q", "tests"),
        rationale="Verify the approved implementation.",
    )


def test_approval_status_values() -> None:
    assert ApprovalStatus.PENDING.value == "pending"
    assert ApprovalStatus.APPROVED.value == "approved"
    assert ApprovalStatus.REJECTED.value == "rejected"


def test_approval_request_construction_and_equality() -> None:
    request = make_request()

    assert request.identifier == "approval-a12-1"
    assert request.checkpoint_id == "A12.1"
    assert request.title == "Run Atlas Agent verification"
    assert request.requested_tool == "pytest"
    assert request.requested_command == (
        "python",
        "-m",
        "pytest",
        "-q",
        "tests",
    )
    assert request.rationale == "Verify the approved implementation."
    assert request == make_request()
    assert request.workflow_id is None
    assert request.requested_working_directory is None


def test_approval_request_accepts_workflow_operation_binding() -> None:
    workdir = Path("/workspace/atlas")
    request = ApprovalRequest(
        identifier="approval-a15-2",
        checkpoint_id="A15.2",
        title="Approve implementation",
        requested_tool="codex",
        requested_command=("codex", "implement"),
        rationale="Approve the exact planned operation.",
        workflow_id="workflow-a15-2",
        requested_working_directory=workdir,
    )

    assert request.workflow_id == "workflow-a15-2"
    assert request.requested_command == ("codex", "implement")
    assert request.requested_working_directory is workdir


def test_approval_decision_defaults() -> None:
    decision = ApprovalDecision(
        request=make_request(),
        status=ApprovalStatus.PENDING,
    )

    assert decision.reviewer is None
    assert decision.reason is None


def test_approval_decision_accepts_reviewer_and_reason() -> None:
    decision = ApprovalDecision(
        request=make_request(),
        status=ApprovalStatus.APPROVED,
        reviewer="human-operator",
        reason="Scope and command reviewed.",
    )

    assert decision.reviewer == "human-operator"
    assert decision.reason == "Scope and command reviewed."


@pytest.mark.parametrize(
    ("status", "approved"),
    (
        (ApprovalStatus.PENDING, False),
        (ApprovalStatus.APPROVED, True),
        (ApprovalStatus.REJECTED, False),
    ),
)
def test_approval_result_approved(
    status: ApprovalStatus,
    approved: bool,
) -> None:
    decision = ApprovalDecision(
        request=make_request(),
        status=status,
    )

    assert ApprovalResult(decision=decision).approved is approved


def test_models_are_frozen() -> None:
    request = make_request()
    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING,
    )
    result = ApprovalResult(decision=decision)

    with pytest.raises(FrozenInstanceError):
        request.title = "Changed"

    with pytest.raises(FrozenInstanceError):
        decision.status = ApprovalStatus.APPROVED

    with pytest.raises(FrozenInstanceError):
        result.decision = decision


def test_models_use_slots() -> None:
    request = make_request()
    decision = ApprovalDecision(
        request=request,
        status=ApprovalStatus.PENDING,
    )
    result = ApprovalResult(decision=decision)

    assert not hasattr(request, "__dict__")
    assert not hasattr(decision, "__dict__")
    assert not hasattr(result, "__dict__")
