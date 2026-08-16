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


class ProviderIntentReadStatus(StrEnum):
    CONFIGURED = "configured"
    NEEDS_REVIEW = "needs_review"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class ProviderIntentReadAuthority(StrEnum):
    LEGACY_POLICY = "legacy_policy"
    PROVIDER_INTENT = "provider_intent"


class ProviderIntentReadReason(StrEnum):
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


class ProviderIntentMutationReadiness(StrEnum):
    READY = "ready"
    NOT_ACTIVATED = "not_activated"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    STORE_MIGRATION_REQUIRED = "store_migration_required"
    STORE_UNAVAILABLE = "store_unavailable"
    RESOURCE_MISSING = "resource_missing"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    RESOURCE_TYPE_UNSUPPORTED = "resource_type_unsupported"


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
    intent_authority: ProviderIntentReadAuthority = (
        ProviderIntentReadAuthority.LEGACY_POLICY
    )
    intent_status: ProviderIntentReadStatus = ProviderIntentReadStatus.NEEDS_REVIEW
    intent_reason: ProviderIntentReadReason = ProviderIntentReadReason.NO_LEGACY_POLICY
    expectation: ProviderMonitoringExpectation | None = None
    record_version: int | None = Field(default=None, ge=1)
    legacy_review_available: bool = False
    legacy_expectation: ProviderMonitoringExpectation | None = None
    replacement_detected: bool = False
    mutation_available: Literal[False] = False
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
        provider_intent_configured = (
            self.intent_authority is ProviderIntentReadAuthority.PROVIDER_INTENT
            and self.intent_status
            in {ProviderIntentReadStatus.CONFIGURED, ProviderIntentReadStatus.MISSING}
        )
        if provider_intent_configured != (self.record_version is not None):
            raise ValueError(
                "configured Provider Intent state requires expectation and version."
            )
        if provider_intent_configured and self.expectation is None:
            raise ValueError(
                "configured Provider Intent state requires expectation and version."
            )
        if self.legacy_review_available != (self.legacy_expectation is not None):
            raise ValueError(
                "legacy review availability and expectation must agree."
            )
        if self.replacement_detected != (
            self.intent_reason is ProviderIntentReadReason.INCARNATION_MISMATCH
        ):
            raise ValueError("replacement detection and reason must agree.")
        valid_reasons = {
            ProviderIntentReadAuthority.LEGACY_POLICY: {
                ProviderIntentReadStatus.CONFIGURED: {
                    ProviderIntentReadReason.LEGACY_POLICY_MATCH
                },
                ProviderIntentReadStatus.MISSING: {
                    ProviderIntentReadReason.LEGACY_POLICY_MATCH
                },
                ProviderIntentReadStatus.NEEDS_REVIEW: {
                    ProviderIntentReadReason.NO_LEGACY_POLICY
                },
            },
            ProviderIntentReadAuthority.PROVIDER_INTENT: {
                ProviderIntentReadStatus.CONFIGURED: {
                    ProviderIntentReadReason.MATCHING_ACTIVE_INTENT
                },
                ProviderIntentReadStatus.MISSING: {
                    ProviderIntentReadReason.RESOURCE_MISSING
                },
                ProviderIntentReadStatus.NEEDS_REVIEW: {
                    ProviderIntentReadReason.NO_ACTIVE_INTENT,
                    ProviderIntentReadReason.LEGACY_UNBOUND_EVIDENCE,
                    ProviderIntentReadReason.INCARNATION_MISMATCH,
                    ProviderIntentReadReason.IDENTITY_UNAVAILABLE,
                },
                ProviderIntentReadStatus.UNSUPPORTED: {
                    ProviderIntentReadReason.RESOURCE_TYPE_UNSUPPORTED
                },
                ProviderIntentReadStatus.UNAVAILABLE: {
                    ProviderIntentReadReason.AUTHORITY_STORE_UNAVAILABLE
                },
            },
        }
        if self.intent_reason not in valid_reasons[self.intent_authority].get(
            self.intent_status, set()
        ):
            raise ValueError(
                "monitoring intent authority, status, and reason contradict."
            )
        if (
            self.intent_authority is ProviderIntentReadAuthority.PROVIDER_INTENT
            and self.intent_status is ProviderIntentReadStatus.CONFIGURED
            and self.identity_assurance
            is not ManagedResourceIdentityAssurance.AUTHORITATIVE
        ):
            raise ValueError(
                "configured Provider Intent requires current authoritative identity."
            )
        if (
            self.intent_status is ProviderIntentReadStatus.MISSING
            and self.identity_assurance
            is ManagedResourceIdentityAssurance.AUTHORITATIVE
        ):
            raise ValueError("missing resources cannot claim current identity.")
        return self


class ProviderManagementDescriptor(ProviderManagementModel):
    schema_version: Literal["provider-management-v2"] = "provider-management-v2"
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    provider_name: str = Field(min_length=1)
    sections: tuple[ProviderManagementSectionDescriptor, ...]
    resource_types: tuple[ProviderResourceManagementSupport, ...]
    resources: tuple[ManagedResourceProjection, ...]
    provider_intent_activation: Literal["not_activated", "activated"] = (
        "not_activated"
    )
    provider_intent_authority_status: Literal["available", "unavailable"] = (
        "available"
    )
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


