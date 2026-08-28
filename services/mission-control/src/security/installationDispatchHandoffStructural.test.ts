import { describe, expect, it } from "vitest";
import api from "../api/installationDispatchHandoff.ts?raw";
import view from "../features/discovery/InstallationDispatchHandoffs.tsx?raw";
import executionRequestView from "../features/discovery/InstallationExecutionRequests.tsx?raw";

describe("installation dispatch handoff authority isolation", () => {
    it("contains only the guarded Core list, get, and explicit create calls", () => {
        expect(api.match(/atlas\.get<unknown>/g)).toHaveLength(2);
        expect(api.match(/atlas\.post<unknown>/g)).toHaveLength(1);
        expect(api.match(/\/installation\/dispatch-handoffs/g)).toHaveLength(3);
        expect(api).not.toMatch(/atlas\.(?:put|patch|delete)/);
        expect(api).not.toMatch(/agent-api|atlasAgent|worker|workflow|provider|repository/);
    });

    it("has no delivery, execution, deployment, workflow, or rollback surface", () => {
        expect(view).toContain("Prepared only; not sent to Agent; no work has started.");
        expect(view).toContain("Home Assistant remains blocked and non-executable");
        expect(view).not.toMatch(/<form|<Link|navigate\(|href=/);
        expect(executionRequestView).not.toMatch(/\/installation\/dispatch-handoffs/);
        for (const label of ["Install", "Run", "Execute", "Deploy", "Dispatch", "Deliver", "Send to Agent", "Start workflow", "Rollback"]) {
            expect(view).not.toMatch(new RegExp(`>\\s*${label}(?:\\s+now)?\\s*<`, "i"));
        }
    });
});
