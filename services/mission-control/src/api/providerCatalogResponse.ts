import type { Provider } from "../types/provider";
import { normalizeServiceHealth } from "../utils/healthPresentation";

export class ProviderCatalogResponseError extends Error {
    constructor() {
        super("Provider catalog response could not be read.");
        this.name = "ProviderCatalogResponseError";
    }
}

function object(value: unknown): Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new ProviderCatalogResponseError();
    return value as Record<string, unknown>;
}
function string(value: unknown): string {
    if (typeof value !== "string") throw new ProviderCatalogResponseError();
    return value;
}

export function parseProviderCatalog(value: unknown): Provider[] {
    if (!Array.isArray(value)) throw new ProviderCatalogResponseError();
    const ids = new Set<string>();
    return value.map(entry => {
        const row = object(entry);
        const id = string(row.id);
        const name = string(row.name);
        // Core IDs are URL-safe slugs; detail views need an unambiguous, readable identity.
        if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id) || id.trim() !== id
            || !name.trim() || ids.has(id)) throw new ProviderCatalogResponseError();
        ids.add(id);
        if (!Array.isArray(row.capabilities) || row.capabilities.some(item => typeof item !== "string")) throw new ProviderCatalogResponseError();
        const health = normalizeServiceHealth(row.health);
        return {
            id, name, workspace: string(row.workspace), priority: string(row.priority),
            version: string(row.version), description: string(row.description), icon: string(row.icon),
            capabilities: [...row.capabilities] as string[],
            health: {
                status: health.status, latency_ms: health.latency_ms, http_status: health.http_status,
                message: health.message, details: { ...health.details },
            },
        };
    });
}
