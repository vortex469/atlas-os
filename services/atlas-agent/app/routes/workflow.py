"""Workflow execution routes for Atlas Agent."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status
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
from app.workflow.models import (
    SprintStatus,
    WorkflowRequest,
    WorkflowResult,
    WorkflowSessionState,
)
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


class WorkflowTimelineStageResponse(BaseModel):
    name: str
    status: str


class WorkflowExecutionSummaryResponse(BaseModel):
    execution_status: str | None
    started_at: str | None
    completed_at: str | None
    result: str | None
    changed_files_count: int
    tool: str | None
    working_directory: str | None
    repository: str | None
    changed_files: list[str]
    execution_request_id: str | None


class WorkflowVerificationPlanResponse(BaseModel):
    verification_plan_id: str | None
    verifier_version: str | None
    changed_files_digest: str | None
    verification_check_ids: list[str]
    command_backed_checks: list[str]
    working_directory: str | None
    repository: str | None
    verification_status: str


class WorkflowVerificationEvidenceResponse(BaseModel):
    verification_status: str | None
    completed_time: str | None
    executed_checks: list[str]
    check_results: list[dict[str, str | int | float | bool | None]]
    repository_head: str | None
    changed_files_digest: str | None


class WorkflowReviewResponse(BaseModel):
    review_result: str | None
    review_status: str | None
    approved: bool | None
    evidence_summary: str | None
    changed_files: list[str]
    review_fingerprint: str | None
    model_assisted_review: str


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
    timeline: list[WorkflowTimelineStageResponse]
    execution: WorkflowExecutionSummaryResponse
    verification_plan: WorkflowVerificationPlanResponse
    verification_evidence: WorkflowVerificationEvidenceResponse
    review: WorkflowReviewResponse
    verification_approval_status: str


class WorkflowSummaryResponse(BaseModel):
    """Read-only persisted workflow summary for Mission Control dashboards."""

    workflow_id: str
    workflow_source: str
    workflow_state: str
    candidate_id: str | None
    planning_session_id: str | None
    repository: str | None
    target_id: str | None
    last_result_summary: str
    timeline: list[WorkflowTimelineStageResponse]


class WorkflowListResponse(BaseModel):
    """Paginated list of read-only workflow summaries."""

    items: list[WorkflowSummaryResponse]
    total: int
    limit: int
    offset: int


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


class WorkflowVerificationApprovalRequest(BaseModel):
    """Boundary-safe verification approval decision request."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    decision: str = Field(pattern="^(approve|reject)$")


class WorkflowVerificationApprovalResponse(BaseModel):
    workflow_id: str
    workflow_state: str
    verification_approval_status: str
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


def _workflow_execution_summary(workflow) -> WorkflowExecutionSummaryResponse:
    execution = workflow.execution_result
    implementation = workflow.candidate_implementation_request
    changed_files = [str(path) for path in workflow.changed_files]
    return WorkflowExecutionSummaryResponse(
        execution_status=execution.status.value if execution else None,
        started_at=None,
        completed_at=None,
        result=execution.status.value if execution else None,
        changed_files_count=len(changed_files),
        tool=execution.argv[0] if execution and execution.argv else None,
        working_directory=str(execution.working_directory) if execution else None,
        repository=str(implementation.repository_root) if implementation else None,
        changed_files=changed_files,
        execution_request_id=execution.request_id if execution else None,
    )


def _verification_approval_status(request: Request, workflow) -> str:
    return _approval_status(request, f"approval-verification-{workflow.identifier}")


def _workflow_verification_plan(workflow) -> WorkflowVerificationPlanResponse:
    plan = workflow.candidate_verification_plan
    if plan is None:
        return WorkflowVerificationPlanResponse(
            verification_plan_id=None,
            verifier_version=None,
            changed_files_digest=None,
            verification_check_ids=[],
            command_backed_checks=[],
            working_directory=None,
            repository=None,
            verification_status="not_available",
        )
    check_ids = [check.identifier for check in plan.verification_checks]
    return WorkflowVerificationPlanResponse(
        verification_plan_id=plan.identifier,
        verifier_version=plan.verifier_version,
        changed_files_digest=plan.changed_files_digest,
        verification_check_ids=check_ids,
        command_backed_checks=check_ids,
        working_directory=str(plan.verification_checks[0].working_directory) if plan.verification_checks else None,
        repository=str(plan.repository_root),
        verification_status=workflow.state.value,
    )


