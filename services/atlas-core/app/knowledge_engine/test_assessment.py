from app.deploy.components import (
    ApplicationComponent,
    StorageMount,
)
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
from app.deploy.components import (
    ApplicationComponent,
    HealthCheck,
    StorageMount,
)
from app.deploy.components import (
    ApplicationComponent,
    HealthCheck,
    PortBinding,
    StorageMount,
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

    finding_titles = {
        finding.title
        for finding in assessment.findings
    }

    assert "PostgreSQL detected" in finding_titles
    assert "Persistent storage missing" in finding_titles

    assert (
        "Mount /var/lib/postgresql/data to persistent storage."
        in assessment.recommendations
    )

    assert len(assessment.best_practices) == 3


def test_postgres_without_storage_generates_warning() -> None:
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

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "Persistent storage missing" in warning_titles


def test_postgres_with_persistent_data_storage_has_no_warning() -> None:
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
                storage=[
                    StorageMount(
                        source="postgres-data",
                        target="/var/lib/postgresql/data",
                        persistent=True,
                    )
                ],
            )
        ],
    )

    assessment = KnowledgeAssessment()

    PostgresAssessor().assess(
        plan,
        assessment,
    )

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "Persistent storage missing" not in warning_titles

def test_postgres_without_password_generates_warning() -> None:
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
                storage=[
                    StorageMount(
                        source="postgres-data",
                        target="/var/lib/postgresql/data",
                    )
                ],
            )
        ],
    )

    assessment = KnowledgeAssessment()

    PostgresAssessor().assess(
        plan,
        assessment,
    )

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "POSTGRES_PASSWORD missing" in warning_titles

def test_postgres_with_password_has_no_password_warning() -> None:
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
                storage=[
                    StorageMount(
                        source="postgres-data",
                        target="/var/lib/postgresql/data",
                    )
                ],
                environment={
                    "POSTGRES_PASSWORD": "secret",
                },
            )
        ],
    )

    assessment = KnowledgeAssessment()

    PostgresAssessor().assess(
        plan,
        assessment,
    )

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "POSTGRES_PASSWORD missing" not in warning_titles

def test_postgres_without_healthcheck_generates_warning() -> None:
    plan = DeploymentPlan(
        id="postgres",
        name="postgres",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="db",
                name="Database",
                image="postgres:16",
                environment={
                    "POSTGRES_PASSWORD": "secret",
                },
                storage=[
                    StorageMount(
                        source="postgres-data",
                        target="/var/lib/postgresql/data",
                    )
                ],
            )
        ],
    )

    assessment = KnowledgeAssessment()
    PostgresAssessor().assess(plan, assessment)

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "Health check missing" in warning_titles


def test_postgres_with_healthcheck_has_no_health_warning() -> None:
    plan = DeploymentPlan(
        id="postgres",
        name="postgres",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="db",
                name="Database",
                image="postgres:16",
                environment={
                    "POSTGRES_PASSWORD": "secret",
                },
                storage=[
                    StorageMount(
                        source="postgres-data",
                        target="/var/lib/postgresql/data",
                    )
                ],
                healthcheck=HealthCheck(
                    test=[
                        "CMD-SHELL",
                        "pg_isready -U postgres",
                    ],
                ),
            )
        ],
    )

    assessment = KnowledgeAssessment()
    PostgresAssessor().assess(plan, assessment)

    warning_titles = {
        finding.title
        for finding in assessment.findings
        if finding.severity == "warning"
    }

    assert "Health check missing" not in warning_titles

def test_public_postgres_port_generates_warning() -> None:
    plan = DeploymentPlan(
        id="postgres",
        name="postgres",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="db",
                name="Database",
                image="postgres:16",
                ports=[
                    PortBinding(
                        container_port=5432,
                        host_port=5432,
                        public=True,
                    )
                ],
            )
        ],
    )

    assessment = KnowledgeAssessment()
    PostgresAssessor().assess(plan, assessment)

    finding_titles = {
        finding.title
        for finding in assessment.findings
    }

    assert "PostgreSQL publicly exposed" in finding_titles


def test_private_postgres_port_has_no_exposure_warning() -> None:
    plan = DeploymentPlan(
        id="postgres",
        name="postgres",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="db",
                name="Database",
                image="postgres:16",
                ports=[
                    PortBinding(
                        container_port=5432,
                        host_port=5432,
                        public=False,
                    )
                ],
            )
        ],
    )

    assessment = KnowledgeAssessment()
    PostgresAssessor().assess(plan, assessment)

    finding_titles = {
        finding.title
        for finding in assessment.findings
    }

    assert "PostgreSQL publicly exposed" not in finding_titles