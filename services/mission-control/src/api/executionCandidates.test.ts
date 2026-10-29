import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { listExecutionCandidates } from "./executionCandidates";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("execution candidate API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("maps the expired eligibility filter to Core's explicit expiry query", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { candidates: [], total: 0, limit: 25, offset: 0, has_more: false } });

        await listExecutionCandidates({ status: "expired" });

        expect(atlas.get).toHaveBeenCalledWith("/execution-candidates", {
            params: {
                status: undefined,
                expired: true,
                category: undefined,
                intent: undefined,
                source_subsystem: undefined,
                target_id: undefined,
                limit: 25,
                offset: 0,
            },
        });
    });
});
