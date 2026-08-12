"""End-to-end reliability coverage for the Phase 3 candidate workflow."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from app.approval.engine import ApprovalEngine
from app.approval.models import ApprovalDecision, ApprovalStatus
from app.approval.repository import ApprovalRepository
from app.candidate_planning.audit import (
    CandidateAuditApprovals,
    CandidateAuditChainValidator,
)
from app.candidate_planning.commit import CandidateCommitValidator
from app.candidate_planning.execution import CandidateExecutionValidator
from app.candidate_planning.models import (
    CandidateImplementationTranslationRequest,
    CandidatePlanRequest,
    CandidateWorkflowConversionRequest,
)
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.service import CandidatePlanningService
from app.candidate_planning.state import CandidatePlanningStateStore
from app.candidate_planning.verification import (
    CandidateReviewAdapter,
    CandidateVerificationValidator,
)
from app.config.settings import Settings
from app.execution.engine import ExecutionEngine
from app.execution.models import RunnerOutcome
from app.main import create_app
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.planning.engine import PlanningEngine
from app.repository.committer import GitCommitter
from app.repository.inspector import GitInspector
from app.review.engine import ReviewEngine
from app.verification.engine import VerificationEngine
from app.workflow.engine import WorkflowEngine
from app.workflow.models import SprintPhase, WorkflowSessionState
from app.workflow.state import WorkflowStateStore
from fastapi.testclient import TestClient
from tests.candidate_planning.test_execution import FakeCoreClient, core_response


def run_git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def initialize_candidate_repository(repository: Path) -> str:
    repository.mkdir()
    run_git(repository, "init", "-b", "feature/atlas-agent")
    run_git(repository, "config", "user.name", "Atlas Tests")
    run_git(repository, "config", "user.email", "atlas-tests@example.invalid")
    (repository / "compose.production.yaml").write_text(
        "services:\n  atlas-core:\n    image: atlas-core:old\n",
        encoding="utf-8",
    )
    run_git(repository, "add", "compose.production.yaml")
    run_git(repository, "commit", "-m", "Initial compose")
    return run_git(repository, "rev-parse", "HEAD")


class FakeImplementationRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, argv, cwd, environment, timeout_seconds) -> RunnerOutcome:
        self.calls += 1
        assert argv[0] == "codex"
        compose = cwd / "compose.production.yaml"
        compose.write_text(
            "services:\n  atlas-core:\n    image: atlas-core:new\n",
            encoding="utf-8",
        )
        return RunnerOutcome(return_code=0, stdout="implemented", stderr="")


class FakeVerificationRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, argv, cwd, environment, timeout_seconds) -> RunnerOutcome:
        self.calls += 1
        assert argv[:5] == (
            "docker",
            "compose",
            "--file",
            "compose.production.yaml",
            "config",
        )
        assert set(argv[5:]) == {"--quiet", "--no-env-resolution"}
        assert (cwd / "compose.production.yaml").read_text(encoding="utf-8").endswith(
            "image: atlas-core:new\n"
        )
        return RunnerOutcome(return_code=0, stdout="valid compose", stderr="")


def test_complete_candidate_workflow_e2e_persists_audit_chain_and_local_commit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    head = initialize_candidate_repository(repository)
    mock_now = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
    core = FakeCoreClient(core_response(fingerprint="a" * 64))
    candidate_state = CandidatePlanningStateStore()
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = AgentStatePersistenceCoordinator(
        state_dir=tmp_path / "state",
        workflow_state=workflow_state,
        approval_repository=approvals,
        candidate_planning_state=candidate_state,
    )
    persistence.initialize()
    resolver = RepositoryResolver(repository_root=repository)
    service = CandidatePlanningService(
        core_client=core,
        state_store=candidate_state,
        state_persistence=persistence,
        repository_resolver=resolver,
        clock=lambda: mock_now,
    )
    implementation_runner = FakeImplementationRunner()
    verification_runner = FakeVerificationRunner()
    review_engine = ReviewEngine()
    engine = WorkflowEngine(
        repository_inspector_factory=GitInspector,
        planning_engine=Mock(spec=PlanningEngine),
        execution_engine=ExecutionEngine(implementation_runner),
        verification_engine=VerificationEngine(verification_runner),
        review_engine=review_engine,
        approval_engine=ApprovalEngine(),
        approval_repository=approvals,
        state_store=workflow_state,
        repository_committer_factory=GitCommitter,
        state_persistence=persistence,
        candidate_execution_validator=CandidateExecutionValidator(
            core_client=core,
            candidate_state=candidate_state,
            repository_resolver=resolver,
            clock=lambda: mock_now,
        ),
        candidate_verification_validator=CandidateVerificationValidator(
            core_client=core,
            candidate_state=candidate_state,
            repository_resolver=resolver,
            clock=lambda: mock_now,
        ),
        candidate_review_adapter=CandidateReviewAdapter(review_engine=review_engine),
        candidate_commit_validator=CandidateCommitValidator(
            core_client=core,
            candidate_state=candidate_state,
            repository_resolver=resolver,
            clock=lambda: mock_now,
        ),
    )

    intake = asyncio.run(
        service.create_planning_session(
            CandidatePlanRequest(
                candidate_id="candidate-1",
                expected_candidate_fingerprint="a" * 64,
            )
        )
    )
    assert intake.session_id is not None
    planned = asyncio.run(service.generate_plan(intake.session_id))
    assert planned.plan is not None
    converted = asyncio.run(
        service.convert_plan_to_workflow_shell(
            intake.session_id,
            CandidateWorkflowConversionRequest(
                expected_candidate_fingerprint="a" * 64,
            ),
        )
    )
    assert converted.workflow_session_id is not None
    translated = asyncio.run(
        service.translate_workflow_shell_to_implementation(
            intake.session_id,
            CandidateImplementationTranslationRequest(
                expected_candidate_fingerprint="a" * 64,
                expected_repository_head=head,
            ),
        )
    )
    assert translated.implementation_request_id is not None
    workflow_id = converted.workflow_session_id

    implementation_approval = approvals.get_request(f"approval-implementation-{workflow_id}")
    assert implementation_approval is not None
    assert approvals.update_decision(
        implementation_approval.decision.request.identifier,
        ApprovalDecision(
            request=implementation_approval.decision.request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    verification_boundary = engine.resume(workflow_id)
    assert verification_boundary.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL

    exact_verification_boundary = engine.resume(workflow_id)
    assert exact_verification_boundary.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    verification_approval = exact_verification_boundary.approval_request
    assert verification_approval is not None
    assert approvals.update_decision(
        verification_approval.identifier,
        ApprovalDecision(
            request=verification_approval,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    commit_boundary = engine.resume(workflow_id)
    assert commit_boundary.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL

    commit_approval = commit_boundary.approval_request
    assert commit_approval is not None
    assert approvals.update_decision(
        commit_approval.identifier,
        ApprovalDecision(
            request=commit_approval,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    completed = engine.resume(workflow_id)
    assert completed.sprint.phase is SprintPhase.COMPLETED

    final_workflow = workflow_state.get_session(workflow_id)
    assert final_workflow is not None
    assert final_workflow.state is WorkflowSessionState.COMPLETED
    assert implementation_runner.calls == 1
    assert verification_runner.calls == 1
    assert completed.commit_result is not None
    assert run_git(repository, "rev-parse", "HEAD") == completed.commit_result.commit_sha
    assert run_git(repository, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") == "compose.production.yaml"
    assert run_git(repository, "tag", "--list") == ""
    assert core.calls
    assert len(candidate_state.export_snapshot()) == 1
    assert len(workflow_state.export_snapshot()[3]) == 1

    planning_session = candidate_state.get_session(intake.session_id)
    assert planning_session is not None
    audit = CandidateAuditChainValidator().validate(
        planning_session=planning_session,
        workflow=final_workflow,
        approvals=CandidateAuditApprovals(
            implementation=approvals.get_request(f"approval-implementation-{workflow_id}"),
            verification=approvals.get_request(f"approval-verification-{workflow_id}"),
            commit=approvals.get_request(f"approval-commit-{workflow_id}"),
        ),
    )
    assert audit.valid is True
    assert audit.chain is not None
    assert audit.chain.commit_sha == completed.commit_result.commit_sha
    assert audit.chain.committed_files == (Path("compose.production.yaml"),)

    recovered_workflow = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered_candidates = CandidatePlanningStateStore()
    AgentStatePersistenceCoordinator(
        state_dir=tmp_path / "state",
        workflow_state=recovered_workflow,
        approval_repository=recovered_approvals,
        candidate_planning_state=recovered_candidates,
    ).initialize()
    recovered = recovered_workflow.get_session(workflow_id)
    assert recovered is not None
    assert recovered.state is WorkflowSessionState.COMPLETED
    assert recovered.commit_result == final_workflow.commit_result
    assert recovered.candidate_verification_evidence == final_workflow.candidate_verification_evidence
    assert recovered_candidates.get_session(intake.session_id) == planning_session


def test_candidate_implementation_route_sequence_claims_once_and_pauses_for_verification(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    head = initialize_candidate_repository(repository)
    mock_now = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
    core = FakeCoreClient(core_response(fingerprint="a" * 64))
    candidate_state = CandidatePlanningStateStore()
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = AgentStatePersistenceCoordinator(
        state_dir=tmp_path / "state",
        workflow_state=workflow_state,
        approval_repository=approvals,
        candidate_planning_state=candidate_state,
    )
    persistence.initialize()
    resolver = RepositoryResolver(repository_root=repository)
    service = CandidatePlanningService(
        core_client=core,
        state_store=candidate_state,
        state_persistence=persistence,
        repository_resolver=resolver,
        clock=lambda: mock_now,
    )
    implementation_runner = FakeImplementationRunner()
    engine = WorkflowEngine(
        repository_inspector_factory=GitInspector,
        planning_engine=Mock(spec=PlanningEngine),
        execution_engine=ExecutionEngine(implementation_runner),
        verification_engine=VerificationEngine(FakeVerificationRunner()),
        review_engine=ReviewEngine(),
        approval_engine=ApprovalEngine(),
        approval_repository=approvals,
        state_store=workflow_state,
        state_persistence=persistence,
        candidate_execution_validator=CandidateExecutionValidator(
            core_client=core,
            candidate_state=candidate_state,
            repository_resolver=resolver,
            clock=lambda: mock_now,
        ),
        candidate_verification_validator=CandidateVerificationValidator(
            core_client=core,
            candidate_state=candidate_state,
            repository_resolver=resolver,
            clock=lambda: mock_now,
        ),
        candidate_review_adapter=CandidateReviewAdapter(review_engine=ReviewEngine()),
        candidate_commit_validator=CandidateCommitValidator(
            core_client=core,
            candidate_state=candidate_state,
            repository_resolver=resolver,
            clock=lambda: mock_now,
        ),
    )

    intake = asyncio.run(
        service.create_planning_session(
            CandidatePlanRequest(
                candidate_id="candidate-route",
                expected_candidate_fingerprint="a" * 64,
            )
        )
    )
    asyncio.run(service.generate_plan(intake.session_id))
    converted = asyncio.run(
        service.convert_plan_to_workflow_shell(
            intake.session_id,
            CandidateWorkflowConversionRequest(
                expected_candidate_fingerprint="a" * 64,
            ),
        )
    )
    translated = asyncio.run(
        service.translate_workflow_shell_to_implementation(
            intake.session_id,
            CandidateImplementationTranslationRequest(
                expected_candidate_fingerprint="a" * 64,
                expected_repository_head=head,
            ),
        )
    )
    workflow_id = converted.workflow_session_id
    assert workflow_id is not None
    assert translated.implementation_request_id is not None
    workflow = workflow_state.get_session(workflow_id)
    assert workflow is not None
    assert workflow.state is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL

    application = create_app()
    application.state.container = replace(
        application.state.container,
        settings=Settings(repository_root=repository),
        workflow_state=workflow_state,
        candidate_planning_state=candidate_state,
        approval_repository=approvals,
        workflow_engine=engine,
        state_persistence=persistence,
    )
    with TestClient(application) as client:
        approval_response = client.post(
            f"/api/v1/agent/workflows/{workflow_id}/implementation-approval",
            json={"workflow_id": workflow_id, "decision": "approve"},
        )
        assert approval_response.status_code == 200
        stored = approvals.get_request(f"approval-implementation-{workflow_id}")
        assert stored is not None
        assert stored.decision.status is ApprovalStatus.APPROVED
        assert stored.decision.reviewer == "workflow-service"

        first_resume = client.post(f"/api/v1/agent/workflows/{workflow_id}/resume")
        assert first_resume.status_code == 200
        assert first_resume.json()["sprint"]["phase"] == "awaiting_verification_approval"
        assert implementation_runner.calls == 1

        second_resume = client.post(f"/api/v1/agent/workflows/{workflow_id}/resume")
        assert second_resume.status_code == 200
        assert second_resume.json()["sprint"]["phase"] == "awaiting_verification_approval"
        assert implementation_runner.calls == 1

    workflow = workflow_state.get_session(workflow_id)
    assert workflow is not None
    assert workflow.state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
