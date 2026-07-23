from __future__ import annotations

from pydantic import BaseModel

from app.deploy.analysis import AnalysisResult
from app.planning import PlanningResult


class DeploymentAnalysis(BaseModel):
    """Complete result of analyzing a deployment."""

    analysis: AnalysisResult
    planning: PlanningResult