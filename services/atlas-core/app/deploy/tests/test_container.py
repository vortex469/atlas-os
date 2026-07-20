from app.application import DeploymentService
from app.container.deployment import (
    create_analyzer_registry,
    create_deployment_service,
    create_planning_engine,
    create_risk_engine,
)


def test_create_analyzer_registry() -> None:
    registry = create_analyzer_registry()

    assert registry.get("compose") is not None


def test_create_risk_engine() -> None:
    engine = create_risk_engine()

    assert len(engine.registered()) == 3


def test_create_planning_engine() -> None:
    planner = create_planning_engine()

    assert planner is not None


def test_create_deployment_service() -> None:
    service = create_deployment_service()

    assert isinstance(service, DeploymentService)
