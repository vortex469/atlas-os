from typing import Literal

from fastapi import APIRouter, Query

from app.actions import (
    ProviderActionAuditEntry,
    get_provider_action_history,
)

from app.services.summary_service import get_ops_summary
from app.services.system_service import get_system_status


router = APIRouter(
    prefix="/ops",
    tags=["Operations"],
)


@router.get("/status")
def ops_status():
    return get_system_status()


@router.get("/summary")
def ops_summary():
    return get_ops_summary()


@router.get(
    "/actions",
    response_model=list[ProviderActionAuditEntry],
)
def action_history(
    limit: int = Query(default=50, ge=1, le=200),
    provider_id: str | None = None,
    status: Literal["succeeded", "failed"] | None = None,
) -> list[ProviderActionAuditEntry]:
    return get_provider_action_history().list(
        limit=limit,
        provider_id=provider_id,
        status=status,
    )
