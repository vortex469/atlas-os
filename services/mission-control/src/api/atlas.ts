import axios from "axios";
import { parse } from "yaml";

import type { DeploymentAnalysisResponse } from "../features/forge/types";
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
): Promise<ProviderActionAuditEntry[]> {
    const response = await atlas.get<ProviderActionAuditEntry[]>(
        "/ops/actions",
        {
            params: {
                limit: options.limit ?? 100,
                status: options.status,
                provider_id: options.providerId,
                completed_from: options.completedFrom,
                completed_to: options.completedTo,
            },
        },
    );

    return response.data;
}

export async function getProviderActionHistorySummary(): Promise<ProviderActionHistorySummary> {
    const response =
        await atlas.get<ProviderActionHistorySummary>(
            "/ops/actions/summary",
        );

    return response.data;
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

    return response.data;
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
