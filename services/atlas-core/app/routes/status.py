from fastapi import APIRouter

from app.config.settings import settings

router = APIRouter()


@router.get("/")
def root():
    return {
        "atlas": "online",
        "assistant": settings.atlas.assistant,
        "engine": "Hermes",
        "release": settings.atlas.release,
    }
