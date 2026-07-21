import pytest

from app.deploy.components import ApplicationComponent
from app.deploy.enums import (
    ComponentKind,
    DeploymentSource,
)
from app.deploy.plan import DeploymentPlan
from app.knowledge_engine import (
    ApplicationMatcher,
    KnowledgeCatalogLoader,
    KnowledgeEngine,
)


def create_knowledge_engine() -> KnowledgeEngine:
    return KnowledgeEngine(
        loader=KnowledgeCatalogLoader(),
        matcher=ApplicationMatcher(),
    )


@pytest.mark.parametrize(
    ("image", "expected_id", "expected_name"),
    [
        ("nginx:latest", "nginx", "NGINX"),
        ("postgres:16", "postgres", "PostgreSQL"),
        ("redis:7", "redis", "Redis"),
        (
            "ghcr.io/home-assistant/home-assistant:stable",
            "homeassistant",
            "Home Assistant",
        ),
        ("traefik:v3.0", "traefik", "Traefik"),
        ("caddy:2", "caddy", "Caddy"),
    ],
)
def test_recognizes_catalog_applications(
    image: str,
    expected_id: str,
    expected_name: str,
) -> None:
    engine = create_knowledge_engine()

    plan = DeploymentPlan(
        id=f"{expected_id}-demo",
        name=f"{expected_id}-demo",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="service",
                name="Service",
                kind=ComponentKind.SERVICE,
                image=image,
            )
        ],
    )

    match = engine.recognize(plan)

    assert match is not None
    assert match.application.id == expected_id
    assert match.application.name == expected_name
    assert match.confidence == 100
    assert match.matched_component_ids == ["service"]


def test_loads_postgres_operational_metadata() -> None:
    engine = create_knowledge_engine()

    plan = DeploymentPlan(
        id="postgres-demo",
        name="postgres-demo",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="database",
                name="Database",
                kind=ComponentKind.SERVICE,
                image="postgres:16",
            )
        ],
    )

    match = engine.recognize(plan)

    assert match is not None
    assert match.application.id == "postgres"
    assert match.application.recommended_ports == [5432]

    assert "/var/lib/postgresql/data" in (
        match.application.persistent_paths
    )

    assert "POSTGRES_PASSWORD" in (
        match.application.environment_variables
    )

    password = match.application.environment_variables[
        "POSTGRES_PASSWORD"
    ]

    assert password.required is True

def test_assesses_postgres_deployment() -> None:
    engine = create_knowledge_engine()

    plan = DeploymentPlan(
        id="postgres-demo",
        name="postgres-demo",
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

    assessment = engine.assess(plan)

    assert assessment.recognition is not None
    assert assessment.recognition.application.id == "postgres"
    assert len(assessment.findings) == 1
    assert len(assessment.recommendations) == 1
    assert len(assessment.best_practices) == 3