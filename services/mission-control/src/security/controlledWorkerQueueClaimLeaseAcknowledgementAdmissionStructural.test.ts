import { describe, expect, it } from "vitest";

import api from "../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission.ts?raw";
import component from "../features/installation/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx?raw";
import parent from "../features/installation/ControlledWorkerQueueClaimAdmissions.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("v0.51 controlled queue claim lease acknowledgement admission Mission Control boundary", () => {
    it("uses only guarded Core read APIs and no polling transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|Worker\(/);
        expect(component).toMatch(/listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions/);
        expect(component).not.toMatch(/createControlledWorkerQueueClaimLeaseAcknowledgementAdmission|atlas\.|setInterval|setTimeout|refetchInterval|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
    });

    it("is nested in the existing installation workflow with no route, navigation, or controls", () => {
        expect(parent).toMatch(/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions/);
        expect(router).not.toMatch(/controlled-worker-queue-claim-lease-acknowledgement-admissions|ControlledWorkerQueueClaimLeaseAcknowledgementAdmission/i);
        expect(navigation).not.toMatch(/claim lease acknowledgement|controlled_worker_queue_claim_lease_acknowledgement/i);
        const controls = component.match(/<(button|form|input|select|textarea)\b/gi) ?? [];
        expect(controls).toHaveLength(1);
        expect(component).not.toMatch(/>\s*(activate|contact|start|poll|claim|lease|ack|run|execute|install|deploy|dispatch|resend|send to agent|start workflow|rollback)\s*</i);
    });

    it("keeps operator state simple and advanced evidence collapsed", () => {
        expect(component).toMatch(/This saved review checks the required queue and worker details\. It does not claim queue work or start a worker/);
        expect(component).toMatch(/Queue and worker review \{status\.toLowerCase\(\)\}/);
        expect(component).toMatch(/Technical details/);
        expect(component).toMatch(/v0\.50 prerequisite state/);
        expect(component).toMatch(/Ordered v0\.51 blockers/);
        expect(component).toMatch(/Controlled queue claim lease acknowledgement fixed-false authority fields/);
        expect(component).toMatch(/raw queue selectors, claim tokens, lease tokens, acknowledgement handles, payloads, commands, endpoints, and credentials are not accepted or shown/);
        expect(component).not.toMatch(/queue selector input|payload editor|command editor|endpoint input|credential input|raw queue identity value|claim token value|lease token value|acknowledgement handle value|runtime endpoint|store endpoint/i);
        const consumers = Object.entries(productionModules).filter(([, source]) => /controlledWorkerQueueClaimLeaseAcknowledgementAdmission|ControlledWorkerQueueClaimLeaseAcknowledgementAdmission|controlled-worker-queue-claim-lease-acknowledgement-admissions/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission.ts",
            "../api/controlledWorkerQueueReceipt.ts",
            "../features/installation/ControlledWorkerQueueClaimAdmissions.tsx",
            "../features/installation/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx",
            "../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission.ts",
        ]);
    });
});
