"""Read-only Atlas Agent status endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.container.application import ApplicationContainer
from app.review.models import ReviewReport
from app.verification.models import VerificationReport, VerificationStatus
from app.workflow.models import SprintPhase, SprintStatus

router = APIRouter(prefix="/api/v1/agent", tags=["atlas-agent"])


class AgentInfoResponse(BaseModel):
    """Serialized Atlas Agent runtime information."""

    app_name: str
    version: str
    environment: str
    repository_root: str
    supported_workflow_phases: list[str]
    supported_verification_statuses: list[str]


class RepositoryStatusResponse(BaseModel):
    """Serialized Git repository status."""

    root: str
    branch: str | None
    head_commit: str | None
    is_clean: bool
    modified_files: list[str]
    staged_files: list[str]
    untracked_files: list[str]


class SprintStatusResponse(BaseModel):
    """Serialized current sprint status."""

    checkpoint_id: str
    title: str
    goal: str
    phase: str


class VerificationCheckResponse(BaseModel):
    """Serialized verification-check result."""

    identifier: str
    argv: list[str]
    working_directory: str
    status: str
    return_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None


class VerificationReportResponse(BaseModel):
    """Serialized latest verification report."""

    repository_root: str
    status: str
    duration_seconds: float
    results: list[VerificationCheckResponse]


class ReviewFindingResponse(BaseModel):
    """Serialized review finding."""

    code: str
    category: str
    severity: str
    summary: str
    evidence: str
    recommendation: str


class ReviewReportResponse(BaseModel):
    """Serialized latest review report."""

    request_id: str
    checkpoint_id: str
    status: str
    findings: list[ReviewFindingResponse]
    recommendations: list[str]


def _container(request: Request) -> ApplicationContainer:
    return request.app.state.container


def _path(value: Path) -> str:
    return str(value)


def _verification_response(
    report: VerificationReport,
) -> VerificationReportResponse:
    return VerificationReportResponse(
        repository_root=_path(report.repository_root),
        status=report.status.value,
        duration_seconds=report.duration_seconds,
        results=[
            VerificationCheckResponse(
                identifier=result.identifier,
                argv=list(result.argv),
                working_directory=_path(result.working_directory),
                status=result.status.value,
                return_code=result.return_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=result.duration_seconds,
                error=result.error,
            )
            for result in report.results
        ],
    )


def _review_response(report: ReviewReport) -> ReviewReportResponse:
    return ReviewReportResponse(
        request_id=report.request_id,
        checkpoint_id=report.checkpoint_id,
        status=report.status.value,
        findings=[
            ReviewFindingResponse(
                code=finding.code,
                category=finding.category.value,
                severity=finding.severity.value,
                summary=finding.summary,
                evidence=finding.evidence,
                recommendation=finding.recommendation,
            )
            for finding in report.findings
        ],
        recommendations=list(report.recommendations),
    )


def _sprint_response(sprint: SprintStatus) -> SprintStatusResponse:
    return SprintStatusResponse(
        checkpoint_id=sprint.checkpoint_id,
        title=sprint.title,
        goal=sprint.goal,
        phase=sprint.phase.value,
    )


@router.get("/info", response_model=AgentInfoResponse)
async def agent_info(request: Request) -> AgentInfoResponse:
    """Return Atlas Agent runtime information."""

    container = _container(request)
    settings = container.settings

    return AgentInfoResponse(
        app_name=settings.app_name,
        version="development",
        environment=settings.environment,
        repository_root=_path(settings.repository_root),
        supported_workflow_phases=[
            phase.value
            for phase in SprintPhase
        ],
        supported_verification_statuses=[
            status.value
            for status in VerificationStatus
        ],
    )


@router.get("/repository", response_model=RepositoryStatusResponse)
async def repository_status(request: Request) -> RepositoryStatusResponse:
    """Return the current Git repository status."""

    snapshot = _container(request).repository_inspector.inspect()

    return RepositoryStatusResponse(
        root=_path(snapshot.root),
        branch=snapshot.branch,
        head_commit=snapshot.head_commit,
        is_clean=snapshot.is_clean,
        modified_files=list(snapshot.modified_files),
        staged_files=list(snapshot.staged_files),
        untracked_files=list(snapshot.untracked_files),
    )


@router.get("/sprint", response_model=SprintStatusResponse)
async def sprint_status(request: Request) -> SprintStatusResponse:
    """Return the current sprint status."""

    sprint = _container(request).workflow_state.get_sprint()

    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sprint status has been published",
        )

    return _sprint_response(sprint)


@router.get(
    "/verification",
    response_model=VerificationReportResponse,
)
async def verification_report(
    request: Request,
) -> VerificationReportResponse:
    """Return the latest verification report."""

    report = _container(request).workflow_state.get_verification()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verification report has been published",
        )

    return _verification_response(report)


@router.get("/review", response_model=ReviewReportResponse)
async def review_report(request: Request) -> ReviewReportResponse:
    """Return the latest review report."""

    report = _container(request).workflow_state.get_review()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No review report has been published",
        )

    return _review_response(report)
