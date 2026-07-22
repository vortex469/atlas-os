from app.deploy.enums import (
    ComponentKind,
    DeploymentSource,
)
from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
)
from app.knowledge_engine.assessors.redis import (
    RedisAssessor,
)
from app.deploy.components import (
    ApplicationComponent,
    HealthCheck,
    PortBinding,
    StorageMount,
)
def test_redis_assessment() -> None:
    plan = DeploymentPlan(
        id="redis",
        name="redis",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="db",
                name="Database",
                kind=ComponentKind.SERVICE,
                image="redis:7",
            )
        ],
    )

    assessment = KnowledgeAssessment()

    RedisAssessor().assess(
        plan,
        assessment,
    )

    finding_titles = {
        finding.title
        for finding in assessment.findings
    }

    assert "Redis detected" in finding_titles
    assert "Persistent storage missing" in finding_titles

    assert (
        "Mount /data to persistent storage."
        in assessment.recommendations
    )
def test_redis_without_storage_generates_warning() -> None:
    plan = DeploymentPlan(
        id="redis",
        name="redis",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="cache",
                name="Redis",
                kind=ComponentKind.SERVICE,
                image="redis:7",
            )
        ],
    )

    assessment = KnowledgeAssessment()

    RedisAssessor().assess(
        plan,
        assessment,
    )

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "Persistent storage missing" in warning_titles


def test_redis_with_persistent_storage_has_no_warning() -> None:
    plan = DeploymentPlan(
        id="redis",
        name="redis",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="cache",
                name="Redis",
                kind=ComponentKind.SERVICE,
                image="redis:7",
                storage=[
                    StorageMount(
                        source="redis-data",
                        target="/data",
                        persistent=True,
                    )
                ],
            )
        ],
    )

    assessment = KnowledgeAssessment()

    RedisAssessor().assess(
        plan,
        assessment,
    )

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "Persistent storage missing" not in warning_titles