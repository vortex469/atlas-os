from __future__ import annotations

from app.application.models import DeploymentAnalysis
from app.deploy.analysis import AnalysisRequest
from app.deploy.analyzers import AnalyzerRegistry
from app.deploy.recognition import ApplicationRecognizer
from app.deploy.risk import RiskEngine
from app.planning import (
    PlanningEngine,
    PlanningRequest,
)


class DeploymentService:
    """Coordinate deployment analysis and planning."""

    def __init__(
        self,
        *,
        analyzer_registry: AnalyzerRegistry,
        recognizer: ApplicationRecognizer,
        risk_engine: RiskEngine,
        planner: PlanningEngine,
    ) -> None:
        self._registry = analyzer_registry
        self._recognizer = recognizer
        self._risk_engine = risk_engine
        self._planner = planner

    def analyze(
        self,
        request: AnalysisRequest,
    ) -> DeploymentAnalysis:
        """Analyze a deployment and generate a proposal."""

        analyzer = self._registry.get(request.source.value)
        analysis = analyzer.analyze(request)

        analysis.recognition = self._recognizer.recognize(
            analysis.plan
        )

        diagnostics = self._risk_engine.evaluate(
            analysis.plan
        )
        analysis.diagnostics.extend(diagnostics)

        planning = self._planner.plan(
            PlanningRequest(
                deployment=analysis.plan,
                risk=analysis.plan.risk,
            )
        )

        return DeploymentAnalysis(
            analysis=analysis,
            planning=planning,
        )