import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getDiscoveryImageGrounding } from "./discovery";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("getDiscoveryImageGrounding", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only GET against the encoded P2 projection route", async () => {
        const data = {
            schema_version: "discovery-image-grounding-projection-v1",
            catalog_item_id: "item/id",
            status: "no_deployment_binding",
            release_version: null,
            deployment_binding: null,
            observed_image: null,
            accepted_evidence: [],
        };
        vi.mocked(atlas.get).mockResolvedValue({ data });

        await expect(getDiscoveryImageGrounding("item/id")).resolves.toBe(data);
        expect(atlas.get).toHaveBeenCalledWith("/discovery/items/item%2Fid/image-grounding");
        expect(Object.keys(atlas)).toEqual(["get"]);
    });
});
