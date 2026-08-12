"""Tests for workflow execution routes."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import AsyncMock, Mock

import pytest
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
    CommitApprovalMetadata,
    VerificationApprovalCheck,
)
from app.candidate_planning.audit import (
    CandidateAuditFailureCode,
    CandidateAuditValidationResult,
)
from app.candidate_planning.commit import CandidateCommitFailureCode
from app.candidate_planning.execution import CandidateExecutionFailureCode
from app.candidate_planning.models import (
    CandidateImplementationRequest,
    CandidateImplementationTranslationResponse,
    CandidatePlan,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.verification import CandidateVerificationFailureCode
from app.config.settings import Settings
from app.execution.models import ExecutionResult, ExecutionStatus
from app.main import create_app
from app.model_providers.models import ModelResponse
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitRequest, CommitResult
from app.routes import workflow as workflow_routes
from app.workflow.engine import WorkflowEngine
from app.workflow.models import (
    CandidateWorkflowMetadata,
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowResult,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)
from app.workflow.orchestrator import WorkflowOrchestrator
from fastapi.testclient import TestClient


def request_body(repository: Path) -> dict:
    return {
        "checkpoint": {
            "identifier": "A16",
            "title": "Workflow HTTP integration",
            "goal": "Expose workflow execution safely.",
            "scope_items": ["Add workflow routes"],
            "affected_files": ["app/routes/workflow.py"],
            "required_tests": ["python -m pytest -q"],
            "risks": [],
        },
        "repository_root": str(repository),
        "execution_identifier": "execution-a16",
        "execution_argv": ["codex", "implement"],
        "execution_workdir": str(repository),
        "verification_checks": [
            {
                "identifier": "pytest",
                "argv": ["python", "-m", "pytest", "-q"],
                "working_directory": str(repository),
                "environment": [{"name": "ATLAS_ENV", "value": "testing"}],
            }
        ],
        "review_identifier": "review-a16",
        "architecture_assessments": [
            {
                "identifier": "boundary",
                "summary": "HTTP remains outside the workflow domain.",
                "passed": True,
                "evidence": "Route conversion is explicit.",
            }
        ],
        "test_evidence": [
            {
                "requirement": "python -m pytest -q",
                "check_identifier": "pytest",
            }
        ],
    }


def workflow_result(
    repository: Path,
    *,
    phase: SprintPhase,
    error_message: str | None = None,
    review_analysis: ModelResponse | None = None,
) -> WorkflowResult:
    checkpoint = RoadmapCheckpoint(
        identifier="A16",
        title="Workflow HTTP integration",
        goal="Expose workflow execution safely.",
    )
    plan = ImplementationPlan(
        checkpoint_id=checkpoint.identifier,
        title=checkpoint.title,
        goal=checkpoint.goal,
        repository_root=repository,
        branch="feature/atlas-agent",
        head_commit="abc123",
        scope_items=("Add workflow routes",),
        affected_files=(Path("app/routes/workflow.py"),),
        required_tests=("python -m pytest -q",),
        risks=(),
    )
    approval_request = None
    if phase is SprintPhase.AWAITING_APPROVAL:
        approval_request = ApprovalRequest(
            identifier="approval-workflow-a16",
            workflow_id="workflow-a16",
            checkpoint_id="A16",
            title="Approve implementation",
            requested_tool="codex",
            requested_command=("codex", "implement"),
            requested_working_directory=repository,
            rationale="Approve the exact planned implementation operation.",
        )
    elif phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL:
        approval_request = ApprovalRequest(
            identifier="approval-verification-workflow-a16",
            workflow_id="workflow-a16",
            checkpoint_id="A16",
            title="Approve verification",
            requested_tool="verification",
            requested_command=("verification-suite", "pytest"),
            requested_working_directory=repository,
            rationale="Approve the exact ordered verification checks.",
            purpose=ApprovalPurpose.VERIFICATION,
            verification_checks=(
                VerificationApprovalCheck(
                    identifier="pytest",
                    command=("python", "-m", "pytest", "-q"),
                    working_directory=repository,
                    timeout_seconds=None,
                ),
            ),
        )
    elif phase is SprintPhase.AWAITING_COMMIT_APPROVAL:
        approval_request = ApprovalRequest(
            identifier="approval-commit-workflow-a16",
            workflow_id="workflow-a16",
            checkpoint_id="A16",
            title="Approve commit",
            requested_tool="git",
            requested_command=("git-commit", "app/routes/workflow.py"),
            requested_working_directory=repository,
            rationale="Approve the exact reviewed Git commit.",
            purpose=ApprovalPurpose.COMMIT,
            commit_metadata=CommitApprovalMetadata(
                expected_branch="feature/atlas-agent",
                expected_head="abc123",
                reviewed_files=(Path("app/routes/workflow.py"),),
                reviewed_content_fingerprint="a" * 64,
                commit_message="feat(agent): workflow http integration",
            ),
        )
    return WorkflowResult(
        sprint=SprintStatus(
            checkpoint_id=checkpoint.identifier,
            title=checkpoint.title,
            goal=checkpoint.goal,
            phase=phase,
        ),
        plan=plan,
        review_analysis=review_analysis,
        approval_request=approval_request,
        error_message=error_message,
    )


def make_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, object, Mock, Mock]:
    settings = Settings(repository_root=Path.cwd().resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    application = create_app()
    workflow_engine = Mock(spec=WorkflowEngine)
    workflow_orchestrator = Mock(spec=WorkflowOrchestrator)
    workflow_orchestrator.run = AsyncMock()
    application.state.container = replace(
        application.state.container,
        settings=Settings(repository_root=tmp_path.resolve()),
        workflow_engine=workflow_engine,
        workflow_orchestrator=workflow_orchestrator,
    )
    return (
        TestClient(application),
        application.state.container,
        workflow_engine,
        workflow_orchestrator,
    )


def test_create_app_constructs_single_shared_workflow_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.main.load_settings",
        lambda: Settings(repository_root=Path.cwd().resolve()),
    )

    application = create_app()
    container = application.state.container

    assert isinstance(container.workflow_engine, WorkflowEngine)
    assert isinstance(container.workflow_orchestrator, WorkflowOrchestrator)
    assert container.workflow_orchestrator._workflow_engine is container.workflow_engine
    assert container.workflow_orchestrator._context_engine is container.context_engine


def test_start_offloads_domain_conversion_and_pauses_for_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, workflow_engine, workflow_orchestrator = make_client(
        tmp_path, monkeypatch
    )
    workflow_orchestrator.run.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_APPROVAL,
    )
    offloaded = []
    original_run_in_threadpool = workflow_routes.run_in_threadpool

    async def run_offloaded(function, *args):
        offloaded.append((function, args))
        return await original_run_in_threadpool(function, *args)

    monkeypatch.setattr("app.routes.workflow.run_in_threadpool", run_offloaded)

    response = client.post(
        "/api/v1/agent/workflows",
        json=request_body(tmp_path),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["sprint"]["phase"] == "awaiting_approval"
    assert body["approval_request"]["workflow_id"] == "workflow-a16"
    assert body["execution_result"] is None
    assert len(offloaded) == 1
    submitted = workflow_orchestrator.run.await_args.args[0]
    assert isinstance(submitted, WorkflowRequest)
    assert submitted.execution_argv == ("codex", "implement")
    assert submitted.verification_checks[0].environment[0].name == "ATLAS_ENV"
    workflow_engine.resume.assert_not_called()


@pytest.mark.parametrize(
    ("error_message", "expected_code"),
    [
        ("approval_not_granted", "approval_not_granted"),
        ("core_unavailable", "core_unavailable"),
        ("Workflow already resumed", "invalid_workflow_state"),
    ],
)
def test_resume_candidate_pre_execution_conflicts_preserve_diagnostic_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_message: str,
    expected_code: str,
) -> None:
    client, _, workflow_engine, _ = make_client(tmp_path, monkeypatch)
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_APPROVAL,
        error_message=error_message,
    )

    response = client.post("/api/v1/agent/workflows/workflow-a16/resume")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {"code": expected_code, "message": error_message}
    }


def test_start_accepts_exact_configured_repository_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, _, workflow_orchestrator = make_client(tmp_path, monkeypatch)
    workflow_orchestrator.run.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_APPROVAL,
    )

    response = client.post(
        "/api/v1/agent/workflows",
        json=request_body(tmp_path.resolve()),
    )

    assert response.status_code == 202
    workflow_orchestrator.run.assert_awaited_once()


def test_start_accepts_equivalent_normalized_repository_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, _, workflow_orchestrator = make_client(tmp_path, monkeypatch)
    workflow_orchestrator.run.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_APPROVAL,
    )
    equivalent_path = tmp_path / "."

    response = client.post(
        "/api/v1/agent/workflows",
        json=request_body(equivalent_path),
    )

    assert response.status_code == 202
    workflow_orchestrator.run.assert_awaited_once()


def test_start_rejects_repository_path_outside_configured_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, container, _, workflow_orchestrator = make_client(tmp_path, monkeypatch)
    different_repository = tmp_path.parent / f"{tmp_path.name}-other"
    different_repository.mkdir()
    body = request_body(different_repository)

    response = client.post("/api/v1/agent/workflows", json=body)

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "repository_root_mismatch",
            "message": "Workflow repository root must match the configured repository root",
        }
    }
    workflow_orchestrator.run.assert_not_awaited()
    assert container.workflow_state.get_sprint() is None


def test_resume_offloads_engine_and_returns_completed_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, workflow_engine, workflow_orchestrator = make_client(
        tmp_path, monkeypatch
    )
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.COMPLETED,
    )
    calls = []

    async def run_offloaded(function, *args):
        calls.append((function, args))
        return function(*args)

    monkeypatch.setattr("app.routes.workflow.run_in_threadpool", run_offloaded)

    response = client.post("/api/v1/agent/workflows/workflow-a16/resume")

    assert response.status_code == 200
    assert response.json()["sprint"]["phase"] == "completed"
    assert calls == [(workflow_engine.resume, ("workflow-a16",))]
    workflow_engine.resume.assert_called_once_with("workflow-a16")
    workflow_orchestrator.run.assert_not_awaited()


def test_resume_returns_verification_approval_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, workflow_engine, _ = make_client(tmp_path, monkeypatch)
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_VERIFICATION_APPROVAL,
    )

    response = client.post("/api/v1/agent/workflows/workflow-a16/resume")

    assert response.status_code == 200
    body = response.json()
    assert body["sprint"]["phase"] == "awaiting_verification_approval"
    assert body["approval_request"]["purpose"] == "verification"
    assert body["approval_request"]["verification_checks"][0][
        "identifier"
    ] == "pytest"


def test_resume_returns_commit_approval_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, workflow_engine, _ = make_client(tmp_path, monkeypatch)
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_COMMIT_APPROVAL,
    )

    response = client.post("/api/v1/agent/workflows/workflow-a16/resume")

    assert response.status_code == 200
    body = response.json()
    assert body["sprint"]["phase"] == "awaiting_commit_approval"
    assert body["approval_request"]["purpose"] == "commit"
    metadata = body["approval_request"]["commit_metadata"]
    assert metadata["reviewed_files"] == ["app/routes/workflow.py"]
    assert metadata["reviewed_content_fingerprint"] == "a" * 64


def test_workflow_response_serializes_review_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, workflow_engine, _ = make_client(tmp_path, monkeypatch)
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.AWAITING_COMMIT_APPROVAL,
        review_analysis=ModelResponse(
            text="Advisory review analysis.",
            model="test-model",
            provider_id="test-provider",
        ),
    )

    response = client.post("/api/v1/agent/workflows/workflow-a16/resume")

    assert response.status_code == 200
    assert response.json()["review_analysis"] == {
        "text": "Advisory review analysis.",
        "model": "test-model",
        "provider_id": "test-provider",
    }


def test_invalid_request_returns_422_without_starting_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, _, workflow_orchestrator = make_client(tmp_path, monkeypatch)
    body = request_body(tmp_path)
    body["execution_argv"] = []

    response = client.post("/api/v1/agent/workflows", json=body)

    assert response.status_code == 422
    workflow_orchestrator.run.assert_not_awaited()


@pytest.mark.parametrize(
    "mutate",
    (
        lambda body: body.update({"command_override": ["bash"]}),
        lambda body: body["checkpoint"].update({"command_override": ["bash"]}),
        lambda body: body["verification_checks"][0].update({"shell": True}),
        lambda body: body["verification_checks"][0]["environment"][0].update(
            {"secret": "value"}
        ),
        lambda body: body["architecture_assessments"][0].update({"raw_diff": "secret"}),
        lambda body: body["test_evidence"][0].update({"argv": ["pytest"]}),
    ),
)
def test_workflow_creation_rejects_extra_caller_controlled_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
) -> None:
    client, _, _, workflow_orchestrator = make_client(tmp_path, monkeypatch)
    body = request_body(tmp_path)
    mutate(body)

    response = client.post("/api/v1/agent/workflows", json=body)

    assert response.status_code == 422
    workflow_orchestrator.run.assert_not_awaited()


def test_resume_accepts_no_stage_override_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, workflow_engine, _ = make_client(tmp_path, monkeypatch)
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.COMPLETED,
    )

    response = client.post(
        "/api/v1/agent/workflows/workflow-a16/resume",
        json={"requested_command": ["bash"]},
    )

    assert response.status_code == 200
    workflow_engine.resume.assert_called_once_with("workflow-a16")


def test_candidate_failure_route_mapping_is_owned_by_candidate_enums() -> None:
    expected = {
        *(code.value for code in CandidateExecutionFailureCode),
        *(code.value for code in CandidateVerificationFailureCode),
        *(code.value for code in CandidateCommitFailureCode),
    }

    assert workflow_routes._CANDIDATE_EXECUTION_ERRORS == expected


@pytest.mark.parametrize(
    ("error_message", "status_code", "code"),
    (
        ("Workflow not found", 404, "workflow_not_found"),
        ("Workflow already completed", 409, "invalid_workflow_state"),
        ("Approval pending", 424, "workflow_blocked"),
        ("Approval rejected", 424, "workflow_blocked"),
        ("Model-assisted review analysis failed", 424, "workflow_blocked"),
    ),
)
def test_resume_maps_domain_failures_to_deterministic_statuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_message: str,
    status_code: int,
    code: str,
) -> None:
    client, _, workflow_engine, _ = make_client(tmp_path, monkeypatch)
    workflow_engine.resume.return_value = workflow_result(
        tmp_path,
        phase=SprintPhase.BLOCKED,
        error_message=error_message,
    )

    response = client.post("/api/v1/agent/workflows/workflow-a16/resume")

    assert response.status_code == status_code
    assert response.json() == {
        "detail": {"code": code, "message": error_message}
    }


@pytest.mark.parametrize("operation", ("start", "resume"))
def test_unexpected_failure_returns_sanitized_500(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    client, _, workflow_engine, workflow_orchestrator = make_client(
        tmp_path, monkeypatch
    )
    if operation == "start":
        workflow_orchestrator.run.side_effect = RuntimeError("sensitive start error")
        response = client.post(
            "/api/v1/agent/workflows",
            json=request_body(tmp_path),
        )
        message = "Workflow start failed"
    else:
        workflow_engine.resume.side_effect = RuntimeError("sensitive resume error")
        response = client.post("/api/v1/agent/workflows/workflow-a16/resume")
        message = "Workflow resume failed"

    assert response.status_code == 500
    assert response.json() == {
        "detail": {"code": "internal_failure", "message": message}
    }
    assert "sensitive" not in response.text


def candidate_workflow_session(repository: Path) -> WorkflowSession:
    implementation = CandidateImplementationRequest(
        identifier="impl-request-123",
        workflow_session_id="workflow-123",
        candidate_planning_session_id="candidate-plan-123",
        candidate_id="candidate-123",
        candidate_fingerprint="candidate-fingerprint-123",
        candidate_plan_id="plan-123",
        candidate_plan_fingerprint="plan-fingerprint-123",
        execution_intent="update-compose-stack",
        repository_root=repository,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        argv=("docker-compose", "up", "-d"),
        working_directory=repository / "services/demo",
        affected_files=(Path("compose.yaml"), Path("services/demo/Dockerfile")),
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="compat-1",
        compatibility_status="compatible",
        translator_version="candidate-translator-v1",
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    metadata = CandidateWorkflowMetadata(
        candidate_planning_session_id="candidate-plan-123",
        candidate_id="candidate-123",
        candidate_fingerprint="candidate-fingerprint-123",
        candidate_plan_id="plan-123",
        candidate_plan_fingerprint="plan-fingerprint-123",
        source_recommendation_id="recommendation-123",
        source_subsystem="discovery",
        catalog_item_id="catalog-1",
        target_id="compose-stack-1",
        target_type="compose_stack",
        execution_category="maintenance",
        execution_intent="update-compose-stack",
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="compat-1",
        compatibility_status="compatible",
        relationship_ids=("rel-1",),
        conversion_timestamp=datetime(2026, 8, 2, tzinfo=UTC),
        core_revalidation_status="accepted_for_planning",
        core_revalidation_fingerprint="candidate-fingerprint-123",
    )
    return WorkflowSession(
        identifier="workflow-123",
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=metadata,
        candidate_implementation_request=implementation,
        candidate_implementation_approval_id="approval-workflow-123",
    )


def candidate_planning_session_for_workflow(_repository: Path) -> CandidatePlanningSession:
    timestamp = datetime(2026, 8, 2, tzinfo=UTC)
    snapshot = CandidateSnapshot(
        candidate_id="candidate-123",
        candidate_fingerprint="candidate-fingerprint-123",
        source_recommendation_id="recommendation-123",
        source_subsystem="discovery",
        recommendation_class="update-compose-stack",
        catalog_item_id="catalog-1",
        target_id="compose-stack-1",
        target_type="compose_stack",
        execution_category="maintenance",
        execution_intent="update-compose-stack",
        required_approval_level="standard",
        rationale="Update compose stack",
        constraints=("compose",),
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="compat-1",
        compatibility_status="compatible",
        relationship_ids=("rel-1",),
        expires_at=None,
        intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
        intake_reason_codes=(),
        intake_timestamp=timestamp,
    )
    return CandidatePlanningSession(
        identifier="candidate-plan-123",
        candidate_id="candidate-123",
        candidate_fingerprint="candidate-fingerprint-123",
        status=CandidatePlanningSessionStatus.PLAN_READY,
        snapshot=snapshot,
        created_at=timestamp,
        plan=CandidatePlan(
            identifier="plan-123",
            session_id="candidate-plan-123",
            candidate_id="candidate-123",
            candidate_fingerprint="candidate-fingerprint-123",
            title="Prepare compose stack update proposal",
            objective="Create a minimal repository change proposal.",
            assumptions=("Read-only planning only.",),
            constraints=("requires-current-evidence",),
            proposed_steps=("Inspect compose definitions.",),
            likely_affected_components=("atlas-compose",),
            likely_affected_files=(Path("compose.production.yaml"),),
            verification_strategy=("Validate with runtime checks.",),
            rollback_considerations=("Revert commit if needed.",),
            unresolved_questions=(),
            evidence_ids=("evidence-1",),
            created_at=timestamp,
            repository_root=_repository,
            repository_branch="feature/atlas-agent",
            repository_head="abc123",
            revalidated_candidate_fingerprint="candidate-fingerprint-123",
        ),
        candidate_plan_fingerprint="plan-fingerprint-123",
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
    )


def save_candidate_workflow(container, workflow: WorkflowSession) -> None:
    approval = ApprovalRequest(
        identifier="approval-workflow-123",
        workflow_id=workflow.identifier,
        checkpoint_id="impl-request-123",
        title="Approve exact candidate implementation request",
        requested_tool="docker-compose",
        requested_command=("docker-compose", "up", "-d"),
        requested_working_directory=workflow.candidate_implementation_request.working_directory,
        rationale="Approve exact implementation request.",
    )
    container.workflow_state.delete_session(workflow.identifier)
    approvals = container.approval_repository.export_snapshot()
    approvals.pop("approval-workflow-123", None)
    container.approval_repository.replace_snapshot(approvals)
    container.workflow_state.create_session(workflow)
    container.approval_repository.save_request(approval)


def shell_workflow_session(repository: Path, *, state=WorkflowSessionState.AWAITING_APPROVAL) -> WorkflowSession:
    base = candidate_workflow_session(repository)
    return replace(
        base,
        state=state,
        candidate_implementation_request=None,
        candidate_implementation_approval_id="approval-workflow-123",
    )


def save_shell_workflow(container, workflow: WorkflowSession, *, command=(), purpose=ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, checkpoint_id="plan-123") -> None:
    container.workflow_state.delete_session(workflow.identifier)
    approvals = container.approval_repository.export_snapshot()
    approvals.pop("approval-workflow-123", None)
    container.approval_repository.replace_snapshot(approvals)
    container.workflow_state.create_session(workflow)
    container.approval_repository.save_request(
        ApprovalRequest(
            identifier="approval-workflow-123",
            workflow_id=workflow.identifier,
            checkpoint_id=checkpoint_id,
            title="Approve candidate workflow shell",
            requested_tool="atlas-agent",
            requested_command=command,
            requested_working_directory=workflow.candidate_metadata and Path("."),
            rationale="Approve candidate workflow shell.",
            purpose=purpose,
        )
    )


def configure_shell_translation(container, workflow: WorkflowSession, *, result=None) -> AsyncMock:
    translated = result or CandidateImplementationTranslationResponse(
        candidate_planning_session_id="candidate-plan-123",
        workflow_session_id=workflow.identifier,
        translation_status=CandidatePlanningSessionStatus.IMPLEMENTATION_READY,
        implementation_request_id="impl-request-123",
        exact_approval_request_id="approval-implementation-workflow-123",
        candidate_fingerprint="candidate-fingerprint-123",
        plan_fingerprint="plan-fingerprint-123",
        repository_head="abc123",
        translator_version="candidate-translator-v1",
    )
    async def translate(*_args, **_kwargs):
        if translated.exact_approval_request_id:
            implementation = candidate_workflow_session(workflow.candidate_metadata and Path("."))
            implementation = replace(implementation, identifier=workflow.identifier)
            current = container.workflow_state.get_session(workflow.identifier)
            container.workflow_state.delete_session(workflow.identifier)
            container.workflow_state.create_session(replace(current, state=WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL, candidate_implementation_request=implementation.candidate_implementation_request))
            container.approval_repository.save_request(
                ApprovalRequest(
                    identifier=translated.exact_approval_request_id,
                    workflow_id=workflow.identifier,
                    checkpoint_id="impl-request-123",
                    title="Approve exact candidate implementation",
                    requested_tool="docker-compose",
                    requested_command=("docker-compose", "up", "-d"),
                    requested_working_directory=Path("."),
                    rationale="Approve exact implementation request.",
                )
            )
        return translated
    mock = AsyncMock(side_effect=translate)
    container.candidate_planning_service.translate_workflow_shell_to_implementation = mock
    return mock


def test_candidate_workflow_shell_approval_approve_translates_to_implementation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    save_shell_workflow(container, workflow)
    translator = configure_shell_translation(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/shell-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )

    assert response.status_code == 200
    assert response.json()["workflow_state"] == "awaiting_implementation_approval"
    assert response.json()["implementation_approval_request_id"] == "approval-implementation-workflow-123"
    assert translator.await_count == 1
    updated = container.workflow_state.get_session("workflow-123")
    assert updated.candidate_implementation_request is not None
    shell = container.approval_repository.get_request("approval-workflow-123")
    implementation = container.approval_repository.get_request("approval-implementation-workflow-123")
    assert shell.decision.request.purpose is ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL
    assert implementation is not None
    assert shell.decision.request.identifier != implementation.decision.request.identifier
    assert sum(
        container.approval_repository.get_request(identifier) is not None
        for identifier in ("approval-implementation-workflow-123",)
    ) == 1


def test_candidate_workflow_shell_translation_failure_blocks_and_suppresses_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    save_shell_workflow(container, workflow)
    translator = AsyncMock(side_effect=RuntimeError("synthetic translation failure"))
    container.candidate_planning_service.translate_workflow_shell_to_implementation = translator

    first = client.post(
        "/api/v1/agent/workflows/workflow-123/shell-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )
    second = client.post(
        "/api/v1/agent/workflows/workflow-123/shell-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )

    assert first.status_code == 409
    assert first.json()["detail"]["code"] == "translation_failed"
    assert second.status_code == 409
    assert second.json()["detail"]["code"] in {"approval_already_decided", "stale_workflow"}
    assert translator.await_count == 1
    blocked = container.workflow_state.get_session("workflow-123")
    assert blocked.state is WorkflowSessionState.BLOCKED
    assert blocked.blocked_reason == "candidate_shell_translation_failed"
    assert blocked.candidate_implementation_request is None
    assert container.approval_repository.get_request("approval-implementation-workflow-123") is None
    assert blocked.execution_result is None


def test_candidate_workflow_shell_approval_concurrent_requests_reconcile_without_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    save_shell_workflow(container, workflow)
    translator = configure_shell_translation(container, workflow)
    start = Barrier(2)
    responses = []

    def submit() -> None:
        start.wait()
        responses.append(
            client.post(
                "/api/v1/agent/workflows/workflow-123/shell-approval",
                json={"workflow_id": "workflow-123", "decision": "approve"},
            )
        )

    threads = [Thread(target=submit), Thread(target=submit)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert translator.await_count == 1
    assert sorted(response.status_code for response in responses) == [200, 409]
    updated = container.workflow_state.get_session("workflow-123")
    assert updated.state is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL
    assert updated.candidate_implementation_request is not None
    approvals = container.approval_repository.export_snapshot()
    implementation_approvals = [
        result
        for identifier, result in approvals.items()
        if identifier == "approval-implementation-workflow-123"
    ]
    assert len(implementation_approvals) == 1


def test_candidate_workflow_shell_approval_reject_does_not_translate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    save_shell_workflow(container, workflow)
    translator = configure_shell_translation(container, workflow)

    response = client.post("/api/v1/agent/workflows/workflow-123/shell-approval", json={"workflow_id": "workflow-123", "decision": "reject"})

    assert response.status_code == 200
    assert response.json()["shell_approval_status"] == "rejected"
    assert translator.await_count == 0
    assert container.workflow_state.get_session("workflow-123").state is WorkflowSessionState.AWAITING_APPROVAL
    assert container.approval_repository.get_request("approval-implementation-workflow-123") is None


@pytest.mark.parametrize(
    ("name", "workflow_id", "body_id", "state", "source", "purpose", "command", "checkpoint", "code"),
    [
        ("unknown", "missing", "missing", WorkflowSessionState.AWAITING_APPROVAL, WorkflowSource.CANDIDATE, ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, (), "plan-123", "workflow_not_found"),
        ("mismatch", "workflow-123", "other", WorkflowSessionState.AWAITING_APPROVAL, WorkflowSource.CANDIDATE, ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, (), "plan-123", "workflow_id_mismatch"),
        ("non_candidate", "workflow-123", "workflow-123", WorkflowSessionState.AWAITING_APPROVAL, WorkflowSource.MANUAL, ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, (), "plan-123", "workflow_not_found"),
        ("wrong_state", "workflow-123", "workflow-123", WorkflowSessionState.EXECUTING, WorkflowSource.CANDIDATE, ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, (), "plan-123", "stale_workflow"),
        ("wrong_purpose", "workflow-123", "workflow-123", WorkflowSessionState.AWAITING_APPROVAL, WorkflowSource.CANDIDATE, ApprovalPurpose.IMPLEMENTATION, (), "plan-123", "invalid_shell_approval"),
        ("non_empty", "workflow-123", "workflow-123", WorkflowSessionState.AWAITING_APPROVAL, WorkflowSource.CANDIDATE, ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, ("unsafe",), "plan-123", "invalid_shell_approval"),
        ("checkpoint", "workflow-123", "workflow-123", WorkflowSessionState.AWAITING_APPROVAL, WorkflowSource.CANDIDATE, ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL, (), "wrong-plan", "checkpoint_mismatch"),
    ],
)
def test_candidate_workflow_shell_approval_rejects_invalid_requests(tmp_path, monkeypatch, name, workflow_id, body_id, state, source, purpose, command, checkpoint, code):
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(shell_workflow_session(tmp_path, state=state), source=source)
    save_shell_workflow(container, workflow, command=command, purpose=purpose, checkpoint_id=checkpoint)
    translator = configure_shell_translation(container, workflow)
    response = client.post(f"/api/v1/agent/workflows/{workflow_id}/shell-approval", json={"workflow_id": body_id, "decision": "approve"})
    assert response.status_code in (400, 404, 409)
    assert response.json()["detail"]["code"] == code
    assert translator.await_count == 0


def test_candidate_workflow_shell_approval_duplicate_is_idempotent_and_conflict_is_reconciled(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    save_shell_workflow(container, workflow)
    translator = configure_shell_translation(container, workflow)
    first = client.post("/api/v1/agent/workflows/workflow-123/shell-approval", json={"workflow_id": "workflow-123", "decision": "approve"})
    second = client.post("/api/v1/agent/workflows/workflow-123/shell-approval", json={"workflow_id": "workflow-123", "decision": "approve"})
    conflict = client.post("/api/v1/agent/workflows/workflow-123/shell-approval", json={"workflow_id": "workflow-123", "decision": "reject"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["shell_approval_status"] == "approved"
    assert conflict.status_code == 409
    assert translator.await_count == 1


def test_candidate_workflow_implementation_request_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    save_candidate_workflow(container, candidate_workflow_session(tmp_path))

    response = client.get("/api/v1/agent/workflows/workflow-123/implementation-request")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "workflow-123"
    assert body["workflow_state"] == "awaiting_implementation_approval"
    assert body["planning_session_id"] == "candidate-plan-123"
    assert body["candidate_id"] == "candidate-123"
    assert body["candidate_fingerprint"] == "candidate-fingerprint-123"
    assert body["plan_fingerprint"] == "plan-fingerprint-123"
    assert body["implementation_approval_status"] == "pending"
    assert body["repository"] == str(tmp_path)
    assert body["working_directory"] == str(tmp_path / "services/demo")
    assert body["translator_version"] == "candidate-translator-v1"
    assert body["affected_files"] == ["compose.yaml", "services/demo/Dockerfile"]
    assert body["implementation_request"] == {
        "immutable_request_id": "impl-request-123",
        "tool": "docker-compose",
        "working_directory": str(tmp_path / "services/demo"),
        "affected_files": ["compose.yaml", "services/demo/Dockerfile"],
        "repository": str(tmp_path),
        "translator_version": "candidate-translator-v1",
    }
    assert body["timeline"][0] == {"name": "Execution Candidate", "status": "completed"}
    assert {stage["name"]: stage["status"] for stage in body["timeline"]}["Execution"] == "waiting"
    assert body["execution"] == {
        "execution_status": None,
        "started_at": None,
        "completed_at": None,
        "result": None,
        "changed_files_count": 0,
        "tool": None,
        "working_directory": None,
        "repository": str(tmp_path),
        "changed_files": [],
        "execution_request_id": None,
    }
    assert "argv" not in body
    assert "requested_command" not in body


def test_candidate_workflow_audit_endpoint_returns_machine_readable_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = candidate_workflow_session(tmp_path)
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_candidate_workflow(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "workflow-123"
    assert body["workflow_state"] == "awaiting_implementation_approval"
    assert body["validation"]["valid"] is False
    assert body["timeline"][0]["name"] == "candidate"
    assert {section["name"] for section in body["timeline"]} == {
        "candidate",
        "planning",
        "plan",
        "workflow",
        "implementation",
        "approvals",
        "execution",
        "verification",
        "review",
        "commit",
    }
    assert body["approvals"]["implementation"]["approval_id"] == "approval-workflow-123"
    assert body["implementation"]["repository_root"] == str(tmp_path)
    assert body["implementation"]["tool"] == "docker-compose"
    assert body["planning"]["planning_state"] == "plan_ready"
    assert body["planning"]["planning_status"] == "plan_ready"


def test_candidate_workflow_audit_includes_blocked_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(
        candidate_workflow_session(tmp_path),
        blocked_reason="Blocked: safety policy failed",
    )
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_candidate_workflow(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["blocked_reason"] == "Blocked: safety policy failed"


def test_candidate_audit_workflow_state_is_authoritative_in_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_routes.CandidateAuditChainValidator,
        "validate",
        lambda self, planning_session, workflow, approvals=None, require_complete=None: CandidateAuditValidationResult(valid=True),
    )
    client, container, _, _ = make_client(tmp_path, monkeypatch)

    workflow = replace(
        candidate_workflow_session(tmp_path),
        state=WorkflowSessionState.BLOCKED,
        blocked_reason="approval_evidence_mismatch",
    )
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_candidate_workflow(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_state"] == "blocked"
    assert body["validation"]["valid"] is True
    assert body["validation"]["failure_code"] is None


def test_candidate_audit_keeps_completed_state_when_validation_is_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_routes.CandidateAuditChainValidator,
        "validate",
        lambda self, planning_session, workflow, approvals=None, require_complete=None: CandidateAuditValidationResult(valid=True),
    )
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(
        candidate_workflow_session(tmp_path),
        state=WorkflowSessionState.COMPLETED,
    )
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_candidate_workflow(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_state"] == "completed"
    assert body["validation"]["valid"] is True


def test_candidate_audit_nonterminal_waiting_state_stays_not_completed_when_validation_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_routes.CandidateAuditChainValidator,
        "validate",
        lambda self, planning_session, workflow, approvals=None, require_complete=None: CandidateAuditValidationResult(valid=True),
    )
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(
        candidate_workflow_session(tmp_path),
        state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
    )
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_candidate_workflow(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_state"] == "awaiting_verification_approval"
    assert body["validation"]["valid"] is True
    assert body["workflow_state"] != "completed"


def test_candidate_audit_invalid_validation_does_not_override_workflow_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_routes.CandidateAuditChainValidator,
        "validate",
        lambda self, planning_session, workflow, approvals=None, require_complete=None: CandidateAuditValidationResult(
            valid=False,
            failure_code=CandidateAuditFailureCode.MISSING_IMPLEMENTATION_REQUEST,
        ),
    )
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(
        candidate_workflow_session(tmp_path),
        state=WorkflowSessionState.BLOCKED,
        blocked_reason="approval_evidence_mismatch",
    )
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_candidate_workflow(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_state"] == "blocked"
    assert body["validation"]["valid"] is False


def test_candidate_workflow_audit_after_shell_creation_shows_planning_without_implementation_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)

    workflow = WorkflowSession(
        identifier="workflow-456",
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_APPROVAL,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=CandidateWorkflowMetadata(
            candidate_planning_session_id="candidate-plan-123",
            candidate_id="candidate-123",
            candidate_fingerprint="candidate-fingerprint-123",
            candidate_plan_id="plan-123",
            candidate_plan_fingerprint="plan-fingerprint-123",
            source_recommendation_id="recommendation-123",
            source_subsystem="discovery",
            catalog_item_id="catalog-1",
            target_id="compose-stack-1",
            target_type="compose_stack",
            execution_category="maintenance",
            execution_intent="update-compose-stack",
            evidence_ids=("evidence-1",),
            compatibility_assessment_id="compat-1",
            compatibility_status="compatible",
            relationship_ids=("rel-1",),
            conversion_timestamp=datetime(2026, 8, 2, tzinfo=UTC),
            core_revalidation_status="accepted_for_planning",
            core_revalidation_fingerprint="candidate-fingerprint-123",
        ),
        candidate_implementation_request=None,
        candidate_implementation_approval_id="approval-workflow-456",
    )
    workflow_placeholder_approval = ApprovalRequest(
        identifier="approval-workflow-456",
        workflow_id="workflow-456",
        checkpoint_id="plan-123",
        title="Approve candidate workflow shell for compose stack update",
        requested_tool="atlas-agent",
        requested_command=(),
        requested_working_directory=tmp_path,
        rationale="Approve candidate workflow shell.",
        purpose=ApprovalPurpose.IMPLEMENTATION,
    )
    planning_session = candidate_planning_session_for_workflow(tmp_path)
    container.candidate_planning_state.create_session(planning_session)
    container.workflow_state.create_session(workflow)
    container.approval_repository.save_request(
        workflow_placeholder_approval
    )

    response = client.get("/api/v1/agent/workflows/workflow-456/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "workflow-456"
    assert body["workflow_state"] == "awaiting_approval"
    assert body["plan"]["plan_id"] == "plan-123"
    assert body["plan"]["likely_affected_files"] == ["compose.production.yaml"]
    assert body["implementation"]["implementation_request_id"] is None
    assert body["implementation"]["tool"] is None
    assert body["implementation"]["affected_files"] == []
    assert body["approvals"]["implementation"]["approval_id"] == "approval-workflow-456"


def test_candidate_workflow_audit_distinguishes_shell_from_pending_implementation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    container.candidate_planning_state.replace_snapshot({})
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_shell_workflow(container, workflow)
    translator = configure_shell_translation(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/shell-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )
    assert response.status_code == 200
    assert translator.await_count == 1
    updated = container.workflow_state.get_session("workflow-123")
    container.workflow_state.delete_session("workflow-123")
    container.workflow_state.create_session(
        replace(
            updated,
            candidate_implementation_approval_id="approval-implementation-workflow-123",
        )
    )

    audit = client.get("/api/v1/agent/workflows/workflow-123/audit")
    assert audit.status_code == 200
    body = audit.json()
    assert body["approvals"]["shell"] == {
        "status": "approved",
        "approval_id": "approval-workflow-123",
    }
    assert body["approvals"]["implementation"] == {
        "status": "pending",
        "approval_id": "approval-implementation-workflow-123",
    }
    assert body["workflow_state"] == "awaiting_implementation_approval"
    assert body["execution"]["execution_request_id"] is None
    assert body["execution"]["changed_files"] == []


def test_candidate_workflow_audit_translation_failure_has_no_execution_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = shell_workflow_session(tmp_path)
    container.candidate_planning_state.replace_snapshot({})
    container.candidate_planning_state.create_session(
        candidate_planning_session_for_workflow(tmp_path)
    )
    save_shell_workflow(container, workflow)
    translator = AsyncMock(side_effect=RuntimeError("synthetic translation failure"))
    container.candidate_planning_service.translate_workflow_shell_to_implementation = translator

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/shell-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )
    assert response.status_code == 409
    assert translator.await_count == 1
    blocked = container.workflow_state.get_session("workflow-123")
    container.workflow_state.delete_session("workflow-123")
    container.workflow_state.create_session(
        replace(blocked, candidate_implementation_approval_id=None)
    )

    audit = client.get("/api/v1/agent/workflows/workflow-123/audit")
    assert audit.status_code == 200
    body = audit.json()
    assert body["workflow_state"] == "blocked"
    assert body["blocked_reason"] == "candidate_shell_translation_failed"
    assert body["approvals"]["shell"]["status"] == "approved"
    assert body["approvals"]["implementation"]["approval_id"] is None
    assert body["implementation"]["implementation_request_id"] is None
    assert body["execution"]["execution_request_id"] is None
    assert body["execution"]["changed_files"] == []


def test_list_workflows_returns_read_only_summaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    save_candidate_workflow(container, candidate_workflow_session(tmp_path))

    response = client.get(
        "/api/v1/agent/workflows",
        params={"workflow_id": "workflow-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    summary = body["items"][0]
    assert summary == {
        "workflow_id": "workflow-123",
        "workflow_source": "candidate",
        "workflow_state": "awaiting_implementation_approval",
        "candidate_id": "candidate-123",
        "planning_session_id": "candidate-plan-123",
        "repository": str(tmp_path),
        "target_id": "compose-stack-1",
        "last_result_summary": "No result yet",
        "timeline": summary["timeline"],
    }
    assert {stage["name"] for stage in summary["timeline"]} == {
        "Execution Candidate",
        "Planning Session",
        "Candidate Plan",
        "Workflow",
        "Implementation Approval",
        "Execution",
        "Verification",
        "Review",
        "Commit",
    }
    assert "candidate_implementation_request" not in summary
    assert "argv" not in summary
    assert "requested_command" not in summary


def test_list_workflows_filters_and_paginates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = candidate_workflow_session(tmp_path)
    save_candidate_workflow(container, workflow)
    second = replace(
        workflow,
        identifier="workflow-456",
        state=WorkflowSessionState.EXECUTING,
        candidate_implementation_approval_id=None,
    )
    container.workflow_state.delete_session(second.identifier)
    container.workflow_state.create_session(second)

    response = client.get(
        "/api/v1/agent/workflows",
        params={
            "state": "awaiting_implementation_approval",
            "source": "candidate",
            "candidate_id": "candidate-123",
            "limit": 1,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["workflow_id"] == "workflow-123"


def test_candidate_workflow_implementation_approval_accepts_only_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = candidate_workflow_session(tmp_path)
    save_candidate_workflow(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/implementation-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "workflow_id": "workflow-123",
        "workflow_state": "awaiting_implementation_approval",
        "implementation_approval_status": "approved",
        "message": "Implementation approved. Execution is now available.",
    }
    result = container.approval_repository.get_request("approval-workflow-123")
    assert result.decision.status is ApprovalStatus.APPROVED
    assert result.decision.reviewer == "workflow-service"
    assert result.decision.reason is None


def test_candidate_workflow_implementation_approval_rejects_extra_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    save_candidate_workflow(container, candidate_workflow_session(tmp_path))

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/implementation-approval",
        json={
            "workflow_id": "workflow-123",
            "decision": "approve",
            "argv": ["docker-compose", "up", "-d"],
        },
    )

    assert response.status_code == 422
    result = container.approval_repository.get_request("approval-workflow-123")
    assert result.decision.status is ApprovalStatus.PENDING


def test_candidate_workflow_implementation_approval_conflict_after_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = candidate_workflow_session(tmp_path)
    save_candidate_workflow(container, workflow)
    stored = container.approval_repository.get_request("approval-workflow-123")
    container.approval_repository.update_decision(
        "approval-workflow-123",
        ApprovalDecision(request=stored.decision.request, status=ApprovalStatus.REJECTED),
    )

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/implementation-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "approval_already_decided"


def save_verification_approval(container, workflow: WorkflowSession) -> None:
    approval = ApprovalRequest(
        identifier=f"approval-verification-{workflow.identifier}",
        workflow_id=workflow.identifier,
        checkpoint_id="verification-plan-123",
        title="Approve verification",
        requested_tool="verification",
        requested_command=("verification-suite",),
        requested_working_directory=workflow.candidate_implementation_request.working_directory,
        rationale="Approve exact verification.",
        purpose=ApprovalPurpose.VERIFICATION,
    )
    approvals = container.approval_repository.export_snapshot()
    approvals.pop(approval.identifier, None)
    container.approval_repository.replace_snapshot(approvals)
    container.approval_repository.save_request(approval)


def save_commit_approval(container, workflow: WorkflowSession) -> None:
    approval = ApprovalRequest(
        identifier=f"approval-commit-{workflow.identifier}",
        workflow_id=workflow.identifier,
        checkpoint_id="commit-plan-123",
        title="Approve commit",
        requested_tool="git",
        requested_command=("git-commit", "compose.yaml"),
        requested_working_directory=workflow.candidate_implementation_request.repository_root,
        rationale="Approve exact commit.",
        purpose=ApprovalPurpose.COMMIT,
        commit_metadata=CommitApprovalMetadata(
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            reviewed_files=(Path("compose.yaml"), Path("services/demo/Dockerfile")),
            reviewed_content_fingerprint="a" * 64,
            commit_message="feat(compose): update stack",
        ),
    )
    approvals = container.approval_repository.export_snapshot()
    approvals.pop(approval.identifier, None)
    container.approval_repository.replace_snapshot(approvals)
    container.approval_repository.save_request(approval)


def commit_ready_workflow(workflow: WorkflowSession) -> WorkflowSession:
    repository = workflow.candidate_implementation_request.repository_root
    return replace(
        workflow,
        state=WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
        commit_request=CommitRequest(
            repository_root=repository,
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            paths=(Path("compose.yaml"), Path("services/demo/Dockerfile")),
            message="feat(compose): update stack",
        ),
        reviewed_files=(Path("compose.yaml"), Path("services/demo/Dockerfile")),
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        reviewed_content_fingerprint="a" * 64,
    )


def test_candidate_workflow_verification_approval_accepts_only_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(candidate_workflow_session(tmp_path), state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL)
    save_candidate_workflow(container, workflow)
    save_verification_approval(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/verification-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "workflow_id": "workflow-123",
        "workflow_state": "awaiting_verification_approval",
        "verification_approval_status": "approved",
        "message": "Verification approved. Verification is now available.",
    }
    result = container.approval_repository.get_request("approval-verification-workflow-123")
    assert result.decision.status is ApprovalStatus.APPROVED
    assert result.decision.reviewer == "workflow-service"
    assert result.decision.reason is None


def test_candidate_workflow_verification_approval_rejects_extra_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(candidate_workflow_session(tmp_path), state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL)
    save_candidate_workflow(container, workflow)
    save_verification_approval(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/verification-approval",
        json={"workflow_id": "workflow-123", "decision": "approve", "verification_commands": ["pytest"]},
    )

    assert response.status_code == 422
    result = container.approval_repository.get_request("approval-verification-workflow-123")
    assert result.decision.status is ApprovalStatus.PENDING


def test_candidate_workflow_commit_request_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = commit_ready_workflow(candidate_workflow_session(tmp_path))
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/implementation-request")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_state"] == "awaiting_commit_approval"
    assert body["commit_approval_status"] == "pending"
    assert body["commit_request"] == {
        "commit_request_id": "approval-commit-workflow-123",
        "repository": str(tmp_path),
        "branch": "feature/atlas-agent",
        "expected_head": "abc123",
        "commit_message": "feat(compose): update stack",
        "reviewed_files": ["compose.yaml", "services/demo/Dockerfile"],
        "reviewed_content_fingerprint": "a" * 64,
        "commit_approval_status": "pending",
    }
    assert body["commit_result"] == {
        "commit_sha": None,
        "commit_message": None,
        "committed_files": [],
        "completion_time": None,
    }
    assert "requested_command" not in body["commit_request"]


def test_candidate_workflow_commit_approval_accepts_only_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = commit_ready_workflow(candidate_workflow_session(tmp_path))
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/commit-approval",
        json={"workflow_id": "workflow-123", "decision": "approve"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "workflow_id": "workflow-123",
        "workflow_state": "awaiting_commit_approval",
        "commit_approval_status": "approved",
        "message": "Commit approved. Workflow may now complete through the existing backend resume path.",
    }
    result = container.approval_repository.get_request("approval-commit-workflow-123")
    assert result.decision.status is ApprovalStatus.APPROVED
    assert result.decision.reviewer == "workflow-service"
    assert result.decision.reason is None


@pytest.mark.parametrize(
    "path, approval_id",
    (
        ("/api/v1/agent/workflows/workflow-123/implementation-approval", "approval-workflow-123"),
        ("/api/v1/agent/workflows/workflow-123/verification-approval", "approval-verification-workflow-123"),
        ("/api/v1/agent/workflows/workflow-123/commit-approval", "approval-commit-workflow-123"),
    ),
)
def test_workflow_approval_rejection_records_reviewer_and_reason(
    path: str,
    approval_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = candidate_workflow_session(tmp_path)

    if "verification" in path:
        workflow = replace(workflow, state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL)
    elif "commit" in path:
        workflow = commit_ready_workflow(workflow)

    save_candidate_workflow(container, workflow)
    if "verification" in path:
        save_verification_approval(container, workflow)
    elif "commit" in path:
        save_commit_approval(container, workflow)

    response = client.post(
        path,
        json={"workflow_id": "workflow-123", "decision": "reject"},
    )

    assert response.status_code == 200
    result = container.approval_repository.get_request(approval_id)
    assert result.decision.status is ApprovalStatus.REJECTED
    assert result.decision.reviewer == "workflow-service"
    assert result.decision.reason == "Rejected via workflow route."


def test_candidate_workflow_commit_approval_rejects_extra_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = commit_ready_workflow(candidate_workflow_session(tmp_path))
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)

    response = client.post(
        "/api/v1/agent/workflows/workflow-123/commit-approval",
        json={"workflow_id": "workflow-123", "decision": "approve", "commit_message": "override"},
    )

    assert response.status_code == 422
    result = container.approval_repository.get_request("approval-commit-workflow-123")
    assert result.decision.status is ApprovalStatus.PENDING


def test_candidate_workflow_completed_includes_commit_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(
        commit_ready_workflow(candidate_workflow_session(tmp_path)),
        state=WorkflowSessionState.COMPLETED,
        commit_result=CommitResult(
            repository_root=tmp_path,
            branch="feature/atlas-agent",
            parent_head="abc123",
            commit_sha="def456",
            message="feat(compose): update stack",
            committed_files=(Path("compose.yaml"), Path("services/demo/Dockerfile")),
        ),
    )
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)

    response = client.get("/api/v1/agent/workflows/workflow-123/implementation-request")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_state"] == "completed"
    assert body["commit_result"] == {
        "commit_sha": "def456",
        "commit_message": "feat(compose): update stack",
        "committed_files": ["compose.yaml", "services/demo/Dockerfile"],
        "completion_time": None,
    }


def test_candidate_workflow_implementation_request_includes_execution_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = replace(
        candidate_workflow_session(tmp_path),
        state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
        execution_result=ExecutionResult(
            request_id="exec-123",
            checkpoint_id="impl-request-123",
            argv=("docker-compose", "up", "-d"),
            working_directory=tmp_path / "services/demo",
            status=ExecutionStatus.SUCCEEDED,
            return_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=1.2,
        ),
        changed_files=(Path("compose.yaml"), Path("services/demo/Dockerfile")),
    )
    save_candidate_workflow(container, workflow)
    stored = container.approval_repository.get_request("approval-workflow-123")
    container.approval_repository.update_decision(
        "approval-workflow-123",
        ApprovalDecision(request=stored.decision.request, status=ApprovalStatus.APPROVED),
    )

    response = client.get("/api/v1/agent/workflows/workflow-123/implementation-request")

    assert response.status_code == 200
    body = response.json()
    assert {stage["name"]: stage["status"] for stage in body["timeline"]}["Execution"] == "completed"
    assert body["execution"] == {
        "execution_status": "succeeded",
        "started_at": None,
        "completed_at": None,
        "result": "succeeded",
        "changed_files_count": 2,
        "tool": "docker-compose",
        "working_directory": str(tmp_path / "services/demo"),
        "repository": str(tmp_path),
        "changed_files": ["compose.yaml", "services/demo/Dockerfile"],
        "execution_request_id": "exec-123",
    }
    assert "argv" not in body["execution"]
