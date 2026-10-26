import type { DiscoveryRelationshipCollection, DiscoveryRelationshipReference, DiscoveryRelationshipType } from "../types/discovery";

export class DiscoveryRelationshipsResponseError extends Error {
    constructor() { super("The relationship response could not be read for this catalog item."); }
}

const types = new Set<DiscoveryRelationshipType>(["depends_on", "provides", "consumes", "requires", "integrates_with", "conflicts_with", "runs_on", "deployed_by", "compatible_with", "incompatible_with"]);
function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}
function text(value: unknown): string {
    if (typeof value !== "string") throw new DiscoveryRelationshipsResponseError();
    return value;
}
function nullableText(value: unknown): string | null {
    return value === null ? null : text(value);
}
function reference(value: unknown): DiscoveryRelationshipReference {
    if (!record(value) || !record(value.relationship)) throw new DiscoveryRelationshipsResponseError();
    const item: Record<string, unknown> = { resolved_target_item_id: null, ...value };
    const relationship: Record<string, unknown> = { required: true, minimum_version: null, maximum_version: null, description: "", metadata: {}, ...value.relationship };
    if (!types.has(relationship.type as DiscoveryRelationshipType) || typeof relationship.required !== "boolean"
        || !record(relationship.metadata) || typeof item.resolved !== "boolean") throw new DiscoveryRelationshipsResponseError();
    return {
        source_item_id: text(item.source_item_id), target: text(item.target), resolved: item.resolved,
        resolved_target_item_id: nullableText(item.resolved_target_item_id),
        relationship: { type: relationship.type as DiscoveryRelationshipType, target: text(relationship.target),
            required: relationship.required, minimum_version: nullableText(relationship.minimum_version),
            maximum_version: nullableText(relationship.maximum_version), description: text(relationship.description), metadata: relationship.metadata },
    };
}

// Defaults match Core's public DiscoveryRelationshipCollectionResponse and nested DTOs.
export function parseDiscoveryRelationships(value: unknown, itemId: string): DiscoveryRelationshipCollection {
    if (!record(value) || value.item_id !== itemId) throw new DiscoveryRelationshipsResponseError();
    const incoming = value.incoming === undefined ? [] : value.incoming;
    const outgoing = value.outgoing === undefined ? [] : value.outgoing;
    if (!Array.isArray(incoming) || !Array.isArray(outgoing)) throw new DiscoveryRelationshipsResponseError();
    return { item_id: itemId, incoming: incoming.map(reference), outgoing: outgoing.map(reference) };
}
