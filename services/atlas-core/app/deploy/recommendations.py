from pydantic import BaseModel, Field

from app.deploy.enums import RecommendationSeverity


class Recommendation(BaseModel):
    """An improvement suggested by the planning engine."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    severity: RecommendationSeverity
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class DeploymentWarning(BaseModel):
    """A risk, concern, or unsafe configuration found in a plan."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    severity: RecommendationSeverity
    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    blocking: bool = False
