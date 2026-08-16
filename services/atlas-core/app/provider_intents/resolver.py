"""Pure identity-bound monitoring-intent resolution over sanitized snapshots."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.models.provider_intents import (
    ProviderIntentModel,
    ProviderIntentRecord,
    ProviderIntentValue,
)
from app.models.provider_management import (
    PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
)
from app.provider_intents.read_compatibility import ProviderIntentReadStore
from app.provider_intents.store import ProviderIntentStoreError


class ProviderIntentResolutionStatus(StrEnum):
    CONFIGURED = "configured"
    NEEDS_REVIEW = "needs_review"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class ProviderIntentResolutionReason(StrEnum):
    MATCHING_ACTIVE_INTENT = "matching_active_intent"
    NO_ACTIVE_INTENT = "no_active_intent"
    LEGACY_UNBOUND_EVIDENCE = "legacy_unbound_evidence"
    INCARNATION_MISMATCH = "incarnation_mismatch"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    RESOURCE_MISSING = "resource_missing"
    RESOURCE_TYPE_UNSUPPORTED = "resource_type_unsupported"
    AUTHORITY_STORE_UNAVAILABLE = "authority_store_unavailable"
    AUTHORITY_NOT_ACTIVATED = "authority_not_activated"


class ProviderIntentResolution(ProviderIntentModel):
    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1, max_length=200)
    status: ProviderIntentResolutionStatus
    reason: ProviderIntentResolutionReason
    expectation: ProviderIntentValue | None = None
    record_version: int | None = Field(default=None, ge=1)
    bound_management_fingerprint: str | None = Field(
        default=None,
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    )
    legacy_review_available: bool = False
    legacy_expectation: ProviderIntentValue | None = None
    replacement_detected: bool = False
    mutation_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_resolution(self) -> ProviderIntentResolution:
        valid_reasons = {
            ProviderIntentResolutionStatus.CONFIGURED: {
                ProviderIntentResolutionReason.MATCHING_ACTIVE_INTENT
            },
            ProviderIntentResolutionStatus.NEEDS_REVIEW: {
                ProviderIntentResolutionReason.NO_ACTIVE_INTENT,
                ProviderIntentResolutionReason.LEGACY_UNBOUND_EVIDENCE,
                ProviderIntentResolutionReason.INCARNATION_MISMATCH,
                ProviderIntentResolutionReason.IDENTITY_UNAVAILABLE,
            },
            ProviderIntentResolutionStatus.MISSING: {
                ProviderIntentResolutionReason.RESOURCE_MISSING
            },
            ProviderIntentResolutionStatus.UNSUPPORTED: {
                ProviderIntentResolutionReason.RESOURCE_TYPE_UNSUPPORTED
            },
            ProviderIntentResolutionStatus.UNAVAILABLE: {
                ProviderIntentResolutionReason.AUTHORITY_STORE_UNAVAILABLE,
                ProviderIntentResolutionReason.AUTHORITY_NOT_ACTIVATED,
            },
        }
        if self.reason not in valid_reasons[self.status]:
            raise ValueError("provider intent resolution status and reason contradict")
        authoritative = self.status in {
            ProviderIntentResolutionStatus.CONFIGURED,
            ProviderIntentResolutionStatus.MISSING,
        }
        if authoritative != (
            self.expectation is not None and self.record_version is not None
        ):
            raise ValueError(
                "configured or missing intent requires expectation and version"
            )
        if authoritative != (self.bound_management_fingerprint is not None):
            raise ValueError(
                "configured or missing intent requires its sanitized binding"
            )
        if self.legacy_review_available != (self.legacy_expectation is not None):
            raise ValueError("legacy review flag and expectation must agree")
        if self.replacement_detected != (
            self.reason is ProviderIntentResolutionReason.INCARNATION_MISMATCH
        ):
            raise ValueError("replacement flag and reason must agree")
        return self


class ProviderIntentResolutionSet(ProviderIntentModel):
    activation: ProviderIntentActivation
    authority_available: bool
    authority_reason: ProviderIntentResolutionReason | None = None
    resources: tuple[ProviderIntentResolution, ...]

    @model_validator(mode="after")
    def validate_authority(self) -> ProviderIntentResolutionSet:
        if self.authority_available == (self.authority_reason is not None):
            raise ValueError("authority availability and reason contradict")
        if tuple(sorted(self.resources, key=_resolution_order)) != self.resources:
            raise ValueError("provider intent resolutions are not canonical")
        if self.authority_available and any(
            item.status is ProviderIntentResolutionStatus.UNAVAILABLE
            for item in self.resources
        ):
            raise ValueError("available authority cannot return unavailable resources")
        if not self.authority_available and any(
            item.status is not ProviderIntentResolutionStatus.UNAVAILABLE
            for item in self.resources
        ):
            raise ValueError("unavailable authority must fail every resource closed")
        return self


class ProviderMonitoringIntentResolver:
    """Resolve existing store evidence without provider access or mutation."""

    def __init__(
        self,
        settings: ProviderIntentSettings,
        store: ProviderIntentReadStore | None,
    ) -> None:
        self._settings = settings
        self._store = store

    def resolve(
        self,
        snapshots: tuple[ManagedResourceProjection, ...],
    ) -> ProviderIntentResolutionSet:
        ordered = tuple(
            sorted(
                (snapshot for snapshot in snapshots if not snapshot.missing),
                key=lambda item: (
                    item.provider_id,
                    item.resource_type,
                    item.resource_id,
                    item.management_fingerprint or "",
                ),
            )
        )
        if self._settings.activation is ProviderIntentActivation.NOT_ACTIVATED:
            return self._unavailable(
                ordered,
                ProviderIntentResolutionReason.AUTHORITY_NOT_ACTIVATED,
            )
        if self._store is None:
            return self._unavailable(
                ordered,
                ProviderIntentResolutionReason.AUTHORITY_STORE_UNAVAILABLE,
            )
        try:
            evidence = self._store.read_snapshot()
            active = evidence.active_identity_bound_records
            legacy_by_coordinate = {
                (record.provider_id, record.resource_id): record.intent_value
                for record in evidence.legacy_unbound_records
            }
            results = [
                self._resolve_one(snapshot, active, legacy_by_coordinate)
                for snapshot in ordered
            ]
            live_coordinates = {
                (item.provider_id, item.resource_type, item.resource_id)
                for item in ordered
            }
            results.extend(
                ProviderIntentResolution(
                    provider_id=record.provider_id,
                    resource_type=record.resource_type,
                    resource_id=record.resource_id,
                    status=ProviderIntentResolutionStatus.MISSING,
                    reason=ProviderIntentResolutionReason.RESOURCE_MISSING,
                    expectation=record.intent_value,
                    record_version=record.record_version,
                    bound_management_fingerprint=record.incarnation_fingerprint,
                )
                for record in active
                if record.resource_type == "qemu"
                and (
                    record.provider_id,
                    record.resource_type,
                    record.resource_id,
                )
                not in live_coordinates
            )
            return ProviderIntentResolutionSet(
                activation=self._settings.activation,
                authority_available=True,
                resources=tuple(sorted(results, key=_resolution_order)),
            )
        except ProviderIntentStoreError:
            return self._unavailable(
                ordered,
                ProviderIntentResolutionReason.AUTHORITY_STORE_UNAVAILABLE,
            )

    def _resolve_one(
        self,
        snapshot: ManagedResourceProjection,
        active: tuple[ProviderIntentRecord, ...],
        legacy_by_coordinate: dict[tuple[str, str], ProviderIntentValue],
    ) -> ProviderIntentResolution:
        legacy_expectation = legacy_by_coordinate.get(
            (snapshot.provider_id, snapshot.resource_id)
        )
        legacy_fields = {
            "legacy_review_available": legacy_expectation is not None,
            "legacy_expectation": legacy_expectation,
        }
        if snapshot.provider_id != "proxmox" or snapshot.resource_type != "qemu":
            return ProviderIntentResolution(
                provider_id=snapshot.provider_id,
                resource_type=snapshot.resource_type,
                resource_id=snapshot.resource_id,
                status=ProviderIntentResolutionStatus.UNSUPPORTED,
                reason=ProviderIntentResolutionReason.RESOURCE_TYPE_UNSUPPORTED,
                **legacy_fields,
            )
        if (
            snapshot.identity_assurance
            is not ManagedResourceIdentityAssurance.AUTHORITATIVE
            or snapshot.management_fingerprint is None
        ):
            return ProviderIntentResolution(
                provider_id=snapshot.provider_id,
                resource_type=snapshot.resource_type,
                resource_id=snapshot.resource_id,
                status=ProviderIntentResolutionStatus.NEEDS_REVIEW,
                reason=ProviderIntentResolutionReason.IDENTITY_UNAVAILABLE,
                **legacy_fields,
            )
        coordinate = tuple(
            record
            for record in active
            if record.provider_id == snapshot.provider_id
            and record.resource_type == snapshot.resource_type
            and record.resource_id == snapshot.resource_id
        )
        matching = tuple(
            record
            for record in coordinate
            if record.incarnation_fingerprint == snapshot.management_fingerprint
        )
        if matching:
            record = matching[0]
            return ProviderIntentResolution(
                provider_id=snapshot.provider_id,
                resource_type=snapshot.resource_type,
                resource_id=snapshot.resource_id,
                status=ProviderIntentResolutionStatus.CONFIGURED,
                reason=ProviderIntentResolutionReason.MATCHING_ACTIVE_INTENT,
                expectation=record.intent_value,
                record_version=record.record_version,
                bound_management_fingerprint=record.incarnation_fingerprint,
                **legacy_fields,
            )
        if coordinate:
            return ProviderIntentResolution(
                provider_id=snapshot.provider_id,
                resource_type=snapshot.resource_type,
                resource_id=snapshot.resource_id,
                status=ProviderIntentResolutionStatus.NEEDS_REVIEW,
                reason=ProviderIntentResolutionReason.INCARNATION_MISMATCH,
                replacement_detected=True,
                **legacy_fields,
            )
        return ProviderIntentResolution(
            provider_id=snapshot.provider_id,
            resource_type=snapshot.resource_type,
            resource_id=snapshot.resource_id,
            status=ProviderIntentResolutionStatus.NEEDS_REVIEW,
            reason=(
                ProviderIntentResolutionReason.LEGACY_UNBOUND_EVIDENCE
                if legacy_expectation is not None
                else ProviderIntentResolutionReason.NO_ACTIVE_INTENT
            ),
            **legacy_fields,
        )

    def _unavailable(
        self,
        snapshots: tuple[ManagedResourceProjection, ...],
        reason: ProviderIntentResolutionReason,
    ) -> ProviderIntentResolutionSet:
        return ProviderIntentResolutionSet(
            activation=self._settings.activation,
            authority_available=False,
            authority_reason=reason,
            resources=tuple(
                ProviderIntentResolution(
                    provider_id=item.provider_id,
                    resource_type=item.resource_type,
                    resource_id=item.resource_id,
                    status=ProviderIntentResolutionStatus.UNAVAILABLE,
                    reason=reason,
                )
                for item in snapshots
            ),
        )


def _resolution_order(value: ProviderIntentResolution) -> tuple[str, ...]:
    return (
        value.provider_id,
        value.resource_type,
        value.resource_id,
        value.bound_management_fingerprint or "",
        value.status.value,
    )
