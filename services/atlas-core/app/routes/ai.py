from fastapi import APIRouter, HTTPException

from app.actions import (
    ProviderActionDisabledError,
    ProviderActionNotFoundError,
)
from app.application.ai_service import ai_service
from app.providers import ProviderNotFoundError


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


@router.get("/status")
async def ai_status():
    """Return the current state of the Atlas AI subsystem."""

    try:
        return await ai_service.status()
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail="The configured AI provider is unavailable.",
        ) from error
    except (
        ProviderActionNotFoundError,
        ProviderActionDisabledError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
