import { describe, expect, it } from "vitest";

import api from "../api/workerBindingActivationPreflight.ts?raw";
import component from "../features/installation/WorkerBindingActivationPreflights.tsx?raw";
import parent from "../features/installation/OneShotDequeueWorkerBindings.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.47 worker binding activation preflight Mission Control boundary", () => {
    it("uses only guarded read APIs and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listWorkerBindingActivationPreflights/);
        expect(component).not.toMatch(/createWorkerBindingActivationPreflight|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested in the existing installation workflow with no route, navigation, or controls", () => {
        expect(parent).toMatch(/WorkerBindingActivationPreflights/);
        expect(router).not.toMatch(/worker-binding-activation-preflights|WorkerBindingActivationPreflight/i);
        expect(navigation).not.toMatch(/worker binding activation preflight|worker_binding_activation_preflight/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(0);
        expect(component).not.toMatch(/>\s*(activate|contact|start|poll|claim|lease|ack|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("keeps operator state simple and technical evidence under Advanced details", () => {
        expect(component).toMatch(/State: eligible for later activation consideration; activation: not defined; blocked: yes/);
        expect(component).toMatch(/Advanced details/);
        expect(component).toMatch(/Worker capability fingerprint/);
        expect(component).toMatch(/Inherited sandbox, resource, network, and filesystem limits/);
        expect(component).toMatch(/Blockers/);
        expect(component).toMatch(/Worker binding activation preflight fixed-false authority fields/);
        expect(component).toMatch(/No activation, store contact, runtime contact, queue claim, queue lease, queue acknowledgement/);
        expect(component).not.toMatch(/worker selector|payload editor|editable limit|raw receipt document|raw queue identity value|lease token|acknowledgement token|runtime endpoint|store endpoint/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /workerBindingActivationPreflight|WorkerBindingActivationPreflight|worker-binding-activation-preflights/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/workerBindingActivationPreflight.ts",
            "../features/installation/OneShotDequeueWorkerBindings.tsx",
            "../features/installation/WorkerBindingActivationPreflights.tsx",
            "../types/workerBindingActivationPreflight.ts",
        ]);
    });
});
