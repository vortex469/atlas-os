from fastapi import APIRouter, HTTPException

from app.models.contracts import AceSummary, APIError
from app.services.intelligence_service import get_intelligence_summary


router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence"],
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
