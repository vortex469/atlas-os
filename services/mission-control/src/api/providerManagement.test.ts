import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import {
    getAuthenticatedProviderManagement,
    getProviderManagement,
    parseProviderManagementV2,
    putProviderMonitoringIntent,
} from "./providerManagement";

vi.mock("./atlas", () => ({
    atlas: { get: vi.fn(), put: vi.fn() },
}));

describe("provider management API", () => {
    beforeEach(() => vi.clearAllMocks());

    it("loads authenticated v3 management with session cookies", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { schema_version: "provider-management-v3" } });
        await getAuthenticatedProviderManagement("proxmox");
        expect(atlas.get).toHaveBeenCalledWith(
            "/providers/proxmox/management/operator",
            { withCredentials: true },
        );
    });

    it("sends only the bounded mutation body with CSRF and cookies", async () => {
        vi.mocked(atlas.put).mockResolvedValue({ data: { outcome: "created" } });
        const request = {
            request_id: `provider-intent-mutation-${"a".repeat(32)}`,
            expected_management_fingerprint: `provider-management-fingerprint-v1:${"b".repeat(64)}`,
            expectation: "running" as const,
            expected_record_version: 0,
            acknowledge_monitoring_suppression: false,
        };
        await putProviderMonitoringIntent("proxmox", "qemu", "110", request, "csrf");
        expect(atlas.put).toHaveBeenCalledWith(
            "/providers/proxmox/management/resources/qemu/110/monitoring-intent",
            request,
            {
                withCredentials: true,
                headers: { "X-Atlas-CSRF-Token": "csrf" },
            },
        );
        expect(request).not.toHaveProperty("operator_id");
        expect(request).not.toHaveProperty("intent_id");
        expect(request).not.toHaveProperty("digest");
    });
});
    const publicDescriptor = {
        schema_version: "provider-management-v2",
        provider_id: "proxmox",
        provider_name: "Proxmox",
        sections: ["connection", "discovery", "resources", "monitoring", "diagnostics", "actions"].map((section) => ({
            section,
            availability: "available",
            read_only_descriptor: true,
            grants_permission: false,
            grants_execution: false,
        })),
        resource_types: [],
        resources: [],
        provider_intent_activation: "activated",
        provider_intent_authority_status: "available",
        grants_permission: false,
        grants_execution: false,
    };

    it("loads and validates public v2 management without authentication options", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: publicDescriptor });
        await expect(getProviderManagement("proxmox")).resolves.toEqual(publicDescriptor);
        expect(atlas.get).toHaveBeenCalledWith("/providers/proxmox/management");
    });

    it.each([
        [{ ...publicDescriptor, schema_version: "provider-management-v3" }],
        [{ ...publicDescriptor, grants_permission: true }],
        [{ ...publicDescriptor, caller_has_provider_intent_update: true }],
        [{ ...publicDescriptor, provider_intent_authority_status: "unknown" }],
    ])("rejects malformed or authority-expanding public responses", (value) => {
        expect(() => parseProviderManagementV2(value)).toThrow();
    });

    it("rejects contradictory managed-resource semantics", () => {
        const contradictory = {
            ...publicDescriptor,
            resources: [{
                provider_id: "proxmox",
                resource_id: "110",
                resource_type: "qemu",
                display_name: "Frigate",
                current_state: "running",
                missing: false,
                identity_assurance: "authoritative",
                management_fingerprint: `provider-management-fingerprint-v1:${"a".repeat(64)}`,
                intent_authority: "provider_intent",
                intent_status: "needs_review",
                intent_reason: "matching_active_intent",
                expectation: null,
                record_version: null,
                legacy_review_available: false,
                legacy_expectation: null,
                replacement_detected: false,
                mutation_available: false,
                operationally_requestable: false,
                grants_execution: false,
            }],
        };
        expect(() => parseProviderManagementV2(contradictory)).toThrow(/contradict/);
    });

    it("propagates public API errors", async () => {
        vi.mocked(atlas.get).mockRejectedValue(new Error("offline"));
        await expect(getProviderManagement("proxmox")).rejects.toThrow("offline");
    });
