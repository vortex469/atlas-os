from __future__ import annotations

from typing import Any

from pydantic import Field

from app.discovery.models import (
    CATALOG_SCHEMA_VERSION,
    CatalogProvenance,
    DiscoveryCenterModel,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationship,
    DiscoveryRequirements,
)
from app.discovery.repository import DiscoveryRelationshipReference
from app.discovery.search import DiscoverySearchEvidence, DiscoverySearchResult


class DiscoveryItemResponse(DiscoveryCenterModel):
    """Public API projection of a Discovery Center item."""

    id: str
    type: DiscoveryItemType
    status: DiscoveryItemStatus
    name: str
    description: str = ""
    version: str | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    homepage_url: str | None = None
    documentation_url: str | None = None
    capabilities: tuple[str, ...] = ()
    requirements: DiscoveryRequirements = Field(default_factory=DiscoveryRequirements)
    relationships: tuple[DiscoveryRelationship, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCatalogEntryResponse(DiscoveryCenterModel):
    """Public API projection of a catalog entry."""

    schema_version: int
    item: DiscoveryItemResponse
    provenance: CatalogProvenance
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCatalogPageResponse(DiscoveryCenterModel):
    """Paginated public catalog browse response."""

    entries: tuple[DiscoveryCatalogEntryResponse, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool


class DiscoverySearchEvidenceResponse(DiscoveryCenterModel):
    """Public search evidence without internal numeric score details."""

    field: str
    value: str
    matched_text: str
    match_type: str


class DiscoverySearchResultResponse(DiscoveryCenterModel):
    """Public deterministic search result without raw ranking score."""

    item: DiscoveryItemResponse
    entry: DiscoveryCatalogEntryResponse
    evidence: tuple[DiscoverySearchEvidenceResponse, ...] = ()


class DiscoverySearchPageResponse(DiscoveryCenterModel):
    """Paginated public search response."""

    results: tuple[DiscoverySearchResultResponse, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool


class DiscoveryRelationshipReferenceResponse(DiscoveryCenterModel):
    """Public direct relationship reference."""

    source_item_id: str
    target: str
    relationship: DiscoveryRelationship
    resolved_target_item_id: str | None = None
    resolved: bool


class DiscoveryRelationshipCollectionResponse(DiscoveryCenterModel):
    """Public incoming and outgoing direct relationship response."""

    item_id: str
    incoming: tuple[DiscoveryRelationshipReferenceResponse, ...] = ()
    outgoing: tuple[DiscoveryRelationshipReferenceResponse, ...] = ()


class DiscoveryMetadataResponse(DiscoveryCenterModel):
    """Public Discovery Center status metadata."""

    catalog_loaded: bool
    entry_count: int = Field(ge=0)
    schema_version: int = CATALOG_SCHEMA_VERSION


def entry_to_response(entry) -> DiscoveryCatalogEntryResponse:
    item = entry.item
    return DiscoveryCatalogEntryResponse(
        schema_version=entry.schema_version,
        item=DiscoveryItemResponse(
            id=item.id,
            type=item.type,
            status=item.status,
            name=item.name,
            description=item.description,
            version=item.version,
            aliases=item.aliases,
            tags=item.tags,
            homepage_url=item.homepage_url,
            documentation_url=item.documentation_url,
            capabilities=tuple(capability.id for capability in item.capabilities),
            requirements=item.requirements,
            relationships=item.relationships,
            metadata=dict(item.metadata),
        ),
        provenance=entry.provenance,
        metadata=dict(entry.metadata),
    )


def relationship_to_response(
    reference: DiscoveryRelationshipReference,
) -> DiscoveryRelationshipReferenceResponse:
    return DiscoveryRelationshipReferenceResponse(
        source_item_id=reference.source_item_id,
        target=reference.target,
        relationship=reference.relationship,
        resolved_target_item_id=reference.resolved_target_item_id,
        resolved=reference.resolved,
    )


def search_evidence_to_response(
    evidence: DiscoverySearchEvidence,
) -> DiscoverySearchEvidenceResponse:
    return DiscoverySearchEvidenceResponse(
        field=evidence.field,
        value=evidence.value,
        matched_text=evidence.matched_text,
        match_type=evidence.match_type,
    )


def search_result_to_response(
    result: DiscoverySearchResult,
) -> DiscoverySearchResultResponse:
    return DiscoverySearchResultResponse(
        item=entry_to_response(result.entry).item,
        entry=entry_to_response(result.entry),
        evidence=tuple(search_evidence_to_response(item) for item in result.evidence),
    )
