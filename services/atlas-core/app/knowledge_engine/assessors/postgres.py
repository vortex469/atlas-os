from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)
from app.knowledge_engine.assessors.base import (
    ApplicationAssessor,
)
from app.knowledge_engine.rules.authentication import (
    AuthenticationRule,
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
from app.knowledge_engine.assessors.redis import (
    RedisAssessor
)
class PostgresAssessor(ApplicationAssessor):
    """Assess PostgreSQL deployments."""

    _POSTGRES_IMAGES = {
        "postgres",
        "library/postgres",
        "docker.io/library/postgres",
    }

    def __init__(self) -> None:
        self._healthcheck_rule = HealthCheckRule(
            application_name="PostgreSQL",
            recommendation=(
                "Add a PostgreSQL health check using pg_isready."
            ),
        )

        self._storage_rule = StorageRule(
            application_name="PostgreSQL",
            target_path="/var/lib/postgresql/data",
            recommendation=(
                "Mount /var/lib/postgresql/data "
                "to persistent storage."
            ),
        )

        self._authentication_rule = AuthenticationRule(
            application_name="PostgreSQL",
            required_variables=[
                "POSTGRES_PASSWORD",
            ],
        )

        self._port_rule = PortExposureRule(
            application_name="PostgreSQL",
            container_port=5432,
            recommendation=(
                "Keep PostgreSQL on an internal network and "
                "avoid publicly exposing port 5432."
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

        for component in self.iter_matching_components(
            plan,
            self._POSTGRES_IMAGES,
        ):
            self._storage_rule.assess(
                component,
                assessment,
            )

            self._authentication_rule.assess(
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