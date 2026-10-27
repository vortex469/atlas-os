import type { DiscoveryCatalogPage, DiscoverySearchPage } from "../types/discovery";

export class DiscoveryCatalogResponseError extends Error {
    constructor() { super("The catalog results could not be read. Try again."); }
}

function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

function readableEntry(value: unknown): boolean {
    if (!record(value) || !record(value.item)) return false;
    const item = value.item;
    return ["id", "name", "type", "status", "description"].every(key => typeof item[key] === "string")
        && ["id", "name"].every(key => (item[key] as string).trim().length > 0)
        && ["capabilities", "tags"].every(key => Array.isArray(item[key])
            && item[key].every(value => typeof value === "string"));
}

// Check fields used by the catalog screen; retain additive metadata and future labels.
// This is a display guard, not installation or execution validation.
export function parseDiscoveryCatalogPage(value: unknown, search: false): DiscoveryCatalogPage;
export function parseDiscoveryCatalogPage(value: unknown, search: true): DiscoverySearchPage;
export function parseDiscoveryCatalogPage(value: unknown, search: boolean): DiscoveryCatalogPage | DiscoverySearchPage {
    if (record(value) && Number.isSafeInteger(value.total) && Number(value.total) >= 0
        && Number.isSafeInteger(value.limit) && Number(value.limit) >= 1
        && Number.isSafeInteger(value.offset) && Number(value.offset) >= 0
        && typeof value.has_more === "boolean") {
        const entries = search ? value.results : value.entries;
        if (Array.isArray(entries) && entries.every(entry => search
            ? record(entry) && readableEntry(entry.entry) : readableEntry(entry))) {
            return value as DiscoveryCatalogPage | DiscoverySearchPage;
        }
    }
    throw new DiscoveryCatalogResponseError();
}
