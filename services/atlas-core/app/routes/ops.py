from fastapi import APIRouter

from app.services.system_service import get_system_status

router = APIRouter()


@router.get("/ops/status")
def ops_status():
    return get_system_status()
