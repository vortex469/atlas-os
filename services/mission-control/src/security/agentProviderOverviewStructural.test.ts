import { describe, expect, it } from "vitest";
import content from "../features/mission-control/AgentProviderContent.tsx?raw";
import normalization from "../features/mission-control/agentProviderEvidence.ts?raw";
import dashboard from "../features/mission-control/MissionControl.tsx?raw";

describe("agent/provider overview authority boundaries", () => {
    it("only presents shared evidence and existing navigation", () => {
        for (const source of [content, normalization]) {
            expect(source).not.toMatch(/from ["'].*api\/|fetch\(|axios|\.post\(|\.put\(|\.patch\(|\.delete\(|useEffect|useState|setInterval|localStorage|sessionStorage|dangerouslySetInnerHTML/);
            expect(source).not.toMatch(/<(button|form|input|select|textarea)\b/);
        }
        expect(dashboard).toContain("useOverviewEvidence()");
        expect(dashboard).toContain("<AgentOverviewContent evidence={evidence.agent}");
        expect(dashboard).toContain("<ProviderOverviewContent evidence={evidence.providers}");
        expect(dashboard).toContain("<SystemHealthSummary");
        expect(dashboard).toContain("<WorkerExecutionSection");
        expect(dashboard).not.toMatch(/useMissionControl|AtlasAgentPanel|ProviderCard|AgentProviderSection/);
    });
});
