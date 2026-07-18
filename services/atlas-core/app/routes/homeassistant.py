from fastapi import APIRouter, HTTPException

from app.services.homeassistant_service import (
    get_homeassistant_status,
)


router = APIRouter(
    prefix="/home",
    tags=["Home Assistant"],
)


@router.get("/status")
def home_status():
    try:
        return get_homeassistant_status()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
