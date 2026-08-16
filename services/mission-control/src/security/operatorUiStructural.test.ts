import { describe, expect, it } from "vitest";

import operatorAuth from "../api/operatorAuth.ts?raw";
import operatorIntent from "../api/operatorIntent.ts?raw";
import operatorSessionProvider from "../hooks/useOperatorSession.tsx?raw";
import operatorSessionContext from "../hooks/operatorSessionContext.ts?raw";
import operatorLoginPage from "../pages/OperatorLoginPage.tsx?raw";
import maintenanceRequestPage from "../pages/MaintenanceRequestPage.tsx?raw";
import providerIntentEditor from "../components/ProviderIntentEditor.tsx?raw";
import providerResources from "../components/ProviderResources.tsx?raw";

describe("operator UI structural boundary", () => {
    it("contains no dispatch, arbitrary action, identity header, bearer, or browser-storage path", () => {
        const source = [
            operatorAuth,
            operatorIntent,
            operatorSessionProvider,
            operatorSessionContext,
            operatorLoginPage,
            maintenanceRequestPage,
        ].join("\n");
        for (const forbidden of [
            "operational-dispatch",
            "provider_action_id",
            "localStorage",
            "sessionStorage",
            "Authorization",
            "Bearer",
            "X-Atlas-Operator",
            "X-User",
        ]) {
            expect(source).not.toContain(forbidden);
        }
    });

    it("keeps monitoring presentation isolated from execution, legacy writes, and proposals", () => {
        const source = [providerResources, providerIntentEditor].join("\n");
        for (const forbidden of [
            "runProviderAction",
            "operational-dispatch",
            "execution-candidates",
            "planning",
            "approval",
            "discoveryProposals",
            "proposal_id",
            "/policies",
            "policies.yaml",
            "Start VM",
            "Restart to match",
            "Apply state",
            "Remediate",
            "Fix automatically",
        ]) {
            expect(source).not.toContain(forbidden);
        }
    });
});
