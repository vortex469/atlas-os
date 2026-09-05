import { describe, expect, it } from "vitest";

import api from "../api/controlledDequeueAdmission.ts?raw";
import component from "../features/installation/ControlledDequeueAdmissions.tsx?raw";
import queueObservationComponent from "../features/installation/QueueObservationEvidence.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.44 controlled dequeue admission Mission Control boundary", () => {
    it("uses only guarded controlled dequeue admission API calls and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/atlas\.post/g)).toHaveLength(1);
        expect(api).not.toMatch(/atlas\.(put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listControlledDequeueAdmissions/);
        expect(component).toMatch(/createControlledDequeueAdmission/);
        expect(component).toMatch(/getQueueObservation/);
        expect(component).not.toMatch(/setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested under queue observation with no standalone route or top-level navigation", () => {
        expect(queueObservationComponent).toMatch(/ControlledDequeueAdmissions/);
        expect(router).not.toMatch(/controlled-dequeue-admissions|ControlledDequeueAdmission/i);
        expect(navigation).not.toMatch(/controlled dequeue|controlled_dequeue/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /controlledDequeueAdmission|ControlledDequeueAdmission|controlled-dequeue-admissions/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/controlledDequeueAdmission.ts",
            "../features/installation/ControlledDequeueAdmissions.tsx",
            "../features/installation/QueueObservationEvidence.tsx",
            "../types/controlledDequeueAdmission.ts",
        ]);
    });

    it("keeps technical evidence in details and omits prohibited effect controls", () => {
        expect(component).toMatch(/Readiness: \{admitted \? "Ready for later dequeue consideration" : "Blocked or not yet admitted"\}/);
        expect(component).toMatch(/<details className="mt-3">/);
        expect(component).toMatch(/Queue observation receipt fingerprint/);
        expect(component).toMatch(/Admission decision fingerprint/);
        expect(component).toMatch(/controlled_dequeue_admission_recorded/);
        expect(component).toMatch(/Controlled dequeue admission fixed-false authority fields/);
        expect(component).toMatch(/Record controlled dequeue admission evidence only/);
        expect(component).not.toMatch(/queue selector|worker selector|payload editor|editable limit|raw receipt document|raw queue identity value|lease token|acknowledgement token/i);
        expect(component).not.toMatch(/>\s*(dequeue|poll|claim|lease|ack|consume|remove|start worker|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });
});
