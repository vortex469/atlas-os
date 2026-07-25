from fastapi import APIRouter

from app.models.dashboard import Dashboard
from app.services.dashboard_service import get_dashboard


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("", response_model=Dashboard)
async def dashboard() -> Dashboard:
    return await get_dashboard()
