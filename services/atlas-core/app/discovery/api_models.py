from __future__ import annotations

from typing import Any

from pydantic import Field

from app.discovery.compatibility import (
    CompatibilityAssessment,
    CompatibilityCheckType,
    CompatibilityFindingSeverity,
    CompatibilityStatus,
)
from app.discovery.models import (
    CATALOG_SCHEMA_VERSION,
    CatalogSourceType,
    CatalogTrustLevel,
    DiscoveryCenterModel,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationshipType,
)
from app.discovery.repository import DiscoveryRelationshipReference
from app.discovery.search import DiscoverySearchEvidence, DiscoverySearchResult


class DiscoveryCapabilityReferenceResponse(DiscoveryCenterModel):
    """Public API projection of a capability reference."""

    id: str


class DiscoveryResourceRequirementsResponse(DiscoveryCenterModel):
    """Public API projection of resource requirements."""

    cpu_cores_min: float | None = None
    memory_mb_min: int | None = None
    storage_gb_min: float | None = None
    gpu_required: bool = False
    gpu_memory_gb_min: float | None = None


class DiscoveryPlatformRequirementsResponse(DiscoveryCenterModel):
    """Public API projection of platform requirements."""

    architectures: tuple[str, ...] = ()
    operating_systems: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()


class DiscoveryPortRequirementResponse(DiscoveryCenterModel):
    """Public API projection of a port requirement."""

    port: int
    protocol: str
    direction: str
    required: bool
    description: str = ""


class DiscoveryNetworkRequirementsResponse(DiscoveryCenterModel):
    """Public API projection of network requirements."""

    ports: tuple[DiscoveryPortRequirementResponse, ...] = ()
    requires_internet: bool = False
    requires_lan: bool = False
    notes: tuple[str, ...] = ()


class DiscoveryRequirementsResponse(DiscoveryCenterModel):
    """Public API projection of Discovery requirements."""

    capabilities: tuple[DiscoveryCapabilityReferenceResponse, ...] = ()
    resources: DiscoveryResourceRequirementsResponse = Field(
        default_factory=DiscoveryResourceRequirementsResponse,
    )
    platform: DiscoveryPlatformRequirementsResponse = Field(
        default_factory=DiscoveryPlatformRequirementsResponse,
    )
    network: DiscoveryNetworkRequirementsResponse = Field(
        default_factory=DiscoveryNetworkRequirementsResponse,
    )


