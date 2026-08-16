"""Strict identity-bound provider-intent domain contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.provider_management import (
    PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    ProviderMonitoringExpectation,
)
from app.providers.management import (
    ProviderResourceManagementNotRegisteredError,
    provider_resource_management_registry,
)

PROVIDER_INTENT_SCHEMA_VERSION = 1
PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION = 1
PROVIDER_INTENT_STORE_SCHEMA_VERSION = 2
PROVIDER_INTENT_ID_VERSION = "provider-intent-series-v1"
PROVIDER_INTENT_REQUEST_DIGEST_VERSION = "provider-intent-request-v1"
PROVIDER_INTENT_SUPERSEDE_DIGEST_VERSION = "provider-intent-supersede-v1"
PROVIDER_INTENT_COORDINATE_MUTATION_DIGEST_VERSION = (
    "provider-intent-coordinate-mutation-v1"
)
LEGACY_POLICY_IMPORT_VERSION = "provider-intent-legacy-policy-import-v1"
LEGACY_POLICY_SOURCE_REFERENCE_VERSION = (
    "provider-intent-legacy-policy-source-reference-v1"
)
LEGACY_POLICY_SOURCE_VERSION = "atlas-policy-source-v1"
MAX_RECORD_VERSION = 2**63 - 1


class ProviderIntentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderIntentKind(StrEnum):
    MONITORING_EXPECTATION = "monitoring_expectation"


class ProviderIntentLifecycle(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    LEGACY_UNBOUND = "legacy_unbound"


class ProviderIntentProvenance(StrEnum):
    LEGACY_POLICY_IMPORT = "legacy_policy_import"
    OPERATOR = "operator"


class ProviderIntentAuditEventKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    REBOUND = "rebound"


def build_legacy_policy_source_digest(payload: dict[str, object]) -> str:
    return _canonical_digest(
        LEGACY_POLICY_SOURCE_VERSION,
        {"policy": payload, "version": LEGACY_POLICY_SOURCE_VERSION},
    )


def build_legacy_policy_source_reference(
    *,
    source_policy_digest: str,
    provider_id: str,
    resource_id: str,
    intent_kind: ProviderIntentKind,
    intent_value: ProviderIntentValue,
) -> str:
    return _canonical_digest(
        LEGACY_POLICY_SOURCE_REFERENCE_VERSION,
        {
            "intent_kind": intent_kind.value,
            "intent_value": intent_value.value,
            "provider_id": provider_id,
            "resource_id": resource_id,
            "source_policy_digest": source_policy_digest,
            "version": LEGACY_POLICY_SOURCE_REFERENCE_VERSION,
        },
    )


ProviderIntentValue = ProviderMonitoringExpectation


def _canonical_digest(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def build_provider_intent_id(
    *,
    provider_id: str,
    resource_type: str | None,
    resource_id: str,
    incarnation_fingerprint: str | None,
    intent_kind: ProviderIntentKind,
) -> str:
    """Identify one coordinate/incarnation/kind series, excluding value/version."""

    digest = _canonical_digest(
        PROVIDER_INTENT_ID_VERSION,
        {
            "incarnation_fingerprint": incarnation_fingerprint,
            "intent_kind": intent_kind.value,
            "provider_id": provider_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "version": PROVIDER_INTENT_ID_VERSION,
        },
    ).rsplit(":", 1)[1]
    return f"{PROVIDER_INTENT_ID_VERSION}:{digest}"


class ProviderIntentRecord(ProviderIntentModel):
    schema_version: Literal[1] = PROVIDER_INTENT_SCHEMA_VERSION
    intent_id: str = Field(
        pattern=r"^provider-intent-series-v1:[a-f0-9]{64}$"
    )
    record_version: int = Field(ge=1, le=MAX_RECORD_VERSION)
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_type: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    resource_id: str = Field(min_length=1, max_length=200)
    incarnation_fingerprint: str | None = Field(
        default=None,
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    )
    intent_kind: ProviderIntentKind
    intent_value: ProviderIntentValue
    lifecycle: ProviderIntentLifecycle
    provenance: ProviderIntentProvenance
    source_reference: str | None = Field(default=None, min_length=1, max_length=200)
    created_at: datetime
    updated_at: datetime
    previous_record_version: int | None = Field(
        default=None,
        ge=1,
        le=MAX_RECORD_VERSION,
    )

    @field_validator("created_at", "updated_at")
    @classmethod
    def canonical_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider intent timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("resource_id", "source_reference")
    @classmethod
    def exact_text(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise ValueError("provider intent text fields must be exact")
        return value

    @model_validator(mode="after")
    def validate_record(self) -> ProviderIntentRecord:
        if self.updated_at < self.created_at:
            raise ValueError("provider intent updated_at precedes created_at")
        expected_previous = (
            None if self.record_version == 1 else self.record_version - 1
        )
        if self.previous_record_version != expected_previous:
            raise ValueError("provider intent version chain is invalid")
        if self.lifecycle is ProviderIntentLifecycle.LEGACY_UNBOUND:
            if self.resource_type is not None or self.incarnation_fingerprint is not None:
                raise ValueError(
                    "legacy-unbound intent cannot claim resource type or incarnation"
                )
            if self.provenance is not ProviderIntentProvenance.LEGACY_POLICY_IMPORT:
                raise ValueError("legacy-unbound intent requires legacy provenance")
        else:
            if self.resource_type is None or self.incarnation_fingerprint is None:
                raise ValueError(
                    "identity-bound intent requires resource type and fingerprint"
                )
            try:
                support = provider_resource_management_registry.get(
                    self.provider_id,
                    self.resource_type,
                )
            except ProviderResourceManagementNotRegisteredError as error:
                raise ValueError("provider intent resource support is unavailable") from error
            if not (
                support.authoritative_identity_supported
                and support.provider_intent_capability_supported
            ):
                raise ValueError("resource type does not support identity-bound intent")
        expected_id = build_provider_intent_id(
            provider_id=self.provider_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            incarnation_fingerprint=self.incarnation_fingerprint,
            intent_kind=self.intent_kind,
        )
        if self.intent_id != expected_id:
            raise ValueError("provider intent series identity is invalid")
        return self


def build_provider_intent_request_digest(
    *,
    request_id: str,
    provider_id: str,
    resource_type: str,
    resource_id: str,
    incarnation_fingerprint: str,
    intent_kind: ProviderIntentKind,
    desired_value: ProviderIntentValue,
    expected_record_version: int,
) -> str:
    return _canonical_digest(
        PROVIDER_INTENT_REQUEST_DIGEST_VERSION,
        {
            "desired_value": desired_value.value,
            "expected_record_version": expected_record_version,
            "incarnation_fingerprint": incarnation_fingerprint,
            "intent_kind": intent_kind.value,
            "provider_id": provider_id,
            "request_id": request_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "version": PROVIDER_INTENT_REQUEST_DIGEST_VERSION,
        },
    )


class ProviderIntentMutationCommand(ProviderIntentModel):
    request_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    request_digest: str = Field(
        pattern=r"^provider-intent-request-v1:[a-f0-9]{64}$"
    )
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_type: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_id: str = Field(min_length=1, max_length=200)
    incarnation_fingerprint: str = Field(
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN
    )
    intent_kind: ProviderIntentKind
    desired_value: ProviderIntentValue
    expected_record_version: int = Field(ge=0, le=MAX_RECORD_VERSION)
    provenance: Literal[ProviderIntentProvenance.OPERATOR] = (
        ProviderIntentProvenance.OPERATOR
    )

    @model_validator(mode="after")
    def validate_command(self) -> ProviderIntentMutationCommand:
        try:
            support = provider_resource_management_registry.get(
                self.provider_id,
                self.resource_type,
            )
        except ProviderResourceManagementNotRegisteredError as error:
            raise ValueError("provider intent resource support is unavailable") from error
        if not (
            support.authoritative_identity_supported
            and support.provider_intent_capability_supported
        ):
            raise ValueError("resource type does not support identity-bound intent")
        expected = build_provider_intent_request_digest(
            request_id=self.request_id,
            provider_id=self.provider_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            incarnation_fingerprint=self.incarnation_fingerprint,
            intent_kind=self.intent_kind,
            desired_value=self.desired_value,
            expected_record_version=self.expected_record_version,
        )
        if self.request_digest != expected:
            raise ValueError("provider intent request digest is invalid")
        return self

    @property
    def intent_id(self) -> str:
        return build_provider_intent_id(
            provider_id=self.provider_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            incarnation_fingerprint=self.incarnation_fingerprint,
            intent_kind=self.intent_kind,
        )


def build_provider_intent_supersede_digest(
    *, request_id: str, intent_id: str, expected_record_version: int
) -> str:
    return _canonical_digest(
        PROVIDER_INTENT_SUPERSEDE_DIGEST_VERSION,
        {
            "expected_record_version": expected_record_version,
            "intent_id": intent_id,
            "request_id": request_id,
            "version": PROVIDER_INTENT_SUPERSEDE_DIGEST_VERSION,
        },
    )


class ProviderIntentSupersedeCommand(ProviderIntentModel):
    request_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    request_digest: str = Field(
        pattern=r"^provider-intent-supersede-v1:[a-f0-9]{64}$"
    )
    intent_id: str = Field(
        pattern=r"^provider-intent-series-v1:[a-f0-9]{64}$"
    )
    expected_record_version: int = Field(ge=1, le=MAX_RECORD_VERSION)

    @model_validator(mode="after")
    def validate_digest(self) -> ProviderIntentSupersedeCommand:
        expected = build_provider_intent_supersede_digest(
            request_id=self.request_id,
            intent_id=self.intent_id,
            expected_record_version=self.expected_record_version,
        )
        if self.request_digest != expected:
            raise ValueError("provider intent supersede digest is invalid")
        return self


class ProviderIntentMutationResult(ProviderIntentModel):
    outcome: Literal["created", "updated", "superseded"]
    record: ProviderIntentRecord


class ProviderIntentAuditEvent(ProviderIntentModel):
    sequence: int = Field(ge=1)
    occurred_at: datetime
    intent_id: str
    record_version: int = Field(ge=1, le=MAX_RECORD_VERSION)
    request_id: str
    request_digest: str
    event: ProviderIntentAuditEventKind

    @field_validator("occurred_at")
    @classmethod
    def canonical_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider intent audit timestamp must be timezone-aware")
        return value.astimezone(UTC)


def build_provider_intent_coordinate_mutation_digest(
    *,
    operator_id: str,
    request_id: str,
    provider_id: str,
    resource_type: str,
    resource_id: str,
    management_fingerprint: str,
    intent_kind: ProviderIntentKind,
    desired_value: ProviderIntentValue,
    expected_record_version: int,
    acknowledge_monitoring_suppression: bool,
) -> str:
    """Bind every caller-controlled P3 mutation input canonically."""

    return _canonical_digest(
        PROVIDER_INTENT_COORDINATE_MUTATION_DIGEST_VERSION,
        {
            "acknowledge_monitoring_suppression": (
                acknowledge_monitoring_suppression
            ),
            "desired_value": desired_value.value,
            "expected_record_version": expected_record_version,
            "intent_kind": intent_kind.value,
            "management_fingerprint": management_fingerprint,
            "operator_id": operator_id,
            "provider_id": provider_id,
            "request_id": request_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "version": PROVIDER_INTENT_COORDINATE_MUTATION_DIGEST_VERSION,
        },
    )


class ProviderIntentCoordinateMutationCommand(ProviderIntentModel):
    """Actor-bound P3 command with no provider or execution authority."""

    operator_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[a-zA-Z0-9._@-]+$",
    )
    request_id: str = Field(
        min_length=57,
        max_length=90,
        pattern=r"^provider-intent-mutation-[a-f0-9]{32,64}$",
    )
    provider_id: Literal["proxmox"]
    resource_type: Literal["qemu"]
    resource_id: str = Field(pattern=r"^[0-9]+$", max_length=20)
    management_fingerprint: str = Field(
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN
    )
    intent_kind: Literal[ProviderIntentKind.MONITORING_EXPECTATION] = (
        ProviderIntentKind.MONITORING_EXPECTATION
    )
    desired_value: ProviderIntentValue
    expected_record_version: int = Field(ge=0, le=MAX_RECORD_VERSION)
    acknowledge_monitoring_suppression: bool = False

    @model_validator(mode="after")
    def validate_suppression_acknowledgement(
        self,
    ) -> ProviderIntentCoordinateMutationCommand:
        ignored = self.desired_value is ProviderIntentValue.IGNORED
        if ignored != self.acknowledge_monitoring_suppression:
            raise ValueError(
                "monitoring suppression acknowledgement contradicts expectation"
            )
        return self

    @property
    def request_digest(self) -> str:
        return build_provider_intent_coordinate_mutation_digest(
            operator_id=self.operator_id,
            request_id=self.request_id,
            provider_id=self.provider_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            management_fingerprint=self.management_fingerprint,
            intent_kind=self.intent_kind,
            desired_value=self.desired_value,
            expected_record_version=self.expected_record_version,
            acknowledge_monitoring_suppression=(
                self.acknowledge_monitoring_suppression
            ),
        )

    @property
    def intent_id(self) -> str:
        return build_provider_intent_id(
            provider_id=self.provider_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            incarnation_fingerprint=self.management_fingerprint,
            intent_kind=self.intent_kind,
        )


class ProviderIntentCoordinateMutationResult(ProviderIntentModel):
    outcome: Literal["created", "updated", "rebound"]
    request_id: str = Field(
        min_length=57,
        max_length=90,
        pattern=r"^provider-intent-mutation-[a-f0-9]{32,64}$",
    )
    provider_id: Literal["proxmox"]
    resource_type: Literal["qemu"]
    resource_id: str = Field(pattern=r"^[0-9]+$", max_length=20)
    management_fingerprint: str = Field(
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN
    )
    expectation: ProviderIntentValue
    record_version: int = Field(ge=1, le=MAX_RECORD_VERSION)
    superseded_previous_incarnation: bool

    @model_validator(mode="after")
    def validate_outcome(self) -> ProviderIntentCoordinateMutationResult:
        if self.superseded_previous_incarnation != (self.outcome == "rebound"):
            raise ValueError("mutation outcome and supersession flag contradict")
        if self.outcome in {"created", "rebound"} and self.record_version != 1:
            raise ValueError("new incarnation mutation must create version one")
        return self


class ProviderIntentMutationRequest(ProviderIntentModel):
    """Bounded HTTP body; path and authenticated actor are server-owned."""

    request_id: str = Field(
        min_length=57,
        max_length=90,
        pattern=r"^provider-intent-mutation-[a-f0-9]{32,64}$",
    )
    expected_management_fingerprint: str = Field(
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN
    )
    expectation: ProviderIntentValue
    expected_record_version: int = Field(ge=0, le=MAX_RECORD_VERSION)
    acknowledge_monitoring_suppression: bool = False

    @model_validator(mode="after")
    def validate_suppression_acknowledgement(
        self,
    ) -> ProviderIntentMutationRequest:
        ignored = self.expectation is ProviderIntentValue.IGNORED
        if ignored != self.acknowledge_monitoring_suppression:
            raise ValueError(
                "monitoring suppression acknowledgement contradicts expectation"
            )
        return self


class VerifiedProviderIntentMutationTarget(ProviderIntentModel):
    """Sanitized live target proof with no provider-native identity."""

    provider_id: Literal["proxmox"]
    resource_type: Literal["qemu"]
    resource_id: str = Field(pattern=r"^[0-9]+$", max_length=20)
    management_fingerprint: str = Field(
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN
    )


class ProviderIntentDomainAuditEvent(ProviderIntentModel):
    sequence: int = Field(ge=1)
    event_id: str = Field(pattern=r"^provider-intent-audit-v1:[a-f0-9]{64}$")
    occurred_at: datetime
    operation_id: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=200)
    operator_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[a-zA-Z0-9._@-]+$",
    )
    intent_id: str = Field(pattern=r"^provider-intent-series-v1:[a-f0-9]{64}$")
    record_version: int = Field(ge=1, le=MAX_RECORD_VERSION)
    event: ProviderIntentAuditEventKind
    lifecycle: ProviderIntentLifecycle
    resulting_value: ProviderIntentValue

    @field_validator("occurred_at")
    @classmethod
    def canonical_audit_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider intent audit timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_event_lifecycle(self) -> ProviderIntentDomainAuditEvent:
        superseded = self.event is ProviderIntentAuditEventKind.SUPERSEDED
        if superseded != (self.lifecycle is ProviderIntentLifecycle.SUPERSEDED):
            raise ValueError("provider intent audit event and lifecycle contradict")
        return self
