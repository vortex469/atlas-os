"""Atlas Agent health endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return the service health status."""

    return {
        "status": "healthy",
        "service": "atlas-agent",
    }
