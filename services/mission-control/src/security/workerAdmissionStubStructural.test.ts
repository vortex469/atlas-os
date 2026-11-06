import { describe, expect, it } from "vitest";

import api from "../api/workerAdmissionStub.ts?raw";
import component from "../features/installation/WorkerAdmissionStubs.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.38 worker admission stub presentation boundary", () => {
    it("uses GET plus the one explicit create mutation and never polls", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/atlas\.post/g)).toHaveLength(1);
        expect(api).not.toMatch(/atlas\.(put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
        expect(component).toMatch(/listWorkerAdmissionStubs/);
        expect(component).not.toMatch(/createWorkerAdmissionStub|atlas\.|setInterval|setTimeout/);
    });
    it("adds no route or navigation and exposes no prohibited control labels", () => {
        expect(router).not.toMatch(/worker-admission-stubs|WorkerAdmissionStub/i);
        expect(navigation).not.toMatch(/worker admission stub|worker-admission-stubbed/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(1);
        expect(component).toMatch(/>Retry<\/button>/);
        expect(component).not.toMatch(/>\s*(worker|start|enqueue|queue|run|execute|install|deploy|dispatch|resend|send to agent|start workflow|rollback)\s*</i);
    });
    it("renders simple state and keeps technical evidence collapsed", () => {
        expect(component).toMatch(/This review record does not start a worker or put work on a queue/i);
        expect(component).toMatch(/Worker setup record is current/);
        expect(component).toMatch(/Technical details/);
        expect(component).toMatch(/Worker admission fixed-false authority fields/);
        expect(component).toMatch(/Worker capability fingerprint/);
        expect(component).toMatch(/Sandbox and resource limits/);
        expect(component).toMatch(/Blockers/);
        expect(component).toMatch(/No worker has been contacted or started, and no work has been put on a queue/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /worker-admission-stubs|WorkerAdmissionStub/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/workerAdmissionStub.ts",
            "../features/installation/RunnerBindingPlans.tsx",
            "../features/installation/WorkerAdmissionStubs.tsx",
            "../types/workerAdmissionStub.ts",
            "../types/workerQueueReservation.ts",
        ]);
    });
});
