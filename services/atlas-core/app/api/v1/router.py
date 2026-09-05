from fastapi import APIRouter

from app.config.settings import settings
from app.models.api import APIDiscovery
from app.routes.ace import router as ace_router
from app.routes.ai import router as ai_router
from app.routes.analysis import router as analysis_router
from app.routes.controlled_dequeue_admission import (
    router as controlled_dequeue_admission_router,
)
from app.routes.dashboard import router as dashboard_router
from app.routes.delivery_activation_preflight import (
    router as delivery_activation_preflight_router,
)
from app.routes.delivery_enablement import router as delivery_enablement_router
from app.routes.discovery import router as discovery_router
from app.routes.docker import router as docker_router
from app.routes.execution_candidate_intake import (
    router as execution_candidate_intake_router,
)
from app.routes.execution_candidates import router as execution_candidates_router
from app.routes.execution_permission_grant import (
    router as execution_permission_grant_router,
)
from app.routes.health import router as health_router
from app.routes.homeassistant import router as homeassistant_router
from app.routes.installation import router as installation_router
from app.routes.installation_approval_intent import (
    router as installation_approval_intent_router,
)
from app.routes.installation_candidate_admission import (
    router as installation_candidate_admission_router,
)
from app.routes.installation_candidate_lifecycle import (
    router as installation_candidate_lifecycle_router,
)
from app.routes.installation_capability import router as installation_capability_router
from app.routes.installation_dispatch_handoff import (
    router as installation_dispatch_handoff_router,
)
from app.routes.installation_execution_admission import (
    router as installation_execution_admission_router,
)
from app.routes.installation_execution_request import (
    router as installation_execution_request_router,
)
from app.routes.installation_live_enqueue_admission import (
    router as installation_live_enqueue_admission_router,
)
from app.routes.installation_one_shot_live_enqueue import (
    router as installation_one_shot_live_enqueue_router,
)
from app.routes.installation_plan import router as installation_plan_router
from app.routes.installation_readiness_review import (
    router as installation_readiness_review_router,
)
from app.routes.intelligence import router as intelligence_router
from app.routes.internal_operational_actions import (
    router as internal_operational_actions_router,
)
from app.routes.one_shot_controlled_dequeue import (
    router as one_shot_controlled_dequeue_router,
)
from app.routes.operator_auth import router as operator_auth_router
from app.routes.ops import router as ops_router
from app.routes.policies import router as policies_router
from app.routes.provider_connections import router as provider_connections_router
from app.routes.provider_intent_mutation import (
    router as provider_intent_mutation_router,
)
from app.routes.provider_intent_suggestions import (
    router as provider_intent_suggestions_router,
)
from app.routes.provider_management import router as provider_management_router
from app.routes.provider_resources import router as provider_resources_router
from app.routes.providers import router as providers_router
from app.routes.proxmox import router as proxmox_router
from app.routes.queue_observation import router as queue_observation_router
from app.routes.runner_binding_plan import router as runner_binding_plan_router
from app.routes.status import router as status_router
from app.routes.worker_admission_stub import router as worker_admission_stub_router
from app.routes.worker_intake_admission import (
    router as worker_intake_admission_router,
)
from app.routes.worker_queue_reservation import (
    router as worker_queue_reservation_router,
)

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
            "provider_connections": "/api/v1/providers/{provider_id}/connection",
            "provider_management": "/api/v1/providers/{provider_id}/management",
            "provider_resources": "/api/v1/providers/{provider_id}/resources",
            "discovery": "/api/v1/discovery/items",
            "execution_candidates": "/api/v1/execution-candidates",
            "ai": "/api/v1/ai",
            "operations": "/api/v1/ops",
            "policies": "/api/v1/policies",
            "intelligence": "/api/v1/intelligence",
        },
    )


# Existing routers are mounted beneath /api/v1 without changing their
# internal paths. Legacy routes remain mounted by app.main.
router.include_router(analysis_router)
router.include_router(health_router)
router.include_router(providers_router)
router.include_router(provider_connections_router)
router.include_router(provider_management_router)
router.include_router(provider_intent_suggestions_router)
router.include_router(provider_intent_mutation_router)
router.include_router(provider_resources_router)
router.include_router(discovery_router)
router.include_router(delivery_activation_preflight_router)
router.include_router(delivery_enablement_router)
router.include_router(installation_plan_router)
router.include_router(installation_router)
router.include_router(installation_capability_router)
router.include_router(installation_candidate_admission_router)
router.include_router(installation_candidate_lifecycle_router)
router.include_router(installation_approval_intent_router)
router.include_router(installation_execution_request_router)
router.include_router(installation_execution_admission_router)
router.include_router(runner_binding_plan_router)
router.include_router(worker_admission_stub_router)
router.include_router(worker_queue_reservation_router)
router.include_router(worker_intake_admission_router)
router.include_router(installation_live_enqueue_admission_router)
router.include_router(installation_one_shot_live_enqueue_router)
router.include_router(queue_observation_router)
router.include_router(controlled_dequeue_admission_router)
router.include_router(one_shot_controlled_dequeue_router)
router.include_router(installation_dispatch_handoff_router)
router.include_router(installation_readiness_review_router)
router.include_router(execution_permission_grant_router)
router.include_router(execution_candidates_router)
router.include_router(execution_candidate_intake_router)
router.include_router(ops_router)
router.include_router(operator_auth_router)
router.include_router(policies_router)
router.include_router(docker_router)
router.include_router(proxmox_router)
router.include_router(homeassistant_router)
router.include_router(intelligence_router)
router.include_router(internal_operational_actions_router)
router.include_router(ace_router)
router.include_router(ai_router)
router.include_router(dashboard_router)

# status_router defines "/", so mounting it with this prefix exposes
# the endpoint as /api/v1/status/.
router.include_router(status_router, prefix="/status", tags=["Status"])
