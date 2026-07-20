from app.deploy.analysis import AnalysisRequest
from app.application.deployment_service import DeploymentService
from app.deploy.analyzers import (
    AnalyzerRegistry,
    ComposeAnalyzer,
)
from app.deploy.enums import DeploymentSource
from app.deploy.risk import (
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

def test_complete_analysis_pipeline() -> None:
    registry = AnalyzerRegistry()
    registry.register(ComposeAnalyzer())

    risk = RiskEngine(
        rules=[
            PrivilegedContainerRule(),
        ]
    )

    planner = PlanningEngine()

    service = DeploymentService(
        analyzer_registry=registry,
        recognizer=ApplicationRecognizer(
            knowledge_engine=KnowledgeEngine(
                loader=KnowledgeCatalogLoader(),
                matcher=ApplicationMatcher(),
            ),
        ),
        risk_engine=risk,
        planner=planner,
    )

    request = AnalysisRequest(
        source=DeploymentSource.COMPOSE,
        document={
            "services": {
                "web": {
                    "image": "nginx",
                }
            }
        },
    )

    result = service.analyze(request)

    assert result.analysis.plan.name == "Compose Deployment"
    assert result.analysis.recognition.application_id == "nginx"
    assert result.analysis.recognition.confidence == 100
    assert len(result.planning.proposal.steps) > 0