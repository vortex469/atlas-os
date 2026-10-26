import type { DiscoveryMetadata } from "../types/discovery";

export class DiscoveryMetadataResponseError extends Error {
    constructor() { super("The catalog summary response could not be read."); }
}

export function parseDiscoveryMetadata(value: unknown): DiscoveryMetadata {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new DiscoveryMetadataResponseError();
    const data: Record<string, unknown> = { schema_version: 1, ...value };
    if (typeof data.catalog_loaded !== "boolean" || !Number.isSafeInteger(data.entry_count) || Number(data.entry_count) < 0
        || !Number.isSafeInteger(data.schema_version)) throw new DiscoveryMetadataResponseError();
    return { catalog_loaded: data.catalog_loaded, entry_count: data.entry_count as number, schema_version: data.schema_version as number };
}
