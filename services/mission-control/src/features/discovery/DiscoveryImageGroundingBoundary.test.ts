import { describe, expect, it } from "vitest";

import apiSource from "../../api/discovery.ts?raw";
import pageSource from "../../pages/DiscoveryItemPage.tsx?raw";
import componentSource from "./DiscoveryImageGroundingPanel.tsx?raw";

describe("image-grounding presentation boundary", () => {
    it("does not import mutation, Agent, provider-action, execution, or workflow-creation APIs", () => {
        const imports = `${componentSource}\n${pageSource}`
            .split("\n")
            .filter((line) => line.startsWith("import "))
            .join("\n");
        expect(imports).not.toMatch(/atlas-agent|providerAction|api\/execution|createProposal|createCandidate|createWorkflow/i);
    });

    it("keeps the focused client operation GET-only", () => {
        const functionSource = apiSource.slice(apiSource.indexOf("export async function getDiscoveryImageGrounding"));
        const focusedFunction = functionSource.slice(0, functionSource.indexOf("\n}\n") + 3);
        expect(focusedFunction).toContain("atlas.get<DiscoveryImageGroundingProjection>");
        expect(focusedFunction).not.toMatch(/atlas\.(post|put|patch|delete)/);
    });

    it("contains no action controls or proposal/candidate/workflow navigation", () => {
        expect(componentSource).not.toMatch(/<button|<Link|<a\s|to=|navigate\(/);
        expect(componentSource).not.toMatch(/>\s*(Apply|Execute|Update|Pull|Restart|Remediate|Install|Approve|Commit|Deploy)\s*</i);
    });
});
