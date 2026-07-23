from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)
from app.knowledge_engine.assessors.base import (
    ApplicationAssessor,
)
from app.knowledge_engine.rules.healthcheck import (
    HealthCheckRule,
)
from app.knowledge_engine.rules.port_exposure import (
    PortExposureRule,
)
from app.knowledge_engine.rules.storage import (
    StorageRule,
)
from app.knowledge_engine.assessors.database import (
    DatabaseAssessor,
)

class RedisAssessor(DatabaseAssessor):
    """Assess Redis deployments."""

    _REDIS_IMAGES = {
        "redis",
        "library/redis",
        "docker.io/library/redis",
    }

    APPLICATION_NAME = "Redis"

    IMAGES = {
        "redis",
        "library/redis",
        "docker.io/library/redis",
    }

    STORAGE_PATH = "/data"

    CONTAINER_PORT = 6379

    HEALTHCHECK_RECOMMENDATION = (
        "Add a Redis health check using redis-cli ping."
    )

    STORAGE_RECOMMENDATION = (
        "Mount /data to persistent storage."
    )

    PORT_RECOMMENDATION = (
        "Keep Redis on an internal network and "
        "avoid publicly exposing port 6379."
    )