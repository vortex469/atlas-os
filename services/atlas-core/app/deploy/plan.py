from pydantic import BaseModel, Field, model_validator

from app.deploy.components import ApplicationComponent
from app.deploy.enums import DeploymentRisk, DeploymentSource
from app.deploy.execution import ExecutionStep
from app.deploy.recommendations import (
    DeploymentWarning,
    Recommendation,
)
from app.deploy.resources import ResourceEstimate


class DeploymentPlan(BaseModel):
    """Provider-independent plan describing an application deployment."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    name: str = Field(min_length=1)
    description: str = ""
    source: DeploymentSource
    source_reference: str | None = None
    components: list[ApplicationComponent] = Field(
        default_factory=list,
    )
    estimated_resources: ResourceEstimate = Field(
        default_factory=ResourceEstimate,
    )
    recommendations: list[Recommendation] = Field(
        default_factory=list,
    )
    warnings: list[DeploymentWarning] = Field(
        default_factory=list,
    )
    execution_steps: list[ExecutionStep] = Field(
        default_factory=list,
    )
    risk: DeploymentRisk = DeploymentRisk.LOW
    requires_approval: bool = True

    @model_validator(mode="after")
    def validate_plan(self) -> "DeploymentPlan":
        component_ids = [
            component.id
            for component in self.components
        ]

        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component IDs must be unique")

        step_ids = [
            step.id
            for step in self.execution_steps
        ]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError("execution step IDs must be unique")

        step_orders = [
            step.order
            for step in self.execution_steps
        ]

        if len(step_orders) != len(set(step_orders)):
            raise ValueError("execution step order values must be unique")

        return self

    @property
    def blocking_warnings(self) -> list[DeploymentWarning]:
        """Return warnings that prevent execution."""

        return [
            warning
            for warning in self.warnings
            if warning.blocking
        ]

    @property
    def executable(self) -> bool:
        """Return whether the plan may proceed to approval."""

        return not self.blocking_warnings
