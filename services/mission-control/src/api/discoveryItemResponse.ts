import type { DiscoveryCatalogEntry } from "../types/discovery";

export class DiscoveryItemResponseError extends Error {
    constructor(message = "The catalog item could not be read. Reload to try again.") { super(message); }
}
function object(value: unknown): Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new DiscoveryItemResponseError();
    return value as Record<string, unknown>;
}
function text(value: unknown): value is string { return typeof value === "string"; }
function strings(value: unknown): value is string[] { return Array.isArray(value) && value.every(text); }
function metadata(value: unknown) {
    const result = object(value === undefined ? {} : value);
    if ((result.catalog_notes !== undefined && !strings(result.catalog_notes))
        || (result.reviewed_for_d5 !== undefined && typeof result.reviewed_for_d5 !== "boolean")) throw new DiscoveryItemResponseError();
    return result;
}

// Validate rendered item details only. Preserve future labels and additive fields;
// public DTO defaults do not supply any operational authority.
export function parseDiscoveryItem(value: unknown, itemId: string): DiscoveryCatalogEntry {
    const entry = object(value);
    const item = object(entry.item);
    if (typeof item.id === "string" && item.id !== itemId) {
        throw new DiscoveryItemResponseError("The catalog response does not match this item. Reload to check again.");
    }
    if (![item.id, item.name, item.type, item.status].every(text) || !String(item.name).trim()
        || !Number.isSafeInteger(entry.schema_version)) throw new DiscoveryItemResponseError();
    const normalizedItem = { description: "", capabilities: [], tags: [], ...item };
    if (!text(normalizedItem.description) || !strings(normalizedItem.capabilities) || !strings(normalizedItem.tags)) throw new DiscoveryItemResponseError();
    const requirements = object(item.requirements === undefined ? {} : item.requirements);
    const resources = { gpu_required: false, ...object(requirements.resources === undefined ? {} : requirements.resources) };
    if (typeof resources.gpu_required !== "boolean") throw new DiscoveryItemResponseError();
    for (const key of ["cpu_cores_min", "memory_mb_min", "storage_gb_min", "gpu_memory_gb_min"]) {
        const number = (resources as Record<string, unknown>)[key];
        if (number !== undefined && number !== null && (typeof number !== "number" || !Number.isFinite(number))) throw new DiscoveryItemResponseError();
    }
    const platform = { architectures: [], operating_systems: [], runtimes: [], devices: [],
        ...object(requirements.platform === undefined ? {} : requirements.platform) };
    if (![platform.architectures, platform.operating_systems, platform.runtimes, platform.devices].every(strings)) throw new DiscoveryItemResponseError();
    const capabilities = requirements.capabilities === undefined ? [] : requirements.capabilities;
    if (!Array.isArray(capabilities) || !capabilities.every(value => text(object(value).id))) throw new DiscoveryItemResponseError();
    const network = { ports: [], ...object(requirements.network === undefined ? {} : requirements.network) } as Record<string, unknown>;
    if (!Array.isArray(network.ports)) throw new DiscoveryItemResponseError();
    for (const value of network.ports) {
        const port = object(value);
        if (!Number.isSafeInteger(port.port) || !text(port.protocol) || !text(port.direction)
            || typeof port.required !== "boolean" || (port.description !== undefined && !text(port.description))) throw new DiscoveryItemResponseError();
    }
    for (const key of ["requires_internet", "requires_lan"]) {
        if (network[key] !== undefined && network[key] !== null && typeof network[key] !== "boolean") throw new DiscoveryItemResponseError();
    }
    if (network.notes !== undefined && network.notes !== null && !text(network.notes) && !strings(network.notes)) throw new DiscoveryItemResponseError();
    const provenance = object(entry.provenance);
    if (![provenance.source_type, provenance.source, provenance.trust_level].every(text)
        || (provenance.entry_id !== undefined && provenance.entry_id !== null && !text(provenance.entry_id))) throw new DiscoveryItemResponseError();
    return { ...entry, item: { ...normalizedItem, metadata: metadata(item.metadata),
        requirements: { ...requirements, resources, platform, capabilities, network } },
        provenance, metadata: metadata(entry.metadata) } as unknown as DiscoveryCatalogEntry;
}
