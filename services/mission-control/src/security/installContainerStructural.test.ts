import { describe, expect, it } from "vitest";

import agentApi from "../api/atlas-agent.ts?raw";
import agentPanel from "../components/AtlasAgentPanel.tsx?raw";
import validationPanel from "../components/InstallContainerValidationPanel.tsx?raw";

describe("install-container validation authority isolation", () => {
    it("has only the existing Agent info read and no validation mutation call", () => {
        expect(agentApi.match(/atlasAgent\.get<unknown>\("\/api\/v1\/agent\/info"\)/g)).toHaveLength(1);
        expect(agentApi).not.toMatch(/["`]\/[^"`]*install[-_]container[^"`]*["`]/i);
        expect(agentApi).not.toMatch(/(?:post|put|patch|delete)[^\n]*agent\/info/i);
    });

    it("keeps validation advisory and allows only the Agent status retry", () => {
        const source = [agentPanel, validationPanel].join("\n");
        expect(validationPanel).toContain("Unsupported · default-disabled");
        expect(validationPanel).toContain("Validation is not installation");
        expect(validationPanel).toContain("Home Assistant remains blocked");
        expect(validationPanel).toContain("no Core request route or Core-to-Agent bridge");
        expect(validationPanel).not.toMatch(/<button|<form|<Link|navigate\(|href=/);
        expect(agentPanel.match(/<button\b/g)).toHaveLength(1);
        expect(agentPanel).toMatch(/<button[^>]*>\s*Retry status\s*<\/button>/);
        expect(agentPanel).not.toMatch(/<form|<Link|navigate\(|href=/);
        for (const label of [
            "Install now", "Execute now", "Deploy now", "Dispatch now",
            "Send to Agent", "Start workflow",
        ]) {
            expect(source).not.toContain(`>${label}<`);
            expect(source).not.toContain(`"${label}"`);
        }
    });
});
