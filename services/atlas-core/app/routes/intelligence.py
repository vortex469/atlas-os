from fastapi import APIRouter, HTTPException, Query

from app.intelligence import history as history_module
from app.intelligence.report import IntelligenceTelemetrySnapshot
from app.models.contracts import AceSummary, APIError
from app.services.intelligence_service import get_intelligence_summary


router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence"],
)


@router.get(
    "/telemetry/history",
    response_model=list[IntelligenceTelemetrySnapshot],
)
def intelligence_telemetry_history(
    limit: int = Query(default=50, ge=1, le=500),
) -> list[IntelligenceTelemetrySnapshot]:
    return history_module.intelligence_telemetry_history.list(
        limit=limit
    )


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