def _workflow_verification_evidence(workflow) -> WorkflowVerificationEvidenceResponse:
    evidence = workflow.candidate_verification_evidence
    if evidence is None:
        return WorkflowVerificationEvidenceResponse(
            verification_status=None,
            completed_time=None,
            executed_checks=[],
            check_results=[],
            repository_head=None,
            changed_files_digest=None,
        )
    return WorkflowVerificationEvidenceResponse(
        verification_status=evidence.status.value,
        completed_time=evidence.completed_at.isoformat(),
        executed_checks=[check.identifier for check in evidence.check_results],
        check_results=[
            {
                "identifier": check.identifier,
                "status": check.status.value,
                "return_code": check.return_code,
                "stdout_digest": check.stdout_digest,
                "stderr_digest": check.stderr_digest,
                "output_truncated": check.output_truncated,
                "duration_seconds": check.duration_seconds,
                "error": check.error,
            }
            for check in evidence.check_results
        ],
        repository_head=evidence.repository_head,
        changed_files_digest=evidence.changed_files_digest,
    )


def _workflow_review(workflow) -> WorkflowReviewResponse:
    result = workflow.candidate_review_result
    report = workflow.review_report
    status = result.status.value if result else report.status.value if report else None
    findings = len(report.findings) if report else 0
    recommendations = len(report.recommendations) if report else 0
    return WorkflowReviewResponse(
        review_result=status,
        review_status=status,
        approved=(status == "approved") if status is not None else None,
        evidence_summary=(f"{findings} findings, {recommendations} recommendations" if report else None),
        changed_files=[str(path) for path in workflow.changed_files],
        review_fingerprint=result.reviewed_content_fingerprint if result else None,
        model_assisted_review="Disabled",
    )


def _stage_status(workflow, stage: str, approval_status: str) -> str:
    state = workflow.state.value
    execution = workflow.execution_result
    if stage in {"Execution Candidate", "Planning Session", "Candidate Plan", "Workflow"}:
        return "completed"
    if stage == "Implementation Approval":
        if approval_status == "approved":
            return "completed"
        if approval_status == "rejected":
            return "blocked"
        return "current" if state == "awaiting_implementation_approval" else "waiting"
    if stage == "Execution":
        if state == "executing":
            return "current"
        if execution is None:
            return "waiting"
        return "completed" if execution.status.value == "succeeded" else "failed"
    if stage == "Verification":
        if state in {"awaiting_verification_approval", "verifying"}:
            return "current"
        if workflow.verification_report is not None or workflow.candidate_verification_evidence is not None:
            return "completed"
        return "waiting"
    if stage == "Review":
        if workflow.review_report is not None or workflow.candidate_review_result is not None:
            return "completed"
        return "waiting"
    if stage == "Commit":
        if state in {"awaiting_commit_approval", "committing"}:
            return "current"
        if workflow.commit_result is not None:
            return "completed"
        return "waiting"
    return "waiting"


def _workflow_timeline(workflow, approval_status: str) -> list[WorkflowTimelineStageResponse]:
    stages = [
        "Execution Candidate",
        "Planning Session",
        "Candidate Plan",
        "Workflow",
        "Implementation Approval",
        "Execution",
        "Verification",
        "Review",
        "Commit",
    ]
    return [WorkflowTimelineStageResponse(name=stage, status=_stage_status(workflow, stage, approval_status)) for stage in stages]


def _workflow_repository(workflow) -> str | None:
    implementation = workflow.candidate_implementation_request
    if implementation is not None:
        return str(implementation.repository_root)
    if workflow.request is not None:
        return str(workflow.request.repository_root)
    return None


def _last_result_summary(workflow) -> str:
    if workflow.commit_result is not None:
        return "Commit completed"
    if workflow.candidate_review_result is not None:
        return f"Review {workflow.candidate_review_result.status.value}"
    if workflow.review_report is not None:
        return f"Review {workflow.review_report.status.value}"
    if workflow.candidate_verification_evidence is not None:
        return f"Verification {workflow.candidate_verification_evidence.status.value}"
    if workflow.verification_report is not None:
        return f"Verification {workflow.verification_report.status.value}"
    if workflow.execution_result is not None:
        return f"Execution {workflow.execution_result.status.value}"
    if workflow.blocked_reason:
        return f"Blocked: {workflow.blocked_reason}"
    return "No result yet"


