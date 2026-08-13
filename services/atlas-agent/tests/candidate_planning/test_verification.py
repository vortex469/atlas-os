"""Tests for candidate verification planning and approval binding."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from app.approval.models import ApprovalDecision, ApprovalResult, ApprovalStatus
from app.approval.repository import ApprovalRepository
from app.candidate_planning.execution import implementation_plan_from_candidate_request
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.candidate_planning.verification import (
    COMPOSE_CHECK_ID,
    CandidateVerificationFailureCode,
    CandidateVerificationValidationResult,
    CandidateVerificationValidator,
    changed_files_digest,
)
from app.execution.models import ExecutionResult, ExecutionStatus
from app.execution.patches import WorkerPatchApplier
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


def _validator(root: Path, *, intent: str = "update-compose-stack") -> CandidateVerificationValidator:
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
        core_client=FakeCoreClient(core_response(execution_intent=intent)),
        candidate_state=state,
        repository_resolver=RepositoryResolver(repository_root=root),
        repository_inspector_factory=FakeInspector,
    )


def _real_checkout(root: Path, *, baseline: tuple[str, ...] = ()) -> tuple[Path, str]:
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "feature/atlas-agent"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=root, check=True)
    target = root / "compose.production.yaml"
    target.write_text("old\n", encoding="utf-8")
    for path in baseline:
        candidate = root / path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "compose.production.yaml"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    return root, subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


@pytest.mark.parametrize(
    "baseline",
    (
        (),
        ("compose.execution-smoke.override.yaml",),
        ("notes.txt", "services/other.txt"),
    ),
)
def test_verification_uses_workflow_delta_and_preserves_dirty_baseline(
    tmp_path: Path, baseline: tuple[str, ...]
) -> None:
    root, _ = _real_checkout(tmp_path / "repo", baseline=baseline)
    for path in baseline:
        candidate = root / path
        if not candidate.exists():
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text("baseline\n", encoding="utf-8")
    captured = WorkerPatchApplier.capture_baseline(root)
    (root / "compose.production.yaml").write_text("new\n", encoding="utf-8")
    validator = _validator(root)
    validator._validate_core = lambda workflow: CandidateVerificationValidationResult(approved=True)
    session = replace(_awaiting_verification_workflow(root), worker_baseline_status=captured)

    result = validator.build_plan(session)

    assert result.approved
    assert result.plan is not None
    assert result.plan.changed_files == (Path("compose.production.yaml"),)


@pytest.mark.parametrize("mutation", ("modify", "remove"))
def test_verification_rejects_mutated_or_removed_baseline_path(
    tmp_path: Path, mutation: str
) -> None:
    root, _ = _real_checkout(tmp_path / "repo", baseline=("baseline.txt",))
    baseline_file = root / "baseline.txt"
    baseline_file.write_text("baseline\n", encoding="utf-8")
    captured = WorkerPatchApplier.capture_baseline(root)
    (root / "compose.production.yaml").write_text("new\n", encoding="utf-8")
    if mutation == "modify":
        baseline_file.write_text("changed\n", encoding="utf-8")
    else:
        baseline_file.unlink()
    validator = _validator(root)
    session = replace(_awaiting_verification_workflow(root), worker_baseline_status=captured)

    result = validator.build_plan(session)

    assert not result.approved
    assert result.failure_code is CandidateVerificationFailureCode.REPOSITORY_STALE


def test_verification_preserves_preexisting_modified_tracked_file(tmp_path: Path) -> None:
    root, _ = _real_checkout(tmp_path / "repo")
    baseline_file = root / "baseline.txt"
    baseline_file.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "add", "baseline.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
    baseline_file.write_text("pre-existing edit\n", encoding="utf-8")
    captured = WorkerPatchApplier.capture_baseline(root)
    (root / "compose.production.yaml").write_text("new\n", encoding="utf-8")
    validator = _validator(root)
    session = replace(_awaiting_verification_workflow(root), worker_baseline_status=captured)

    result = validator.build_plan(session)

    assert result.approved
    assert result.plan is not None
    assert result.plan.changed_files == (Path("compose.production.yaml"),)


def test_verification_rejects_new_unrelated_path_and_target_drift(tmp_path: Path) -> None:
    root, _ = _real_checkout(tmp_path / "repo", baseline=("baseline.txt",))
    (root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    captured = WorkerPatchApplier.capture_baseline(root)
    (root / "compose.production.yaml").write_text("new\n", encoding="utf-8")
    validator = _validator(root)
    validator._validate_core = lambda workflow: CandidateVerificationValidationResult(approved=True)
    session = replace(_awaiting_verification_workflow(root), worker_baseline_status=captured)
    (root / "unrelated.txt").write_text("unexpected\n", encoding="utf-8")
    assert validator.build_plan(session).failure_code is CandidateVerificationFailureCode.REPOSITORY_STALE
    (root / "unrelated.txt").unlink()
    built = validator.build_plan(session)
    assert built.approved and built.plan is not None and built.approval_request is not None
    (root / "compose.production.yaml").write_text("different\n", encoding="utf-8")
    result = validator.validate_for_execution(
        workflow=replace(session, candidate_verification_plan=built.plan),
        approval_result=ApprovalResult(
            decision=ApprovalDecision(
                request=built.approval_request,
                status=ApprovalStatus.APPROVED,
            )
        ),
    )
    assert result.failure_code is CandidateVerificationFailureCode.REPOSITORY_STALE
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


def test_gated_rc1_smoke_builds_verification_plan_without_compose_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    validator = _validator(tmp_path, intent="rc1-validation-smoke")
    session = _awaiting_verification_workflow(tmp_path)
    request = session.candidate_implementation_request
    metadata = session.candidate_metadata
    assert request is not None and metadata is not None
    session = replace(
        session,
        candidate_implementation_request=replace(
            request,
            execution_intent="rc1-validation-smoke",
            argv=("atlas-rc1-validation-smoke",),
        ),
        candidate_metadata=replace(metadata, execution_intent="rc1-validation-smoke"),
    )

    result = validator.build_plan(session)

    assert result.approved
    assert result.plan is not None
    assert result.plan.verification_checks == ()
    assert result.approval_request is not None
    assert result.approval_request.requested_command == ("verification-suite",)


def test_gated_rc1_smoke_is_rejected_when_gate_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", raising=False)
    validator = _validator(tmp_path, intent="rc1-validation-smoke")
    session = _awaiting_verification_workflow(tmp_path)
    request = session.candidate_implementation_request
    metadata = session.candidate_metadata
    assert request is not None and metadata is not None
    session = replace(
        session,
        candidate_implementation_request=replace(
            request,
            execution_intent="rc1-validation-smoke",
            argv=("atlas-rc1-validation-smoke",),
        ),
        candidate_metadata=replace(metadata, execution_intent="rc1-validation-smoke"),
    )

    result = validator._validate_local_inputs(session)

    assert not result.approved
    assert result.failure_code is CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH
    assert result.should_block


def test_unsupported_verification_intent_fails_closed(tmp_path: Path) -> None:
    validator = _validator(tmp_path, intent="arbitrary-intent")
    session = _awaiting_verification_workflow(tmp_path)
    request = session.candidate_implementation_request
    metadata = session.candidate_metadata
    assert request is not None and metadata is not None
    session = replace(
        session,
        candidate_implementation_request=replace(request, execution_intent="arbitrary-intent"),
        candidate_metadata=replace(metadata, execution_intent="arbitrary-intent"),
    )

    result = validator._validate_local_inputs(session)

    assert not result.approved
    assert result.failure_code is CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH
    assert result.should_block


def test_gated_rc1_smoke_preserves_scope_digest_head_and_approval_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    validator = _validator(tmp_path, intent="rc1-validation-smoke")
    session = _awaiting_verification_workflow(tmp_path)
    request = session.candidate_implementation_request
    metadata = session.candidate_metadata
    assert request is not None and metadata is not None
    session = replace(
        session,
        candidate_implementation_request=replace(
            request,
            execution_intent="rc1-validation-smoke",
            argv=("atlas-rc1-validation-smoke",),
        ),
        candidate_metadata=replace(metadata, execution_intent="rc1-validation-smoke"),
    )
    built = validator.build_plan(session)
    assert built.plan is not None and built.approval_request is not None
    validator._validate_core = lambda workflow: CandidateVerificationValidationResult(approved=True)

    wrong_files = replace(session, changed_files=(Path("README.md"),))
    wrong_scope = validator.build_plan(wrong_files)
    assert not wrong_scope.approved
    assert wrong_scope.failure_code is CandidateVerificationFailureCode.REPOSITORY_STALE

    bad_digest_plan = replace(built.plan, changed_files_digest="changed-files-digest-v1:bad")
    bad_digest = validator.validate_for_execution(
        workflow=replace(session, candidate_verification_plan=bad_digest_plan),
        approval_result=ApprovalResult(
            decision=ApprovalDecision(
                request=built.approval_request,
                status=ApprovalStatus.APPROVED,
            )
        ),
    )
    assert not bad_digest.approved
    assert bad_digest.failure_code is CandidateVerificationFailureCode.CHANGED_FILES_DIGEST_MISMATCH

    FakeInspector.snapshot = replace(
        FakeInspector.snapshot,
        head_commit="different-base-head",
    )
    stale = built.plan
    stale_result = validator.validate_for_execution(
        workflow=replace(session, candidate_verification_plan=stale),
        approval_result=ApprovalResult(
            decision=ApprovalDecision(
                request=validator.exact_approval_request(stale),
                status=ApprovalStatus.APPROVED,
            )
        ),
    )
    assert not stale_result.approved
    assert stale_result.failure_code is CandidateVerificationFailureCode.REPOSITORY_STALE

    mismatch = validator.validate_for_execution(
        workflow=replace(session, candidate_verification_plan=built.plan),
        approval_result=ApprovalResult(
            decision=ApprovalDecision(
                request=replace(built.approval_request, identifier="approval-wrong"),
                status=ApprovalStatus.APPROVED,
            )
        ),
    )
    assert not mismatch.approved
    assert mismatch.failure_code is CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH


def test_gated_rc1_smoke_workflow_reaches_actual_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    from unittest.mock import Mock

    from app.candidate_planning.execution import CandidateExecutionValidationResult
    from app.execution.models import ExecutionRequest
    from app.verification.models import VerificationReport, VerificationStatus
    from tests.candidate_planning.test_execution import approval, rc1_workflow
    from tests.test_workflow_engine import make_candidate_engine, make_execution_result

    root, _ = _real_checkout(
        tmp_path / "repo",
        baseline=("compose.execution-smoke.override.yaml",),
    )
    engine, state_store, approvals, execution_engine, verification_engine, _, _ = make_candidate_engine(root)
    workflow = replace(
        rc1_workflow(root),
        worker_baseline_status=WorkerPatchApplier.capture_baseline(root),
    )
    state_store.delete_session(workflow.identifier)
    state_store.create_session(workflow)
    approvals.replace_snapshot({})
    request = workflow.candidate_implementation_request
    assert request is not None
    implementation_approval = approval(request)
    approvals.save_request(implementation_approval.decision.request)
    assert approvals.update_decision(
        implementation_approval.decision.request.identifier,
        implementation_approval.decision,
    )
    implementation_plan = implementation_plan_from_candidate_request(request)
    execution_request = ExecutionRequest(
        identifier=request.identifier,
        plan=implementation_plan,
        argv=request.argv,
        working_directory=request.working_directory,
    )

    class ApprovedExecution:
        def validate(self, *, workflow, approval_result):
            return CandidateExecutionValidationResult(
                approved=True,
                implementation_request=request,
                implementation_plan=implementation_plan,
                execution_request=execution_request,
            )

    execution_engine.execute.return_value = make_execution_result(root)
    (root / "compose.production.yaml").write_text("new\n", encoding="utf-8")
    execution_validator = ApprovedExecution()
    engine._candidate_execution_validator = execution_validator
    verification_validator = _validator(root, intent="rc1-validation-smoke")
    verification_validator._validate_core = lambda workflow: CandidateVerificationValidationResult(approved=True)
    engine._candidate_verification_validator = verification_validator
    engine._candidate_review_adapter = Mock()
    engine._candidate_review_adapter.review.return_value = Mock(
        approved=False,
        failure_code=CandidateVerificationFailureCode.REVIEW_FAILED,
        review_report=None,
        candidate_review_result=None,
    )
    verification_engine.verify.return_value = VerificationReport(
        repository_root=tmp_path,
        results=(),
        status=VerificationStatus.PASSED,
        duration_seconds=0.0,
        context=None,
    )

    boundary = engine.resume(workflow.identifier)
    assert boundary.sprint.phase.value == "awaiting_verification_approval"
    (root / "compose.production.yaml").write_text("new\n", encoding="utf-8")
    exact_boundary = engine.resume(workflow.identifier)
    assert exact_boundary.sprint.phase.value == "awaiting_verification_approval"
    verification_approval = approvals.get_request(f"approval-verification-{workflow.identifier}")
    assert verification_approval is not None
    assert verification_approval.decision.request.verification_checks == ()
    assert approvals.update_decision(
        verification_approval.decision.request.identifier,
        replace(
            verification_approval.decision,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )

    resumed = engine.resume(workflow.identifier)

    assert verification_engine.verify.called, resumed
    assert resumed.error_message != CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH.value


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


def test_approved_placeholder_cannot_authorize_exact_candidate_verification(
    tmp_path: Path,
) -> None:
    validator = _validator(tmp_path)
    session = _awaiting_verification_workflow(tmp_path)
    built = validator.build_plan(session)
    assert built.plan is not None and built.approval_request is not None
    placeholder = validator.placeholder_approval_request(session)
    session = replace(session, candidate_verification_plan=built.plan)

    result = validator.validate_for_execution(
        workflow=session,
        approval_result=ApprovalResult(
            decision=ApprovalDecision(
                request=placeholder,
                status=ApprovalStatus.APPROVED,
                reviewer="tester",
            )
        ),
    )

    assert not result.approved
    assert result.failure_code is CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH
    assert result.should_block
