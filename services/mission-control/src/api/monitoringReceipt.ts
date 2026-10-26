import type { ProviderIntentMutationRequest, ProviderIntentMutationResult } from "../types/providerManagement";

function invalid(): never {
    throw new Error("Monitoring save response could not be confirmed.");
}

export function parseMonitoringReceipt(
    value: unknown,
    providerId: string,
    resourceType: string,
    resourceId: string,
    request: ProviderIntentMutationRequest,
): ProviderIntentMutationResult {
    if (typeof value !== "object" || value === null || Array.isArray(value)) invalid();
    const result = value as Record<string, unknown>;
    if ((result.outcome !== "created" && result.outcome !== "updated" && result.outcome !== "rebound")
        || typeof result.request_id !== "string"
        || !/^provider-intent-mutation-[a-f0-9]{32,64}$/.test(result.request_id)
        || result.request_id !== request.request_id
        || result.provider_id !== "proxmox" || result.provider_id !== providerId
        || result.resource_type !== "qemu" || result.resource_type !== resourceType
        || typeof result.resource_id !== "string" || !/^[0-9]{1,20}$/.test(result.resource_id)
        || result.resource_id !== resourceId
        || typeof result.management_fingerprint !== "string"
        || !/^provider-management-fingerprint-v1:[a-f0-9]{64}$/.test(result.management_fingerprint)
        || result.management_fingerprint !== request.expected_management_fingerprint
        || (result.expectation !== "running" && result.expectation !== "stopped" && result.expectation !== "ignored")
        || result.expectation !== request.expectation
        || typeof result.record_version !== "number" || !Number.isSafeInteger(result.record_version)
        || result.record_version < 1
        || typeof result.superseded_previous_incarnation !== "boolean"
        || result.superseded_previous_incarnation !== (result.outcome === "rebound")
    ) invalid();
    if (!Number.isSafeInteger(request.expected_record_version) || request.expected_record_version < 0
        || result.record_version !== request.expected_record_version + 1
        || (result.outcome === "updated" ? request.expected_record_version < 1 : result.record_version !== 1)
    ) invalid();
    return {
        outcome: result.outcome,
        request_id: result.request_id,
        provider_id: result.provider_id,
        resource_type: result.resource_type,
        resource_id: result.resource_id,
        management_fingerprint: result.management_fingerprint,
        expectation: result.expectation,
        record_version: result.record_version,
        superseded_previous_incarnation: result.superseded_previous_incarnation,
    };
}
