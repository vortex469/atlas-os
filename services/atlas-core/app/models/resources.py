from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ResourceExpectationState = Literal[
    "needs_review",
    "configured",
    "ignored",
    "unsupported",
    "unavailable",
]


class ResourceIntentAuthority(StrEnum):
    LEGACY_POLICY = "legacy_policy"
    PROVIDER_INTENT = "provider_intent"


class ResourceIntentReason(StrEnum):
    LEGACY_POLICY_MATCH = "legacy_policy_match"
    NO_LEGACY_POLICY = "no_legacy_policy"
    MATCHING_ACTIVE_INTENT = "matching_active_intent"
    NO_ACTIVE_INTENT = "no_active_intent"
    LEGACY_UNBOUND_EVIDENCE = "legacy_unbound_evidence"
    INCARNATION_MISMATCH = "incarnation_mismatch"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    RESOURCE_MISSING = "resource_missing"
    RESOURCE_TYPE_UNSUPPORTED = "resource_type_unsupported"
    AUTHORITY_STORE_UNAVAILABLE = "authority_store_unavailable"


class ProviderResourceIdentity(BaseModel):
    """Provider-issued identity that distinguishes resource replacement."""

    model_config = ConfigDict(frozen=True)

    token: str = Field(min_length=1)
    token_version: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    )

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("identity token must not have surrounding whitespace.")
        if value.casefold() in {"*", "all", "ambiguous", "unknown"}:
            raise ValueError("identity token must identify exactly one resource.")
        return value


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
    authority: ResourceIntentAuthority = ResourceIntentAuthority.LEGACY_POLICY
    reason: ResourceIntentReason = ResourceIntentReason.NO_LEGACY_POLICY
    record_version: int | None = Field(default=None, ge=1)
    legacy_review_available: bool = False
    legacy_expectation: str | None = None
    replacement_detected: bool = False
    mutation_available: Literal[False] = False
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
        if (
            "reason" not in self.model_fields_set
            and self.authority is ResourceIntentAuthority.LEGACY_POLICY
            and self.state in {"configured", "ignored"}
        ):
            self.reason = ResourceIntentReason.LEGACY_POLICY_MATCH
        if self.state in {"needs_review", "unsupported", "unavailable"} and (
            self.value is not None
        ):
            raise ValueError(
                "non-authoritative expectations must not persist a value.",
            )
        if self.state in {"configured", "ignored"} and self.value is None:
            raise ValueError(
                "configured expectations must include a value.",
            )
        authoritative = self.authority is ResourceIntentAuthority.PROVIDER_INTENT
        configured = self.state in {"configured", "ignored"}
        if (self.record_version is not None) != (authoritative and configured):
            raise ValueError(
                "only configured Provider Intent expectations have a record version."
            )
        if self.legacy_review_available != (self.legacy_expectation is not None):
            raise ValueError(
                "legacy review availability and legacy expectation must agree."
            )
        if self.replacement_detected != (
            self.reason is ResourceIntentReason.INCARNATION_MISMATCH
        ):
            raise ValueError("replacement detection and reason must agree.")
        valid_states = {
            ResourceIntentAuthority.LEGACY_POLICY: {
                "configured": {ResourceIntentReason.LEGACY_POLICY_MATCH},
                "ignored": {ResourceIntentReason.LEGACY_POLICY_MATCH},
                "needs_review": {ResourceIntentReason.NO_LEGACY_POLICY},
            },
            ResourceIntentAuthority.PROVIDER_INTENT: {
                "configured": {
                    ResourceIntentReason.MATCHING_ACTIVE_INTENT,
                    ResourceIntentReason.RESOURCE_MISSING,
                },
                "ignored": {ResourceIntentReason.MATCHING_ACTIVE_INTENT},
                "needs_review": {
                    ResourceIntentReason.NO_ACTIVE_INTENT,
                    ResourceIntentReason.LEGACY_UNBOUND_EVIDENCE,
                    ResourceIntentReason.INCARNATION_MISMATCH,
                    ResourceIntentReason.IDENTITY_UNAVAILABLE,
                },
                "unsupported": {
                    ResourceIntentReason.RESOURCE_TYPE_UNSUPPORTED
                },
                "unavailable": {
                    ResourceIntentReason.AUTHORITY_STORE_UNAVAILABLE
                },
            },
        }
        if self.reason not in valid_states[self.authority].get(self.state, set()):
            raise ValueError(
                "monitoring intent authority, state, and reason contradict."
            )
        return self


class ProviderResource(BaseModel):
    """Provider-neutral representation of a discovered resource."""

    provider_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    current_state: str = Field(min_length=1)
    identity: ProviderResourceIdentity | None = None
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
    intent_authority: ResourceIntentAuthority = ResourceIntentAuthority.LEGACY_POLICY
    intent_authority_status: Literal["available", "unavailable"] = "available"


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
