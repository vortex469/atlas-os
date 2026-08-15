"""Strict sanitized contracts for read-only provider management."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN = (
    r"^provider-management-fingerprint-v1:[a-f0-9]{64}$"
)


class ProviderManagementModel(BaseModel):
    """Base contract that rejects extension and mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderManagementSection(StrEnum):
    CONNECTION = "connection"
    DISCOVERY = "discovery"
    RESOURCES = "resources"
    MONITORING = "monitoring"
    DIAGNOSTICS = "diagnostics"
    ACTIONS = "actions"


class ProviderManagementSectionAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ManagedResourceIdentityAssurance(StrEnum):
    AUTHORITATIVE = "authoritative"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class ProviderManagementSectionDescriptor(ProviderManagementModel):
    section: ProviderManagementSection
    availability: ProviderManagementSectionAvailability
    read_only_descriptor: Literal[True] = True
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False


class ManagedResourceProjection(ProviderManagementModel):
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    current_state: str = Field(min_length=1)
    missing: bool = False
    identity_assurance: ManagedResourceIdentityAssurance
    management_fingerprint: str | None = Field(
        default=None,
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    )
    operationally_requestable: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_identity_assurance(self) -> "ManagedResourceProjection":
        authoritative = (
            self.identity_assurance
            is ManagedResourceIdentityAssurance.AUTHORITATIVE
        )
        if authoritative != (self.management_fingerprint is not None):
            raise ValueError(
                "only authoritative identity may have a management fingerprint."
            )
        return self


class ProviderManagementDescriptor(ProviderManagementModel):
    schema_version: Literal["provider-management-v1"] = "provider-management-v1"
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    provider_name: str = Field(min_length=1)
    sections: tuple[ProviderManagementSectionDescriptor, ...]
    resources: tuple[ManagedResourceProjection, ...]
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_closed_sections(self) -> "ProviderManagementDescriptor":
        sections = tuple(item.section for item in self.sections)
        if len(sections) != len(set(sections)):
            raise ValueError("provider management sections must be unique.")
        if set(sections) != set(ProviderManagementSection):
            raise ValueError("provider management sections must be complete.")
        return self
