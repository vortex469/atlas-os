from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ResourceExpectationState = Literal[
    "needs_review",
    "configured",
    "ignored",
    "unsupported",
]


class ProviderExpectationOption(BaseModel):
    """Provider-advertised monitoring expectation choice."""

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    terminal: bool = False


class ProviderResourceExpectation(BaseModel):
    """Current Atlas intent for a provider resource."""

    value: str | None = None
    label: str = "Needs Review"
    state: ResourceExpectationState = "needs_review"
    allowed_values: list[ProviderExpectationOption] = Field(
        default_factory=list,
    )

    @field_validator("allowed_values")
    @classmethod
    def validate_unique_option_values(
        cls,
        values: list[ProviderExpectationOption],
    ) -> list[ProviderExpectationOption]:
        option_values = [option.value for option in values]
        if len(option_values) != len(set(option_values)):
            raise ValueError(
                "allowed expectation option values must be unique.",
            )
        return values

    @model_validator(mode="after")
    def validate_expectation_value(self) -> ProviderResourceExpectation:
        if self.state == "needs_review" and self.value is not None:
            raise ValueError(
                "needs_review expectations must not persist a value.",
            )
        if self.state != "needs_review" and self.value is None:
            raise ValueError(
                "configured expectations must include a value.",
            )
        return self


class ProviderResource(BaseModel):
    """Provider-neutral representation of a discovered resource."""

    provider_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    current_state: str = Field(min_length=1)
    expectation: ProviderResourceExpectation
    configured: bool
    missing: bool = False
    needs_review: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def derive_review_flags(self) -> ProviderResource:
        self.needs_review = self.expectation.state == "needs_review"
        if self.needs_review:
            self.configured = False
        elif self.expectation.state in {"configured", "ignored"}:
            self.configured = True
        return self


class ProviderResourceSummary(BaseModel):
    """Summary counts for a provider resource collection."""

    total: int = Field(ge=0)
    configured: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    missing: int = Field(ge=0)
    ignored: int = Field(ge=0)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_state: dict[str, int] = Field(default_factory=dict)


class ProviderResourceCollection(BaseModel):
    """Resources discovered for a provider at a point in time."""

    provider_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    refreshed_at: datetime
    resources: list[ProviderResource] = Field(default_factory=list)
    summary: ProviderResourceSummary
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateResourceExpectationRequest(BaseModel):
    """Request to change user intent for one provider resource."""

    expectation: str = Field(min_length=1)
    confirmed: bool = False


class UpdateResourceExpectationResult(BaseModel):
    """Result of a provider resource intent update."""

    provider_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    expectation: ProviderResourceExpectation
    updated_at: datetime
