import { describe, expect, it } from "vitest";

import api from "../api/liveEnqueueAdmission.ts?raw";
import component from "../features/installation/LiveEnqueueAdmissions.tsx?raw";
import workerIntakeComponent from "../features/installation/WorkerIntakeAdmissions.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.41 live enqueue admission Mission Control boundary", () => {
    it("has only the guarded create/list/get client and no polling", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/atlas\.post/g)).toHaveLength(1);
        expect(api).not.toMatch(/atlas\.(put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
        expect(component).toMatch(/listLiveEnqueueAdmissions/);
        expect(component).not.toMatch(/createLiveEnqueueAdmission|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
    });

    it("is nested under worker intake with no standalone route, navigation, selectors, editors, or controls", () => {
        expect(workerIntakeComponent).toMatch(/LiveEnqueueAdmissions/);
        expect(router).not.toMatch(/live-enqueue-admissions|LiveEnqueueAdmission/i);
        expect(navigation).not.toMatch(/live enqueue admission|live_enqueue_admission/i);
        expect(component.match(/<(button|form|input|select|textarea)\b/gi) ?? []).toHaveLength(0);
        expect(component).not.toMatch(/queue selector|worker selector|payload editor|editable queue|editable limit/i);
        expect(component).not.toMatch(/>\s*(enqueue|dequeue|claim|lease|poll|start|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("presents evidence without sensitive values or operational authority", () => {
        expect(component).toMatch(/inside the worker-intake hierarchy/i);
        expect(component).toMatch(/does not enqueue, dequeue, poll, contact or start a worker, dispatch, install, or execute anything/i);
        expect(component).toMatch(/Advanced live enqueue evidence/);
        expect(component).toMatch(/Live enqueue admission fixed-false authority fields/);
        expect(component).toMatch(/Permanent live-enqueue subject reservation: true/);
        expect(component).not.toMatch(/process\.env|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /live-enqueue-admissions|LiveEnqueueAdmission/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/liveEnqueueAdmission.ts",
            "../features/installation/LiveEnqueueAdmissions.tsx",
            "../features/installation/WorkerIntakeAdmissions.tsx",
            "../types/liveEnqueueAdmission.ts",
        ]);
    });
});
