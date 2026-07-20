from app.application import DeploymentService
from app.deploy.analyzers import (
    AnalyzerRegistry,
    ComposeAnalyzer,
)
from app.deploy.risk import (
    DockerSocketMountRule,
    HostNetworkRule,
    PrivilegedContainerRule,
    RiskEngine,
)
from app.planning import PlanningEngine


def create_analyzer_registry() -> AnalyzerRegistry:
    registry = AnalyzerRegistry()
    registry.register(ComposeAnalyzer())
    return registry


def create_risk_engine() -> RiskEngine:
    return RiskEngine(
        rules=[
            PrivilegedContainerRule(),
            DockerSocketMountRule(),
            HostNetworkRule(),
        ]
    )


def create_planning_engine() -> PlanningEngine:
    return PlanningEngine()


def create_deployment_service() -> DeploymentService:
    return DeploymentService(
        analyzer_registry=create_analyzer_registry(),
        risk_engine=create_risk_engine(),
        planner=create_planning_engine(),
    )
