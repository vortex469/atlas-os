import { describe, expect, it } from "vitest";

import api from "../api/oneShotDequeueWorkerBinding.ts?raw";
import component from "../features/installation/OneShotDequeueWorkerBindings.tsx?raw";
import parent from "../features/installation/OneShotControlledDequeues.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.46 one-shot dequeue worker binding Mission Control boundary", () => {
    it("uses only guarded read APIs and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listOneShotDequeueWorkerBindings/);
        expect(component).not.toMatch(/createOneShotDequeueWorkerBinding|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested in the existing installation workflow with no route, navigation, or controls", () => {
        expect(parent).toMatch(/OneShotDequeueWorkerBindings/);
        expect(router).not.toMatch(/one-shot-dequeue-worker-bindings|OneShotDequeueWorkerBinding/i);
        expect(navigation).not.toMatch(/one-shot dequeue worker binding|one_shot_dequeue_worker_binding/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(0);
        expect(component).not.toMatch(/>\s*(contact|start|poll|claim|lease|ack|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("keeps operator state simple and technical evidence under Advanced details", () => {
        expect(component).toMatch(/State: eligible; bound: readiness gated; blocked: yes/);
        expect(component).toMatch(/Advanced details/);
        expect(component).toMatch(/Worker capability fingerprint/);
        expect(component).toMatch(/Inherited sandbox, resource, network, and filesystem limits/);
        expect(component).toMatch(/Blockers/);
        expect(component).toMatch(/One-shot dequeue worker binding fixed-false authority fields/);
        expect(component).toMatch(/No worker-start, Agent invocation, execution, installation, deployment, rollback, retry, resend/);
        expect(component).not.toMatch(/worker selector|payload editor|editable limit|raw receipt document|raw queue identity value|lease token|acknowledgement token|runtime endpoint|store endpoint/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /oneShotDequeueWorkerBinding|OneShotDequeueWorkerBinding|one-shot-dequeue-worker-bindings/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/oneShotDequeueWorkerBinding.ts",
            "../features/installation/OneShotControlledDequeues.tsx",
            "../features/installation/OneShotDequeueWorkerBindings.tsx",
            "../types/oneShotDequeueWorkerBinding.ts",
        ]);
    });
});
