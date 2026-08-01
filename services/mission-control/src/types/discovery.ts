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
