from __future__ import annotations

from typing import ClassVar

from app.knowledge_engine.assessors.database import (
    DatabaseAssessor,
)


class RedisAssessor(DatabaseAssessor):
    """Assess Redis deployments."""

    _REDIS_IMAGES: ClassVar[set[str]] = {
        "redis",
        "library/redis",
        "docker.io/library/redis",
    }

    APPLICATION_NAME = "Redis"

    IMAGES: ClassVar[set[str]] = {
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