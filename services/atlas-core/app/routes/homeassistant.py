from fastapi import APIRouter, HTTPException

from app.services.homeassistant_service import (
    get_homeassistant_status,
    get_unavailable_entities,
)

router = APIRouter(
    prefix="/home",
    tags=["Home Assistant"],
)


@router.get("/unavailable")
def home_unavailable():
    try:
        return get_unavailable_entities()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
