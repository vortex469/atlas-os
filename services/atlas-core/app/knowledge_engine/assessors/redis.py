from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)
from app.knowledge_engine.assessors.base import (
    ApplicationAssessor,
)


class RedisAssessor(ApplicationAssessor):
    """Assess Redis deployments."""

    def assess(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        assessment.best_practices.extend(
            [
                "Restrict network exposure.",
                "Enable authentication when appropriate.",
                "Configure health checks.",
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