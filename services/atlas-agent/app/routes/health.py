"""Atlas Agent health and diagnostics endpoints."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.approval.engine import ApprovalEngine
from app.repository.exceptions import InvalidRepositoryError, RepositoryInspectionError
from app.version import AGENT_VERSION
from app.workflow.engine import WorkflowEngine

router = APIRouter()


class DiagnosticsResponse(BaseModel):
    """Serialized Atlas Agent diagnostics."""

    version: str
    git_branch: str | None
    approval_engine_available: bool
    workflow_engine_available: bool


@router.get("/health")
async def health() -> dict[str, str]:
    """Return the service health status."""

    return {
        "status": "healthy",
        "service": "atlas-agent",
    }


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(request: Request) -> DiagnosticsResponse:
    """Return read-only Atlas Agent runtime diagnostics."""

    try:
        snapshot = request.app.state.container.repository_inspector.inspect()
    except (InvalidRepositoryError, RepositoryInspectionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "repository_diagnostics_unavailable",
                "message": "Repository diagnostics are unavailable",
            },
        ) from exc

    return DiagnosticsResponse(
        version=AGENT_VERSION,
        git_branch=snapshot.branch,
        approval_engine_available=bool(ApprovalEngine),
        workflow_engine_available=bool(WorkflowEngine),
    )
