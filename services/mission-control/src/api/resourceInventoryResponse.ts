import type { ProviderResourceCollection, ProviderResourceExpectation } from "../types/resources";
import { evidenceTimestamp } from "../utils/healthPresentation";

export class ResourceInventoryResponseError extends Error {
    constructor() {
        super("Observed resource inventory could not be read.");
        this.name = "ResourceInventoryResponseError";
    }
}
function object(value: unknown): Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new ResourceInventoryResponseError();
    return value as Record<string, unknown>;
}
function string(value: unknown, nonempty = false): string {
    if (typeof value !== "string" || (nonempty && value.length === 0)) throw new ResourceInventoryResponseError();
    return value;
}
function coordinatePart(value: unknown): string {
    const result = string(value, true);
    if (result.includes("\u0000")) throw new ResourceInventoryResponseError();
    return result;
}
function boolean(value: unknown): boolean {
    if (typeof value !== "boolean") throw new ResourceInventoryResponseError();
    return value;
}
function count(value: unknown): number {
    if (!Number.isSafeInteger(value) || Number(value) < 0) throw new ResourceInventoryResponseError();
    return value as number;
}
function counts(value: unknown): Record<string, number> {
    return Object.fromEntries(Object.entries(object(value)).map(([key, value]) => [key, count(value)]));
}
function rows<T>(value: unknown, parse: (row: Record<string, unknown>) => T): T[] {
    if (!Array.isArray(value)) throw new ResourceInventoryResponseError();
    return value.map(row => parse(object(row)));
}
function expectation(value: unknown): ProviderResourceExpectation {
    const row = object(value);
    const state = row.state;
    if (state !== "needs_review" && state !== "configured" && state !== "ignored" && state !== "unsupported" && state !== "unavailable") throw new ResourceInventoryResponseError();
    const options = new Set<string>();
    return {
        value: row.value === null ? null : string(row.value), label: string(row.label), state,
        allowed_values: rows(row.allowed_values, option => {
            const value = string(option.value, true);
            if (options.has(value)) throw new ResourceInventoryResponseError();
            options.add(value);
            return { value, label: string(option.label, true), description: string(option.description), terminal: boolean(option.terminal) };
        }),
    };
}
function timestamp(value: unknown): string {
    const result = string(value);
    const checked = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(result) ? `${result}Z` : result;
    if (result.startsWith("0000-") || evidenceTimestamp(checked) === null) throw new ResourceInventoryResponseError();
    return result;
}

// Extract the read-only inventory view. Monitoring authority comes from management APIs.
export function parseResourceInventory(value: unknown, providerId: string): ProviderResourceCollection {
    const root = object(value);
    if (coordinatePart(root.provider_id) !== providerId) throw new ResourceInventoryResponseError();
    const summary = object(root.summary);
    const seen = new Set<string>();
    return {
        provider_id: providerId, provider_name: string(root.provider_name, true), refreshed_at: timestamp(root.refreshed_at),
        resources: rows(root.resources, row => {
            const provider_id = coordinatePart(row.provider_id), resource_type = coordinatePart(row.resource_type), resource_id = coordinatePart(row.resource_id);
            if (provider_id !== providerId) throw new ResourceInventoryResponseError();
            const coordinate = JSON.stringify([provider_id, resource_type, resource_id]);
            if (seen.has(coordinate)) throw new ResourceInventoryResponseError();
            seen.add(coordinate);
            return { provider_id, resource_type, resource_id, display_name: string(row.display_name, true), current_state: string(row.current_state, true),
                expectation: expectation(row.expectation), configured: boolean(row.configured), missing: boolean(row.missing), needs_review: boolean(row.needs_review),
                metadata: { ...object(row.metadata) },
            };
        }),
        summary: { total: count(summary.total), configured: count(summary.configured), needs_review: count(summary.needs_review), missing: count(summary.missing), ignored: count(summary.ignored),
            by_type: counts(summary.by_type), by_state: counts(summary.by_state) },
        metadata: { ...object(root.metadata) },
    };
}
