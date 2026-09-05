import { describe, expect, it } from "vitest";

import api from "../api/oneShotLiveEnqueue.ts?raw";
import component from "../features/installation/OneShotLiveEnqueues.tsx?raw";
import liveEnqueueComponent from "../features/installation/LiveEnqueueAdmissions.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.42 one-shot live enqueue Mission Control boundary", () => {
    it("has read-only client access with no polling or mutation calls", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
        expect(component).toMatch(/listOneShotLiveEnqueues/);
        expect(component).not.toMatch(/getOneShotLiveEnqueue|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
    });

    it("is nested under v0.41 live enqueue admission with no standalone route or controls", () => {
        expect(liveEnqueueComponent).toMatch(/OneShotLiveEnqueues/);
        expect(router).not.toMatch(/one-shot-live-enqueues|OneShotLiveEnqueue/i);
        expect(navigation).not.toMatch(/one-shot live enqueue|one_shot_live_enqueue/i);
        expect(component.match(/<(button|form|input|select|textarea)\b/gi) ?? []).toHaveLength(0);
        expect(component).not.toMatch(/payload editor|queue selector|worker selector|editable limit/i);
        expect(component).not.toMatch(/>\s*(dequeue|claim|lease|poll|start|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("presents only the authorized inert item and denies all downstream authority", () => {
        expect(component).toMatch(/inert and reference-only/i);
        expect(component).toMatch(/not dequeue, queue polling, worker contact, worker start, Agent invocation, workflow start, process execution/i);
        expect(component).toMatch(/Permanent one-shot subject reservation: true/);
        expect(component).toMatch(/One-shot live enqueue fixed-false authority fields/);
        expect(component).not.toMatch(/process\.env|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /one-shot-live-enqueues|OneShotLiveEnqueue/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/oneShotLiveEnqueue.ts",
            "../api/queueObservation.ts",
            "../features/installation/LiveEnqueueAdmissions.tsx",
            "../features/installation/OneShotLiveEnqueues.tsx",
            "../features/installation/QueueObservationEvidence.tsx",
            "../types/controlledDequeueAdmission.ts",
            "../types/oneShotLiveEnqueue.ts",
            "../types/queueObservation.ts",
        ]);
    });
});
