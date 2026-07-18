from fastapi import APIRouter

from app.services.docker_service import get_docker_status

router = APIRouter(prefix="/docker", tags=["Docker"])


@router.get("/status")
def docker_status():
    return get_docker_status()
