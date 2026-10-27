import { atlas } from "./atlas";
import { parseDiscoveryProposal, parseDiscoveryProposalPage } from "./discoveryProposalResponse";
import { parseDiscoveryInstallationPlan } from "./discoveryInstallationPlanResponse";
import { parseDiscoveryImageGrounding } from "./discoveryImageGroundingResponse";
import { parseDiscoveryEvidence } from "./discoveryEvidenceResponse";
import { parseDiscoveryCompatibility } from "./discoveryCompatibilityResponse";
import { parseDiscoveryItem } from "./discoveryItemResponse";
import { parseDiscoveryMetadata } from "./discoveryMetadataResponse";
import { parseDiscoveryCatalogPage } from "./discoveryCatalogResponse";
import { parseDiscoveryRelationships } from "./discoveryRelationshipsResponse";
import type {
    DiscoveryCatalogEntry,
    DiscoveryCatalogPage,
    DiscoveryCompatibilityAssessment,
    DiscoveryItemEvidence,
    DiscoveryImageGroundingProjection,
    DiscoveryListQuery,
    DiscoveryMetadata,
    DiscoveryProposalNavigation,
    DiscoveryProposalPage,
    DiscoveryRelationshipCollection,
    DiscoveryRelationshipType,
    DiscoverySearchPage,
    DiscoverySearchQuery,
} from "../types/discovery";
import type { InstallationPlan } from "../types/installationPlan";

const DEFAULT_LIMIT = 25;

export async function getDiscoveryMetadata(): Promise<DiscoveryMetadata> {
    const response = await atlas.get<unknown>("/discovery");

    return parseDiscoveryMetadata(response.data);
}

export async function listDiscoveryProposals(limit = 50): Promise<DiscoveryProposalPage> {
    const response = await atlas.get<unknown>("/discovery/proposals", {
        params: { limit },
    });
    return parseDiscoveryProposalPage(response.data);
}

export async function getDiscoveryProposal(
    proposalId: string,
): Promise<DiscoveryProposalNavigation> {
    const response = await atlas.get<unknown>(
        `/discovery/proposals/${encodeURIComponent(proposalId)}`,
    );
    return parseDiscoveryProposal(response.data, proposalId);
}

export async function listDiscoveryItems(
    query: DiscoveryListQuery = {},
): Promise<DiscoveryCatalogPage> {
    const response = await atlas.get<unknown>("/discovery/items", {
        params: discoveryParams(query),
    });

    return parseDiscoveryCatalogPage(response.data, false);
}

export async function searchDiscoveryItems(
    query: DiscoverySearchQuery,
): Promise<DiscoverySearchPage> {
    const response = await atlas.get<unknown>("/discovery/search", {
        params: discoveryParams(query),
    });

    return parseDiscoveryCatalogPage(response.data, true);
}

export async function getDiscoveryItem(
    itemId: string,
): Promise<DiscoveryCatalogEntry> {
    const response = await atlas.get<unknown>(
        `/discovery/items/${encodeURIComponent(itemId)}`,
    );

    return parseDiscoveryItem(response.data, itemId);
}

export async function getDiscoveryItemEvidence(
    itemId: string,
): Promise<DiscoveryItemEvidence> {
    const response = await atlas.get<unknown>(
        `/discovery/items/${encodeURIComponent(itemId)}/evidence`,
    );

    return parseDiscoveryEvidence(response.data, itemId);
}

export async function getDiscoveryImageGrounding(
    itemId: string,
): Promise<DiscoveryImageGroundingProjection> {
    const response = await atlas.get<unknown>(
        `/discovery/items/${encodeURIComponent(itemId)}/image-grounding`,
    );

    return parseDiscoveryImageGrounding(response.data, itemId);
}

export async function getDiscoveryInstallationPlan(itemId: string): Promise<InstallationPlan> {
    const response = await atlas.get<unknown>(
        `/discovery/items/${encodeURIComponent(itemId)}/installation-plan`,
    );
    return parseDiscoveryInstallationPlan(response.data, itemId);
}

export async function getDiscoveryRelationships(
    itemId: string,
    relationshipType?: DiscoveryRelationshipType,
): Promise<DiscoveryRelationshipCollection> {
    const response = await atlas.get<unknown>(
        `/discovery/items/${encodeURIComponent(itemId)}/relationships`,
        {
            params: relationshipType ? { type: relationshipType } : undefined,
        },
    );

    return parseDiscoveryRelationships(response.data, itemId);
}

export async function getDiscoveryCompatibility(
    itemId: string,
    target?: string,
): Promise<DiscoveryCompatibilityAssessment> {
    const normalizedTarget = target?.trim();
    const response = await atlas.get<unknown>(
        `/discovery/items/${encodeURIComponent(itemId)}/compatibility`,
        {
            params: normalizedTarget ? { target: normalizedTarget } : undefined,
        },
    );

    return parseDiscoveryCompatibility(response.data, itemId, normalizedTarget || "atlas");
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
