import type { IntelligenceTelemetrySnapshot, ProviderCollectionTiming } from "../types/ace";
import { evidenceTimestamp } from "../utils/healthPresentation";

export class IntelligenceHistoryResponseError extends Error {
    constructor() { super("Collection history response could not be read."); }
}

function object(value: unknown): Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new IntelligenceHistoryResponseError();
    return value as Record<string, unknown>;
}

function string(value: unknown): string {
    if (typeof value !== "string") throw new IntelligenceHistoryResponseError();
    return value;
}

function nonnegative(value: unknown): number {
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0) throw new IntelligenceHistoryResponseError();
    return value;
}

function collectedAt(value: unknown): string {
    const timestamp = string(value);
    // Core's public datetime model permits naive values; its history writer uses UTC.
    const check = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(timestamp) ? `${timestamp}Z` : timestamp;
    if (timestamp.startsWith("0000-") || evidenceTimestamp(check) === null) throw new IntelligenceHistoryResponseError();
    return timestamp;
}

export function parseIntelligenceHistory(value: unknown): IntelligenceTelemetrySnapshot[] {
    if (!Array.isArray(value)) throw new IntelligenceHistoryResponseError();
    const ids = new Set<string>();
    return value.map(entry => {
        const row = object(entry);
        const id = string(row.id);
        if (ids.has(id)) throw new IntelligenceHistoryResponseError();
        ids.add(id);
        const telemetry = { provider_collection_duration_ms: 0, provider_timeout_seconds: 0, providers: [], ...object(row.telemetry) };
        if (!Array.isArray(telemetry.providers)) throw new IntelligenceHistoryResponseError();
        const providers = telemetry.providers.map(entry => {
            const timing = object(entry);
            if (timing.status !== "completed" && timing.status !== "timed_out" && timing.status !== "failed") throw new IntelligenceHistoryResponseError();
            if (!Number.isSafeInteger(timing.finding_count) || Number(timing.finding_count) < 0) throw new IntelligenceHistoryResponseError();
            return {
                provider_id: string(timing.provider_id), provider_name: string(timing.provider_name), status: timing.status,
                duration_ms: nonnegative(timing.duration_ms), finding_count: timing.finding_count as number,
            } satisfies ProviderCollectionTiming;
        });
        return {
            id, collected_at: collectedAt(row.collected_at), telemetry: {
                provider_collection_duration_ms: nonnegative(telemetry.provider_collection_duration_ms),
                provider_timeout_seconds: nonnegative(telemetry.provider_timeout_seconds), providers,
            },
        };
    });
}
