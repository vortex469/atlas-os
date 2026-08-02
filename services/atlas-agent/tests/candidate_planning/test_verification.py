"""Tests for candidate verification planning and approval binding."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.approval.models import ApprovalDecision, ApprovalStatus
from app.approval.repository import ApprovalRepository
from app.candidate_planning.execution import implementation_plan_from_candidate_request
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.candidate_planning.verification import (
    COMPOSE_CHECK_ID,
    CandidateVerificationFailureCode,
    CandidateVerificationValidator,
    changed_files_digest,
)
from app.execution.models import ExecutionResult, ExecutionStatus
from app.repository.models import RepositorySnapshot
from app.workflow.models import WorkflowSessionState
from tests.candidate_planning.test_execution import (
    FakeCoreClient,
    FakeInspector,
    core_response,
    planning_session,
    workflow,
)


def _awaiting_verification_workflow(root: Path):
    shell = workflow(root)
    request = shell.candidate_implementation_request
    assert request is not None
    plan = implementation_plan_from_candidate_request(request)
    return replace(
        shell,
        state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
        request=None,
        plan=plan,
        execution_result=ExecutionResult(
            request_id=request.identifier,
            checkpoint_id=request.identifier,
            argv=request.argv,
            working_directory=request.working_directory,
            status=ExecutionStatus.SUCCEEDED,
            return_code=0,
            stdout="",
            stderr="",
            duration_seconds=1.0,
        ),
        changed_files=(Path("compose.production.yaml"),),
    )


def _validator(root: Path) -> CandidateVerificationValidator:
    state = CandidatePlanningStateStore()
    state.create_session(planning_session(root))
    FakeInspector.snapshot = RepositorySnapshot(
        root=root.resolve(strict=False),
        branch="feature/atlas-agent",
        head_commit="abc123",
        is_clean=False,
        modified_files=("compose.production.yaml",),
        staged_files=(),
        untracked_files=("logs/runtime.log",),
    )
    return CandidateVerificationValidator(
        core_client=FakeCoreClient(core_response()),
        candidate_state=state,
        repository_resolver=RepositoryResolver(repository_root=root),
        repository_inspector_factory=FakeInspector,
    )


def test_changed_files_digest_rejects_absolute_parent_and_out_of_scope(tmp_path: Path) -> None:
    kwargs = {
        "workflow_id": "workflow",
        "implementation_request_id": "request",
        "candidate_fingerprint": "candidate-fingerprint-v1:aaa",
        "plan_fingerprint": "candidate-plan-fingerprint-v1:bbb",
        "repository_branch": "feature/atlas-agent",
        "base_head": "abc123",
        "post_execution_head": "abc123",
        "approved_affected_files": (Path("compose.production.yaml"),),
    }

    digest = changed_files_digest(changed_files=(Path("compose.production.yaml"),), **kwargs)

    assert digest.startswith("changed-files-digest-v1:")
    with pytest.raises(ValueError):
        changed_files_digest(changed_files=(tmp_path / "compose.production.yaml",), **kwargs)
    with pytest.raises(ValueError):
        changed_files_digest(changed_files=(Path("../compose.production.yaml"),), **kwargs)
    with pytest.raises(ValueError):
        changed_files_digest(changed_files=(Path("README.md"),), **kwargs)


def test_build_plan_creates_exact_compose_verification_approval(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    session = _awaiting_verification_workflow(tmp_path)

    result = validator.build_plan(session)

    assert result.approved
    assert result.plan is not None
    assert result.plan.identifier.startswith("candidate-verification-plan-")
    assert result.plan.changed_files == (Path("compose.production.yaml"),)
    assert result.plan.changed_files_digest.startswith("changed-files-digest-v1:")
    assert result.approval_request is not None
    assert result.approval_request.checkpoint_id == result.plan.identifier
    assert result.approval_request.requested_command == ("verification-suite", COMPOSE_CHECK_ID)
    assert result.approval_request.verification_checks[0].command == (
        "docker",
        "compose",
        "--file",
        "compose.production.yaml",
        "config",
        "--no-env-resolution",
        "--quiet",
    )


def test_pending_placeholder_can_be_superseded_but_approved_placeholder_cannot(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    session = _awaiting_verification_workflow(tmp_path)
    built = validator.build_plan(session)
    assert built.plan is not None and built.approval_request is not None
    placeholder = validator.placeholder_approval_request(session)
    repository = ApprovalRepository()
    repository.save_request(placeholder)

    assert repository.supersede_pending_request(
        identifier=placeholder.identifier,
        expected_request=placeholder,
        replacement_request=built.approval_request,
    )
    assert repository.get_request(placeholder.identifier).decision.request == built.approval_request

    terminal = ApprovalRepository()
    terminal.save_request(placeholder)
    assert terminal.update_decision(
        placeholder.identifier,
        ApprovalDecision(request=placeholder, status=ApprovalStatus.APPROVED),
    )
    assert not terminal.supersede_pending_request(
        identifier=placeholder.identifier,
        expected_request=placeholder,
        replacement_request=built.approval_request,
    )
    assert terminal.get_request(placeholder.identifier).decision.request == placeholder


def test_exact_approval_required_before_candidate_verification(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    session = _awaiting_verification_workflow(tmp_path)
    built = validator.build_plan(session)
    assert built.plan is not None and built.approval_request is not None
    session = replace(session, candidate_verification_plan=built.plan)

    missing = validator.validate_for_execution(workflow=session, approval_result=None)

    assert not missing.approved
    assert missing.failure_code is CandidateVerificationFailureCode.VERIFICATION_APPROVAL_MISSING
    assert missing.retryable
