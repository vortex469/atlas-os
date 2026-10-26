import type {
    ActionHistoryQuery,
    ProviderActionAuditEntry,
    ProviderActionHistoryPage,
    ProviderActionHistoryProvider,
    ProviderActionHistorySummary,
} from "../types/actionHistory";
import { evidenceTimestamp } from "../utils/healthPresentation";

const READ_ERRORS = {
    record: "This audit record is incomplete or inconsistent. Try loading it again.",
    identity: "The returned record does not match this audit link. Try again.",
    page: "The action history report is incomplete or inconsistent. Refresh history to try again.",
    summary: "Retention policy unavailable. Refresh history to try again.",
    providers: "Provider choices are unavailable. Refresh history to try again.",
} as const;

export class ActionHistoryResponseError extends Error {
    constructor(kind: keyof typeof READ_ERRORS) {
        super(READ_ERRORS[kind]);
    }
}

function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

function text(value: unknown): value is string {
    return typeof value === "string" && value.trim().length > 0;
}

function integer(value: unknown, minimum = 0): value is number {
    return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum;
}

export function parseActionHistoryEntry(value: unknown, expectedId?: string): ProviderActionAuditEntry {
    if (!record(value)) throw new ActionHistoryResponseError("record");
    if (expectedId !== undefined && typeof value.id === "string" && value.id !== expectedId) {
        throw new ActionHistoryResponseError("identity");
    }
    // These defaults belong to the published Core DTO, not inferred outcomes.
    const data: Record<string, unknown> = { parameter_names: [], request_id: null, ...value };
    if (![data.id, data.provider_id, data.provider_name, data.action_id, data.action_label].every(text)
        || (data.status !== "succeeded" && data.status !== "failed")
        || typeof data.success !== "boolean" || data.success !== (data.status === "succeeded")
        || typeof data.message !== "string"
        || typeof data.confirmed !== "boolean" || typeof data.destructive !== "boolean"
        || !Array.isArray(data.parameter_names) || !data.parameter_names.every((name) => typeof name === "string")
        || !(data.request_id === null || typeof data.request_id === "string")
        || evidenceTimestamp(data.started_at) === null || evidenceTimestamp(data.completed_at) === null
        || typeof data.duration_ms !== "number" || !Number.isFinite(data.duration_ms) || data.duration_ms < 0) {
        throw new ActionHistoryResponseError("record");
    }
    return data as unknown as ProviderActionAuditEntry;
}

export function parseActionHistoryPage(value: unknown, query: ActionHistoryQuery): ProviderActionHistoryPage {
    if (!record(value)) throw new ActionHistoryResponseError("page");
    const data: Record<string, unknown> = { items: [], ...value };
    if (!integer(data.total) || !integer(data.offset) || !integer(data.limit, 1) || data.limit > 100
        || data.offset !== (query.offset ?? 0) || data.limit !== (query.limit ?? 25)
        || typeof data.has_more !== "boolean" || !Array.isArray(data.items)
        || data.items.length !== Math.min(data.limit, Math.max(0, data.total - data.offset))) {
        throw new ActionHistoryResponseError("page");
    }
    let items: ProviderActionAuditEntry[];
    try {
        items = data.items.map((item) => parseActionHistoryEntry(item));
    } catch {
        throw new ActionHistoryResponseError("page");
    }
    if (new Set(items.map((item) => item.id)).size !== items.length
        || data.has_more !== (data.offset + items.length < data.total)
        || items.some((item) => (query.status !== undefined && item.status !== query.status)
            || (query.providerId !== undefined && item.provider_id !== query.providerId))) {
        throw new ActionHistoryResponseError("page");
    }
    return { items, total: data.total, offset: data.offset, limit: data.limit, has_more: data.has_more };
}

export function parseActionHistorySummary(value: unknown): ProviderActionHistorySummary {
    if (!record(value)) throw new ActionHistoryResponseError("summary");
    const data: Record<string, unknown> = { oldest_entry_at: null, newest_entry_at: null, ...value };
    if (!integer(data.entry_count) || !integer(data.max_entries, 1) || !integer(data.retention_days, 1)
        || data.entry_count > data.max_entries
        || (data.oldest_entry_at !== null && evidenceTimestamp(data.oldest_entry_at) === null)
        || (data.newest_entry_at !== null && evidenceTimestamp(data.newest_entry_at) === null)
        || (data.oldest_entry_at !== null && data.newest_entry_at !== null
            && evidenceTimestamp(data.oldest_entry_at)! > evidenceTimestamp(data.newest_entry_at)!)) {
        throw new ActionHistoryResponseError("summary");
    }
    return data as unknown as ProviderActionHistorySummary;
}

export function parseActionHistoryProviders(value: unknown): ProviderActionHistoryProvider[] {
    if (!Array.isArray(value) || !value.every((provider) => record(provider) && text(provider.id) && text(provider.name))
        || new Set(value.map((provider) => provider.id)).size !== value.length) {
        throw new ActionHistoryResponseError("providers");
    }
    return value as ProviderActionHistoryProvider[];
}
