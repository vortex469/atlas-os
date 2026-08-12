"""Workflow execution routes for Atlas Agent."""

import asyncio
from dataclasses import replace
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.approval.exceptions import ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
)
from app.candidate_planning.audit import (
    CandidateAuditApprovals,
    CandidateAuditChainValidator,
    CandidateAuditFailureCode,
)
from app.candidate_planning.commit import CandidateCommitFailureCode
from app.candidate_planning.execution import CandidateExecutionFailureCode
from app.candidate_planning.models import CandidateImplementationTranslationRequest
from app.candidate_planning.verification import CandidateVerificationFailureCode
from app.context.models import AgentContext
from app.execution.models import EnvironmentVariable, ExecutionResult
from app.model_providers.models import ModelResponse
from app.persistence.snapshot import StatePersistenceError
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

_AUDIT_STAGE_ORDER = [
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
]
_AUDIT_STAGE_RANK = {name: rank for rank, name in enumerate(_AUDIT_STAGE_ORDER)}

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


class WorkflowCommitRequestResponse(BaseModel):
    commit_request_id: str
    repository: str | None
    branch: str | None
    expected_head: str | None
    commit_message: str
    reviewed_files: list[str]
    reviewed_content_fingerprint: str
    commit_approval_status: str


class WorkflowCommitResultResponse(BaseModel):
    commit_sha: str | None
    commit_message: str | None
    committed_files: list[str]
    completion_time: str | None


class WorkflowAuditFailureResponse(BaseModel):
    valid: bool
    failure_code: str | None
    failure_stage: str | None


class WorkflowAuditSection(BaseModel):
    name: str
    status: str


class WorkflowAuditCandidateResponse(BaseModel):
    status: str
    candidate_id: str | None
    candidate_fingerprint: str | None
    source_recommendation_id: str | None
    target_id: str | None
    target_type: str | None


class WorkflowAuditPlanningResponse(BaseModel):
    status: str
    planning_session_id: str | None
    planning_state: str | None
    planning_status: str | None
    created_at: str | None
    planning_completed_at: str | None
    candidate_plan_id: str | None
    candidate_plan_fingerprint: str | None


class WorkflowAuditPlanResponse(BaseModel):
    status: str
    plan_id: str | None
    candidate_plan_fingerprint: str | None
    likely_affected_files: list[str]


class WorkflowAuditWorkflowResponse(BaseModel):
    status: str
    workflow_id: str
    workflow_source: str
    workflow_state: str


class WorkflowAuditImplementationResponse(BaseModel):
    status: str
    implementation_request_id: str | None
    execution_intent: str | None
    tool: str | None
    repository_root: str | None
    repository_head: str | None
    repository_branch: str | None
    working_directory: str | None
    affected_files: list[str]
    translator_version: str | None


class WorkflowAuditApprovalResponse(BaseModel):
    status: str
    approval_id: str | None


class WorkflowAuditApprovalsResponse(BaseModel):
    status: str
    shell: WorkflowAuditApprovalResponse
    implementation: WorkflowAuditApprovalResponse
    verification: WorkflowAuditApprovalResponse
    commit: WorkflowAuditApprovalResponse


class WorkflowAuditExecutionResponse(BaseModel):
    status: str
    execution_request_id: str | None
    execution_status: str | None
    changed_files_count: int
    changed_files: list[str]
    tool: str | None
    repository: str | None


class WorkflowAuditVerificationResponse(BaseModel):
    status: str
    verification_plan_id: str | None
    verification_evidence_id: str | None
    verification_status: str | None
    changed_files_digest: str | None
    verification_check_ids: list[str]
    repository_head: str | None
    verification_started_at: str | None
    verification_completed_at: str | None


class WorkflowAuditReviewResponse(BaseModel):
    status: str
    review_result_id: str | None
    review_report_id: str | None
    review_status: str | None
    reviewed_content_fingerprint: str | None
    changed_files: list[str]


class WorkflowAuditCommitResponse(BaseModel):
    status: str
    commit_request_id: str | None
    reviewed_files: list[str]
    reviewed_content_fingerprint: str | None
    expected_branch: str | None
    expected_head: str | None
    commit_message: str | None
    commit_sha: str | None
    committed_files: list[str]


