import { describe, expect, it } from "vitest";
import api from "../api/installationExecutionRequest.ts?raw";
import view from "../features/discovery/InstallationExecutionRequests.tsx?raw";
import approvalView from "../features/discovery/InstallationApprovalIntents.tsx?raw";

describe("installation execution request authority isolation", () => {
    it("contains only guarded Core list/get/create calls and no Agent or other mutation", () => {
        expect(api.match(/atlas\.get<unknown>/g)).toHaveLength(2);
        expect(api.match(/atlas\.post<unknown>/g)).toHaveLength(1);
        expect(api.match(/\/installation\/execution-requests/g)).toHaveLength(3);
        expect(api).not.toMatch(/atlas\.(?:put|patch|delete)/);
        expect(api).not.toMatch(/agent-api|atlasAgent|workflow|provider|repository/);
    });
    it("has explicit non-authorizing copy and no navigation or prohibited controls", () => {
        expect(view).toContain("Non-executing; Agent evidence is operator-submitted; no work has started.");
        expect(view).toContain("Home Assistant remains blocked and non-executable");
        expect(view).not.toMatch(/<form|<Link|navigate\(|href=/);
        expect(approvalView).not.toMatch(/\/installation\/execution-requests/);
        for (const label of ["Install", "Run", "Execute", "Deploy", "Dispatch", "Send to Agent", "Start workflow", "Rollback"]) {
            expect(view).not.toMatch(new RegExp(`>\\s*${label}(?:\\s+now)?\\s*<`, "i"));
        }
    });
});
