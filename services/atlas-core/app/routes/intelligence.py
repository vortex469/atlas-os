from fastapi import APIRouter, HTTPException

from app.services.intelligence_service import get_intelligence_summary


router = APIRouter(
    prefix="/intelligence",
    tags=["Intelligence"],
)


@router.get("/summary")
def intelligence_summary():
    try:
        return get_intelligence_summary()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
