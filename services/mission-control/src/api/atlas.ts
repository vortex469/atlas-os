import axios from "axios";
import { parse } from "yaml";

import type { DeploymentAnalysisResponse } from "../features/forge/types";
import type { DoctorReport } from "../types/doctor";
import type {
    IntelligenceTelemetryExportFormat,
    IntelligenceTelemetryHistoryQuery,
    IntelligenceTelemetryPruneResult,
    IntelligenceTelemetryRetentionSummary,
} from "../types/ace";
import type {
    AtlasAPIError,
    ProviderAction,
    ProviderActionRequest,
    ProviderActionResult,
} from "../types/providerAction";
import type {
    ActionHistoryExportFormat,
    ActionHistoryQuery,
    ProviderActionAuditEntry,
    ProviderActionHistoryPage,
    ProviderActionHistorySummary,
    ProviderActionHistoryProvider,
    ProviderActionPruneResult,
} from "../types/actionHistory";

const ATLAS_API_BASE_URL =
    import.meta.env.VITE_ATLAS_API_BASE_URL ?? "/api/v1";

export const atlas = axios.create({
    baseURL: ATLAS_API_BASE_URL,
    timeout: 15_000,
    headers: {
        Accept: "application/json",
    },
});

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
    return typeof value === "string" && value.trim().length > 0;
}

function isSafeRouteId(value: unknown): value is string {
    if (!isNonEmptyString(value)) return false;
    try {
        encodeURIComponent(value);
        return true;
    } catch {
        return false;
    }
}

