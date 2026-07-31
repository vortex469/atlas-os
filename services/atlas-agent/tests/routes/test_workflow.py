"""Tests for workflow execution routes."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.approval.models import ApprovalRequest
from app.config.settings import Settings
from app.main import create_app
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.routes import workflow as workflow_routes
from app.workflow.engine import WorkflowEngine
from app.workflow.models import (
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowResult,
)
from app.workflow.orchestrator import WorkflowOrchestrator


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
    return WorkflowResult(
        sprint=SprintStatus(
            checkpoint_id=checkpoint.identifier,
            title=checkpoint.title,
            goal=checkpoint.goal,
            phase=phase,
        ),
        plan=plan,
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
    ("error_message", "status_code", "code"),
    (
        ("Workflow not found", 404, "workflow_not_found"),
        ("Workflow already completed", 409, "invalid_workflow_state"),
        ("Approval rejected", 424, "workflow_blocked"),
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
