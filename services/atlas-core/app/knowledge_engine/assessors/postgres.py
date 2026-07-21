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
class PostgresAssessor(ApplicationAssessor):
    """Assess PostgreSQL deployments."""

    _DATA_PATH = "/var/lib/postgresql/data"

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
        assessment.findings.append(
            KnowledgeFinding(
                severity="info",
                title="PostgreSQL detected",
                description=(
                    "Atlas recognized a PostgreSQL deployment."
                ),
            )
        )        
        self._check_persistent_storage(
            plan,
            assessment,
        )
        self._check_password(
            plan,
            assessment,
        )
        for component in plan.components:
            if component.image is None:
                continue

            normalized_image = (
                component.image.strip()
                .lower()
                .split("@", 1)[0]
            )

            if ":" in normalized_image.rsplit("/", 1)[-1]:
                normalized_image = normalized_image.rsplit(":", 1)[0]

            if normalized_image not in {
                "postgres",
                "library/postgres",
                "docker.io/library/postgres",
            }:
                continue

            self._healthcheck_rule.assess(
                component,
                assessment,
            )

        self._check_port_exposure(
            plan,
            assessment,
        )

    def _check_persistent_storage(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        for component in plan.components:
            for mount in component.storage:
                if (
                    mount.target == self._DATA_PATH
                    and mount.persistent
                ):
                    return

        assessment.findings.append(
            KnowledgeFinding(
                severity="warning",
                title="Persistent storage missing",
                description=(
                    "PostgreSQL data is not mounted to persistent "
                    "storage at /var/lib/postgresql/data."
                ),
            )
        )

        assessment.recommendations.append(
            "Mount /var/lib/postgresql/data to persistent storage."
        )

    def _check_password(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        for component in plan.components:
            if "POSTGRES_PASSWORD" in component.environment:
                return

        assessment.findings.append(
            KnowledgeFinding(
                severity="warning",
                title="POSTGRES_PASSWORD missing",
                description=(
                    "PostgreSQL should be configured with "
                    "POSTGRES_PASSWORD."
                ),
            )
        )

        assessment.recommendations.append(
            "Configure POSTGRES_PASSWORD."
        )

        assessment.recommendations.append(
            "Add a PostgreSQL health check using pg_isready."
        )

    def _check_port_exposure(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        for component in plan.components:
            if component.image is None:
                continue

            normalized_image = (
                component.image.strip()
                .lower()
                .split("@", 1)[0]
            )

            if ":" in normalized_image.rsplit("/", 1)[-1]:
                normalized_image = normalized_image.rsplit(":", 1)[0]

            if normalized_image not in {
                "postgres",
                "library/postgres",
                "docker.io/library/postgres",
            }:
                continue

            for port in component.ports:
                if (
                    port.container_port == 5432
                    and port.public
                ):
                    assessment.findings.append(
                        KnowledgeFinding(
                            severity="warning",
                            title="PostgreSQL publicly exposed",
                            description=(
                                "PostgreSQL port 5432 is exposed "
                                "publicly."
                            ),
                        )
                    )

                    assessment.recommendations.append(
                        "Keep PostgreSQL on an internal network and "
                        "avoid publicly exposing port 5432."
                    )
                    return
                
    def __init__(self) -> None:
        self._healthcheck_rule = HealthCheckRule(
            application_name="PostgreSQL",
            recommendation=(
                "Add a PostgreSQL health check using pg_isready."
            ),
        )                