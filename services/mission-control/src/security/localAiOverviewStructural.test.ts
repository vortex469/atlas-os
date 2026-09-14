import { describe, expect, it } from "vitest";
import content from "../features/mission-control/LocalAiContent.tsx?raw";
import dashboard from "../features/mission-control/MissionControl.tsx?raw";
import hook from "../features/mission-control/useOverviewEvidence.ts?raw";

describe("Local AI overview authority boundaries", () => {
    it("consumes shared observations without adding an execution or polling path", () => {
        expect(content).not.toMatch(/from ["'].*api\/|fetch\(|axios|\.(post|put|patch|delete)\(|useEffect|useState|setInterval|localStorage|sessionStorage|dangerouslySetInnerHTML|runProviderAction|load-model|unload-model/);
        expect(content).not.toMatch(/<(button|form|input|select|textarea)\b/);
        expect(hook.match(/"\/ai\/status"/g)).toHaveLength(1);
        expect(dashboard.match(/<LocalAiContent /g)).toHaveLength(1);
        expect(dashboard).toContain('<LocalAiContent evidence={evidence.ai} />');
        expect(dashboard).toContain('useOverviewEvidence()');
        expect(dashboard).not.toMatch(/useMissionControl|LocalAiSection|LocalAIRuntimeOverviewSection|refreshKey/);
        for (const section of ['SystemHealthSummary', 'WorkerExecutionSection', 'AgentOverviewContent', 'ProviderOverviewContent']) expect(dashboard).toContain(`<${section}`);
    });
});
