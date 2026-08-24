export type DiscoveryItemType =
    | "application"
    | "service"
    | "container_image"
    | "ai_model"
    | "integration"
    | "hardware_device"
    | "deployment_method";

export type DiscoveryItemStatus =
    | "active"
    | "deprecated"
    | "experimental"
    | "unknown";

export type DiscoveryRelationshipType =
    | "depends_on"
    | "provides"
    | "consumes"
    | "requires"
    | "integrates_with"
    | "conflicts_with"
    | "runs_on"
    | "deployed_by"
    | "compatible_with"
    | "incompatible_with";

export type DiscoveryCompatibilityStatus =
    | "compatible"
    | "compatible_with_warnings"
    | "insufficient_information"
    | "incompatible";

export type DiscoveryCompatibilityFindingSeverity =
    | "blocker"
    | "warning"
    | "info"
    | "unknown";

export type DiscoveryCompatibilityCheckType =
    | "capability"
    | "resource"
    | "platform"
    | "network"
    | "relationship"
    | "catalog";

export type DiscoveryCapabilityReference = {
    id: string;
};

export type DiscoveryPortRequirement = {
    port: number;
    protocol: string;
    direction: string;
    required: boolean;
    description?: string | null;
};

export type DiscoveryRequirements = {
    capabilities: DiscoveryCapabilityReference[];
    resources: {
        cpu_cores_min?: number | null;
        memory_mb_min?: number | null;
        storage_gb_min?: number | null;
        gpu_required: boolean;
        gpu_memory_gb_min?: number | null;
    };
    platform: {
        architectures: string[];
        operating_systems: string[];
        runtimes: string[];
        devices: string[];
    };
    network: {
        ports: DiscoveryPortRequirement[];
        requires_internet?: boolean | null;
        requires_lan?: boolean | null;
        notes?: string | null;
    };
};

export type DiscoveryRelationship = {
    type: DiscoveryRelationshipType;
    target: string;
    required: boolean;
    minimum_version?: string | null;
    maximum_version?: string | null;
    description?: string;
    metadata: Record<string, unknown>;
};

export type DiscoveryItemMetadata = {
    reviewed_for_d5?: boolean;
    catalog_notes?: string[];
};

export type CatalogProvenance = {
    source_type: "curated" | "private" | "community" | "dynamic";
    source: string;
    entry_id?: string | null;
    version?: string | null;
    trust_level: "curated" | "verified" | "community" | "private" | "dynamic";
};

export type DiscoveryItem = {
    id: string;
    type: DiscoveryItemType;
    status: DiscoveryItemStatus;
    name: string;
    description: string;
    version?: string | null;
    aliases: string[];
    tags: string[];
    homepage_url?: string | null;
    documentation_url?: string | null;
    capabilities: string[];
    requirements: DiscoveryRequirements;
    relationships: DiscoveryRelationship[];
    metadata: DiscoveryItemMetadata;
};

export type DiscoveryCatalogEntry = {
    schema_version: number;
    item: DiscoveryItem;
    provenance: CatalogProvenance;
    metadata: DiscoveryItemMetadata;
};

export type DiscoveryEvidenceFreshness = "fresh" | "stale";
export type DiscoverySourceHealth = "healthy" | "degraded" | "unavailable";
export type DiscoverySourceCacheState = "absent" | "available" | "corrupt";
export type DiscoveryConflictState =
    | "none"
    | "agreement"
    | "dynamic_conflict"
    | "curated_conflict";

export type DiscoveryDynamicProvenance = {
    source_id: string;
    source_type: "github_latest_release";
    trust_tier: "supplemental";
    repository: string;
    upstream_release_id: number;
    retrieved_at: string;
    expires_at: string;
};

export type DiscoveryDynamicClaim = {
    fact_kind: "latest_stable_release";
    version: string;
    published_at: string;
    freshness: DiscoveryEvidenceFreshness;
    provenance: DiscoveryDynamicProvenance;
};

export type DiscoverySourceState = {
    source_id: string;
    health: DiscoverySourceHealth | null;
    cache_state: DiscoverySourceCacheState;
};

export type DiscoveryReleaseEvaluationStatus =
    | "up_to_date"
    | "update_available"
    | "baseline_ahead"
    | "conflicted"
    | "stale_evidence"
    | "no_baseline"
    | "no_dynamic_evidence"
    | "insufficient_information";

export type DiscoveryReleaseEvaluationBaselineSource =
    | "curated"
    | "item_version";

export type DiscoveryReleaseEvaluationBaseline = {
    version: string;
    source: DiscoveryReleaseEvaluationBaselineSource;
};

export type DiscoveryReleaseEvaluation = {
    status: DiscoveryReleaseEvaluationStatus;
    baseline?: DiscoveryReleaseEvaluationBaseline | null;
    latest_candidate?: string | null;
    reason?: string | null;
};

