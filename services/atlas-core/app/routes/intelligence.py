import csv
import io
import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

from app.intelligence import history as history_module
from app.intelligence.report import IntelligenceTelemetrySnapshot
from app.models.contracts import AceSummary, APIError
from app.services.intelligence_service import get_intelligence_summary


router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence"],
)


def _telemetry_snapshots(
    *,
    limit: int,
    provider_id: str | None,
    status: Literal["completed", "timed_out", "failed"] | None,
    collected_from: datetime | None,
    collected_to: datetime | None,
) -> list[IntelligenceTelemetrySnapshot]:
    try:
        return history_module.intelligence_telemetry_history.list(
            limit=limit,
            provider_id=provider_id,
            status=status,
            collected_from=collected_from,
            collected_to=collected_to,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


@router.get(
    "/telemetry/history",
    response_model=list[IntelligenceTelemetrySnapshot],
)
def intelligence_telemetry_history(
    limit: int = Query(default=50, ge=1, le=500),
    provider_id: str | None = Query(default=None, min_length=1),
    status: Literal[
        "completed",
        "timed_out",
        "failed",
    ]
    | None = None,
    collected_from: datetime | None = None,
    collected_to: datetime | None = None,
) -> list[IntelligenceTelemetrySnapshot]:
    return _telemetry_snapshots(
        limit=limit,
        provider_id=provider_id,
        status=status,
        collected_from=collected_from,
        collected_to=collected_to,
    )


@router.get("/telemetry/history/export")
def export_intelligence_telemetry_history(
    format: Literal["json", "csv"] = "json",
    limit: int = Query(default=500, ge=1, le=500),
    provider_id: str | None = Query(default=None, min_length=1),
    status: Literal[
        "completed",
        "timed_out",
        "failed",
    ]
    | None = None,
    collected_from: datetime | None = None,
    collected_to: datetime | None = None,
) -> Response:
    snapshots = _telemetry_snapshots(
        limit=limit,
        provider_id=provider_id,
        status=status,
        collected_from=collected_from,
        collected_to=collected_to,
    )

    if format == "json":
        content = json.dumps(
            jsonable_encoder(snapshots),
            indent=2,
        )
        media_type = "application/json"
        extension = "json"
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "snapshot_id",
                "collected_at",
                "collection_duration_ms",
                "provider_timeout_seconds",
                "provider_id",
                "provider_name",
                "status",
                "provider_duration_ms",
                "finding_count",
            ],
        )
        for snapshot in snapshots:
            providers = snapshot.telemetry.providers or [None]
            for provider in providers:
                writer.writerow(
                    [
                        snapshot.id,
                        snapshot.collected_at.isoformat(),
                        snapshot.telemetry
                        .provider_collection_duration_ms,
                        snapshot.telemetry
                        .provider_timeout_seconds,
                        provider.provider_id if provider else "",
                        _csv_safe(
                            provider.provider_name
                            if provider
                            else ""
                        ),
                        provider.status if provider else "",
                        provider.duration_ms if provider else "",
                        provider.finding_count if provider else 0,
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
                f'filename="atlas-intelligence-history.{extension}"'
            ),
        },
    )


def _csv_safe(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


@router.get(
    "/summary",
    response_model=AceSummary,
    responses={503: {"model": APIError}},
)
async def intelligence_summary():
    try:
        return await get_intelligence_summary()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
