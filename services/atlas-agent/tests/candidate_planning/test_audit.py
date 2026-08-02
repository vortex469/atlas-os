"""Tests for candidate audit-chain validation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalResult,
    ApprovalStatus,
)
from app.candidate_planning.audit import (
    CandidateAuditApprovals,
    CandidateAuditChainValidator,
    CandidateAuditFailureCode,
)
from app.candidate_planning.models import CandidatePlan
from app.repository.models import CommitResult
from app.workflow.models import WorkflowSessionState
from tests.candidate_planning.test_commit import _approval, _commit_ready_workflow


def _approved_result(request):
    return ApprovalResult(
        decision=ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )


def _complete_workflow(root: Path):
    workflow = _commit_ready_workflow(root)
    commit_request = workflow.commit_request
    assert commit_request is not None
    return replace(
        workflow,
        state=WorkflowSessionState.COMPLETED,
        commit_result=CommitResult(
            repository_root=root.resolve(strict=False),
            branch=commit_request.expected_branch,
            parent_head=commit_request.expected_head,
            commit_sha="b" * 40,
            message=commit_request.message,
            committed_files=commit_request.paths,
        ),
    )


def _planning_session_with_plan(root: Path, workflow):
    from tests.candidate_planning.test_execution import planning_session

    session = planning_session(root)
    plan = CandidatePlan(
        identifier=workflow.candidate_metadata.candidate_plan_id,
        session_id=session.identifier,
        candidate_id=workflow.candidate_metadata.candidate_id,
        candidate_fingerprint=workflow.candidate_metadata.candidate_fingerprint,
        title="Prepare compose stack update proposal",
        objective="Create a minimal repository change proposal.",
        assumptions=("Planning is read-only.",),
        constraints=("requires-current-evidence",),
        proposed_steps=("Inspect trusted compose definitions.",),
        likely_affected_components=("atlas-compose",),
        likely_affected_files=(Path("compose.production.yaml"),),
        verification_strategy=("Validate later after workflow conversion.",),
        rollback_considerations=("Use version control rollback.",),
        unresolved_questions=(),
        evidence_ids=("evidence-1",),
        created_at=datetime(2026, 8, 2, tzinfo=UTC),
        repository_root=root,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        revalidated_candidate_fingerprint=workflow.candidate_metadata.candidate_fingerprint,
    )
    assert workflow.candidate_metadata is not None
    return replace(
        session,
        plan=plan,
        candidate_plan_fingerprint=workflow.candidate_metadata.candidate_plan_fingerprint,
    )


def _approvals(workflow):
    implementation_request = workflow.candidate_implementation_request
    assert implementation_request is not None
    verification_plan = workflow.candidate_verification_plan
    assert verification_plan is not None
    implementation = _approved_result(
        workflow.candidate_implementation_approval_id
        and replace(
            _approval(workflow),
            identifier=workflow.candidate_implementation_approval_id,
            purpose=ApprovalPurpose.IMPLEMENTATION,
            requested_tool="codex",
            requested_command=implementation_request.argv,
            requested_working_directory=implementation_request.working_directory,
        )
    )
    verification = _approved_result(
        replace(
            _approval(workflow),
            identifier=f"approval-verification-{workflow.identifier}",
            purpose=ApprovalPurpose.VERIFICATION,
            requested_tool="verification",
            requested_command=("verification-suite", "compose-production-config"),
        )
    )
    commit = _approved_result(_approval(workflow))
    return CandidateAuditApprovals(
        implementation=implementation,
        verification=verification,
        commit=commit,
    )


def test_complete_candidate_audit_chain_validates_without_parsing_prose(tmp_path: Path) -> None:
    workflow = _complete_workflow(tmp_path)
    session = _planning_session_with_plan(tmp_path, workflow)

    result = CandidateAuditChainValidator().validate(
        planning_session=session,
        workflow=workflow,
        approvals=_approvals(workflow),
    )

    assert result.valid is True
    assert result.chain is not None
    assert result.chain.candidate_id == "candidate-1"
    assert result.chain.source_recommendation_id == "finding-1"
    assert result.chain.implementation_request_id == workflow.candidate_implementation_request.identifier
    assert result.chain.verification_evidence_id == workflow.candidate_verification_evidence.identifier
    assert result.chain.commit_sha == "b" * 40
    assert result.chain.committed_files == (Path("compose.production.yaml"),)


def test_in_progress_candidate_audit_chain_can_validate_partial_chain(tmp_path: Path) -> None:
    workflow = _commit_ready_workflow(tmp_path)
    workflow = replace(workflow, execution_result=None, candidate_verification_plan=None)
    session = _planning_session_with_plan(tmp_path, workflow)

    result = CandidateAuditChainValidator().validate(
        planning_session=session,
        workflow=workflow,
        approvals=CandidateAuditApprovals(
            implementation=_approvals(_commit_ready_workflow(tmp_path)).implementation,
        ),
        require_complete=False,
    )

    assert result.valid is True
    assert result.chain is not None
    assert result.chain.implementation_request_id == workflow.candidate_implementation_request.identifier
    assert result.chain.execution_result_id is None


def test_complete_candidate_audit_chain_requires_commit_result(tmp_path: Path) -> None:
    workflow = _commit_ready_workflow(tmp_path)
    session = _planning_session_with_plan(tmp_path, workflow)

    result = CandidateAuditChainValidator().validate(
        planning_session=session,
        workflow=replace(workflow, state=WorkflowSessionState.COMPLETED),
        approvals=_approvals(workflow),
    )

    assert result.valid is False
    assert result.failure_code is CandidateAuditFailureCode.MISSING_COMMIT_RESULT


def test_candidate_audit_chain_detects_mismatched_verification_evidence(tmp_path: Path) -> None:
    workflow = _complete_workflow(tmp_path)
    evidence = replace(workflow.candidate_verification_evidence, workflow_id="other-workflow")
    workflow = replace(workflow, candidate_verification_evidence=evidence)
    session = _planning_session_with_plan(tmp_path, workflow)

    result = CandidateAuditChainValidator().validate(
        planning_session=session,
        workflow=workflow,
        approvals=_approvals(workflow),
    )

    assert result.valid is False
    assert result.failure_code is CandidateAuditFailureCode.VERIFICATION_MISMATCH


def test_candidate_audit_chain_detects_duplicate_identifiers(tmp_path: Path) -> None:
    workflow = _complete_workflow(tmp_path)
    review = replace(
        workflow.candidate_review_result,
        identifier=workflow.candidate_verification_evidence.identifier,
    )
    workflow = replace(workflow, candidate_review_result=review)
    session = _planning_session_with_plan(tmp_path, workflow)

    result = CandidateAuditChainValidator().validate(
        planning_session=session,
        workflow=workflow,
        approvals=_approvals(workflow),
    )

    assert result.valid is False
    assert result.failure_code is CandidateAuditFailureCode.DUPLICATE_IDENTIFIER