export type DiscoveryItemEvidence = {
    schema_version: "discovery-merged-item-v1";
    catalog_item_id: string;
    curated: DiscoveryCatalogEntry;
    dynamic_claims: DiscoveryDynamicClaim[];
    source_states: DiscoverySourceState[];
    conflict_state: DiscoveryConflictState;
    release_evaluation?: DiscoveryReleaseEvaluation | null;
};

export type DiscoveryImageGroundingStatus =
    | "grounded"
    | "no_deployment_binding"
    | "no_strict_release_version"
    | "no_repository_observation"
    | "observation_mismatch"
    | "mutable_observation"
    | "no_image_release_evidence"
    | "evidence_not_trusted"
    | "evidence_version_mismatch"
    | "repository_identity_mismatch"
    | "digest_mismatch"
    | "conflicted";

export type DiscoveryImageEvidenceSourceClass =
    | "curated"
    | "registry_attested"
    | "upstream_signed";

export type DiscoveryImageGroundingProjection = {
    schema_version: "discovery-image-grounding-projection-v1";
    catalog_item_id: string;
    status: DiscoveryImageGroundingStatus;
    release_version: string | null;
    deployment_binding: {
        compose_file: string;
        compose_service: string;
        mutable_property: "image";
        deployment_method: "docker-compose";
    } | null;
    observed_image: {
        image_reference: string;
        image_digest: string;
    } | null;
    accepted_evidence: Array<{
        release_version: string;
        image_reference: string;
        image_digest: string;
        source_class: DiscoveryImageEvidenceSourceClass;
        source_id: string;
        attested_at: string;
    }>;
};

export type DiscoveryCatalogPage = {
    entries: DiscoveryCatalogEntry[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
};

export type DiscoverySearchEvidence = {
    field: string;
    value: string;
    matched_text: string;
    match_type: string;
};

export type DiscoverySearchResult = {
    item: DiscoveryItem;
    entry: DiscoveryCatalogEntry;
    evidence: DiscoverySearchEvidence[];
};

export type DiscoverySearchPage = {
    results: DiscoverySearchResult[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
};

export type DiscoveryRelationshipReference = {
    source_item_id: string;
    target: string;
    relationship: DiscoveryRelationship;
    resolved_target_item_id?: string | null;
    resolved: boolean;
};

export type DiscoveryRelationshipCollection = {
    item_id: string;
    incoming: DiscoveryRelationshipReference[];
    outgoing: DiscoveryRelationshipReference[];
};

export type DiscoveryMetadata = {
    catalog_loaded: boolean;
    entry_count: number;
    schema_version: number;
};

export type DiscoveryCompatibilityEvidence = {
    id: string;
    check_type: DiscoveryCompatibilityCheckType;
    subject: string;
    status: DiscoveryCompatibilityStatus;
    message: string;
    source: string;
    requirement?: string | null;
    observed?: string | null;
    observed_fact_id?: string | null;
};

export type DiscoveryCompatibilityFinding = {
    id: string;
    check_type: DiscoveryCompatibilityCheckType;
    severity: DiscoveryCompatibilityFindingSeverity;
    status: DiscoveryCompatibilityStatus;
    subject: string;
    message: string;
    evidence_ids: string[];
};

export type DiscoveryCompatibilityAssessment = {
    item_id: string;
    target_id: string;
    target_type: string;
    status: DiscoveryCompatibilityStatus;
    checked_at: string;
    findings: DiscoveryCompatibilityFinding[];
    evidence: DiscoveryCompatibilityEvidence[];
    unknown_facts: string[];
};

export type DiscoveryProposalDestination =
    | "discovery_detail"
    | "compatibility_review"
    | "operator_maintenance_selection";

export type DiscoveryProposalStatus = "current" | "stale" | "expired" | "not_actionable";

export type DiscoveryProposalReason =
    | "compatible"
    | "compatibility_warning"
    | "incompatible"
    | "insufficient_information"
    | "unsupported_resource"
    | "source_changed"
    | "source_missing"
    | "evidence_changed"
    | "evidence_missing"
    | "expired"
    | "no_supported_destination";

export type DiscoveryProposalNavigation = {
    proposal_id: string;
    destination_kind: DiscoveryProposalDestination;
    catalog_item_id: string;
    catalog_source_type: CatalogProvenance["source_type"];
    compatibility_status: DiscoveryCompatibilityStatus;
    finding_reference_count: number;
    evidence_reference_count: number;
    status: DiscoveryProposalStatus;
    reason: DiscoveryProposalReason;
    intent_hint?: "restart-service" | null;
    target_hints: Array<{
        catalog_target_id?: string | null;
        provider_hint?: string | null;
        resource_type_hint?: string | null;
    }>;
    generated_at: string;
    expires_at: string;
    actionable_navigation: boolean;
};

export type DiscoveryProposalPage = {
    proposals: DiscoveryProposalNavigation[];
    total: number;
    limit: number;
};

export type DiscoveryListQuery = {
    limit?: number;
    offset?: number;
    type?: DiscoveryItemType;
    status?: DiscoveryItemStatus;
    tag?: string;
    capability?: string;
};

export type DiscoverySearchQuery = DiscoveryListQuery & {
    q: string;
};