class WorkflowAuditResponse(BaseModel):
    workflow_id: str
    workflow_state: str
    workflow_source: str
    blocked_reason: str | None = None
    validation: WorkflowAuditFailureResponse
    timeline: list[WorkflowAuditSection]
    candidate: WorkflowAuditCandidateResponse
    planning: WorkflowAuditPlanningResponse
    plan: WorkflowAuditPlanResponse
    workflow: WorkflowAuditWorkflowResponse
    implementation: WorkflowAuditImplementationResponse
    approvals: WorkflowAuditApprovalsResponse
    execution: WorkflowAuditExecutionResponse
    verification: WorkflowAuditVerificationResponse
    review: WorkflowAuditReviewResponse
    commit: WorkflowAuditCommitResponse


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
    commit_request: WorkflowCommitRequestResponse | None
    commit_result: WorkflowCommitResultResponse
    commit_approval_status: str


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


class WorkflowShellApprovalRequest(BaseModel):
    """Decision for the non-executable candidate workflow shell boundary."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    decision: str = Field(pattern="^(approve|reject)$")


class WorkflowShellApprovalResponse(BaseModel):
    workflow_id: str
    workflow_state: str
    shell_approval_status: str
    implementation_approval_request_id: str | None = None
    message: str


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


class WorkflowCommitApprovalRequest(BaseModel):
    """Boundary-safe commit approval decision request."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    decision: str = Field(pattern="^(approve|reject)$")


class WorkflowCommitApprovalResponse(BaseModel):
    workflow_id: str
    workflow_state: str
    commit_approval_status: str
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


def _approval_decision_from_route_input(
    approval_request: ApprovalRequest,
    *,
    decision: str,
) -> ApprovalDecision:
    """Build a normalized workflow-level approval decision with stable metadata."""

    route_decision = ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
    route_reviewer = "workflow-service"
    route_reason = None if route_decision is ApprovalStatus.APPROVED else "Rejected via workflow route."

    # Keep approval route behavior permissive for existing persisted approval requests,
    # while ensuring terminal decision metadata is valid.
    if route_decision in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED) and (
        route_reviewer is None or not route_reviewer.strip()
    ):
        raise ApprovalValidationError("Workflow decision reviewer must be nonblank")
    if route_decision is ApprovalStatus.APPROVED and route_reason:
        route_reason = None
    if route_decision is ApprovalStatus.REJECTED and (route_reason is None or not route_reason.strip()):
        raise ApprovalValidationError("Workflow rejection requires a nonblank reason")

    return ApprovalDecision(
        request=approval_request,
        status=route_decision,
        reviewer=route_reviewer,
        reason=route_reason,
    )
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


def _commit_approval_status(request: Request, workflow) -> str:
    return _approval_status(request, f"approval-commit-{workflow.identifier}")


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


def _workflow_commit_request(
    request: Request,
    workflow,
) -> WorkflowCommitRequestResponse | None:
    approval = request.app.state.container.approval_repository.get_request(
        f"approval-commit-{workflow.identifier}"
    )
    if approval is None or approval.decision.request.commit_metadata is None:
        return None
    approval_request = approval.decision.request
    metadata = approval_request.commit_metadata
    return WorkflowCommitRequestResponse(
        commit_request_id=approval_request.identifier,
        repository=(
            str(approval_request.requested_working_directory)
            if approval_request.requested_working_directory is not None
            else None
        ),
        branch=metadata.expected_branch,
        expected_head=metadata.expected_head,
        commit_message=metadata.commit_message,
        reviewed_files=[str(path) for path in metadata.reviewed_files],
        reviewed_content_fingerprint=metadata.reviewed_content_fingerprint,
        commit_approval_status=approval.decision.status.value,
    )


def _workflow_commit_result(workflow) -> WorkflowCommitResultResponse:
    result = workflow.commit_result
    if result is None:
        return WorkflowCommitResultResponse(
            commit_sha=None,
            commit_message=None,
            committed_files=[],
            completion_time=None,
        )
    return WorkflowCommitResultResponse(
        commit_sha=result.commit_sha,
        commit_message=result.message,
        committed_files=[str(path) for path in result.committed_files],
        completion_time=None,
    )


