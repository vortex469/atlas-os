import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { homeAssistantGoldenPlan } from "../test/installationPlan.fixture";
import { getDiscoveryInstallationPlan } from "./discovery";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("getDiscoveryInstallationPlan", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only the item-scoped GET path with an encoded item identity", async () => {
        const data = homeAssistantGoldenPlan();
        vi.mocked(atlas.get).mockResolvedValueOnce({ data });

        await expect(getDiscoveryInstallationPlan("item/with?tampering")).rejects.toThrow("The installation plan could not be read.");
        expect(atlas.get).toHaveBeenCalledWith(
            "/discovery/items/item%2Fwith%3Ftampering/installation-plan",
        );
    });
});
