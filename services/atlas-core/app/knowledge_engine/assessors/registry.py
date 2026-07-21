from __future__ import annotations

from app.knowledge_engine.assessors.base import (
    ApplicationAssessor,
)
from app.knowledge_engine.assessors.postgres import (
    PostgresAssessor,
)
from app.knowledge_engine.assessors.redis import RedisAssessor

class AssessorRegistry:
    """Registry for application-specific assessors."""

    def __init__(self) -> None:
        self._assessors: dict[
            str,
            ApplicationAssessor,
        ] = {
            "postgres": PostgresAssessor(),
        }

    def get(
        self,
        application_id: str,
    ) -> ApplicationAssessor | None:
        return self._assessors.get(application_id)
