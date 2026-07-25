import csv
import io
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

from app.actions import (
    ProviderActionAuditEntry,
    ProviderActionHistoryPage,
    ProviderActionHistoryProvider,
    ProviderActionHistorySummary,
    ProviderActionPruneRequest,
    ProviderActionPruneResult,
    get_provider_action_history,
)

from app.services.summary_service import get_ops_summary
from app.services.system_service import get_system_status


router = APIRouter(
    prefix="/ops",
    tags=["Operations"],
)


def normalized_range(
    completed_from: datetime | None,
    completed_to: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    for value in (completed_from, completed_to):
        if value is not None and value.tzinfo is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Audit date filters must include a timezone."
                ),
            )

    normalized_from = (
        completed_from.astimezone(timezone.utc)
        if completed_from
        else None
    )
    normalized_to = (
        completed_to.astimezone(timezone.utc)
        if completed_to
        else None
    )

    if (
        normalized_from is not None
        and normalized_to is not None
        and normalized_from > normalized_to
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Audit start date must not be after the end date."
            ),
        )

    return normalized_from, normalized_to


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
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=200),
) -> list[ProviderActionAuditEntry]:
    normalized_from, normalized_to = normalized_range(
        completed_from,
        completed_to,
    )

    return get_provider_action_history().list(
        limit=limit,
        provider_id=provider_id,
        status=status,
        completed_from=normalized_from,
        completed_to=normalized_to,
        search=search,
    )


def csv_safe(value: str) -> str:
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"

    return value


@router.get(
    "/actions/summary",
    response_model=ProviderActionHistorySummary,
)
def action_history_summary() -> ProviderActionHistorySummary:
    return get_provider_action_history().summary()


@router.get(
    "/actions/page",
    response_model=ProviderActionHistoryPage,
)
def action_history_page(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    provider_id: str | None = None,
    status: Literal["succeeded", "failed"] | None = None,
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=200),
) -> ProviderActionHistoryPage:
    normalized_from, normalized_to = normalized_range(
        completed_from,
        completed_to,
    )

    return get_provider_action_history().page(
        limit=limit,
        offset=offset,
        provider_id=provider_id,
        status=status,
        completed_from=normalized_from,
        completed_to=normalized_to,
        search=search,
    )


@router.get(
    "/actions/providers",
    response_model=list[ProviderActionHistoryProvider],
)
def action_history_providers() -> list[ProviderActionHistoryProvider]:
    return get_provider_action_history().providers()


@router.get("/actions/export")
def export_action_history(
    format: Literal["json", "csv"] = "json",
    provider_id: str | None = None,
    status: Literal["succeeded", "failed"] | None = None,
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=200),
) -> Response:
    normalized_from, normalized_to = normalized_range(
        completed_from,
        completed_to,
    )
    entries = get_provider_action_history().export_entries(
        provider_id=provider_id,
        status=status,
        completed_from=normalized_from,
        completed_to=normalized_to,
        search=search,
    )

    if format == "json":
        content = json.dumps(
            jsonable_encoder(entries),
            indent=2,
        )
        media_type = "application/json"
        extension = "json"
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "provider_id",
                "provider_name",
                "action_id",
                "action_label",
                "status",
                "success",
                "message",
                "confirmed",
                "destructive",
                "parameter_names",
                "request_id",
                "started_at",
                "completed_at",
                "duration_ms",
            ],
        )

        for entry in entries:
            writer.writerow(
                [
                    entry.id,
                    entry.provider_id,
                    csv_safe(entry.provider_name),
                    entry.action_id,
                    csv_safe(entry.action_label),
                    entry.status,
                    entry.success,
                    csv_safe(entry.message),
                    entry.confirmed,
                    entry.destructive,
                    csv_safe("|".join(entry.parameter_names)),
                    csv_safe(entry.request_id or ""),
                    entry.started_at.isoformat(),
                    entry.completed_at.isoformat(),
                    entry.duration_ms,
                ],
            )

        content = output.getvalue()
        media_type = "text/csv"
        extension = "csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="atlas-action-history.{extension}"'
            ),
        },
    )


@router.post(
    "/actions/prune",
    response_model=ProviderActionPruneResult,
    responses={409: {"description": "Confirmation required"}},
)
def prune_action_history(
    request: ProviderActionPruneRequest,
) -> ProviderActionPruneResult:
    if not request.confirmed:
        raise HTTPException(
            status_code=409,
            detail="Pruning action history requires confirmation.",
        )

    return get_provider_action_history().prune_expired()


@router.get(
    "/actions/{entry_id}",
    response_model=ProviderActionAuditEntry,
    responses={404: {"description": "Audit entry not found"}},
)
def action_history_detail(
    entry_id: str,
) -> ProviderActionAuditEntry:
    entry = get_provider_action_history().get(entry_id)

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Provider action audit entry not found.",
        )

    return entry
