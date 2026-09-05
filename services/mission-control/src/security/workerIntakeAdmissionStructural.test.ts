import { describe, expect, it } from "vitest";

import api from "../api/workerIntakeAdmission.ts?raw";
import component from "../features/installation/WorkerIntakeAdmissions.tsx?raw";
import queueComponent from "../features/installation/WorkerQueueReservations.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.40 worker intake admission Mission Control boundary", () => {
    it("has only the guarded evidence client and no polling", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
        expect(component).toMatch(/listWorkerIntakeAdmissions/);
        expect(component).not.toMatch(/createWorkerIntakeAdmission|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource/);
    });

    it("is nested in the worker flow with no route, navigation, or controls", () => {
        expect(queueComponent).toMatch(/WorkerIntakeAdmissions/);
        expect(router).not.toMatch(/worker-intake-admissions|WorkerIntakeAdmission/i);
        expect(navigation).not.toMatch(/worker intake admission|worker_intake_admission/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(0);
        expect(component).not.toMatch(/>\s*(start|enqueue|dequeue|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("keeps operator status simple and technical evidence under Advanced details", () => {
        expect(component).toMatch(/Mission Control shows the worker intake admission status here in the existing worker flow/i);
        expect(component).toMatch(/does not send work to a queue or start a worker/i);
        expect(component).toMatch(/Advanced details/);
        expect(component).toMatch(/Worker intake admission fixed-false authority fields/);
        expect(component).toMatch(/not live enqueue, dequeue, worker contact, worker start, dispatch, execution/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /worker-intake-admissions|WorkerIntakeAdmission/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/oneShotDequeueWorkerBinding.ts",
            "../api/workerIntakeAdmission.ts",
            "../features/installation/WorkerIntakeAdmissions.tsx",
            "../features/installation/WorkerQueueReservations.tsx",
            "../types/liveEnqueueAdmission.ts",
            "../types/oneShotDequeueWorkerBinding.ts",
            "../types/workerIntakeAdmission.ts",
        ]);
    });
});
