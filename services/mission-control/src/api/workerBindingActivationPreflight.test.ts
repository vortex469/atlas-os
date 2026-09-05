import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getWorkerBindingActivationPreflight, listWorkerBindingActivationPreflights, parseWorkerBindingActivationPreflightCollection, parseWorkerBindingActivationPreflightResult } from "./workerBindingActivationPreflight";
import { workerBindingActivationPreflightCollectionFixture, workerBindingActivationPreflightResultFixture } from "../test/workerBindingActivationPreflight";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("worker binding activation preflight API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded read endpoints", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: workerBindingActivationPreflightCollectionFixture }).mockResolvedValueOnce({ data: workerBindingActivationPreflightResultFixture });
        await listWorkerBindingActivationPreflights("candidate/id");
        await getWorkerBindingActivationPreflight("candidate/id", "preflight/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/worker-binding-activation-preflights", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/worker-binding-activation-preflights/preflight%2Fid", { withCredentials: true });
    });

    it("strictly parses success and rejects authority or sensitive drift", () => {
        expect(parseWorkerBindingActivationPreflightCollection(workerBindingActivationPreflightCollectionFixture).items).toHaveLength(1);
        expect(parseWorkerBindingActivationPreflightResult(workerBindingActivationPreflightResultFixture).record?.preflight_state).toBe("readiness_gated");
        expect(() => parseWorkerBindingActivationPreflightResult({ ...workerBindingActivationPreflightResultFixture, record: { ...workerBindingActivationPreflightResultFixture.record!, binding_activation_allowed: true } })).toThrow();
        expect(() => parseWorkerBindingActivationPreflightResult({ ...workerBindingActivationPreflightResultFixture, record: { ...workerBindingActivationPreflightResultFixture.record!, runtime_endpoint: "http://internal" } })).toThrow();
        expect(() => parseWorkerBindingActivationPreflightResult({ ...workerBindingActivationPreflightResultFixture, status: { ...workerBindingActivationPreflightResultFixture.status!, candidate_record_id: "00000000-0000-4000-8000-000000000099" } })).toThrow();
        expect(() => parseWorkerBindingActivationPreflightCollection({ ...workerBindingActivationPreflightCollectionFixture, items: Array.from({ length: 101 }, () => workerBindingActivationPreflightCollectionFixture.items[0]), count: 101 })).toThrow();
        expect(() => parseWorkerBindingActivationPreflightCollection({ ...workerBindingActivationPreflightCollectionFixture, operator_id: "operator-b" })).toThrow();
    });
});