function isDateTime(value: unknown): value is string {
    return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isNullableDateTime(value: unknown): value is string | null {
    return value === null || isDateTime(value);
}

function isStringArray(value: unknown): value is string[] {
    return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function parseProviderActionHistoryEntry(value: unknown): ProviderActionAuditEntry {
    if (!isRecord(value)
        || !isSafeRouteId(value.id)
        || !isNonEmptyString(value.provider_id)
        || !isNonEmptyString(value.provider_name)
        || !isNonEmptyString(value.action_id)
        || !isNonEmptyString(value.action_label)
        || (value.status !== "succeeded" && value.status !== "failed")
        || typeof value.success !== "boolean"
        || typeof value.message !== "string"
        || typeof value.confirmed !== "boolean"
        || typeof value.destructive !== "boolean"
        || !isStringArray(value.parameter_names)
        || !(value.request_id === null || typeof value.request_id === "string")
        || !isDateTime(value.started_at)
        || !isDateTime(value.completed_at)
        || typeof value.duration_ms !== "number"
        || !Number.isFinite(value.duration_ms)
        || value.duration_ms < 0) {
        throw new Error("Malformed provider action history entry payload.");
    }

    return value as unknown as ProviderActionAuditEntry;
}

function parseProviderActionHistoryPage(value: unknown): ProviderActionHistoryPage {
    if (!isRecord(value) || !Array.isArray(value.items)
        || typeof value.total !== "number" || !Number.isSafeInteger(value.total) || value.total < 0
        || typeof value.offset !== "number" || !Number.isSafeInteger(value.offset) || value.offset < 0
        || typeof value.limit !== "number" || !Number.isSafeInteger(value.limit) || value.limit < 1
        || typeof value.has_more !== "boolean"
        || value.total < value.items.length) {
        throw new Error("Malformed provider action history page payload.");
    }

    const entries = value.items.map(parseProviderActionHistoryEntry);
    if (new Set(entries.map((entry) => entry.id)).size !== entries.length) {
        throw new Error("Malformed provider action history page payload.");
    }

    return { ...value, items: entries } as ProviderActionHistoryPage;
}

function parseProviderActionHistorySummary(value: unknown): ProviderActionHistorySummary {
    if (!isRecord(value)
        || typeof value.entry_count !== "number" || !Number.isSafeInteger(value.entry_count) || value.entry_count < 0
        || typeof value.max_entries !== "number" || !Number.isSafeInteger(value.max_entries) || value.max_entries < 1
        || typeof value.retention_days !== "number" || !Number.isSafeInteger(value.retention_days) || value.retention_days < 1
        || !isNullableDateTime(value.oldest_entry_at)
        || !isNullableDateTime(value.newest_entry_at)) {
        throw new Error("Malformed provider action history summary payload.");
    }

    return value as unknown as ProviderActionHistorySummary;
}

function parseProviderActionHistoryProviders(value: unknown): ProviderActionHistoryProvider[] {
    if (!Array.isArray(value)) throw new Error("Malformed provider action history providers payload.");
    const providers: ProviderActionHistoryProvider[] = [];
    const ids = new Set<string>();
    for (const item of value) {
        if (!isRecord(item) || !isNonEmptyString(item.id) || !isNonEmptyString(item.name) || ids.has(item.id)) {
            throw new Error("Malformed provider action history providers payload.");
        }
        ids.add(item.id);
        providers.push({ id: item.id, name: item.name });
    }
    return providers;
}

export async function analyzeCompose(
    compose: string,
    reference: string,
): Promise<DeploymentAnalysisResponse> {
    const response =
        await atlas.post<DeploymentAnalysisResponse>(
            "/analysis/deployments",
            {
                source: "compose",
                reference,
                document: parse(compose),
            },
        );

    return response.data;
}

export async function getProviderActions(
    providerId: string,
): Promise<ProviderAction[]> {
    const response = await atlas.get<ProviderAction[]>(
        `/providers/${encodeURIComponent(providerId)}/actions`,
    );

    return response.data;
}

export async function runProviderAction(
    providerId: string,
    actionId: string,
    request: ProviderActionRequest = {},
): Promise<ProviderActionResult> {
    const response = await atlas.post<ProviderActionResult>(
        `/providers/${encodeURIComponent(
            providerId,
        )}/actions/${encodeURIComponent(actionId)}`,
        {
            confirmed: request.confirmed ?? false,
            parameters: request.parameters ?? {},
        },
    );

    return response.data;
}

export async function getProviderActionHistory(
    options: ActionHistoryQuery = {},
): Promise<ProviderActionHistoryPage> {
    const response = await atlas.get<ProviderActionHistoryPage>(
        "/ops/actions/page",
        {
            params: {
                limit: options.limit ?? 25,
                offset: options.offset ?? 0,
                search: options.search,
                status: options.status,
                provider_id: options.providerId,
                completed_from: options.completedFrom,
                completed_to: options.completedTo,
            },
        },
    );

    return parseProviderActionHistoryPage(response.data);
}

export async function getAtlasDoctorReport(): Promise<DoctorReport> {
    const response = await atlas.get<DoctorReport>("/ops/doctor");

    return response.data;
}

export async function exportIntelligenceTelemetryHistory(
    format: IntelligenceTelemetryExportFormat,
    options: IntelligenceTelemetryHistoryQuery = {},
): Promise<Blob> {
    const response = await atlas.get<Blob>(
        "/intelligence/telemetry/history/export",
        {
            params: {
                format,
                limit: options.limit ?? 500,
                provider_id: options.providerId,
                status: options.status,
                collected_from: options.collectedFrom,
                collected_to: options.collectedTo,
            },
            responseType: "blob",
        },
    );

    return response.data;
}

export async function getIntelligenceTelemetryRetention(): Promise<IntelligenceTelemetryRetentionSummary> {
    const response =
        await atlas.get<IntelligenceTelemetryRetentionSummary>(
            "/intelligence/telemetry/history/retention",
        );
    return response.data;
}

export async function pruneIntelligenceTelemetryHistory(): Promise<IntelligenceTelemetryPruneResult> {
    const response =
        await atlas.post<IntelligenceTelemetryPruneResult>(
            "/intelligence/telemetry/history/prune",
            { confirmed: true },
        );
    return response.data;
}

export async function getProviderActionHistoryEntry(
    entryId: string,
): Promise<ProviderActionAuditEntry> {
    const response = await atlas.get<ProviderActionAuditEntry>(
        `/ops/actions/${encodeURIComponent(entryId)}`,
    );

    return parseProviderActionHistoryEntry(response.data);
}

export async function getProviderActionHistorySummary(): Promise<ProviderActionHistorySummary> {
    const response =
        await atlas.get<ProviderActionHistorySummary>(
            "/ops/actions/summary",
        );

    return parseProviderActionHistorySummary(response.data);
}

export async function exportProviderActionHistory(
    format: ActionHistoryExportFormat,
    options: ActionHistoryQuery = {},
): Promise<Blob> {
    const response = await atlas.get<Blob>(
        "/ops/actions/export",
        {
            params: {
                format,
                status: options.status,
                provider_id: options.providerId,
                completed_from: options.completedFrom,
                completed_to: options.completedTo,
                search: options.search,
            },
            responseType: "blob",
        },
    );

    return response.data;
}

export async function getProviderActionHistoryProviders(): Promise<ProviderActionHistoryProvider[]> {
    const response = await atlas.get<
        ProviderActionHistoryProvider[]
    >("/ops/actions/providers");

    return parseProviderActionHistoryProviders(response.data);
}

export async function pruneProviderActionHistory(): Promise<ProviderActionPruneResult> {
    const response =
        await atlas.post<ProviderActionPruneResult>(
            "/ops/actions/prune",
            { confirmed: true },
        );

    return response.data;
}

export function getAtlasErrorMessage(
    error: unknown,
    fallback: string,
): string {
    if (!axios.isAxiosError<AtlasAPIError>(error)) {
        return fallback;
    }

    const apiMessage = error.response?.data?.error?.message;

    if (
        typeof apiMessage === "string" &&
        apiMessage.trim().length > 0
    ) {
        return apiMessage;
    }

    if (error.code === "ECONNABORTED") {
        return "Atlas Core did not respond before the request timed out.";
    }

    return fallback;
}
