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


class ProviderMonitoringExpectation(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    IGNORED = "ignored"


class ProviderManagementSectionDescriptor(ProviderManagementModel):
    section: ProviderManagementSection
    availability: ProviderManagementSectionAvailability
    read_only_descriptor: Literal[True] = True
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False


class ProviderResourceManagementSupport(ProviderManagementModel):
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_type: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_readable: bool
    authoritative_identity_supported: bool
    provider_intent_capability_supported: bool
    provider_intent_mutation_available: Literal[False] = False
    supported_expectations: tuple[ProviderMonitoringExpectation, ...] = ()
    operationally_requestable: Literal[False] = False
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_support_combination(self) -> "ProviderResourceManagementSupport":
        if not self.resource_readable and (
            self.authoritative_identity_supported
            or self.provider_intent_capability_supported
            or self.supported_expectations
        ):
            raise ValueError(
                "unreadable resource types cannot advertise management support."
            )
        if (
            self.provider_intent_capability_supported
            and not self.authoritative_identity_supported
        ):
            raise ValueError(
                "identity-bound provider intent requires authoritative identity support."
            )
        if bool(self.supported_expectations) != (
            self.provider_intent_capability_supported
        ):
            raise ValueError(
                "supported expectations require provider-intent capability."
            )
        if len(self.supported_expectations) != len(
            set(self.supported_expectations)
        ):
            raise ValueError("supported expectations must be unique.")
        canonical_expectations = tuple(
            expectation
            for expectation in ProviderMonitoringExpectation
            if expectation in self.supported_expectations
        )
        if self.supported_expectations != canonical_expectations:
            raise ValueError(
                "supported expectations must use canonical contract order."
            )
        return self


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
    resource_types: tuple[ProviderResourceManagementSupport, ...]
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
        resource_keys = tuple(
            (item.provider_id, item.resource_type)
            for item in self.resource_types
        )
        if len(resource_keys) != len(set(resource_keys)):
            raise ValueError("provider resource management support must be unique.")
        if any(
            item.provider_id != self.provider_id
            for item in self.resource_types
        ):
            raise ValueError(
                "resource management support must match the descriptor provider."
            )
        if resource_keys != tuple(sorted(resource_keys)):
            raise ValueError(
                "provider resource management support must be deterministically ordered."
            )
        return self
