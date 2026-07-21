from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)
from app.knowledge_engine.assessors.base import (
    ApplicationAssessor,
)


class PostgresAssessor(ApplicationAssessor):
    """Assess PostgreSQL deployments."""

    def assess(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        assessment.best_practices.extend(
            [
                "Use persistent storage.",
                "Enable regular backups.",
                "Configure health checks.",
            ]
        )

        assessment.recommendations.append(
            "Use POSTGRES_PASSWORD for production deployments."
        )

        assessment.findings.append(
            KnowledgeFinding(
                severity="info",
                title="PostgreSQL detected",
                description=(
                    "Atlas recognized a PostgreSQL deployment."
                ),
            )
        )