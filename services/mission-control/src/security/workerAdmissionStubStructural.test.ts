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
        expect(controls).toHaveLength(0);
        expect(component).not.toMatch(/>\s*(worker|start|enqueue|queue|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });
    it("renders only closed evidence consumers and explicit non-authority copy", () => {
        expect(component).toMatch(/preserves a non-enqueuing worker admission stub evidence record only/i);
        expect(component).toMatch(/not worker start, queue or enqueue, execution start, runner binding, install, dispatch/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /worker-admission-stubs|WorkerAdmissionStub/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/workerAdmissionStub.ts",
            "../features/installation/RunnerBindingPlans.tsx",
            "../features/installation/WorkerAdmissionStubs.tsx",
            "../types/workerAdmissionStub.ts",
        ]);
    });
});
