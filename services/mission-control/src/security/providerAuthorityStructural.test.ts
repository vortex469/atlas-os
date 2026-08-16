import { describe, expect, it } from "vitest";

import findingCard from "../components/FindingCard.tsx?raw";
import providerPolicyDetails from "../components/ProviderPolicyDetails.tsx?raw";
import recommendationCard from "../components/RecommendationCard.tsx?raw";
import providerResources from "../components/ProviderResources.tsx?raw";

describe("provider-page authority structural boundary", () => {
    it("keeps diagnostics, recommendations, and policy evidence read-only", () => {
        const source = [findingCard, providerPolicyDetails, recommendationCard].join("\n");
        for (const forbidden of [
            "putProviderMonitoringIntent",
            "runProviderAction",
            "operational-dispatch",
            "execution-candidates",
            "createOperational",
            "proposal_id",
            "applyProposal",
            "atlas.put",
            "atlas.post",
            "writeFile",
            "yaml.stringify",
        ]) expect(source).not.toContain(forbidden);
    });

    it("keeps monitoring isolated from provider actions and operational requests", () => {
        for (const forbidden of ["runProviderAction", "createOperational", "execution-candidates", "proposal_id"]) {
            expect(providerResources).not.toContain(forbidden);
        }
    });
});
