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


class RedisAssessor(ApplicationAssessor):
    """Assess Redis deployments."""

    _REDIS_IMAGES = {
        "redis",
        "library/redis",
        "docker.io/library/redis",
    }

    def __init__(self) -> None:
        self._storage_rule = StorageRule(
            application_name="Redis",
            target_path="/data",
            recommendation=(
                "Mount /data to persistent storage."
            ),
        )

        self._healthcheck_rule = HealthCheckRule(
            application_name="Redis",
            recommendation=(
                "Add a Redis health check using redis-cli ping."
            ),
        )

        self._port_rule = PortExposureRule(
            application_name="Redis",
            container_port=6379,
            recommendation=(
                "Keep Redis on an internal network and "
                "avoid publicly exposing port 6379."
            ),
        )

    def assess(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        assessment.best_practices.extend(
            [
                "Use persistent storage.",
                "Configure health checks.",
                "Avoid public network exposure.",
            ]
        )

        assessment.findings.append(
            KnowledgeFinding(
                severity="info",
                title="Redis detected",
                description=(
                    "Atlas recognized a Redis deployment."
                ),
            )
        )

        for component in self.iter_matching_components(
            plan,
            self._REDIS_IMAGES,
        ):
            self._storage_rule.assess(
                component,
                assessment,
            )

            self._healthcheck_rule.assess(
                component,
                assessment,
            )

            self._port_rule.assess(
                component,
                assessment,
            )