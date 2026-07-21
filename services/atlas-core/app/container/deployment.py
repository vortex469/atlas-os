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
from app.deploy.recognition import ApplicationRecognizer
from app.knowledge_engine import (
    ApplicationMatcher,
    KnowledgeCatalogLoader,
    KnowledgeEngine,
)
from app.knowledge_engine.assessors.registry import (
    AssessorRegistry,
)

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
        recognizer=create_application_recognizer(),
        risk_engine=create_risk_engine(),
        planner=create_planning_engine(),
    )

def create_application_recognizer() -> ApplicationRecognizer:
    return ApplicationRecognizer(
        knowledge_engine=create_knowledge_engine(),
    )

def create_knowledge_engine() -> KnowledgeEngine:
    return KnowledgeEngine(
        loader=KnowledgeCatalogLoader(),
        matcher=ApplicationMatcher(),
    )
def create_knowledge_engine() -> KnowledgeEngine:
    return KnowledgeEngine(
        loader=KnowledgeCatalogLoader(),
        matcher=ApplicationMatcher(),
        registry=AssessorRegistry(),
    )