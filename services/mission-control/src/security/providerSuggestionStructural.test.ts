import { describe, expect, it } from "vitest";

import suggestionApi from "../api/providerIntentSuggestions.ts?raw";
import suggestionCard from "../components/ProviderIntentSuggestionCard.tsx?raw";
import providerResources from "../components/ProviderResources.tsx?raw";

describe("provider suggestion authority isolation", () => {
    it("contains no alternate mutation, execution, proposal, or prose-conversion calls", () => {
        const source = [suggestionApi, suggestionCard, providerResources].join("\n");
        for (const forbidden of [
            "runProviderAction",
            "createOperational",
            "operationalDispatch",
            "createExecutionCandidate",
            "planning",
            "approval",
            "applyDiscovery",
            "proposalNavigation",
            "intent_hint",
            "/expectation",
            "recommendation",
            ".details",
            "writeYaml",
        ]) {
            expect(source).not.toContain(forbidden);
        }
    });

    it("keeps the existing P3 client as the only mutation call", () => {
        expect(providerResources.match(/putProviderMonitoringIntent\(/g)).toHaveLength(1);
        expect(suggestionCard).not.toContain("putProviderMonitoringIntent");
    });
});
