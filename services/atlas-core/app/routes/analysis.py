from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application import DeploymentAnalysis
from app.container.deployment import create_deployment_service
from app.deploy.analysis import AnalysisRequest
from app.deploy.enums import DeploymentSource


router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
)


class AnalyzeDeploymentRequest(BaseModel):
    """HTTP request for deployment analysis."""

    source: DeploymentSource
    document: dict[str, Any]
    reference: str | None = None


class AnalyzeDeploymentResponse(BaseModel):
    """HTTP response containing analysis and planning results."""

    result: DeploymentAnalysis


@router.post(
    "/deployments",
    response_model=AnalyzeDeploymentResponse,
)
def analyze_deployment(
    request: AnalyzeDeploymentRequest,
) -> AnalyzeDeploymentResponse:
    service = create_deployment_service()

    result = service.analyze(
        AnalysisRequest(
            source=request.source,
            document=request.document,
            reference=request.reference,
        )
    )

    return AnalyzeDeploymentResponse(result=result)
