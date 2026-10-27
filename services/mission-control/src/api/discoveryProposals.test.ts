import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getDiscoveryItemEvidence, getDiscoveryProposal, listDiscoveryProposals } from "./discovery";

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

    it("reads evidence with an encoded item identity and no write options", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: {
            schema_version: "discovery-merged-item-v1", catalog_item_id: "item/with?tampering",
            curated: { item: { id: "item/with?tampering" } }, conflict_state: "none",
        } });

        await expect(getDiscoveryItemEvidence("item/with?tampering")).resolves.toMatchObject({ catalog_item_id: "item/with?tampering" });

        expect(atlas.get).toHaveBeenCalledWith(
            "/discovery/items/item%2Fwith%3Ftampering/evidence",
        );
    });
});
