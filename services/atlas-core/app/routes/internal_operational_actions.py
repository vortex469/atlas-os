"""Authenticated internal Agent-to-Core operational dispatch route."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.operational_dispatch.ledger import OperationalLedgerConflictError
from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchRequest,
    OperationalDispatchResult,
    OperationalLifecycleStatus,
)

MAX_OPERATIONAL_DISPATCH_BODY_BYTES = 65_536

router = APIRouter(prefix="/internal/operational-actions", tags=["Internal"])


def _record(request: Request, audit_status: OperationalDispatchAuditStatus) -> None:
    request.app.state.operational_dispatch_ledger.append_event(
        OperationalDispatchAuditEvent(
            event_id=uuid4().hex,
            status=audit_status,
            occurred_at=datetime.now(UTC),
        )
    )


@router.post(
    "/dispatch",
    response_model=OperationalDispatchResult,
    include_in_schema=False,
)
async def dispatch_operational_action(request: Request) -> OperationalDispatchResult:
    """Authenticate, strictly decode, and submit one immutable request."""

    _record(request, OperationalDispatchAuditStatus.AUTH_ATTEMPTED)
    if not request.app.state.operational_dispatch_authenticator.authenticate(
        request.headers.get("Authorization")
    ):
        _record(request, OperationalDispatchAuditStatus.AUTH_REJECTED)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operational dispatch authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    content_length = request.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = MAX_OPERATIONAL_DISPATCH_BODY_BYTES + 1
        if declared_size < 0 or declared_size > MAX_OPERATIONAL_DISPATCH_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Operational dispatch request is too large.",
            )
    body = await request.body()
    if len(body) > MAX_OPERATIONAL_DISPATCH_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Operational dispatch request is too large.",
        )
    try:
        dispatch_request = OperationalDispatchRequest.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Operational dispatch request is invalid.",
        ) from error

    ledger = request.app.state.operational_dispatch_ledger
    ledger.append_event(
        OperationalDispatchAuditEvent(
            event_id=uuid4().hex,
            status=OperationalDispatchAuditStatus.REQUEST_ACCEPTED,
            occurred_at=datetime.now(UTC),
            request_id=dispatch_request.request_id,
            request_digest=dispatch_request.request_digest,
            workflow_session_id=dispatch_request.workflow_session_id,
            candidate_planning_session_id=(
                dispatch_request.candidate_planning_session_id
            ),
            candidate_id=dispatch_request.candidate_id,
            candidate_plan_id=dispatch_request.candidate_plan_id,
            provider_id=dispatch_request.provider_id,
            resource_id=dispatch_request.resource_id,
            resource_type=dispatch_request.resource_type,
            target_fingerprint=dispatch_request.target_fingerprint,
        )
    )
    try:
        return await request.app.state.operational_lifecycle_service.dispatch(
            dispatch_request
        )
    except OperationalLedgerConflictError as error:
        ledger.append_event(
            OperationalDispatchAuditEvent(
                event_id=uuid4().hex,
                status=OperationalDispatchAuditStatus.REQUEST_CONFLICT,
                occurred_at=datetime.now(UTC),
                request_id=dispatch_request.request_id,
                request_digest=dispatch_request.request_digest,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operational dispatch request identity conflicts.",
        ) from error


@router.get(
    "/{request_id}",
    response_model=OperationalLifecycleStatus,
    include_in_schema=False,
)
async def operational_action_status(
    request_id: str, request: Request
) -> OperationalLifecycleStatus:
    _record(request, OperationalDispatchAuditStatus.AUTH_ATTEMPTED)
    if not request.app.state.operational_dispatch_authenticator.authenticate(
        request.headers.get("Authorization")
    ):
        _record(request, OperationalDispatchAuditStatus.AUTH_REJECTED)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operational dispatch authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    lifecycle_status = request.app.state.operational_lifecycle_service.status(request_id)
    if lifecycle_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operational dispatch request was not found.",
        )
    return lifecycle_status
