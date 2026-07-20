from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.deploy.enums import DeploymentRisk
from app.deploy.plan import DeploymentPlan


class PlanningStepKind(str, Enum):
    """High-level intent represented by a planning step."""

    PREPARE = "prepare"
    CREATE_STORAGE = "create-storage"
    DEPLOY_COMPONENT = "deploy-component"
    VALIDATE = "validate"
    REGISTER = "register"
    CLEANUP = "cleanup"
    OTHER = "other"


class PlanningStep(BaseModel):
    """A provider-independent step in a proposed plan."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    order: int = Field(ge=1)
    kind: PlanningStepKind
    title: str = Field(min_length=1)
    description: str = ""
    component_id: str | None = None
    provider_hint: str | None = None
    requires_confirmation: bool = False
    destructive: bool = False
    estimated_duration_minutes: int | None = Field(
        default=None,
        ge=0,
    )


class ProposedPlan(BaseModel):
    """A reviewable plan that has not yet been approved."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    deployment_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    steps: list[PlanningStep] = Field(default_factory=list)
    risk: DeploymentRisk = DeploymentRisk.LOW
    approval_required: bool = True
    rollback_supported: bool = False
    estimated_duration_minutes: int | None = Field(
        default=None,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_steps(self) -> "ProposedPlan":
        step_ids = [step.id for step in self.steps]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError("planning step IDs must be unique")

        step_orders = [step.order for step in self.steps]

        if len(step_orders) != len(set(step_orders)):
            raise ValueError(
                "planning step order values must be unique"
            )

        return self


class PlanningRequest(BaseModel):
    """Input used by the planning engine."""

    deployment: DeploymentPlan
    risk: DeploymentRisk | None = None


class PlanningResult(BaseModel):
    """Result produced by the planning engine."""

    planner: str
    proposal: ProposedPlan
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: float = Field(default=0.0, ge=0)