class DiscoveryRelationshipResponse(DiscoveryCenterModel):
    """Public API projection of a Discovery relationship."""

    type: DiscoveryRelationshipType
    target: str
    required: bool = True
    minimum_version: str | None = None
    maximum_version: str | None = None
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCatalogProvenanceResponse(DiscoveryCenterModel):
    """Public API projection of catalog provenance."""

    source_type: CatalogSourceType
    source: str
    entry_id: str | None = None
    version: str | None = None
    trust_level: CatalogTrustLevel


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
    requirements: DiscoveryRequirementsResponse = Field(
        default_factory=DiscoveryRequirementsResponse,
    )
    relationships: tuple[DiscoveryRelationshipResponse, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCatalogEntryResponse(DiscoveryCenterModel):
    """Public API projection of a catalog entry."""

    schema_version: int
    item: DiscoveryItemResponse
    provenance: DiscoveryCatalogProvenanceResponse
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
    relationship: DiscoveryRelationshipResponse
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


class DiscoveryCompatibilityEvidenceResponse(DiscoveryCenterModel):
    """Public compatibility evidence without provider internals."""

    id: str
    check_type: CompatibilityCheckType
    subject: str
    status: CompatibilityStatus
    message: str
    source: str
    requirement: str | None = None
    observed: str | None = None
    observed_fact_id: str | None = None


class DiscoveryCompatibilityFindingResponse(DiscoveryCenterModel):
    """Public compatibility finding referencing evidence by id."""

    id: str
    check_type: CompatibilityCheckType
    severity: CompatibilityFindingSeverity
    status: CompatibilityStatus
    subject: str
    message: str
    evidence_ids: tuple[str, ...]


class DiscoveryCompatibilityAssessmentResponse(DiscoveryCenterModel):
    """Public read-only compatibility assessment response."""

    item_id: str
    target_id: str
    target_type: str
    status: CompatibilityStatus
    checked_at: str
    findings: tuple[DiscoveryCompatibilityFindingResponse, ...] = ()
    evidence: tuple[DiscoveryCompatibilityEvidenceResponse, ...] = ()
    unknown_facts: tuple[str, ...] = ()


def requirements_to_response(requirements) -> DiscoveryRequirementsResponse:
    return DiscoveryRequirementsResponse(
        capabilities=tuple(
            DiscoveryCapabilityReferenceResponse(id=capability.id)
            for capability in requirements.capabilities
        ),
        resources=DiscoveryResourceRequirementsResponse(
            cpu_cores_min=requirements.resources.cpu_cores_min,
            memory_mb_min=requirements.resources.memory_mb_min,
            storage_gb_min=requirements.resources.storage_gb_min,
            gpu_required=requirements.resources.gpu_required,
            gpu_memory_gb_min=requirements.resources.gpu_memory_gb_min,
        ),
        platform=DiscoveryPlatformRequirementsResponse(
            architectures=requirements.platform.architectures,
            operating_systems=requirements.platform.operating_systems,
            runtimes=requirements.platform.runtimes,
            devices=requirements.platform.devices,
        ),
        network=DiscoveryNetworkRequirementsResponse(
            ports=tuple(
                DiscoveryPortRequirementResponse(
                    port=port.port,
                    protocol=port.protocol,
                    direction=port.direction,
                    required=port.required,
                    description=port.description,
                )
                for port in requirements.network.ports
            ),
            requires_internet=requirements.network.requires_internet,
            requires_lan=requirements.network.requires_lan,
            notes=requirements.network.notes,
        ),
    )


def relationship_domain_to_response(relationship) -> DiscoveryRelationshipResponse:
    return DiscoveryRelationshipResponse(
        type=relationship.type,
        target=relationship.target,
        required=relationship.required,
        minimum_version=relationship.minimum_version,
        maximum_version=relationship.maximum_version,
        description=relationship.description,
        metadata=dict(relationship.metadata),
    )


def provenance_to_response(provenance) -> DiscoveryCatalogProvenanceResponse:
    return DiscoveryCatalogProvenanceResponse(
        source_type=provenance.source_type,
        source=provenance.source,
        entry_id=provenance.entry_id,
        version=provenance.version,
        trust_level=provenance.trust_level,
    )


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
            requirements=requirements_to_response(item.requirements),
            relationships=tuple(
                relationship_domain_to_response(relationship)
                for relationship in item.relationships
            ),
            metadata=dict(item.metadata),
        ),
        provenance=provenance_to_response(entry.provenance),
        metadata=dict(entry.metadata),
    )


def relationship_to_response(
    reference: DiscoveryRelationshipReference,
) -> DiscoveryRelationshipReferenceResponse:
    return DiscoveryRelationshipReferenceResponse(
        source_item_id=reference.source_item_id,
        target=reference.target,
        relationship=relationship_domain_to_response(reference.relationship),
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
    response_entry = entry_to_response(result.entry)
    return DiscoverySearchResultResponse(
        item=response_entry.item,
        entry=response_entry,
        evidence=tuple(search_evidence_to_response(item) for item in result.evidence),
    )


def compatibility_assessment_to_response(
    assessment: CompatibilityAssessment,
) -> DiscoveryCompatibilityAssessmentResponse:
    return DiscoveryCompatibilityAssessmentResponse(
        item_id=assessment.item_id,
        target_id=assessment.target_id,
        target_type=assessment.target_type,
        status=assessment.status,
        checked_at=assessment.checked_at.isoformat(),
        findings=tuple(
            DiscoveryCompatibilityFindingResponse(
                id=finding.id,
                check_type=finding.check_type,
                severity=finding.severity,
                status=finding.status,
                subject=finding.subject,
                message=finding.message,
                evidence_ids=finding.evidence_ids,
            )
            for finding in assessment.findings
        ),
        evidence=tuple(
            DiscoveryCompatibilityEvidenceResponse(
                id=evidence.id,
                check_type=evidence.check_type,
                subject=evidence.subject,
                status=evidence.status,
                message=evidence.message,
                source=evidence.source,
                requirement=evidence.requirement,
                observed=evidence.observed,
                observed_fact_id=evidence.observed_fact_id,
            )
            for evidence in assessment.evidence
        ),
        unknown_facts=assessment.unknown_facts,
    )
