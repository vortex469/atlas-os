import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getInstallationDispatchHandoff, listInstallationDispatchHandoffs, parseInstallationDispatchHandoff, preserveInstallationDispatchHandoff } from "./installationDispatchHandoff";
import type { InstallationDispatchHandoffCreateV1 } from "../types/installationDispatchHandoff";
import { dispatchHandoffFixture } from "../test/installationDispatchHandoff";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));
describe("installation dispatch handoff API", () => {
    beforeEach(() => vi.resetAllMocks());
    it("strictly parses the closed record and rejects extra, raw, invalid-lifetime, or authority-bearing values", () => {
        expect(parseInstallationDispatchHandoff(dispatchHandoffFixture)).toEqual(dispatchHandoffFixture);
        expect(() => parseInstallationDispatchHandoff({ ...dispatchHandoffFixture, provider_payload: { address: "10.0.0.1" } })).toThrow(/invalid/i);
        expect(() => parseInstallationDispatchHandoff({ ...dispatchHandoffFixture, delivery_authorized: true })).toThrow(/invalid/i);
        expect(() => parseInstallationDispatchHandoff({ ...dispatchHandoffFixture, valid_until: "2026-08-28T12:01:01Z" })).toThrow(/invalid/i);
        expect(() => parseInstallationDispatchHandoff({ ...dispatchHandoffFixture, recipient: { ...dispatchHandoffFixture.recipient, endpoint: "/internal/agent" } })).toThrow(/invalid/i);
    });
    it("uses only guarded create, list, and get routes", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { dispatch_handoffs: [dispatchHandoffFixture] } }).mockResolvedValueOnce({ data: dispatchHandoffFixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: dispatchHandoffFixture });
        await listInstallationDispatchHandoffs(); await getInstallationDispatchHandoff("id/unsafe");
        const body = { schema: "installation-dispatch-handoff-create-v1", execution_request_id: dispatchHandoffFixture.linkage.execution_request_id } satisfies InstallationDispatchHandoffCreateV1;
        await preserveInstallationDispatchHandoff(body, "csrf", "key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/dispatch-handoffs", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/dispatch-handoffs/id%2Funsafe", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/dispatch-handoffs", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "key" } });
    });
});
