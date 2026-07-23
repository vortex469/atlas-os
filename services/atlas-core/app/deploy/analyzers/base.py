from __future__ import annotations

from abc import ABC, abstractmethod

from app.deploy.analysis import AnalysisRequest, AnalysisResult


class DeploymentAnalyzer(ABC):
    """Base class for deployment analyzers."""

    source_type: str = "unknown"

    @abstractmethod
    def analyze(
        self,
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Analyze a deployment document."""

        raise NotImplementedError