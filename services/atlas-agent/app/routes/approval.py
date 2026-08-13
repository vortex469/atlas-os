"""Approval routes for Atlas Agent."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, status

from app.approval.engine import ApprovalEngine
from app.approval.exceptions import ApprovalValidationError
from app.approval.models import ApprovalDecision, ApprovalRequest, ApprovalStatus
from app.approval.repository import ApprovalRepository

router = APIRouter(prefix="/api/v1/agent/approval", tags=["approval"])


def _repository(request: Request) -> ApprovalRepository:
    """Get the approval repository from the application container."""
    return request.app.state.container.approval_repository


def _state_persistence(request: Request):
    return getattr(request.app.state.container, "state_persistence", None)


def _engine() -> ApprovalEngine:
    """Get the approval engine instance."""
    return ApprovalEngine()


@router.post("/request")
async def create_approval_request(request: Request, approval_request: ApprovalRequest) -> dict[str, str]:
    """Create a new approval request.

    Args:
        request: The approval request to create.

    Returns:
        A dictionary with the identifier of the created request.

    Raises:
        HTTPException: If there's an error creating the request.
    """
    # Get repository from container
    repository = _repository(request)
    
    # Get engine
    engine = _engine()
    
    try:
        result = engine.evaluate(
            ApprovalDecision(
                request=approval_request,
                status=ApprovalStatus.PENDING,
            )
        )
    except ApprovalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    persistence = _state_persistence(request)
    if persistence is None:
        identifier = repository.save_request(result.decision.request)
    else:
        identifier = persistence.mutate_approval(
            lambda approvals: approvals.save_request(result.decision.request)
        )

    return {
        "identifier": identifier,
    }


@router.get("/pending")
async def get_pending_requests(
    request: Request,
) -> list[dict]:
    """Get all pending approval requests.

    Args:
        request: The FastAPI request object.

    Returns:
        A list of pending approval requests.
    """
    repository = _repository(request)
    return [
        {
            "identifier": result.decision.request.identifier,
            "request": asdict(result.decision.request),
            "status": result.decision.status,
        }
        for result in repository.get_pending_requests()
    ]


@router.get("/{request_id}")
async def get_approval_request(
    request_id: str,
    request: Request,
) -> dict:
    """Get a specific approval request by ID.

    Args:
        request_id: The identifier of the approval request.
        request: The FastAPI request object.

    Returns:
        The approval request details.

    Raises:
        HTTPException: If the request is not found.
    """
    repository = _repository(request)
    result = repository.get_request(request_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    return {
        "identifier": request_id,
        "request": asdict(result.decision.request),
        "status": result.decision.status,
        "reviewer": result.decision.reviewer,
        "reason": result.decision.reason
    }


@router.post("/{request_id}/decision")
async def submit_approval_decision(
    request_id: str,
    decision: ApprovalDecision,
    request: Request,
) -> dict[str, str]:
    """Submit an approval decision for a specific request."""
    repository = _repository(request)
    engine = _engine()

    try:
        result = engine.evaluate(decision)
    except ApprovalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if repository.get_request(request_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found",
        )

    persistence = _state_persistence(request)
    if persistence is None:
        success = repository.update_decision(request_id, result.decision)
    else:
        success = persistence.mutate_approval(
            lambda approvals: approvals.update_decision(request_id, result.decision)
        )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval decision conflicts with the stored request",
        )

    return {
        "status": "success",
        "identifier": request_id,
        "approval_status": result.decision.status.value,
        "reviewer": result.decision.reviewer or "",
        "reason": result.decision.reason or "",
    }
