"""Workflow execution routes for Atlas Agent."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.approval.models import ApprovalDecision, ApprovalRequest, ApprovalStatus
from app.candidate_planning.commit import CandidateCommitFailureCode
from app.candidate_planning.execution import CandidateExecutionFailureCode
from app.candidate_planning.verification import CandidateVerificationFailureCode
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
from app.workflow.models import SprintStatus, WorkflowRequest, WorkflowResult, WorkflowSessionState
from app.workflow.orchestrator import WorkflowOrchestrator

router = APIRouter(prefix="/api/v1/agent/workflows", tags=["workflows"])


class EnvironmentVariableRequest(BaseModel):
    """One environment override for a verification command."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: str


class VerificationCheckRequest(BaseModel):
    """One verification command submitted through the HTTP API."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    passed: bool
    evidence: str = Field(min_length=1)
    recommendation: str | None = None

    def to_domain(self) -> ArchitectureAssessment:
        return ArchitectureAssessment(**self.model_dump())


class TestEvidenceRequest(BaseModel):
    """Mapping from a required test to a verification check."""

    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(min_length=1)
    check_identifier: str = Field(min_length=1)

    def to_domain(self) -> TestEvidence:
        return TestEvidence(**self.model_dump())


class WorkflowExecutionRequest(BaseModel):
    """Validated HTTP request for planning one workflow."""

    model_config = ConfigDict(extra="forbid")

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


class WorkflowImplementationRequestSummary(BaseModel):
    """Read-only safe fields for an immutable candidate implementation request."""

    immutable_request_id: str
    tool: str
    working_directory: str
    affected_files: list[str]
    repository: str
    translator_version: str | None


class WorkflowDetailResponse(BaseModel):
    """Read-only workflow implementation approval detail."""

    workflow_id: str
    workflow_source: str
    workflow_state: str
    planning_session_id: str | None
    candidate_id: str | None
    candidate_fingerprint: str | None
    plan_fingerprint: str | None
    implementation_approval_status: str
    repository: str | None
    working_directory: str | None
    translator_version: str | None
    affected_files: list[str]
    implementation_request: WorkflowImplementationRequestSummary | None


class WorkflowImplementationApprovalRequest(BaseModel):
    """Boundary-safe approval decision request."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    decision: str = Field(pattern="^(approve|reject)$")


class WorkflowImplementationApprovalResponse(BaseModel):
    workflow_id: str
    workflow_state: str
    implementation_approval_status: str
    message: str | None = None


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
_CANDIDATE_EXECUTION_ERRORS = {
    *(code.value for code in CandidateExecutionFailureCode),
    *(code.value for code in CandidateVerificationFailureCode),
    *(code.value for code in CandidateCommitFailureCode),
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
    elif result.error_message in _CANDIDATE_EXECUTION_ERRORS:
        code = result.error_message
        status_code = status.HTTP_424_FAILED_DEPENDENCY
        if result.error_message in {
            "approval_not_granted",
            "verification_approval_missing",
            "verification_not_approved",
            "commit_approval_missing",
            "commit_not_approved",
            "core_unavailable",
        }:
            status_code = status.HTTP_409_CONFLICT
    else:
        code = "workflow_blocked"
        status_code = status.HTTP_424_FAILED_DEPENDENCY
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": result.error_message},
    )


def _approval_status(request: Request, approval_id: str | None) -> str:
    if approval_id is None:
        return "not_requested"
    result = request.app.state.container.approval_repository.get_request(approval_id)
    if result is None:
        return "not_found"
    return result.decision.status.value


def _workflow_detail(request: Request, workflow_id: str) -> WorkflowDetailResponse:
    workflow = request.app.state.container.workflow_state.get_session(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "workflow_not_found", "message": "Workflow not found"},
        )

    implementation = workflow.candidate_implementation_request
    metadata = workflow.candidate_metadata
    summary = None
    if implementation is not None:
        summary = WorkflowImplementationRequestSummary(
            immutable_request_id=implementation.identifier,
            tool=implementation.argv[0] if implementation.argv else "not_available",
            working_directory=str(implementation.working_directory),
            affected_files=[str(path) for path in implementation.affected_files],
            repository=str(implementation.repository_root),
            translator_version=implementation.translator_version,
        )

    return WorkflowDetailResponse(
        workflow_id=workflow.identifier,
        workflow_source=workflow.source.value,
        workflow_state=workflow.state.value,
        planning_session_id=metadata.candidate_planning_session_id if metadata else None,
        candidate_id=metadata.candidate_id if metadata else None,
        candidate_fingerprint=metadata.candidate_fingerprint if metadata else None,
        plan_fingerprint=metadata.candidate_plan_fingerprint if metadata else None,
        implementation_approval_status=_approval_status(request, workflow.candidate_implementation_approval_id),
        repository=str(implementation.repository_root) if implementation else None,
        working_directory=str(implementation.working_directory) if implementation else None,
        translator_version=implementation.translator_version if implementation else None,
        affected_files=[str(path) for path in implementation.affected_files] if implementation else [],
        implementation_request=summary,
    )


@router.get(
    "/{workflow_id}/implementation-request",
    response_model=WorkflowDetailResponse,
    responses=_ERROR_RESPONSES,
)
async def get_workflow_implementation_request(
    request: Request,
    workflow_id: str,
) -> WorkflowDetailResponse:
    """Return a safe, read-only candidate workflow implementation approval view."""

    return _workflow_detail(request, workflow_id)


@router.post(
    "/{workflow_id}/implementation-approval",
    response_model=WorkflowImplementationApprovalResponse,
    responses=_ERROR_RESPONSES,
)
async def submit_workflow_implementation_approval(
    workflow_id: str,
    approval_request: WorkflowImplementationApprovalRequest,
    request: Request,
) -> WorkflowImplementationApprovalResponse:
    """Approve or reject the exact candidate implementation request by workflow ID only."""

    if approval_request.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "workflow_id_mismatch", "message": "Workflow ID must match the route"},
        )

    workflow = request.app.state.container.workflow_state.get_session(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "workflow_not_found", "message": "Workflow not found"},
        )
    if workflow.state is not WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_workflow", "message": "Workflow is not awaiting implementation approval"},
        )
    approval_id = workflow.candidate_implementation_approval_id
    if approval_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "approval_not_found", "message": "Implementation approval request not found"},
        )
    stored = request.app.state.container.approval_repository.get_request(approval_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "approval_not_found", "message": "Implementation approval request not found"},
        )
    if stored.decision.status is not ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "approval_already_decided", "message": "Approval already decided"},
        )

    decision = ApprovalDecision(
        request=stored.decision.request,
        status=ApprovalStatus.APPROVED if approval_request.decision == "approve" else ApprovalStatus.REJECTED,
    )
    persistence = getattr(request.app.state.container, "state_persistence", None)
    try:
        if persistence is None:
            success = request.app.state.container.approval_repository.update_decision(approval_id, decision)
        else:
            success = persistence.mutate_approval(lambda approvals: approvals.update_decision(approval_id, decision))
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failure", "message": "Implementation approval could not be persisted"},
        ) from exc
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "approval_already_decided", "message": "Approval already decided"},
        )

    return WorkflowImplementationApprovalResponse(
        workflow_id=workflow.identifier,
        workflow_state=workflow.state.value,
        implementation_approval_status=decision.status.value,
        message="Implementation approved. Execution is now available." if decision.status is ApprovalStatus.APPROVED else "Approval rejected.",
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