def _iso_ts(value: object | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()  # type: ignore[union-attr]


def _audit_approval_status(request: Request, approval_id: str | None) -> str:
    result = request.app.state.container.approval_repository.get_request(approval_id)
    if approval_id is None or result is None:
        return "not_requested"
    return result.decision.status.value


def _audit_stage_rank_for_state(
    state: WorkflowSessionState,
    workflow,
    *,
    implementation_approved: bool,
    verification_approved: bool,
    commit_approved: bool,
) -> int:
    if state in {
        WorkflowSessionState.COMPLETED,
        WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
        WorkflowSessionState.COMMITTING,
    }:
        return _AUDIT_STAGE_RANK["commit"]
    if state in {
        WorkflowSessionState.VERIFYING,
        WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
    }:
        return _AUDIT_STAGE_RANK["verification"]
    if state is WorkflowSessionState.EXECUTING:
        return _AUDIT_STAGE_RANK["execution"]
    if state is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL:
        return _AUDIT_STAGE_RANK["approvals"]
    if state in {WorkflowSessionState.AWAITING_APPROVAL, WorkflowSessionState.PLANNED}:
        return _AUDIT_STAGE_RANK["workflow"]
    if state is WorkflowSessionState.BLOCKED:
        if workflow.commit_result is not None:
            return _AUDIT_STAGE_RANK["commit"]
        if workflow.candidate_review_result is not None or workflow.review_report is not None:
            return _AUDIT_STAGE_RANK["review"]
        if workflow.candidate_verification_evidence is not None:
            return _AUDIT_STAGE_RANK["verification"]
        if workflow.candidate_verification_plan is not None and verification_approved:
            return _AUDIT_STAGE_RANK["verification"]
        if workflow.commit_request is not None and commit_approved:
            return _AUDIT_STAGE_RANK["approvals"]
        if workflow.execution_result is not None:
            return _AUDIT_STAGE_RANK["execution"]
        if workflow.candidate_implementation_request is not None and implementation_approved:
            return _AUDIT_STAGE_RANK["approvals"]
        if workflow.candidate_implementation_request is not None:
            return _AUDIT_STAGE_RANK["implementation"]
        return _AUDIT_STAGE_RANK["workflow"]
    return _AUDIT_STAGE_RANK["workflow"]


def _section_status(rank: int, current_rank: int, has_value: bool) -> str:
    if rank > current_rank:
        return "not_reached"
    if rank == current_rank and not has_value:
        return "current"
    return "completed" if has_value else "missing"


def _failure_stage(code: CandidateAuditFailureCode | None) -> str | None:
    if code is None:
        return None
    return {
        CandidateAuditFailureCode.NOT_CANDIDATE_WORKFLOW: "candidate",
        CandidateAuditFailureCode.MISSING_CANDIDATE_METADATA: "candidate",
        CandidateAuditFailureCode.MISSING_PLANNING_SESSION: "planning",
        CandidateAuditFailureCode.MISSING_CANDIDATE_PLAN: "plan",
        CandidateAuditFailureCode.MISSING_IMPLEMENTATION_REQUEST: "implementation",
        CandidateAuditFailureCode.MISSING_IMPLEMENTATION_APPROVAL: "approvals",
        CandidateAuditFailureCode.MISSING_EXECUTION_RESULT: "execution",
        CandidateAuditFailureCode.MISSING_VERIFICATION_PLAN: "verification",
        CandidateAuditFailureCode.MISSING_VERIFICATION_APPROVAL: "approvals",
        CandidateAuditFailureCode.MISSING_VERIFICATION_EVIDENCE: "verification",
        CandidateAuditFailureCode.MISSING_REVIEW_RESULT: "review",
        CandidateAuditFailureCode.MISSING_REVIEW_REPORT: "review",
        CandidateAuditFailureCode.MISSING_COMMIT_REQUEST: "commit",
        CandidateAuditFailureCode.MISSING_COMMIT_APPROVAL: "approvals",
        CandidateAuditFailureCode.MISSING_COMMIT_RESULT: "commit",
        CandidateAuditFailureCode.IDENTITY_MISMATCH: "candidate",
        CandidateAuditFailureCode.FINGERPRINT_MISMATCH: "candidate",
        CandidateAuditFailureCode.APPROVAL_MISMATCH: "approvals",
        CandidateAuditFailureCode.EXECUTION_MISMATCH: "execution",
        CandidateAuditFailureCode.VERIFICATION_MISMATCH: "verification",
        CandidateAuditFailureCode.REVIEW_MISMATCH: "review",
        CandidateAuditFailureCode.COMMIT_MISMATCH: "commit",
        CandidateAuditFailureCode.DUPLICATE_IDENTIFIER: "candidate",
    }.get(code)


def _timeline_statuses(
    current_rank: int,
    has_candidate: bool,
    has_planning: bool,
    has_plan: bool,
    has_workflow: bool,
    has_implementation: bool,
    has_approvals: bool,
    has_execution: bool,
    has_verification: bool,
    has_review: bool,
    has_commit: bool,
    failure_stage: str | None,
) -> list[WorkflowAuditSection]:
    statuses: dict[str, str] = {
        "candidate": _section_status(_AUDIT_STAGE_RANK["candidate"], current_rank, has_candidate),
        "planning": _section_status(_AUDIT_STAGE_RANK["planning"], current_rank, has_planning),
        "plan": _section_status(_AUDIT_STAGE_RANK["plan"], current_rank, has_plan),
        "workflow": _section_status(_AUDIT_STAGE_RANK["workflow"], current_rank, has_workflow),
        "implementation": _section_status(_AUDIT_STAGE_RANK["implementation"], current_rank, has_implementation),
        "approvals": _section_status(_AUDIT_STAGE_RANK["approvals"], current_rank, has_approvals),
        "execution": _section_status(_AUDIT_STAGE_RANK["execution"], current_rank, has_execution),
        "verification": _section_status(_AUDIT_STAGE_RANK["verification"], current_rank, has_verification),
        "review": _section_status(_AUDIT_STAGE_RANK["review"], current_rank, has_review),
        "commit": _section_status(_AUDIT_STAGE_RANK["commit"], current_rank, has_commit),
    }
    if failure_stage is not None and failure_stage in statuses:
        statuses[failure_stage] = "invalid"
    return [WorkflowAuditSection(name=section, status=status) for section, status in statuses.items()]


def _reviewed_content_fingerprint(approval_result: object | None) -> str | None:
    if approval_result is None:
        return None
    request = approval_result.decision.request  # type: ignore[union-attr]
    metadata = request.commit_metadata
    if metadata is None:
        return None
    return metadata.reviewed_content_fingerprint


def _candidate_audit_detail(request: Request, workflow) -> WorkflowAuditResponse:
    metadata = workflow.candidate_metadata
    planning_session = None
    if metadata is not None:
        planning_session = request.app.state.container.candidate_planning_state.get_session(
            metadata.candidate_planning_session_id,
        )

    audit_approvals = CandidateAuditApprovals(
        implementation=request.app.state.container.approval_repository.get_request(
            workflow.candidate_implementation_approval_id,
        ),
        verification=request.app.state.container.approval_repository.get_request(
            f"approval-verification-{workflow.identifier}"
        ),
        commit=request.app.state.container.approval_repository.get_request(
            f"approval-commit-{workflow.identifier}"
        ),
    )
    shell_approval_id = f"approval-{workflow.identifier}"
    shell_approval_status = _audit_approval_status(request, shell_approval_id)

    validation = CandidateAuditChainValidator().validate(
        planning_session=planning_session,
        workflow=workflow,
        approvals=audit_approvals,
    )
    plan = planning_session.plan if planning_session is not None else None
    implementation = workflow.candidate_implementation_request
    execution = workflow.execution_result
    verification_plan = workflow.candidate_verification_plan
    verification_evidence = workflow.candidate_verification_evidence
    review_result = workflow.candidate_review_result
    review_report = workflow.review_report
    commit_request = workflow.commit_request
    commit_result = workflow.commit_result

    implementation_approval_status = _audit_approval_status(
        request,
        workflow.candidate_implementation_approval_id,
    )
    verification_approval_status = _audit_approval_status(
        request,
        f"approval-verification-{workflow.identifier}",
    )
    commit_approval_status = _audit_approval_status(
        request,
        f"approval-commit-{workflow.identifier}",
    )

    current_rank = _audit_stage_rank_for_state(
        workflow.state,
        workflow,
        implementation_approved=implementation_approval_status == "approved",
        verification_approved=verification_approval_status == "approved",
        commit_approved=commit_approval_status == "approved",
    )
    failed_stage = _failure_stage(validation.failure_code)

    has_approvals = implementation_approval_status == "approved"
    if current_rank >= _AUDIT_STAGE_RANK["verification"]:
        has_approvals = has_approvals and verification_approval_status == "approved"
    if current_rank >= _AUDIT_STAGE_RANK["commit"]:
        has_approvals = has_approvals and commit_approval_status == "approved"

    has_verification = verification_plan is not None and verification_evidence is not None
    has_review = review_result is not None or review_report is not None
    has_commit = commit_request is not None and commit_result is not None

    timeline = _timeline_statuses(
        current_rank=current_rank,
        has_candidate=metadata is not None,
        has_planning=planning_session is not None,
        has_plan=plan is not None,
        has_workflow=True,
        has_implementation=implementation is not None,
        has_approvals=has_approvals,
        has_execution=execution is not None,
        has_verification=has_verification,
        has_review=has_review,
        has_commit=has_commit,
        failure_stage=failed_stage,
    )

    changed_files = [str(path) for path in workflow.changed_files]

    return WorkflowAuditResponse(
        workflow_id=workflow.identifier,
        workflow_state=workflow.state.value,
        workflow_source=workflow.source.value,
        blocked_reason=workflow.blocked_reason,
        validation=WorkflowAuditFailureResponse(
            valid=validation.valid,
            failure_code=validation.failure_code.value if validation.failure_code else None,
            failure_stage=failed_stage,
        ),
        timeline=timeline,
        candidate=WorkflowAuditCandidateResponse(
            status=_section_status(_AUDIT_STAGE_RANK["candidate"], current_rank, metadata is not None),
            candidate_id=metadata.candidate_id if metadata else None,
            candidate_fingerprint=metadata.candidate_fingerprint if metadata else None,
            source_recommendation_id=metadata.source_recommendation_id if metadata else None,
            target_id=metadata.target_id if metadata else None,
            target_type=metadata.target_type if metadata else None,
        ),
        planning=WorkflowAuditPlanningResponse(
            status=_section_status(_AUDIT_STAGE_RANK["planning"], current_rank, planning_session is not None),
            planning_session_id=planning_session.identifier if planning_session is not None else None,
            planning_state=planning_session.status.value if planning_session is not None else None,
            planning_status=planning_session.planning_status.value if planning_session is not None else None,
            created_at=_iso_ts(planning_session.created_at) if planning_session is not None else None,
            planning_completed_at=_iso_ts(planning_session.planning_completed_at) if planning_session is not None else None,
            candidate_plan_id=metadata.candidate_plan_id if metadata is not None else None,
            candidate_plan_fingerprint=metadata.candidate_plan_fingerprint if metadata is not None else None,
        ),
        plan=WorkflowAuditPlanResponse(
            status=_section_status(_AUDIT_STAGE_RANK["plan"], current_rank, plan is not None),
            plan_id=plan.identifier if plan is not None else None,
            candidate_plan_fingerprint=(
                metadata.candidate_plan_fingerprint if metadata is not None else None
            ),
            likely_affected_files=[
                str(path)
                for path in (plan.likely_affected_files if plan is not None else ())
            ],
        ),
        workflow=WorkflowAuditWorkflowResponse(
            status=_section_status(_AUDIT_STAGE_RANK["workflow"], current_rank, True),
            workflow_id=workflow.identifier,
            workflow_source=workflow.source.value,
            workflow_state=workflow.state.value,
        ),
        implementation=WorkflowAuditImplementationResponse(
            status=_section_status(_AUDIT_STAGE_RANK["implementation"], current_rank, implementation is not None),
            implementation_request_id=implementation.identifier if implementation is not None else None,
            execution_intent=implementation.execution_intent if implementation is not None else None,
            tool=implementation.argv[0] if implementation is not None and implementation.argv else None,
            repository_root=str(implementation.repository_root) if implementation is not None else None,
            repository_head=implementation.repository_head if implementation is not None else None,
            repository_branch=implementation.repository_branch if implementation is not None else None,
            working_directory=str(implementation.working_directory) if implementation is not None else None,
            affected_files=[str(path) for path in (implementation.affected_files if implementation is not None else ())],
            translator_version=implementation.translator_version if implementation is not None else None,
        ),
        approvals=WorkflowAuditApprovalsResponse(
            status=_section_status(_AUDIT_STAGE_RANK["approvals"], current_rank, has_approvals),
            shell=WorkflowAuditApprovalResponse(
                status=shell_approval_status,
                approval_id=shell_approval_id,
            ),
            implementation=WorkflowAuditApprovalResponse(
                status=implementation_approval_status,
                approval_id=workflow.candidate_implementation_approval_id,
            ),
            verification=WorkflowAuditApprovalResponse(
                status=verification_approval_status,
                approval_id=f"approval-verification-{workflow.identifier}",
            ),
            commit=WorkflowAuditApprovalResponse(
                status=commit_approval_status,
                approval_id=f"approval-commit-{workflow.identifier}",
            ),
        ),
        execution=WorkflowAuditExecutionResponse(
            status=_section_status(_AUDIT_STAGE_RANK["execution"], current_rank, execution is not None),
            execution_request_id=execution.request_id if execution is not None else None,
            execution_status=execution.status.value if execution is not None else None,
            changed_files_count=len(changed_files),
            changed_files=changed_files,
            tool=execution.argv[0] if execution is not None and execution.argv else None,
            repository=str(implementation.repository_root) if implementation is not None else None,
        ),
        verification=WorkflowAuditVerificationResponse(
            status=_section_status(_AUDIT_STAGE_RANK["verification"], current_rank, has_verification),
            verification_plan_id=verification_plan.identifier if verification_plan is not None else None,
            verification_evidence_id=verification_evidence.identifier if verification_evidence is not None else None,
            verification_status=verification_evidence.status.value if verification_evidence is not None else None,
            changed_files_digest=verification_plan.changed_files_digest if verification_plan is not None else None,
            verification_check_ids=(
                [check.identifier for check in verification_plan.verification_checks]
                if verification_plan is not None
                else []
            ),
            repository_head=verification_evidence.repository_head if verification_evidence is not None else None,
            verification_started_at=_iso_ts(verification_evidence.started_at) if verification_evidence is not None else None,
            verification_completed_at=_iso_ts(verification_evidence.completed_at) if verification_evidence is not None else None,
        ),
        review=WorkflowAuditReviewResponse(
            status=_section_status(_AUDIT_STAGE_RANK["review"], current_rank, has_review),
            review_result_id=review_result.identifier if review_result is not None else None,
            review_report_id=review_report.request_id if review_report is not None else None,
            review_status=(
                review_result.status.value
                if review_result is not None
                else review_report.status.value if review_report is not None else None
            ),
            reviewed_content_fingerprint=(
                review_result.reviewed_content_fingerprint if review_result is not None else None
            ),
            changed_files=changed_files,
        ),
        commit=WorkflowAuditCommitResponse(
            status=_section_status(_AUDIT_STAGE_RANK["commit"], current_rank, has_commit),
            commit_request_id=commit_request.identifier if commit_request is not None else None,
            reviewed_files=[str(path) for path in (commit_request.paths if commit_request is not None else ())],
            reviewed_content_fingerprint=_reviewed_content_fingerprint(audit_approvals.commit),
            expected_branch=commit_request.expected_branch if commit_request is not None else None,
            expected_head=commit_request.expected_head if commit_request is not None else None,
            commit_message=commit_request.message if commit_request is not None else None,
            commit_sha=commit_result.commit_sha if commit_result is not None else None,
            committed_files=[str(path) for path in (commit_result.committed_files if commit_result is not None else ())],
        ),
    )


@router.get(
    "/{workflow_id}/audit",
    response_model=WorkflowAuditResponse,
    responses=_ERROR_RESPONSES,
)
async def get_workflow_audit(
    request: Request,
    workflow_id: str,
) -> WorkflowAuditResponse:
    """Return the full machine-auditable workflow state chain details."""

    workflow = request.app.state.container.workflow_state.get_session(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "workflow_not_found", "message": "Workflow not found"},
        )
    return _candidate_audit_detail(request, workflow)


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
    commit_approval = _commit_approval_status(request, workflow)
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
        commit_request=_workflow_commit_request(request, workflow),
        commit_result=_workflow_commit_result(workflow),
        commit_approval_status=commit_approval,
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
    "/{workflow_id}/shell-approval",
    response_model=WorkflowShellApprovalResponse,
    responses=_ERROR_RESPONSES,
)
async def submit_workflow_shell_approval(
    workflow_id: str,
    approval_request: WorkflowShellApprovalRequest,
    request: Request,
) -> WorkflowShellApprovalResponse:
    """Approve the non-executable candidate workflow shell before translation."""

    if approval_request.workflow_id != workflow_id:
        raise HTTPException(status_code=400, detail={"code": "workflow_id_mismatch", "message": "Workflow ID must match the route"})
    workflow = request.app.state.container.workflow_state.get_session(workflow_id)
    if workflow is None or workflow.source.value != "candidate":
        raise HTTPException(status_code=404, detail={"code": "workflow_not_found", "message": "Candidate workflow not found"})
    approval_id = f"approval-{workflow_id}"
    stored = request.app.state.container.approval_repository.get_request(approval_id)
    if stored is None or stored.decision.request.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail={"code": "approval_not_found", "message": "Shell approval request not found"})
    shell = stored.decision.request
    if shell.purpose is not ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL or shell.requested_command:
        raise HTTPException(status_code=409, detail={"code": "invalid_shell_approval", "message": "Stored approval is not a candidate workflow shell approval"})
    if workflow.candidate_metadata is None or shell.checkpoint_id != workflow.candidate_metadata.candidate_plan_id:
        raise HTTPException(status_code=409, detail={"code": "checkpoint_mismatch", "message": "Shell approval checkpoint does not match the candidate plan"})
    if stored.decision.status is not ApprovalStatus.PENDING:
        if workflow.state is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL and approval_request.decision == "approve" and stored.decision.status is ApprovalStatus.APPROVED:
            return WorkflowShellApprovalResponse(
                workflow_id=workflow_id,
                workflow_state=workflow.state.value,
                shell_approval_status=stored.decision.status.value,
                message="Shell approval was already decided.",
            )
        if workflow.state is not WorkflowSessionState.AWAITING_APPROVAL or (
            approval_request.decision == "approve" and stored.decision.status is not ApprovalStatus.APPROVED
        ):
            raise HTTPException(status_code=409, detail={"code": "approval_already_decided", "message": "Shell approval was already decided"})
        return WorkflowShellApprovalResponse(
            workflow_id=workflow_id,
            workflow_state=workflow.state.value,
            shell_approval_status=stored.decision.status.value,
            message="Shell approval was already decided.",
        )
    if workflow.state is not WorkflowSessionState.AWAITING_APPROVAL:
        raise HTTPException(status_code=409, detail={"code": "stale_workflow", "message": "Workflow is not awaiting shell approval"})
    decision = ApprovalDecision(
        request=shell,
        status=ApprovalStatus.APPROVED if approval_request.decision == "approve" else ApprovalStatus.REJECTED,
        reviewer="workflow-shell",
        reason=None,
    )
    persistence = getattr(request.app.state.container, "state_persistence", None)
    try:
        if persistence is None:
            success = request.app.state.container.approval_repository.update_decision(approval_id, decision)
        else:
            success = persistence.mutate_approval(lambda approvals: approvals.update_decision(approval_id, decision))
    except StatePersistenceError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "approval_already_decided", "message": "Shell approval was concurrently decided"},
        ) from error
    if not success:
        raise HTTPException(status_code=409, detail={"code": "approval_already_decided", "message": "Shell approval was concurrently decided"})
    if decision.status is ApprovalStatus.REJECTED:
        return WorkflowShellApprovalResponse(
            workflow_id=workflow_id,
            workflow_state=workflow.state.value,
            shell_approval_status=decision.status.value,
            message="Shell approval rejected.",
        )
    metadata = workflow.candidate_metadata
    try:
        translation = await request.app.state.container.candidate_planning_service.translate_workflow_shell_to_implementation(
            metadata.candidate_planning_session_id,
            CandidateImplementationTranslationRequest(
                expected_candidate_fingerprint=metadata.candidate_fingerprint,
                expected_plan_fingerprint=metadata.candidate_plan_fingerprint,
            ),
        )
    except Exception:  # noqa: BLE001
        translation = None
    if translation is None or translation.exact_approval_request_id is None:
        persistence = getattr(request.app.state.container, "state_persistence", None)
        if persistence is not None:
            def block(workflow_state, approvals, candidate_planning):
                current = workflow_state.get_session(workflow_id)
                if current is not None and current.state is WorkflowSessionState.AWAITING_APPROVAL:
                    workflow_state.sessions[workflow_id] = replace(
                        current,
                        state=WorkflowSessionState.BLOCKED,
                        blocked_reason="candidate_shell_translation_failed",
                    )
            persistence.mutate_aggregate(block)
        raise HTTPException(status_code=409, detail={"code": "translation_failed", "message": "Candidate workflow shell translation failed"})
    updated = request.app.state.container.workflow_state.get_session(workflow_id)
    assert updated is not None
    return WorkflowShellApprovalResponse(
        workflow_id=workflow_id,
        workflow_state=updated.state.value,
        shell_approval_status=decision.status.value,
        implementation_approval_request_id=translation.exact_approval_request_id,
        message="Shell approved. Exact implementation approval is now required.",
    )


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

    persistence = getattr(request.app.state.container, "state_persistence", None)
    try:
        decision = _approval_decision_from_route_input(
            stored.decision.request,
            decision=approval_request.decision,
        )
        if persistence is None:
            success = request.app.state.container.approval_repository.update_decision(approval_id, decision)
        else:
            success = persistence.mutate_approval(lambda approvals: approvals.update_decision(approval_id, decision))
    except ApprovalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_decision", "message": str(exc)},
        ) from exc
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
    persistence = getattr(request.app.state.container, "state_persistence", None)
    try:
        decision = _approval_decision_from_route_input(
            stored.decision.request,
            decision=approval_request.decision,
        )
        if persistence is None:
            success = request.app.state.container.approval_repository.update_decision(approval_id, decision)
        else:
            success = persistence.mutate_approval(lambda approvals: approvals.update_decision(approval_id, decision))
    except ApprovalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_decision", "message": str(exc)},
        ) from exc
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
    "/{workflow_id}/commit-approval",
    response_model=WorkflowCommitApprovalResponse,
    responses=_ERROR_RESPONSES,
)
async def submit_workflow_commit_approval(
    workflow_id: str,
    approval_request: WorkflowCommitApprovalRequest,
    request: Request,
) -> WorkflowCommitApprovalResponse:
    """Approve or reject the exact commit approval by workflow ID only."""

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
    if workflow.state is WorkflowSessionState.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "workflow_completed", "message": "Workflow completed"},
        )
    if workflow.state is WorkflowSessionState.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "workflow_blocked", "message": "Workflow blocked"},
        )
    if workflow.state is not WorkflowSessionState.AWAITING_COMMIT_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_workflow", "message": "Workflow is not awaiting commit approval"},
        )
    approval_id = f"approval-commit-{workflow.identifier}"
    stored = request.app.state.container.approval_repository.get_request(approval_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "approval_not_found", "message": "Commit approval request not found"},
        )
    if stored.decision.status is not ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "approval_already_decided", "message": "Commit approval already decided"},
        )
    persistence = getattr(request.app.state.container, "state_persistence", None)
    try:
        decision = _approval_decision_from_route_input(
            stored.decision.request,
            decision=approval_request.decision,
        )
        if persistence is None:
            success = request.app.state.container.approval_repository.update_decision(approval_id, decision)
        else:
            success = persistence.mutate_approval(lambda approvals: approvals.update_decision(approval_id, decision))
    except ApprovalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_decision", "message": str(exc)},
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failure", "message": "Commit approval could not be persisted"},
        ) from exc
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "approval_already_decided", "message": "Commit approval already decided"},
        )
    return WorkflowCommitApprovalResponse(
        workflow_id=workflow.identifier,
        workflow_state=workflow.state.value,
        commit_approval_status=decision.status.value,
        message=(
            "Commit approved. Workflow may now complete through the existing backend resume path."
            if decision.status is ApprovalStatus.APPROVED
            else "Commit approval rejected."
        ),
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
