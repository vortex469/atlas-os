from app.deploy.components import ApplicationComponent
from app.deploy.enums import (
    ComponentKind,
    DeploymentSource,
)
from app.deploy.plan import DeploymentPlan
from app.knowledge_engine import (
    ApplicationDefinition,
    ApplicationMatcher,
)


def test_matches_nginx_by_image() -> None:
    plan = DeploymentPlan(
        id="nginx-demo",
        name="nginx-demo",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="web",
                name="Web",
                kind=ComponentKind.SERVICE,
                image="nginx:latest",
            )
        ],
    )

    application = ApplicationDefinition(
        id="nginx",
        name="NGINX",
        category="Web Server",
        description="Web server.",
        images=["nginx"],
    )

    match = ApplicationMatcher().match(
        plan,
        [application],
    )

    assert match is not None
    assert match.application.id == "nginx"
    assert match.confidence == 100
    assert match.matched_component_ids == ["web"]


def test_returns_none_when_nothing_matches() -> None:
    plan = DeploymentPlan(
        id="unknown",
        name="unknown",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="database",
                name="Database",
                kind=ComponentKind.SERVICE,
                image="postgres:latest",
            )
        ],
    )

    application = ApplicationDefinition(
        id="nginx",
        name="NGINX",
        category="Web Server",
        description="Web server.",
        images=["nginx"],
    )

    match = ApplicationMatcher().match(
        plan,
        [application],
    )

    assert match is None
