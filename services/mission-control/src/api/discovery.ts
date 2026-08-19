import { atlas } from "./atlas";
import type {
    DiscoveryCatalogEntry,
    DiscoveryCatalogPage,
    DiscoveryCompatibilityAssessment,
    DiscoveryItemEvidence,
    DiscoveryListQuery,
    DiscoveryMetadata,
    DiscoveryProposalNavigation,
    DiscoveryProposalPage,
    DiscoveryRelationshipCollection,
    DiscoveryRelationshipType,
    DiscoverySearchPage,
    DiscoverySearchQuery,
} from "../types/discovery";

const DEFAULT_LIMIT = 25;

export async function getDiscoveryMetadata(): Promise<DiscoveryMetadata> {
    const response = await atlas.get<DiscoveryMetadata>("/discovery");

    return response.data;
}

export async function listDiscoveryProposals(limit = 50): Promise<DiscoveryProposalPage> {
    const response = await atlas.get<DiscoveryProposalPage>("/discovery/proposals", {
        params: { limit },
    });
    return response.data;
}

export async function getDiscoveryProposal(
    proposalId: string,
): Promise<DiscoveryProposalNavigation> {
    const response = await atlas.get<DiscoveryProposalNavigation>(
        `/discovery/proposals/${encodeURIComponent(proposalId)}`,
    );
    return response.data;
}

export async function listDiscoveryItems(
    query: DiscoveryListQuery = {},
): Promise<DiscoveryCatalogPage> {
    const response = await atlas.get<DiscoveryCatalogPage>("/discovery/items", {
        params: discoveryParams(query),
    });

    return response.data;
}

export async function searchDiscoveryItems(
    query: DiscoverySearchQuery,
): Promise<DiscoverySearchPage> {
    const response = await atlas.get<DiscoverySearchPage>("/discovery/search", {
        params: discoveryParams(query),
    });

    return response.data;
}

export async function getDiscoveryItem(
    itemId: string,
): Promise<DiscoveryCatalogEntry> {
    const response = await atlas.get<DiscoveryCatalogEntry>(
        `/discovery/items/${encodeURIComponent(itemId)}`,
    );

    return response.data;
}

export async function getDiscoveryItemEvidence(
    itemId: string,
): Promise<DiscoveryItemEvidence> {
    const response = await atlas.get<DiscoveryItemEvidence>(
        `/discovery/items/${encodeURIComponent(itemId)}/evidence`,
    );

    return response.data;
}

export async function getDiscoveryRelationships(
    itemId: string,
    relationshipType?: DiscoveryRelationshipType,
): Promise<DiscoveryRelationshipCollection> {
    const response = await atlas.get<DiscoveryRelationshipCollection>(
        `/discovery/items/${encodeURIComponent(itemId)}/relationships`,
        {
            params: relationshipType ? { type: relationshipType } : undefined,
        },
    );

    return response.data;
}

export async function getDiscoveryCompatibility(
    itemId: string,
    target?: string,
): Promise<DiscoveryCompatibilityAssessment> {
    const normalizedTarget = target?.trim();
    const response = await atlas.get<DiscoveryCompatibilityAssessment>(
        `/discovery/items/${encodeURIComponent(itemId)}/compatibility`,
        {
            params: normalizedTarget ? { target: normalizedTarget } : undefined,
        },
    );

    return response.data;
}

function discoveryParams(query: DiscoveryListQuery | DiscoverySearchQuery) {
    return {
        q: "q" in query ? query.q : undefined,
        limit: query.limit ?? DEFAULT_LIMIT,
        offset: query.offset ?? 0,
        type: query.type || undefined,
        status: query.status || undefined,
        tag: query.tag || undefined,
        capability: query.capability || undefined,
    };
}