class ProviderResourceManagementSupportV3(ProviderManagementModel):
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_type: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_readable: bool
    authoritative_identity_supported: bool
    provider_intent_capability_supported: bool
    provider_intent_mutation_supported: bool
    supported_expectations: tuple[ProviderMonitoringExpectation, ...] = ()
    operationally_requestable: Literal[False] = False
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_support_combination(
        self,
    ) -> "ProviderResourceManagementSupportV3":
        ProviderResourceManagementSupport(
            **self.model_dump(exclude={"provider_intent_mutation_supported"})
        )
        if self.provider_intent_mutation_supported and not (
            self.resource_readable
            and self.authoritative_identity_supported
            and self.provider_intent_capability_supported
            and self.supported_expectations
        ):
            raise ValueError("mutation support requires complete intent support.")
        if self.provider_intent_mutation_supported and (
            self.provider_id != "proxmox" or self.resource_type != "qemu"
        ):
            raise ValueError("Provider Intent mutation supports only Proxmox QEMU.")
        return self


class ManagedResourceProjectionV3(ProviderManagementModel):
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    current_state: str = Field(min_length=1)
    missing: bool
    resource_live: bool
    identity_assurance: ManagedResourceIdentityAssurance
    management_fingerprint: str | None = Field(
        default=None,
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    )
    intent_authority: ProviderIntentReadAuthority
    intent_status: ProviderIntentReadStatus
    intent_reason: ProviderIntentReadReason
    expectation: ProviderMonitoringExpectation | None = None
    record_version: int | None = Field(default=None, ge=1)
    legacy_review_available: bool
    legacy_expectation: ProviderMonitoringExpectation | None = None
    replacement_detected: bool
    provider_intent_mutation_supported: bool
    mutation_readiness: ProviderIntentMutationReadiness
    editable_in_principle: bool
    caller_can_mutate: bool
    operationally_requestable: Literal[False] = False
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_mutation_state(self) -> "ManagedResourceProjectionV3":
        ManagedResourceProjection(
            **self.model_dump(
                include=set(ManagedResourceProjection.model_fields)
            )
        )
        if self.resource_live == self.missing:
            raise ValueError("resource live and missing state must be opposites.")
        authoritative = (
            self.identity_assurance
            is ManagedResourceIdentityAssurance.AUTHORITATIVE
        )
        if authoritative != (self.management_fingerprint is not None):
            raise ValueError(
                "only authoritative identity may have a management fingerprint."
            )
        if not self.provider_intent_mutation_supported and (
            self.mutation_readiness
            is not ProviderIntentMutationReadiness.RESOURCE_TYPE_UNSUPPORTED
        ):
            raise ValueError("unsupported mutation must fail closed.")
        ready = self.mutation_readiness is ProviderIntentMutationReadiness.READY
        if self.editable_in_principle != ready:
            raise ValueError("editability in principle and readiness must agree.")
        if ready and not (
            self.provider_id == "proxmox"
            and self.resource_type == "qemu"
            and self.provider_intent_mutation_supported
            and self.resource_live
            and not self.missing
            and authoritative
        ):
            raise ValueError(
                "ready Provider Intent mutation requires a live authoritative "
                "supported Proxmox QEMU."
            )
        if self.caller_can_mutate and not self.editable_in_principle:
            raise ValueError("caller mutation requires a ready resource.")
        configured = self.intent_status in {
            ProviderIntentReadStatus.CONFIGURED,
            ProviderIntentReadStatus.MISSING,
        }
        if configured != (self.record_version is not None):
            raise ValueError("configured state requires a record version.")
        if self.legacy_review_available != (self.legacy_expectation is not None):
            raise ValueError("legacy review availability and value must agree.")
        if self.replacement_detected != (
            self.intent_reason is ProviderIntentReadReason.INCARNATION_MISMATCH
        ):
            raise ValueError("replacement detection and reason must agree.")
        return self


class ProviderManagementDescriptorV3(ProviderManagementModel):
    schema_version: Literal["provider-management-v3"] = "provider-management-v3"
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    provider_name: str = Field(min_length=1)
    sections: tuple[ProviderManagementSectionDescriptor, ...]
    resource_types: tuple[ProviderResourceManagementSupportV3, ...]
    resources: tuple[ManagedResourceProjectionV3, ...]
    provider_intent_activation: Literal["not_activated", "activated"]
    provider_intent_authority_status: Literal["available", "unavailable"]
    caller_has_provider_intent_update: bool
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_descriptor(self) -> "ProviderManagementDescriptorV3":
        sections = tuple(item.section for item in self.sections)
        if len(sections) != len(set(sections)) or set(sections) != set(
            ProviderManagementSection
        ):
            raise ValueError("provider management sections must be complete and unique.")
        support_keys = tuple(
            (item.provider_id, item.resource_type) for item in self.resource_types
        )
        if support_keys != tuple(sorted(set(support_keys))):
            raise ValueError("provider resource support must be unique and ordered.")
        if any(
            item.provider_id != self.provider_id
            for item in (*self.resource_types, *self.resources)
        ):
            raise ValueError("provider management projections must match provider.")
        resource_keys = tuple(
            (item.provider_id, item.resource_type, item.resource_id)
            for item in self.resources
        )
        if resource_keys != tuple(sorted(set(resource_keys))):
            raise ValueError("managed resources must be unique and ordered.")
        if any(
            item.mutation_readiness is ProviderIntentMutationReadiness.READY
            for item in self.resources
        ) and (
            self.provider_intent_activation != "activated"
            or self.provider_intent_authority_status != "available"
        ):
            raise ValueError("ready mutation requires activated available authority.")
        if any(item.caller_can_mutate for item in self.resources) and not (
            self.caller_has_provider_intent_update
        ):
            raise ValueError("caller mutation requires session-derived capability.")
        return self
