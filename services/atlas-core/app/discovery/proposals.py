"""Immutable, advisory Discovery-to-operator proposal contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.discovery.compatibility import CompatibilityStatus
from app.discovery.models import (
    CatalogEntry,
    CatalogSourceType,
    DiscoveryCenterModel,
)

PROPOSAL_SCHEMA_VERSION = 1
PROPOSAL_FINGERPRINT_VERSION = "discovery-operator-proposal-fingerprint-v1"
SOURCE_ENTRY_FINGERPRINT_VERSION = "discovery-source-entry-fingerprint-v1"
SOURCE_STATE_FINGERPRINT_VERSION = "discovery-proposal-source-state-fingerprint-v1"
MAXIMUM_PROPOSAL_LIFETIME = timedelta(hours=1)
MAX_IDENTIFIER_LENGTH = 200
MAX_FINDING_REFERENCES = 32
MAX_EVIDENCE_REFERENCES = 64
MAX_TARGET_HINTS = 8
_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
_FINGERPRINT_PATTERN = r"^[a-z0-9-]+-v1:[a-f0-9]{64}$"


class DiscoveryProposalStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    NOT_ACTIONABLE = "not_actionable"


class DiscoveryProposalReason(StrEnum):
    COMPATIBLE = "compatible"
    COMPATIBILITY_WARNING = "compatibility_warning"
    INCOMPATIBLE = "incompatible"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    UNSUPPORTED_RESOURCE = "unsupported_resource"
    SOURCE_CHANGED = "source_changed"
    SOURCE_MISSING = "source_missing"
    EVIDENCE_CHANGED = "evidence_changed"
    EVIDENCE_MISSING = "evidence_missing"
    EXPIRED = "expired"
    NO_SUPPORTED_DESTINATION = "no_supported_destination"


class DiscoveryProposalDestinationKind(StrEnum):
    DISCOVERY_DETAIL = "discovery_detail"
    COMPATIBILITY_REVIEW = "compatibility_review"
    OPERATOR_MAINTENANCE_SELECTION = "operator_maintenance_selection"


class DiscoveryProposalIntentHint(StrEnum):
    """Closed relevance hints; membership grants no planning or execution authority."""

    RESTART_SERVICE = "restart-service"


class DiscoveryProposalDestination(DiscoveryCenterModel):
    kind: DiscoveryProposalDestinationKind


class DiscoveryProposalTargetHint(DiscoveryCenterModel):
    """Non-authoritative identifiers that a destination must resolve afresh."""

    catalog_target_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    provider_hint: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    resource_type_hint: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )

    @model_validator(mode="after")
    def require_one_hint(self) -> DiscoveryProposalTargetHint:
        if not any((self.catalog_target_id, self.provider_hint, self.resource_type_hint)):
            raise ValueError("proposal target hint requires at least one identifier")
        return self


class DiscoveryProposalProvenance(DiscoveryCenterModel):
    catalog_source_type: CatalogSourceType
    catalog_entry_id: str = Field(
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    catalog_item_id: str = Field(
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    source_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$",
    )
    source_entry_fingerprint: str | None = Field(
        default=None,
        pattern=rf"^{SOURCE_ENTRY_FINGERPRINT_VERSION}:[a-f0-9]{{64}}$",
    )

    @model_validator(mode="after")
    def require_version_or_fallback(self) -> DiscoveryProposalProvenance:
        if self.source_version is None and self.source_entry_fingerprint is None:
            raise ValueError("unversioned provenance requires a source-entry fingerprint")
        if self.source_version is not None and self.source_entry_fingerprint is not None:
            raise ValueError("versioned provenance must not also supply a fallback fingerprint")
        return self


class DiscoveryProposalCompatibility(DiscoveryCenterModel):
    target_id: str = Field(
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    target_type: str = Field(
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    status: CompatibilityStatus
    finding_ids: tuple[str, ...] = Field(max_length=MAX_FINDING_REFERENCES)
    evidence_ids: tuple[str, ...] = Field(max_length=MAX_EVIDENCE_REFERENCES)

    @field_validator("finding_ids", "evidence_ids")
    @classmethod
    def normalize_references(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(values))
        if len(normalized) != len(set(normalized)):
            raise ValueError("proposal references must be unique")
        if any(
            not value
            or len(value) > MAX_IDENTIFIER_LENGTH
            or value.strip() != value
            for value in normalized
        ):
            raise ValueError("proposal references must be bounded exact identifiers")
        return normalized


class DiscoveryOperatorProposal(DiscoveryCenterModel):
    schema_version: Literal[1] = PROPOSAL_SCHEMA_VERSION
    proposal_id: str = Field(pattern=r"^discovery-operator-proposal-[a-f0-9]{64}$")
    proposal_fingerprint: str = Field(
        pattern=rf"^{PROPOSAL_FINGERPRINT_VERSION}:[a-f0-9]{{64}}$"
    )
    source_state_fingerprint: str = Field(pattern=_FINGERPRINT_PATTERN)
    status: DiscoveryProposalStatus
    reason: DiscoveryProposalReason
    provenance: DiscoveryProposalProvenance
    source_finding_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_PATTERN,
    )
    compatibility: DiscoveryProposalCompatibility
    destination: DiscoveryProposalDestination
    intent_hint: DiscoveryProposalIntentHint | None = None
    target_hints: tuple[DiscoveryProposalTargetHint, ...] = Field(
        default=(), max_length=MAX_TARGET_HINTS
    )
    generated_at: datetime
    expires_at: datetime

    @field_validator("generated_at", "expires_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("proposal timestamps must be timezone-aware")
        if value.utcoffset() != timedelta(0):
            raise ValueError("proposal timestamps must be UTC")
        return value.astimezone(UTC)

    @field_validator("target_hints")
    @classmethod
    def require_unique_target_hints(
        cls, values: tuple[DiscoveryProposalTargetHint, ...]
    ) -> tuple[DiscoveryProposalTargetHint, ...]:
        keys = [_target_hint_payload(value) for value in values]
        if len({json.dumps(key, sort_keys=True) for key in keys}) != len(keys):
            raise ValueError("proposal target hints must be unique")
        return values

    @model_validator(mode="after")
    def validate_contract(self) -> DiscoveryOperatorProposal:
        if self.expires_at <= self.generated_at:
            raise ValueError("proposal expiry must follow generation")
        if self.expires_at - self.generated_at > MAXIMUM_PROPOSAL_LIFETIME:
            raise ValueError("proposal lifetime exceeds the maximum")
        if self.status is DiscoveryProposalStatus.EXPIRED and self.reason is not DiscoveryProposalReason.EXPIRED:
            raise ValueError("expired proposal status requires expired reason")
        expected_source_state = discovery_proposal_source_state_fingerprint(
            provenance=self.provenance,
            source_finding_id=self.source_finding_id,
            compatibility=self.compatibility,
        )
        if self.source_state_fingerprint != expected_source_state:
            raise ValueError("proposal source-state fingerprint mismatch")
        expected = discovery_operator_proposal_fingerprint(self)
        if self.proposal_fingerprint != expected:
            raise ValueError("proposal fingerprint mismatch")
        if self.proposal_id != _proposal_id(expected):
            raise ValueError("proposal id does not match proposal fingerprint")
        return self


def catalog_source_entry_fingerprint(entry: CatalogEntry) -> str:
    """Hash stable source semantics when provenance has no explicit version.

    Inputs are catalog schema; item id/type/status/version/tags/capability ids;
    structured requirements excluding network notes; relationship type, target,
    required flag, and version bounds; and provenance source type, source,
    entry id, and trust level. Display names, descriptions, URLs, aliases,
    checked times, and arbitrary metadata are intentionally excluded.
    """

    item = entry.item
    requirements = item.requirements.model_dump(mode="json")
    requirements["network"].pop("notes", None)
    payload = {
        "schema_version": entry.schema_version,
        "item": {
            "id": item.id,
            "type": item.type.value,
            "status": item.status.value,
            "version": item.version,
            "tags": sorted(item.tags),
            "capability_ids": sorted(value.id for value in item.capabilities),
            "requirements": requirements,
            "relationships": sorted(
                (
                    {
                        "type": value.type.value,
                        "target": value.target,
                        "required": value.required,
                        "minimum_version": value.minimum_version,
                        "maximum_version": value.maximum_version,
                    }
                    for value in item.relationships
                ),
                key=lambda value: (value["type"], value["target"]),
            ),
        },
        "provenance": {
            "source_type": entry.provenance.source_type.value,
            "source": entry.provenance.source,
            "entry_id": entry.provenance.entry_id,
            "trust_level": entry.provenance.trust_level.value,
        },
    }
    return _fingerprint(SOURCE_ENTRY_FINGERPRINT_VERSION, payload)


def discovery_proposal_source_state_fingerprint(
    *,
    provenance: DiscoveryProposalProvenance,
    source_finding_id: str | None,
    compatibility: DiscoveryProposalCompatibility,
) -> str:
    payload = {
        "provenance": provenance.model_dump(mode="json"),
        "source_finding_id": source_finding_id,
        "compatibility": compatibility.model_dump(mode="json"),
    }
    return _fingerprint(SOURCE_STATE_FINGERPRINT_VERSION, payload)


def discovery_operator_proposal_fingerprint(
    proposal: DiscoveryOperatorProposal,
) -> str:
    payload = {
        "schema_version": proposal.schema_version,
        "catalog_item_id": proposal.provenance.catalog_item_id,
        "provenance": proposal.provenance.model_dump(mode="json"),
        "source_finding_id": proposal.source_finding_id,
        "compatibility": proposal.compatibility.model_dump(mode="json"),
        "destination": proposal.destination.kind.value,
        "intent_hint": proposal.intent_hint.value if proposal.intent_hint else None,
        "target_hints": sorted(
            (_target_hint_payload(value) for value in proposal.target_hints),
            key=lambda value: json.dumps(value, sort_keys=True),
        ),
    }
    return _fingerprint(PROPOSAL_FINGERPRINT_VERSION, payload)


def build_discovery_operator_proposal(
    *,
    status: DiscoveryProposalStatus,
    reason: DiscoveryProposalReason,
    provenance: DiscoveryProposalProvenance,
    compatibility: DiscoveryProposalCompatibility,
    destination: DiscoveryProposalDestination,
    generated_at: datetime,
    expires_at: datetime,
    source_finding_id: str | None = None,
    intent_hint: DiscoveryProposalIntentHint | None = None,
    target_hints: tuple[DiscoveryProposalTargetHint, ...] = (),
) -> DiscoveryOperatorProposal:
    source_state = discovery_proposal_source_state_fingerprint(
        provenance=provenance,
        source_finding_id=source_finding_id,
        compatibility=compatibility,
    )
    placeholder = f"{PROPOSAL_FINGERPRINT_VERSION}:{'0' * 64}"
    proposal = DiscoveryOperatorProposal.model_construct(
        schema_version=PROPOSAL_SCHEMA_VERSION,
        proposal_id=f"discovery-operator-proposal-{'0' * 64}",
        proposal_fingerprint=placeholder,
        source_state_fingerprint=source_state,
        status=status,
        reason=reason,
        provenance=provenance,
        source_finding_id=source_finding_id,
        compatibility=compatibility,
        destination=destination,
        intent_hint=intent_hint,
        target_hints=target_hints,
        generated_at=generated_at,
        expires_at=expires_at,
    )
    fingerprint = discovery_operator_proposal_fingerprint(proposal)
    return DiscoveryOperatorProposal.model_validate(
        {
            **proposal.model_dump(),
            "proposal_id": _proposal_id(fingerprint),
            "proposal_fingerprint": fingerprint,
        }
    )


def _proposal_id(fingerprint: str) -> str:
    return f"discovery-operator-proposal-{fingerprint.rsplit(':', 1)[-1]}"


def _target_hint_payload(value: DiscoveryProposalTargetHint) -> dict[str, str | None]:
    return value.model_dump(mode="json")


def _fingerprint(version: str, payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{version}:{hashlib.sha256(canonical).hexdigest()}"
