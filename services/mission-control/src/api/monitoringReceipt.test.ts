import { beforeEach, describe, expect, it, vi } from "vitest";
import fixtures from "../test/monitoringReceipts.fixture.json";
import type { ProviderIntentMutationRequest } from "../types/providerManagement";
import { atlas } from "./atlas";
import { putProviderMonitoringIntent } from "./providerManagement";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), put: vi.fn() } }));
const request = fixtures.created.request as ProviderIntentMutationRequest;
const result = fixtures.created.result;

async function read(value: unknown, submitted = request) {
    vi.mocked(atlas.put).mockResolvedValue({ data: value });
    return putProviderMonitoringIntent("proxmox", "qemu", "110", submitted, "fixture-csrf");
}

describe("monitoring save receipts", () => {
    beforeEach(() => vi.clearAllMocks());

    it.each(Object.entries(fixtures))("accepts the native %s receipt", async (_name, fixture) => {
        await expect(read(fixture.result, fixture.request as ProviderIntentMutationRequest)).resolves.toEqual(fixture.result);
    });

    it.each([
        { name: "missing body", value: null },
        { name: "incomplete body", value: { outcome: "created" } },
        { name: "unrelated request", value: { ...result, request_id: `provider-intent-mutation-${"d".repeat(32)}` } },
        { name: "unrelated resource", value: { ...result, resource_id: "111" } },
        { name: "unrelated provider", value: { ...result, provider_id: "docker" } },
        { name: "unrelated type", value: { ...result, resource_type: "lxc" } },
        { name: "unrelated identity", value: { ...result, management_fingerprint: `provider-management-fingerprint-v1:${"b".repeat(64)}` } },
        { name: "unrelated expectation", value: { ...result, expectation: "stopped" } },
        { name: "unknown outcome", value: { ...result, outcome: "accepted" } },
        { name: "contradictory supersession", value: { ...result, superseded_previous_incarnation: true } },
        { name: "missing supersession", value: { ...result, superseded_previous_incarnation: undefined } },
        { name: "nonboolean supersession", value: { ...result, superseded_previous_incarnation: "false" } },
        { name: "wrong created version", value: { ...result, record_version: 2 } },
        { name: "zero version", value: { ...result, record_version: 0 } },
        { name: "fractional version", value: { ...result, record_version: 1.5 } },
        { name: "string version", value: { ...result, record_version: "1" } },
        { name: "unsafe version", value: { ...result, outcome: "updated", record_version: Number.MAX_SAFE_INTEGER + 1 } },
        { name: "wrong update version", value: { ...fixtures.updated.result, record_version: 7 } },
    ])("rejects $name without reflecting response data", async ({ value }) => {
        await expect(read(value)).rejects.toThrow("Monitoring save response could not be confirmed.");
        expect(atlas.put).toHaveBeenCalledTimes(1);
    });

    it("does not confirm versions outside the browser's exact integer range", async () => {
        const submitted = { ...fixtures.updated.request, expected_record_version: Number.MAX_SAFE_INTEGER } as ProviderIntentMutationRequest;
        await expect(read({ ...fixtures.updated.result, record_version: Number.MAX_SAFE_INTEGER + 1 }, submitted)).rejects.toThrow("Monitoring save response could not be confirmed.");
    });

    it("binds the receipt to a snapshot of the request sent before awaiting the response", async () => {
        let finish!: (value: { data: unknown }) => void;
        vi.mocked(atlas.put).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
        const submitted = { ...request };
        const receipt = putProviderMonitoringIntent("proxmox", "qemu", "110", submitted, "fixture-csrf");
        submitted.expectation = "stopped";
        finish({ data: result });
        await expect(receipt).resolves.toEqual(result);
        expect(vi.mocked(atlas.put).mock.calls[0][1]).toEqual(request);
    });

    it("checks an update version against its submitted base", async () => {
        await expect(read({ ...fixtures.updated.result, record_version: 6 }, fixtures.updated.request as ProviderIntentMutationRequest)).rejects.toThrow("Monitoring save response could not be confirmed.");
    });
});
