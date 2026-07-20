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


def test_recognizes_nginx_from_catalog() -> None:
    engine = KnowledgeEngine(
        loader=KnowledgeCatalogLoader(),
        matcher=ApplicationMatcher(),
    )

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

    match = engine.recognize(plan)

    assert match is not None
    assert match.application.id == "nginx"
    assert match.application.name == "NGINX"
    assert match.confidence == 100
    assert match.matched_component_ids == ["web"]
