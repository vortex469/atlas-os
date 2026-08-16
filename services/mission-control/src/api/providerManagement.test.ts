import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import {
    getAuthenticatedProviderManagement,
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
