from fastapi import APIRouter

from app.config.settings import settings
from app.models.api import APIDiscovery
from app.routes.ace import router as ace_router
from app.routes.ai import router as ai_router
from app.routes.analysis import router as analysis_router
from app.routes.dashboard import router as dashboard_router
from app.routes.docker import router as docker_router
from app.routes.health import router as health_router
from app.routes.homeassistant import router as homeassistant_router
from app.routes.intelligence import router as intelligence_router
from app.routes.ops import router as ops_router
from app.routes.providers import router as providers_router
from app.routes.proxmox import router as proxmox_router
from app.routes.status import router as status_router


router = APIRouter(prefix="/api/v1")


@router.get(
    "",
    response_model=APIDiscovery,
    tags=["API"],
    summary="Discover Atlas API v1",
)
def api_discovery() -> APIDiscovery:
    return APIDiscovery(
        release=settings.atlas.release,
        endpoints={
            "health": "/api/v1/health",
            "dashboard": "/api/v1/dashboard",
            "status": "/api/v1/status",
            "providers": "/api/v1/providers",
            "ai": "/api/v1/ai",
            "operations": "/api/v1/ops",
            "intelligence": "/api/v1/intelligence",
        },
    )


# Existing routers are mounted beneath /api/v1 without changing their
# internal paths. Legacy routes remain mounted by app.main.
router.include_router(analysis_router)
router.include_router(health_router)
router.include_router(providers_router)
router.include_router(ops_router)
router.include_router(docker_router)
router.include_router(proxmox_router)
router.include_router(homeassistant_router)
router.include_router(intelligence_router)
router.include_router(ace_router)
router.include_router(ai_router)
router.include_router(dashboard_router)

# status_router defines "/", so mounting it with this prefix exposes
# the endpoint as /api/v1/status/.
router.include_router(status_router, prefix="/status", tags=["Status"])
