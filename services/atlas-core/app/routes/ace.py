from fastapi import APIRouter, HTTPException

from app.services.intelligence_service import get_intelligence_summary


router = APIRouter(
    prefix="/ace",
    tags=["Atlas Cognitive Engine"],
)


@router.get("/summary")
def ace_summary():
    try:
        return get_intelligence_summary()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
