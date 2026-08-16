import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import {
    getProviderMonitoringIntentSuggestions,
    parseProviderMonitoringIntentSuggestions,
} from "./providerIntentSuggestions";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

const valid = {
    schema_version: "provider-monitoring-intent-suggestion-v1",
    suggestion_id: `provider-monitoring-intent-suggestion-id-v1:${"a".repeat(64)}`,
    provider_id: "proxmox",
    resource_type: "qemu",
    resource_id: "110",
    management_fingerprint: `provider-management-fingerprint-v1:${"b".repeat(64)}`,
    suggested_expectation: "running",
    base_record_version: 0,
    source: "provider_intelligence_rule",
    source_rule: "qemu-observed-running-no-active-intent-v1",
    reason: "observed_running_without_active_intent",
    advisory_only: true,
    grants_permission: false,
    grants_execution: false,
};

describe("provider monitoring suggestion API", () => {
    beforeEach(() => vi.clearAllMocks());

    it("uses the authenticated read-only endpoint without CSRF", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: [valid] });
        await expect(getProviderMonitoringIntentSuggestions("proxmox")).resolves.toEqual([valid]);
        expect(atlas.get).toHaveBeenCalledWith(
            "/providers/proxmox/management/operator/monitoring-suggestions",
            { withCredentials: true },
        );
    });

    it.each([
        [{ ...valid, schema_version: "provider-monitoring-intent-suggestion-v2" }],
        [{ ...valid, provider_id: "docker" }],
        [{ ...valid, resource_type: "lxc" }],
        [{ ...valid, resource_id: "0110" }],
        [{ ...valid, resource_id: "1".repeat(21) }],
        [{ ...valid, management_fingerprint: "vmgenid-secret" }],
        [{ ...valid, suggested_expectation: "stopped" }],
        [{ ...valid, base_record_version: 1 }],
        [{ ...valid, advisory_only: false }],
        [{ ...valid, grants_permission: true }],
        [{ ...valid, grants_execution: true }],
        [{ ...valid, details: {} }],
    ])("rejects malformed or contradictory entries", (entry) => {
        expect(() => parseProviderMonitoringIntentSuggestions([entry])).toThrow();
    });

    it("rejects duplicate IDs and resource-rule coordinates", () => {
        expect(() => parseProviderMonitoringIntentSuggestions([valid, valid])).toThrow(/duplicated/);
        expect(() => parseProviderMonitoringIntentSuggestions([
            valid,
            { ...valid, suggestion_id: `provider-monitoring-intent-suggestion-id-v1:${"c".repeat(64)}` },
        ])).toThrow(/duplicated/);
    });

    it("rejects noncanonical collection ordering", () => {
        const second = {
            ...valid,
            suggestion_id: `provider-monitoring-intent-suggestion-id-v1:${"c".repeat(64)}`,
            resource_id: "200",
        };
        expect(() => parseProviderMonitoringIntentSuggestions([second, valid])).toThrow(/ordered/);
        expect(parseProviderMonitoringIntentSuggestions([valid, second])).toEqual([valid, second]);
    });
});
