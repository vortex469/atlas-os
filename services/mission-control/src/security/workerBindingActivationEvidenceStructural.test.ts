import { describe, expect, it } from "vitest";

import api from "../api/workerBindingActivationEvidence.ts?raw";
import component from "../features/installation/WorkerBindingActivationEvidences.tsx?raw";
import parent from "../features/installation/WorkerBindingActivationPreflights.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.48 worker binding activation evidence Mission Control boundary", () => {
    it("uses only guarded read APIs and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listWorkerBindingActivationEvidences/);
        expect(component).not.toMatch(/createWorkerBindingActivationEvidence|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested in the existing installation workflow with no route, navigation, or controls", () => {
        expect(parent).toMatch(/WorkerBindingActivationEvidences/);
        expect(router).not.toMatch(/worker-binding-activation-evidence|WorkerBindingActivationEvidence/i);
        expect(navigation).not.toMatch(/worker binding activation evidence|worker_binding_activation_evidence/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(0);
        expect(component).not.toMatch(/>\s*(activate|contact|start|poll|claim|lease|ack|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("keeps operator state simple and technical evidence under Advanced details", () => {
        expect(component).toMatch(/State: evidence recorded for later activation consideration; activation runtime: not defined; worker-start admission: not defined; blocked: yes/);
        expect(component).toMatch(/Advanced details/);
        expect(component).toMatch(/Worker capability fingerprint/);
        expect(component).toMatch(/Inherited sandbox, resource, network, and filesystem limits/);
        expect(component).toMatch(/Blockers/);
        expect(component).toMatch(/Worker binding activation evidence fixed-false authority fields/);
        expect(component).toMatch(/No runtime activation, worker-start admission, store contact, runtime contact, queue claim/);
        expect(component).not.toMatch(/worker selector|payload editor|command editor|endpoint input|credential input|raw receipt document|raw queue identity value|lease token|acknowledgement token|runtime endpoint|store endpoint/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /workerBindingActivationEvidence|WorkerBindingActivationEvidence|worker-binding-activation-evidence/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/workerBindingActivationEvidence.ts",
            "../features/installation/WorkerBindingActivationEvidences.tsx",
            "../features/installation/WorkerBindingActivationPreflights.tsx",
            "../types/workerBindingActivationEvidence.ts",
        ]);
    });
});
