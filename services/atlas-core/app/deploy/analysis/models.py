from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from app.deploy.analysis.diagnostics import Diagnostic
from app.deploy.enums import DeploymentSource
from app.deploy.plan import DeploymentPlan


class AnalysisRequest(BaseModel):
    """Input to a deployment analyzer."""

    source: DeploymentSource

    document: Mapping[str, Any]

    reference: str | None = None


class AnalysisResult(BaseModel):
    """Result produced by a deployment analyzer."""

    analyzer: str

    plan: DeploymentPlan

    diagnostics: list[Diagnostic] = Field(default_factory=list)

    elapsed_ms: float = 0.0