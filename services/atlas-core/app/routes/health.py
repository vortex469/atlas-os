from fastapi import APIRouter

from app.models.contracts import AtlasHealth
from app.services.health_service import get_health

router = APIRouter()


@router.get("/health", response_model=AtlasHealth)
def health():
    results = get_health()

    overall_status = (
        "healthy"
        if all(service["status"] == "online" for service in results.values())
        else "degraded"
    )

    return {
        "atlas": overall_status,
        "services": results,
    }
