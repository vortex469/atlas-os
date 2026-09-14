import { describe, expect, it } from "vitest";
import activity from "../features/mission-control/RecentActivity.tsx?raw";
import dashboard from "../features/mission-control/MissionControl.tsx?raw";
import hook from "../features/mission-control/useOverviewEvidence.ts?raw";

describe("attention/activity authority boundaries", () => {
    it("uses shared authoritative observations and existing detail routes without a local audit or action path", () => {
        for (const source of [dashboard, activity]) {
            expect(source).not.toMatch(/from ["'].*api\/|fetch\(|axios|\.(post|put|patch|delete)\(|localStorage|sessionStorage|dangerouslySetInnerHTML|runProviderAction/);
        }
        expect(hook.match(/"\/ops\/actions\/page"/g)).toHaveLength(1);
        expect(dashboard).toContain("useOverviewEvidence()");
        expect(dashboard).toContain("workflowActionRequired");
        expect(dashboard).toContain("const deduplicated = new Map");
        expect(dashboard).not.toMatch(/useMissionControl|DashboardHeader|Workflow Inbox|AtlasAgentPanel|refreshKey/);
        for (const section of ["SystemHealthSummary", "WorkerExecutionSection", "AgentOverviewContent", "ProviderOverviewContent", "LocalAiContent", "RecentActivity"]) expect(dashboard).toContain(`<${section}`);
        expect(activity).toContain('detailPath("/operations/actions", event.id)');
        expect(activity).not.toMatch(/<(button|form|input|select|textarea)\b/);
    });
});
