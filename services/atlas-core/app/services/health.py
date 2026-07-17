from fastapi import APIRouter

from app.services.health_service import get_health

router = APIRouter()


@router.get("/health")
def health():

    results = get_health()

    statuses = [service["status"] for service in results.values()]

    if all(status == "online" for status in statuses):
        overall_status = "healthy"
    elif any(status == "offline" for status in statuses):
        overall_status = "degraded"
    else:
        overall_status = "degraded"

    return {
        "atlas": overall_status,
        "services": results,
    }