from __future__ import annotations

from pydantic import BaseModel, Field

from app.deploy.enums import RecommendationSeverity


class Diagnostic(BaseModel):
    """Information discovered during deployment analysis."""

    code: str = Field(
        min_length=1,
        pattern=r"^[A-Z0-9_]+$",
    )

    severity: RecommendationSeverity

    message: str

    component_id: str | None = None

    recommendation: str | None = None