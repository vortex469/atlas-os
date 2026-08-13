from pathlib import Path

import pytest
from app.approval.engine import ApprovalEngine
from app.approval.exceptions import ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
)
from app.persistence.snapshot import _decode_approval_request


def request(*, purpose=ApprovalPurpose.IMPLEMENTATION, command=(), workflow_id=None):
    return ApprovalRequest(
        identifier="approval-test",
        checkpoint_id="checkpoint",
        title="Test approval",
        requested_tool="atlas-agent",
        requested_command=command,
        rationale="Test rationale",
        workflow_id=workflow_id,
        requested_working_directory=Path("."),
        purpose=purpose,
    )


def test_generic_implementation_empty_command_remains_rejected():
    with pytest.raises(ApprovalValidationError, match="requested_command"):
        ApprovalEngine().evaluate(
            ApprovalDecision(request=request(), status=ApprovalStatus.APPROVED)
        )


def test_shell_approval_request_allows_empty_command_as_distinct_purpose():
    shell = request(
        purpose=ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL,
        workflow_id="candidate-workflow-test",
    )
    assert shell.requested_command == ()
    assert shell.purpose is ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL


def test_legacy_candidate_empty_implementation_approval_normalizes():
    restored = _decode_approval_request(
        {
            "identifier": "approval-candidate-workflow-test",
            "checkpoint_id": "checkpoint",
            "title": "shell",
            "requested_tool": "atlas-agent",
            "requested_command": [],
            "rationale": "shell",
            "workflow_id": "candidate-workflow-test",
            "requested_working_directory": ".",
            "purpose": "implementation",
        }
    )
    assert restored.purpose is ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL


@pytest.mark.parametrize(
    "workflow_id,command,purpose",
    [
        ("workflow-test", (), ApprovalPurpose.IMPLEMENTATION),
        ("candidate-workflow-test", ("run",), ApprovalPurpose.IMPLEMENTATION),
        ("candidate-workflow-test", (), ApprovalPurpose.VERIFICATION),
        ("candidate-workflow-test", (), ApprovalPurpose.COMMIT),
    ],
)
def test_legacy_normalization_rejects_non_shell_shapes(workflow_id, command, purpose):
    restored = _decode_approval_request(
        {
            "identifier": "approval-test",
            "checkpoint_id": "checkpoint",
            "title": "shell",
            "requested_tool": "atlas-agent",
            "requested_command": list(command),
            "rationale": "shell",
            "workflow_id": workflow_id,
            "requested_working_directory": ".",
            "purpose": purpose.value,
        }
    )
    assert restored.purpose is purpose


@pytest.mark.parametrize(
    ("workflow_id", "workflow_state", "purpose", "command"),
    [
        ("workflow-test", "awaiting_approval", ApprovalPurpose.IMPLEMENTATION, ()),
        (
            "candidate-workflow-test",
            "awaiting_implementation_approval",
            ApprovalPurpose.IMPLEMENTATION,
            (),
        ),
        (
            "candidate-workflow-test",
            "awaiting_approval",
            ApprovalPurpose.VERIFICATION,
            (),
        ),
        (
            "candidate-workflow-test",
            "awaiting_approval",
            ApprovalPurpose.COMMIT,
            (),
        ),
        (
            "candidate-workflow-test",
            "awaiting_approval",
            ApprovalPurpose.IMPLEMENTATION,
            ("docker", "compose"),
        ),
    ],
)
def test_legacy_normalization_negative_matrix_preserves_meaning(
    workflow_id, workflow_state, purpose, command
):
    # The state is included explicitly because only an awaiting shell boundary
    # is eligible for the historical empty implementation placeholder.
    payload = {
        "identifier": "approval-test",
        "checkpoint_id": "checkpoint",
        "title": "legacy approval",
        "requested_tool": "atlas-agent",
        "requested_command": list(command),
        "rationale": "legacy payload",
        "workflow_id": workflow_id,
        "workflow_state": workflow_state,
        "requested_working_directory": ".",
        "purpose": purpose.value,
    }
    restored = _decode_approval_request(payload)
    assert restored.purpose is purpose
