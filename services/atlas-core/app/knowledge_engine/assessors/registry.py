from __future__ import annotations

from app.knowledge_engine.assessors.base import (
    ApplicationAssessor,
)
from app.knowledge_engine.assessors.postgres import (
    PostgresAssessor,
)
from app.knowledge_engine.assessors.redis import (
    RedisAssessor,
)
from app.knowledge_engine.assessors.mssql import (
    MSSQLAssessor,
)
class AssessorRegistry:
    """Registry for application-specific assessors."""

    def __init__(self) -> None:
        self._assessors = {
            "postgres": PostgresAssessor(),
            "redis": RedisAssessor(),
            "mssql": MSSQLAssessor(),
        }
    def get(
        self,
        application_id: str,
    ) -> ApplicationAssessor | None:
        return self._assessors.get(application_id)
