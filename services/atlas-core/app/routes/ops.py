from fastapi import APIRouter

from app.services.summary_service import get_ops_summary
from app.services.system_service import get_system_status


router = APIRouter(
    prefix="/ops",
    tags=["Operations"],
)


@router.get("/status")
def ops_status():
    return get_system_status()


@router.get("/summary")
def ops_summary():
    return get_ops_summary()
