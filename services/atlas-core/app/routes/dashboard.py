from fastapi import APIRouter

from app.services.dashboard_service import get_dashboard

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

@router.get("")
async def dashboard():
    return await get_dashboard()
