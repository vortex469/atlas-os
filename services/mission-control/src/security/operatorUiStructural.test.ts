import { describe, expect, it } from "vitest";

import operatorAuth from "../api/operatorAuth.ts?raw";
import operatorIntent from "../api/operatorIntent.ts?raw";
import operatorSessionProvider from "../hooks/useOperatorSession.tsx?raw";
import operatorSessionContext from "../hooks/operatorSessionContext.ts?raw";
import operatorLoginPage from "../pages/OperatorLoginPage.tsx?raw";
import maintenanceRequestPage from "../pages/MaintenanceRequestPage.tsx?raw";

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
});
