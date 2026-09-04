import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getOneShotLiveEnqueue, listOneShotLiveEnqueues, parseOneShotLiveEnqueueCollection, parseOneShotLiveEnqueueResult } from "./oneShotLiveEnqueue";
import { indeterminateOneShotLiveEnqueueResultFixture, oneShotLiveEnqueueCollectionFixture, oneShotLiveEnqueueFixture } from "../test/oneShotLiveEnqueue";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("one-shot live enqueue API", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: oneShotLiveEnqueueCollectionFixture }).mockResolvedValue({ data: indeterminateOneShotLiveEnqueueResultFixture });
    });

    it("uses only read endpoints and no mutation client", async () => {
        await listOneShotLiveEnqueues("candidate/id");
        await getOneShotLiveEnqueue("candidate/id", "enqueue/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/one-shot-live-enqueues", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/one-shot-live-enqueues/enqueue%2Fid", { withCredentials: true });
        expect(atlas.get).toHaveBeenCalledTimes(2);
    });

    it("rejects contrary authority, malformed items, sensitive fields, and excess collections", () => {
        expect(parseOneShotLiveEnqueueCollection(oneShotLiveEnqueueCollectionFixture).count).toBe(1);
        expect(parseOneShotLiveEnqueueResult(indeterminateOneShotLiveEnqueueResultFixture).outcome).toBe("indeterminate");
        expect(() => parseOneShotLiveEnqueueCollection({ ...oneShotLiveEnqueueCollectionFixture, retry_allowed: true })).toThrow();
        expect(() => parseOneShotLiveEnqueueCollection({ ...oneShotLiveEnqueueCollectionFixture, items: [{ ...oneShotLiveEnqueueFixture, lifecycle: "dequeued" }] })).toThrow();
        expect(() => parseOneShotLiveEnqueueCollection({ ...oneShotLiveEnqueueCollectionFixture, items: [{ ...oneShotLiveEnqueueFixture, command: "sh -c whoami" }] })).toThrow();
        expect(() => parseOneShotLiveEnqueueCollection({ ...oneShotLiveEnqueueCollectionFixture, items: Array.from({ length: 101 }, () => oneShotLiveEnqueueFixture), count: 101 })).toThrow();
    });
});
