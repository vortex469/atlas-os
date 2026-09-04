import { describe, expect, it } from "vitest";

import api from "../api/queueObservation.ts?raw";
import component from "../features/installation/QueueObservationEvidence.tsx?raw";
import oneShotComponent from "../features/installation/OneShotLiveEnqueues.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.43 queue observation Mission Control boundary", () => {
    it("uses only guarded queue observation API calls and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/atlas\.post/g)).toHaveLength(1);
        expect(api).not.toMatch(/atlas\.(put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listQueueObservations/);
        expect(component).toMatch(/createQueueObservation/);
        expect(component).not.toMatch(/setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested under one-shot live enqueue with no standalone route or top-level navigation", () => {
        expect(oneShotComponent).toMatch(/QueueObservationEvidence/);
        expect(router).not.toMatch(/queue-observations|QueueObservation/i);
        expect(navigation).not.toMatch(/queue observation|queue_observation|enqueue receipt/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /queueObservation|QueueObservation/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/queueObservation.ts",
            "../features/installation/OneShotLiveEnqueues.tsx",
            "../features/installation/QueueObservationEvidence.tsx",
            "../types/queueObservation.ts",
        ]);
    });

    it("keeps fingerprints and receipt evidence in details and omits prohibited controls", () => {
        expect(component).toMatch(/State: \{observed \? "Observed" : "Pending or blocked"\}/);
        expect(component).toMatch(/<details className="mt-3">/);
        expect(component).toMatch(/Enqueue receipt fingerprint/);
        expect(component).toMatch(/Lineage fingerprint/);
        expect(component).toMatch(/Queue observation fixed-false authority fields/);
        expect(component).toMatch(/Record bounded queue observation evidence only/);
        expect(component).not.toMatch(/queue selector|worker selector|payload editor|editable limit|raw receipt document|raw queue identity value/i);
        expect(component).not.toMatch(/>\s*(dequeue|poll|claim|lease|ack|start worker|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });
});
