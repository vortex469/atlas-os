import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getInstallationExecutionRequest, listInstallationExecutionRequests, parseInstallationExecutionRequest, recordInstallationExecutionRequest } from "./installationExecutionRequest";
import type { InstallationExecutionRequestCreateV1 } from "../types/installationExecutionRequest";
import { executionRequestFixture } from "../test/installationExecutionRequest";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));
describe("installation execution request API", () => {
    beforeEach(() => vi.resetAllMocks());
    it("strictly parses the closed record and rejects extra, raw, or authority-bearing values", () => {
        expect(parseInstallationExecutionRequest(executionRequestFixture)).toEqual(executionRequestFixture);
        expect(() => parseInstallationExecutionRequest({ ...executionRequestFixture, provider_payload: { address: "10.0.0.1" } })).toThrow(/invalid/i);
        expect(() => parseInstallationExecutionRequest({ ...executionRequestFixture, execution_authorized: true })).toThrow(/invalid/i);
        expect(() => parseInstallationExecutionRequest({ ...executionRequestFixture, linkage: { ...executionRequestFixture.linkage, destination_fingerprint: "secret" } })).toThrow(/invalid/i);
        expect(() => parseInstallationExecutionRequest({ ...executionRequestFixture, recorded_at: "2026-08-28T12:00:00.001Z" })).toThrow(/invalid/i);
    });
    it("uses only guarded create, list, and get routes", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { execution_requests: [executionRequestFixture] } }).mockResolvedValueOnce({ data: executionRequestFixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: executionRequestFixture });
        await listInstallationExecutionRequests(); await getInstallationExecutionRequest("id/unsafe");
        const body = { schema: "installation-execution-request-create-v1" } as InstallationExecutionRequestCreateV1;
        await recordInstallationExecutionRequest(body, "csrf", "key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/execution-requests", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/execution-requests/id%2Funsafe", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/execution-requests", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "key" } });
    });
});
