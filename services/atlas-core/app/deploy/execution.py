from typing import Any

from pydantic import BaseModel, Field

from app.deploy.enums import ExecutionStepStatus


class ExecutionStep(BaseModel):
    """A single provider action proposed by a deployment plan."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    description: str = ""
    provider_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    action_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    destructive: bool = False
    status: ExecutionStepStatus = ExecutionStepStatus.PENDING
