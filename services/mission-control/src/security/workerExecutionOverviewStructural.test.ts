import { describe, expect, it } from "vitest";
import section from "../features/mission-control/WorkerExecutionSection.tsx?raw";
import dashboard from "../features/mission-control/MissionControl.tsx?raw";

describe("worker execution overview isolation", () => {
    it("is a presentation-only consumer with no transport, mutation, or runtime access", () => {
        expect(section).not.toMatch(/from ["'].*api\/|fetch\(|axios|atlas\.|\.post\(|\.put\(|\.patch\(|\.delete\(|WebSocket|EventSource|setInterval|localStorage|sessionStorage|document\.cookie|dangerouslySetInnerHTML/);
        expect(section).not.toMatch(/<(button|form|input|select|textarea)\b/);
        expect(dashboard).toContain("<WorkerExecutionSection");
        expect(dashboard).not.toMatch(/createWorker|enqueue|dequeue\(|startWorker|stopWorker|submitWorkflow|resumeWorkflow/);
    });
});
