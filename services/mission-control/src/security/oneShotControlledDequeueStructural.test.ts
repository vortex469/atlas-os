import { describe, expect, it } from "vitest";

import api from "../api/oneShotControlledDequeue.ts?raw";
import component from "../features/installation/OneShotControlledDequeues.tsx?raw";
import controlledDequeueComponent from "../features/installation/ControlledDequeueAdmissions.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.45 one-shot controlled dequeue Mission Control boundary", () => {
    it("uses only guarded one-shot controlled dequeue API calls and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/atlas\.post/g)).toHaveLength(1);
        expect(api).not.toMatch(/atlas\.(put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listOneShotControlledDequeues/);
        expect(component).toMatch(/createOneShotControlledDequeue/);
        expect(component).toMatch(/getControlledDequeueAdmission/);
        expect(component).not.toMatch(/setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested under controlled dequeue admission with no standalone route or top-level navigation", () => {
        expect(controlledDequeueComponent).toMatch(/OneShotControlledDequeues/);
        expect(router).not.toMatch(/one-shot-controlled-dequeues|OneShotControlledDequeue/i);
        expect(navigation).not.toMatch(/one-shot controlled dequeue|one_shot_controlled_dequeue/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /oneShotControlledDequeue|OneShotControlledDequeue|one-shot-controlled-dequeues/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/oneShotControlledDequeue.ts",
            "../features/installation/ControlledDequeueAdmissions.tsx",
            "../features/installation/OneShotControlledDequeues.tsx",
            "../types/oneShotControlledDequeue.ts",
        ]);
    });

    it("keeps technical evidence in details and omits prohibited downstream controls", () => {
        expect(component).toMatch(/State: \{state\}/);
        expect(component).toMatch(/exact admitted inert item only/);
        expect(component).toMatch(/<details className="mt-3">/);
        expect(component).toMatch(/Queue observation receipt fingerprint/);
        expect(component).toMatch(/Adapter receipt fingerprint/);
        expect(component).toMatch(/Permanent dequeue subject reservation: true/);
        expect(component).toMatch(/One-shot controlled dequeue fixed-false authority fields/);
        expect(component).not.toMatch(/queue selector|worker selector|payload editor|editable limit|raw receipt document|raw queue identity value|lease token|acknowledgement token/i);
        expect(component).not.toMatch(/>\s*(poll|claim|lease|ack|consume|remove|start worker|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });
});
