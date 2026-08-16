import { atlas } from "./atlas";
import type { ProviderMonitoringIntentSuggestionV1 } from "../types/providerManagement";

const fields = [
    "schema_version", "suggestion_id", "provider_id", "resource_type", "resource_id",
    "management_fingerprint", "suggested_expectation", "base_record_version", "source",
    "source_rule", "reason", "advisory_only", "grants_permission", "grants_execution",
] as const;
const fingerprintPattern = /^provider-management-fingerprint-v1:[a-f0-9]{64}$/;
const suggestionIdPattern = /^provider-monitoring-intent-suggestion-id-v1:[a-f0-9]{64}$/;
const resourceIdPattern = /^[1-9][0-9]*$/;

function parseSuggestion(value: unknown): ProviderMonitoringIntentSuggestionV1 {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
        throw new Error("Provider monitoring suggestion is invalid.");
    }
    const item = value as Record<string, unknown>;
    if (Object.keys(item).sort().join("|") !== [...fields].sort().join("|")) {
        throw new Error("Provider monitoring suggestion fields are invalid.");
    }
    if (item.schema_version !== "provider-monitoring-intent-suggestion-v1"
        || typeof item.suggestion_id !== "string" || !suggestionIdPattern.test(item.suggestion_id)
        || item.provider_id !== "proxmox" || item.resource_type !== "qemu"
        || typeof item.resource_id !== "string" || item.resource_id.length > 20 || !resourceIdPattern.test(item.resource_id)
        || typeof item.management_fingerprint !== "string" || !fingerprintPattern.test(item.management_fingerprint)
        || item.suggested_expectation !== "running" || item.base_record_version !== 0
        || item.source !== "provider_intelligence_rule"
        || item.source_rule !== "qemu-observed-running-no-active-intent-v1"
        || item.reason !== "observed_running_without_active_intent"
        || item.advisory_only !== true || item.grants_permission !== false
        || item.grants_execution !== false) {
        throw new Error("Provider monitoring suggestion contract is invalid.");
    }
    return {
        schema_version: item.schema_version,
        suggestion_id: item.suggestion_id as ProviderMonitoringIntentSuggestionV1["suggestion_id"],
        provider_id: item.provider_id,
        resource_type: item.resource_type,
        resource_id: item.resource_id,
        management_fingerprint: item.management_fingerprint as ProviderMonitoringIntentSuggestionV1["management_fingerprint"],
        suggested_expectation: item.suggested_expectation,
        base_record_version: item.base_record_version,
        source: item.source,
        source_rule: item.source_rule,
        reason: item.reason,
        advisory_only: item.advisory_only,
        grants_permission: item.grants_permission,
        grants_execution: item.grants_execution,
    };
}

export function parseProviderMonitoringIntentSuggestions(
    value: unknown,
): ProviderMonitoringIntentSuggestionV1[] {
    if (!Array.isArray(value)) throw new Error("Provider monitoring suggestions are invalid.");
    const parsed = value.map(parseSuggestion);
    const ids = new Set<string>();
    const coordinates = new Set<string>();
    for (const item of parsed) {
        const coordinate = `${item.provider_id}\u0000${item.resource_type}\u0000${item.resource_id}\u0000${item.source_rule}`;
        if (ids.has(item.suggestion_id) || coordinates.has(coordinate)) {
            throw new Error("Provider monitoring suggestions are duplicated.");
        }
        ids.add(item.suggestion_id);
        coordinates.add(coordinate);
    }
    const ordered = [...parsed].sort((left, right) => {
        const provider = left.provider_id.localeCompare(right.provider_id);
        if (provider !== 0) return provider;
        const type = left.resource_type.localeCompare(right.resource_type);
        if (type !== 0) return type;
        const leftResource = BigInt(left.resource_id);
        const rightResource = BigInt(right.resource_id);
        if (leftResource !== rightResource) return leftResource < rightResource ? -1 : 1;
        return left.suggestion_id.localeCompare(right.suggestion_id);
    });
    if (parsed.some((item, index) => item.suggestion_id !== ordered[index]?.suggestion_id)) {
        throw new Error("Provider monitoring suggestions are not canonically ordered.");
    }
    return parsed;
}

export async function getProviderMonitoringIntentSuggestions(
    providerId: string,
): Promise<ProviderMonitoringIntentSuggestionV1[]> {
    const response = await atlas.get<unknown>(
        `/providers/${encodeURIComponent(providerId)}/management/operator/monitoring-suggestions`,
        { withCredentials: true },
    );
    return parseProviderMonitoringIntentSuggestions(response.data);
}
