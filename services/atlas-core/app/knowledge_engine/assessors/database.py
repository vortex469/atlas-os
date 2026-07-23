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


class DatabaseAssessor(ApplicationAssessor):
    """Base assessor for database services."""

    APPLICATION_NAME: str
    IMAGES: set[str]
    STORAGE_PATH: str
    CONTAINER_PORT: int

    HEALTHCHECK_RECOMMENDATION: str
    STORAGE_RECOMMENDATION: str
    PORT_RECOMMENDATION: str

    REQUIRED_ENVIRONMENT_VARIABLES: list[str] = []

    BEST_PRACTICES: list[str] = [
        "Use persistent storage.",
        "Configure health checks.",
        "Avoid public network exposure.",
    ]

    def __init__(self) -> None:
        self._storage_rule = StorageRule(
            application_name=self.APPLICATION_NAME,
            target_path=self.STORAGE_PATH,
            recommendation=self.STORAGE_RECOMMENDATION,
        )

        self._healthcheck_rule = HealthCheckRule(
            application_name=self.APPLICATION_NAME,
            recommendation=self.HEALTHCHECK_RECOMMENDATION,
        )

        self._port_rule = PortExposureRule(
            application_name=self.APPLICATION_NAME,
            container_port=self.CONTAINER_PORT,
            recommendation=self.PORT_RECOMMENDATION,
        )

        self._authentication_rule: AuthenticationRule | None = None

        if self.REQUIRED_ENVIRONMENT_VARIABLES:
            self._authentication_rule = AuthenticationRule(
                application_name=self.APPLICATION_NAME,
                required_variables=(
                    self.REQUIRED_ENVIRONMENT_VARIABLES
                ),
            )

    def assess(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        assessment.best_practices.extend(
            self.BEST_PRACTICES
        )

        assessment.findings.append(
            KnowledgeFinding(
                severity="info",
                title=f"{self.APPLICATION_NAME} detected",
                description=(
                    f"Atlas recognized a "
                    f"{self.APPLICATION_NAME} deployment."
                ),
            )
        )

        for component in self.iter_matching_components(
            plan,
            self.IMAGES,
        ):
            self._storage_rule.assess(
                component,
                assessment,
            )

            if self._authentication_rule is not None:
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