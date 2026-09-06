import { describe, expect, it } from "vitest";

import api from "../api/controlledWorkerQueueClaimAdmission.ts?raw";
import component from "../features/installation/ControlledWorkerQueueClaimAdmissions.tsx?raw";
import parent from "../features/installation/WorkerBindingActivationEvidences.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.49 controlled worker queue claim admission Mission Control boundary with v0.50 prerequisite isolation", () => {
    it("uses only guarded read APIs and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listControlledWorkerQueueClaimAdmissions/);
        expect(component).not.toMatch(/createControlledWorkerQueueClaimAdmission|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested in the existing installation workflow with no route, navigation, or controls", () => {
        expect(parent).toMatch(/ControlledWorkerQueueClaimAdmissions/);
        expect(router).not.toMatch(/controlled-worker-queue-claim-admissions|ControlledWorkerQueueClaimAdmission/i);
        expect(navigation).not.toMatch(/controlled worker queue claim admission|controlled_worker_queue_claim_admission/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(0);
        expect(component).not.toMatch(/>\s*(activate|contact|start|poll|claim|lease|ack|run|execute|install|deploy|dispatch|retry|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("keeps readiness and v0.50 prerequisite state simple with technical evidence under Advanced details", () => {
        expect(component).toMatch(/Readiness\/start-admission state: queue-claim admission evidence recorded; queue claim: not defined; worker-start admission: not defined; blocked: yes/);
        expect(component).toMatch(/v0\.50 progress: prerequisite frozen, documentation-only/);
        expect(component).toMatch(/v0\.50 prerequisite state: documentation-only prerequisite frozen/);
        expect(component).toMatch(/Advanced details/);
        expect(component).toMatch(/v0\.50 prerequisite details/);
        expect(component).toMatch(/one active same-owner v0\.49 controlled worker queue claim admission/);
        expect(component).toMatch(/v0\.50 prerequisite frozen equals queue claimed/);
        expect(component).toMatch(/Worker capability fingerprint/);
        expect(component).toMatch(/Inherited sandbox, resource, network, and filesystem limits/);
        expect(component).toMatch(/Blockers/);
        expect(component).toMatch(/Controlled worker queue claim admission fixed-false authority fields/);
        expect(component).toMatch(/No queue claim, queue lease, queue acknowledgement, worker-start admission/);
        expect(component).not.toMatch(/createControlledWorkerQueueClaim|claim queue|lease queue|acknowledge queue|worker start control|execute control/i);
        expect(component).not.toMatch(/worker selector|queue selector|payload editor|command editor|endpoint input|credential input|raw receipt document|raw queue identity value|claim token|lease token|acknowledgement token|runtime endpoint|store endpoint/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /controlledWorkerQueueClaimAdmission|ControlledWorkerQueueClaimAdmission|controlled-worker-queue-claim-admissions/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/controlledWorkerQueueClaimAdmission.ts",
            "../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission.ts",
            "../features/installation/ControlledWorkerQueueClaimAdmissions.tsx",
            "../features/installation/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx",
            "../features/installation/WorkerBindingActivationEvidences.tsx",
            "../types/controlledWorkerQueueClaimAdmission.ts",
            "../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission.ts",
        ]);
    });
});