def _workflow_summary(request: Request, workflow) -> WorkflowSummaryResponse:
    metadata = workflow.candidate_metadata
    approval_status = _approval_status(
        request,
        workflow.candidate_implementation_approval_id,
    )
    return WorkflowSummaryResponse(
        workflow_id=workflow.identifier,
        workflow_source=workflow.source.value,
        workflow_state=workflow.state.value,
        candidate_id=metadata.candidate_id if metadata else None,
        planning_session_id=(
            metadata.candidate_planning_session_id if metadata else None
        ),
        repository=_workflow_repository(workflow),
        target_id=metadata.target_id if metadata else None,
        last_result_summary=_last_result_summary(workflow),
        timeline=_workflow_timeline(workflow, approval_status),
    )


def _workflow_summary_matches(
    item: WorkflowSummaryResponse,
    *,
    state: str | None,
    source: str | None,
    candidate_id: str | None,
    workflow_id: str | None,
) -> bool:
    if state and item.workflow_state != state:
        return False
    if source and item.workflow_source != source:
        return False
    if candidate_id and candidate_id.lower() not in (item.candidate_id or "").lower():
        return False
    return not (workflow_id and workflow_id.lower() not in item.workflow_id.lower())


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

    approval_status = _approval_status(request, workflow.candidate_implementation_approval_id)
    verification_approval = _verification_approval_status(request, workflow)
    return WorkflowDetailResponse(
        workflow_id=workflow.identifier,
        workflow_source=workflow.source.value,
        workflow_state=workflow.state.value,
        planning_session_id=metadata.candidate_planning_session_id if metadata else None,
        candidate_id=metadata.candidate_id if metadata else None,
        candidate_fingerprint=metadata.candidate_fingerprint if metadata else None,
        plan_fingerprint=metadata.candidate_plan_fingerprint if metadata else None,
        implementation_approval_status=approval_status,
        repository=str(implementation.repository_root) if implementation else None,
        working_directory=str(implementation.working_directory) if implementation else None,
        translator_version=implementation.translator_version if implementation else None,
        affected_files=[str(path) for path in implementation.affected_files] if implementation else [],
        implementation_request=summary,
        timeline=_workflow_timeline(workflow, approval_status),
        execution=_workflow_execution_summary(workflow),
        verification_plan=_workflow_verification_plan(workflow),
        verification_evidence=_workflow_verification_evidence(workflow),
        review=_workflow_review(workflow),
        verification_approval_status=verification_approval,
    )


@router.get("", response_model=WorkflowListResponse, responses=_ERROR_RESPONSES)
async def list_workflows(
    request: Request,
    state: str | None = None,
    source: str | None = None,
    candidate_id: str | None = None,
    workflow_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowListResponse:
    """Return persisted workflow summaries without exposing mutable internals."""

    _sprint, _verification, _review, sessions = (
        request.app.state.container.workflow_state.export_snapshot()
    )
    summaries = [
        _workflow_summary(request, workflow)
        for workflow in sessions.values()
    ]
    filtered = [
        item
        for item in summaries
        if _workflow_summary_matches(
            item,
            state=state,
            source=source,
            candidate_id=candidate_id,
            workflow_id=workflow_id,
        )
    ]
    filtered.sort(key=lambda item: item.workflow_id)
    return WorkflowListResponse(
        items=filtered[offset : offset + limit],
        total=len(filtered),
        limit=limit,
        offset=offset,
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
    "/{workflow_id}/verification-approval",
    response_model=WorkflowVerificationApprovalResponse,
    responses=_ERROR_RESPONSES,
)
async def submit_workflow_verification_approval(
    workflow_id: str,
    approval_request: WorkflowVerificationApprovalRequest,
    request: Request,
) -> WorkflowVerificationApprovalResponse:
    """Approve or reject the exact verification approval by workflow ID only."""

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
    if workflow.state is not WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_workflow", "message": "Workflow is not awaiting verification approval"},
        )
    approval_id = f"approval-verification-{workflow.identifier}"
    stored = request.app.state.container.approval_repository.get_request(approval_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "approval_not_found", "message": "Verification approval request not found"},
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
            detail={"code": "persistence_failure", "message": "Verification approval could not be persisted"},
        ) from exc
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "approval_already_decided", "message": "Approval already decided"},
        )
    return WorkflowVerificationApprovalResponse(
        workflow_id=workflow.identifier,
        workflow_state=workflow.state.value,
        verification_approval_status=decision.status.value,
        message="Verification approved. Verification is now available." if decision.status is ApprovalStatus.APPROVED else "Verification approval rejected.",
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
