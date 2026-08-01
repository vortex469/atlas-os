"""Workflow execution routes for Atlas Agent."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.approval.models import ApprovalRequest
from app.context.models import AgentContext
from app.execution.models import EnvironmentVariable, ExecutionResult
from app.model_providers.models import ModelResponse
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitResult
from app.review.models import (
    ArchitectureAssessment,
    ReviewReport,
    TestEvidence,
)
from app.verification.models import (
    VerificationCheck,
    VerificationReport,
)
from app.workflow.models import SprintStatus, WorkflowRequest, WorkflowResult
from app.workflow.orchestrator import WorkflowOrchestrator

router = APIRouter(prefix="/api/v1/agent/workflows", tags=["workflows"])


class EnvironmentVariableRequest(BaseModel):
    """One environment override for a verification command."""

    name: str = Field(min_length=1)
    value: str


class VerificationCheckRequest(BaseModel):
    """One verification command submitted through the HTTP API."""

    identifier: str = Field(min_length=1)
    argv: list[str] = Field(min_length=1)
    working_directory: Path
    timeout_seconds: float | None = Field(default=None, gt=0)
    environment: list[EnvironmentVariableRequest] = Field(default_factory=list)

    def to_domain(self) -> VerificationCheck:
        return VerificationCheck(
            identifier=self.identifier,
            argv=tuple(self.argv),
            working_directory=self.working_directory,
            timeout_seconds=self.timeout_seconds,
            environment=tuple(
                EnvironmentVariable(name=item.name, value=item.value)
                for item in self.environment
            ),
        )


class RoadmapCheckpointRequest(BaseModel):
    """Roadmap checkpoint submitted for workflow planning."""

    identifier: str = Field(min_length=1)
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    scope_items: list[str] = Field(default_factory=list)
    affected_files: list[Path] = Field(default_factory=list)
    required_tests: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    def to_domain(self) -> RoadmapCheckpoint:
        return RoadmapCheckpoint(
            identifier=self.identifier,
            title=self.title,
            goal=self.goal,
            scope_items=tuple(self.scope_items),
            affected_files=tuple(self.affected_files),
            required_tests=tuple(self.required_tests),
            risks=tuple(self.risks),
        )


class ArchitectureAssessmentRequest(BaseModel):
    """Caller-supplied architecture evidence."""

    identifier: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    passed: bool
    evidence: str = Field(min_length=1)
    recommendation: str | None = None

    def to_domain(self) -> ArchitectureAssessment:
        return ArchitectureAssessment(**self.model_dump())


class TestEvidenceRequest(BaseModel):
    """Mapping from a required test to a verification check."""

    requirement: str = Field(min_length=1)
    check_identifier: str = Field(min_length=1)

    def to_domain(self) -> TestEvidence:
        return TestEvidence(**self.model_dump())


class WorkflowExecutionRequest(BaseModel):
    """Validated HTTP request for planning one workflow."""

    checkpoint: RoadmapCheckpointRequest
    repository_root: Path
    execution_identifier: str = Field(min_length=1)
    execution_argv: list[str] = Field(min_length=1)
    execution_workdir: Path
    verification_checks: list[VerificationCheckRequest]
    review_identifier: str = Field(min_length=1)
    architecture_assessments: list[ArchitectureAssessmentRequest] = Field(
        default_factory=list
    )
    test_evidence: list[TestEvidenceRequest] = Field(default_factory=list)

    def to_domain(self) -> WorkflowRequest:
        return WorkflowRequest(
            checkpoint=self.checkpoint.to_domain(),
            repository_root=self.repository_root,
            execution_identifier=self.execution_identifier,
            execution_argv=tuple(self.execution_argv),
            execution_workdir=self.execution_workdir,
            verification_checks=tuple(
                check.to_domain() for check in self.verification_checks
            ),
            review_identifier=self.review_identifier,
            architecture_assessments=tuple(
                assessment.to_domain()
                for assessment in self.architecture_assessments
            ),
            test_evidence=tuple(item.to_domain() for item in self.test_evidence),
        )


class WorkflowExecutionResponse(BaseModel):
    """Serialized result from workflow planning or execution."""

    model_config = ConfigDict(from_attributes=True)

    sprint: SprintStatus
    plan: ImplementationPlan | None = None
    context: AgentContext | None = None
    planning_analysis: ModelResponse | None = None
    review_analysis: ModelResponse | None = None
    approval_request: ApprovalRequest | None = None
    execution_result: ExecutionResult | None = None
    verification_report: VerificationReport | None = None
    review_report: ReviewReport | None = None
    commit_result: CommitResult | None = None
    error_message: str | None = None


class WorkflowErrorDetail(BaseModel):
    """Stable workflow API error payload."""

    code: str
    message: str


class WorkflowErrorResponse(BaseModel):
    """FastAPI error envelope for workflow failures."""

    detail: WorkflowErrorDetail


_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {"model": WorkflowErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": WorkflowErrorResponse},
    status.HTTP_409_CONFLICT: {"model": WorkflowErrorResponse},
    status.HTTP_424_FAILED_DEPENDENCY: {"model": WorkflowErrorResponse},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": WorkflowErrorResponse},
}
_INVALID_STATE_ERRORS = {
    "Workflow already in progress",
    "Workflow already completed",
    "Workflow is not resumable",
    "Workflow already resumed",
}


def _start_workflow(
    orchestrator: WorkflowOrchestrator,
    workflow_request: WorkflowRequest,
) -> WorkflowResult:
    return asyncio.run(orchestrator.run(workflow_request))


def _validate_repository_root_boundary(
    request: Request,
    workflow_request: WorkflowExecutionRequest,
) -> None:
    """Reject workflow starts outside the configured repository root."""

    configured_root = request.app.state.container.settings.repository_root.resolve()
    requested_root = workflow_request.repository_root.expanduser().resolve()

    if requested_root == configured_root:
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "repository_root_mismatch",
            "message": "Workflow repository root must match the configured repository root",
        },
    )


def _raise_for_failure(result: WorkflowResult) -> None:
    if result.error_message is None:
        return
    if result.error_message == "Workflow not found":
        code = "workflow_not_found"
        status_code = status.HTTP_404_NOT_FOUND
    elif result.error_message in _INVALID_STATE_ERRORS:
        code = "invalid_workflow_state"
        status_code = status.HTTP_409_CONFLICT
    else:
        code = "workflow_blocked"
        status_code = status.HTTP_424_FAILED_DEPENDENCY
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": result.error_message},
    )


@router.post(
    "",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERROR_RESPONSES,
)
async def start_workflow(
    request: Request,
    workflow_request: WorkflowExecutionRequest,
) -> WorkflowResult:
    """Plan one workflow and pause it for explicit approval."""

    _validate_repository_root_boundary(request, workflow_request)

    try:
        result = await run_in_threadpool(
            _start_workflow,
            request.app.state.container.workflow_orchestrator,
            workflow_request.to_domain(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_failure",
                "message": "Workflow start failed",
            },
        ) from exc
    _raise_for_failure(result)
    return result


@router.post(
    "/{workflow_id}/resume",
    response_model=WorkflowExecutionResponse,
    responses=_ERROR_RESPONSES,
)
async def resume_workflow(request: Request, workflow_id: str) -> WorkflowResult:
    """Resume one approved workflow from its stored plan."""

    try:
        result = await run_in_threadpool(
            request.app.state.container.workflow_engine.resume,
            workflow_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_failure",
                "message": "Workflow resume failed",
            },
        ) from exc
    _raise_for_failure(result)
    return result
