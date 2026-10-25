import type { DiscoveryProposalNavigation } from "../../types/discovery";

/** Advisory navigation context only; never a target selection or approval. */
export function proposalIdFromState(state: unknown): string | null {
    if (typeof state !== "object" || state === null || !("proposalId" in state)) return null;
    const value = (state as { proposalId?: unknown }).proposalId;
    return typeof value === "string" && /^discovery-operator-proposal-[a-f0-9]{64}$/.test(value)
        ? value
        : null;
}

export type ClosedProposalDestination = {
    kind: "discovery_item" | "operator_maintenance_selection";
    itemId?: string;
    proposalId?: string;
};

/** Resolve server enums to application-owned routes; no URL from proposal data is accepted. */
export function resolveProposalNavigation(
    proposal: DiscoveryProposalNavigation,
): ClosedProposalDestination {
    if (
        proposal.destination_kind === "operator_maintenance_selection"
        && proposal.status === "current"
        && proposal.actionable_navigation
    ) {
        return { kind: "operator_maintenance_selection", proposalId: proposal.proposal_id };
    }
    if (
        proposal.destination_kind === "discovery_detail"
        || proposal.destination_kind === "compatibility_review"
        || proposal.status !== "current"
        || !proposal.actionable_navigation
    ) {
        return { kind: "discovery_item", itemId: proposal.catalog_item_id };
    }
    throw new Error("Unsupported Discovery proposal destination");
}
