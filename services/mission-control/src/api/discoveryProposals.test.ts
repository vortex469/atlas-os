import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getDiscoveryProposal, listDiscoveryProposals } from "./discovery";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("Discovery proposal API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses bounded GET-only proposal reads", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { proposals: [] } });
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { proposal_id: "proposal" } });

        await listDiscoveryProposals(25);
        await getDiscoveryProposal("proposal/with?tampering");

        expect(atlas.get).toHaveBeenNthCalledWith(1, "/discovery/proposals", {
            params: { limit: 25 },
        });
        expect(atlas.get).toHaveBeenNthCalledWith(
            2,
            "/discovery/proposals/proposal%2Fwith%3Ftampering",
        );
    });
});
