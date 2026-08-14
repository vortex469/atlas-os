import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getOperatorIntentResources, requestRestartServiceIntent } from "./operatorIntent";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

describe("operator intent API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("loads only the authenticated sanitized selector", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { resources: [] } });
        await getOperatorIntentResources();
        expect(atlas.get).toHaveBeenCalledWith(
            "/execution-candidates/operator-intents/resources",
            { withCredentials: true },
        );
    });

    it("posts the exact fixed tuple, CAS fingerprint, and policy expiry", async () => {
        vi.mocked(atlas.post).mockResolvedValue({ data: { candidate_id: "candidate-1" } });
        await requestRestartServiceIntent(
            "110",
            "operational-target-fingerprint-v1:abc",
            "csrf",
            new Date("2026-08-14T00:00:00Z"),
        );
        expect(atlas.post).toHaveBeenCalledWith(
            "/execution-candidates/operator-intents",
            {
                execution_intent: "restart-service",
                provider_id: "proxmox",
                resource_id: "110",
                resource_type: "qemu",
                expected_target_fingerprint: "operational-target-fingerprint-v1:abc",
                expires_at: "2026-08-14T00:15:00.000Z",
            },
            { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf" } },
        );
        const payload = vi.mocked(atlas.post).mock.calls[0][1] as Record<string, unknown>;
        expect(payload).not.toHaveProperty("provider_action_id");
        expect(payload).not.toHaveProperty("parameters");
        expect(payload).not.toHaveProperty("command");
    });
});
