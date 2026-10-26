import type { ProviderActionResult } from "../types/providerAction";

export class ProviderActionResponseError extends Error {
    constructor() {
        super("The provider action response could not confirm the requested outcome.");
    }
}

function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function parseProviderActionResult(value: unknown, providerId: string, actionId: string): ProviderActionResult {
    if (!record(value)) throw new ProviderActionResponseError();
    const data: Record<string, unknown> = { data: {}, warnings: [], ...value };
    if (data.provider_id !== providerId || data.action_id !== actionId
        || (data.status !== "succeeded" && data.status !== "failed")
        || typeof data.success !== "boolean" || data.success !== (data.status === "succeeded")
        || typeof data.message !== "string" || !record(data.data)
        || !Array.isArray(data.warnings) || !data.warnings.every((warning) => typeof warning === "string")) {
        throw new ProviderActionResponseError();
    }
    return { provider_id: providerId, action_id: actionId, status: data.status, success: data.success,
        message: data.message, data: data.data, warnings: data.warnings };
}
