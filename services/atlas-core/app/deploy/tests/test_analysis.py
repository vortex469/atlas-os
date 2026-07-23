from app.deploy.analysis import (
    AnalysisRequest,
    AnalysisResult,
    Diagnostic,
)
from app.deploy.enums import (
    DeploymentSource,
    RecommendationSeverity,
)
from app.deploy.plan import DeploymentPlan


def test_analysis_request() -> None:
    request = AnalysisRequest(
        source=DeploymentSource.COMPOSE,
        document={
            "services": {},
        },
    )

    assert request.source == DeploymentSource.COMPOSE
    assert request.document["services"] == {}


def test_diagnostic() -> None:
    diagnostic = Diagnostic(
        code="HOST_NETWORK",
        severity=RecommendationSeverity.WARNING,
        message="Host networking detected.",
    )

    assert diagnostic.code == "HOST_NETWORK"


def test_analysis_result() -> None:
    plan = DeploymentPlan(
        id="test",
        name="Test",
        source=DeploymentSource.COMPOSE,
    )

    result = AnalysisResult(
        analyzer="compose",
        plan=plan,
    )

    assert result.analyzer == "compose"
    assert result.plan.id == "test"
    assert result.diagnostics == []