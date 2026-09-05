import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getOneShotDequeueWorkerBinding, listOneShotDequeueWorkerBindings, parseOneShotDequeueWorkerBindingCollection, parseOneShotDequeueWorkerBindingResult } from "./oneShotDequeueWorkerBinding";
import { oneShotDequeueWorkerBindingCollectionFixture, oneShotDequeueWorkerBindingResultFixture } from "../test/oneShotDequeueWorkerBinding";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("one-shot dequeue worker binding API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded read endpoints", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: oneShotDequeueWorkerBindingCollectionFixture }).mockResolvedValueOnce({ data: oneShotDequeueWorkerBindingResultFixture });
        await listOneShotDequeueWorkerBindings("candidate/id");
        await getOneShotDequeueWorkerBinding("candidate/id", "binding/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/one-shot-dequeue-worker-bindings", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/one-shot-dequeue-worker-bindings/binding%2Fid", { withCredentials: true });
    });

    it("strictly parses success and rejects authority or sensitive drift", () => {
        expect(parseOneShotDequeueWorkerBindingCollection(oneShotDequeueWorkerBindingCollectionFixture).items).toHaveLength(1);
        expect(parseOneShotDequeueWorkerBindingResult(oneShotDequeueWorkerBindingResultFixture).record?.binding_state).toBe("readiness_gated");
        expect(() => parseOneShotDequeueWorkerBindingResult({ ...oneShotDequeueWorkerBindingResultFixture, record: { ...oneShotDequeueWorkerBindingResultFixture.record!, worker_start_allowed: true } })).toThrow();
        expect(() => parseOneShotDequeueWorkerBindingResult({ ...oneShotDequeueWorkerBindingResultFixture, record: { ...oneShotDequeueWorkerBindingResultFixture.record!, endpoint: "http://internal" } })).toThrow();
        expect(() => parseOneShotDequeueWorkerBindingCollection({ ...oneShotDequeueWorkerBindingCollectionFixture, items: Array.from({ length: 17 }, () => oneShotDequeueWorkerBindingCollectionFixture.items[0]), count: 17 })).toThrow();
    });
});
