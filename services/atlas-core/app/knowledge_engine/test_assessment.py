from app.deploy.components import ApplicationComponent
from app.deploy.enums import (
    ComponentKind,
    DeploymentSource,
)
from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
)
from app.knowledge_engine.assessors.postgres import (
    PostgresAssessor,
)


def test_postgres_assessment() -> None:
    plan = DeploymentPlan(
        id="postgres",
        name="postgres",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="db",
                name="Database",
                kind=ComponentKind.SERVICE,
                image="postgres:16",
            )
        ],
    )

    assessment = KnowledgeAssessment()

    PostgresAssessor().assess(
        plan,
        assessment,
    )

    assert len(assessment.findings) == 1

    assert len(assessment.recommendations) == 1

    assert len(assessment.best_practices) == 3
