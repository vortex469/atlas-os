from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    field_serializer,
    field_validator,
    model_validator,
)

ProviderConnectionFieldKind = Literal[
    "string",
    "host",
    "url",
    "port",
    "boolean",
    "select",
    "secret",
    "path",
]
ProviderConnectionSecretState = Literal["configured", "missing"]
ProviderConnectionTestStatus = Literal["success", "failure", "degraded"]


class ProviderConnectionFieldOption(BaseModel):
    """Provider-advertised option for a connection field."""

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""


class ProviderConnectionField(BaseModel):
    """Sanitized public representation of one provider connection field."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: ProviderConnectionFieldKind
    required: bool = False
    editable: bool = True
    secret: bool = False
    current_value: str | int | bool | None = None
    secret_state: ProviderConnectionSecretState | None = None
    source: str | None = None
    help_text: str = ""
    options: list[ProviderConnectionFieldOption] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)

    @field_validator("options")
    @classmethod
    def validate_unique_option_values(
        cls,
        values: list[ProviderConnectionFieldOption],
    ) -> list[ProviderConnectionFieldOption]:
        option_values = [option.value for option in values]
        if len(option_values) != len(set(option_values)):
            raise ValueError("connection field option values must be unique.")
        return values

    @model_validator(mode="after")
    def validate_secret_safety(self) -> ProviderConnectionField:
        if self.kind == "secret":
            self.secret = True
        if self.secret:
            self.current_value = None
            if self.secret_state is None:
                self.secret_state = "missing"
        elif self.secret_state is not None:
            raise ValueError("secret_state is only valid for secret fields.")
        if self.kind == "select" and not self.options:
            raise ValueError("select connection fields must define options.")
        return self

    @field_serializer("current_value")
    def serialize_current_value(self, value: str | int | bool | None) -> str | int | bool | None:
        if self.secret:
            return None
        return value


class ProviderConnectionSchema(BaseModel):
    """Provider-neutral sanitized connection schema."""

    provider_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    fields: list[ProviderConnectionField] = Field(default_factory=list)
    editable: bool = True
    testable: bool = True
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fields")
    @classmethod
    def validate_unique_field_keys(
        cls,
        values: list[ProviderConnectionField],
    ) -> list[ProviderConnectionField]:
        field_keys = [field.key for field in values]
        if len(field_keys) != len(set(field_keys)):
            raise ValueError("connection field keys must be unique.")
        return values


class TestProviderConnectionRequest(BaseModel):
    """Request to validate provider connection values without persisting them."""

    values: dict[str, Any] = Field(default_factory=dict)
    confirmed: StrictBool = False


class TestProviderConnectionResult(BaseModel):
    """Sanitized provider connection test result."""

    provider_id: str = Field(min_length=1)
    status: ProviderConnectionTestStatus
    message: str = ""
    tested_at: datetime
    latency_ms: float | None = Field(default=None, ge=0)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class UpdateProviderConnectionRequest(BaseModel):
    """Request to persist provider connection values."""

    values: dict[str, Any] = Field(default_factory=dict)
    confirmed: StrictBool = False


class UpdateProviderConnectionResult(BaseModel):
    """Result of a provider connection update."""

    provider_id: str = Field(min_length=1)
    connection_schema: ProviderConnectionSchema
    updated_at: datetime
    message: str = ""
