from fastapi import APIRouter, HTTPException

from app.models.contracts import AceSummary, APIError
from app.services.intelligence_service import get_intelligence_summary


router = APIRouter(
    prefix="/ace",
    tags=["Atlas Cognitive Engine"],
)


@router.get(
    "/summary",
    response_model=AceSummary,
    responses={503: {"model": APIError}},
)
def ace_summary():
    try:
        return get_intelligence_summary()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
