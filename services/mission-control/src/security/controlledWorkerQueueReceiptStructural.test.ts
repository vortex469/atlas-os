import { describe, expect, it } from "vitest";
import api from "../api/controlledWorkerQueueReceipt.ts?raw";
import component from "../features/installation/ControlledWorkerQueueReceipt.tsx?raw";
import parent from "../features/installation/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";

const modules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
describe("v0.52 read-only Mission Control isolation", () => {
    it("uses a guarded Core read with no mutations, polling, storage or worker transport", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(1);
        expect(api).toContain("withCredentials: true");
        expect(api + component).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|WebSocket|EventSource|Worker\(|localStorage|sessionStorage|document\.cookie|Authorization|Bearer/);
        expect(component).not.toMatch(/<(button|form|input|select|textarea)\b/i);
    });
    it("stays under the existing admission with no route or navigation", () => {
        expect(parent).toContain("<ControlledWorkerQueueReceipt candidateId={item.candidate_record_id} admissionId={item.admission_id} operatorId={item.operator_id}");
        expect(router + navigation).not.toMatch(/ControlledWorkerQueueReceipt|controlled-worker-queue-claim-lease-acknowledgements/);
        expect(component).toContain("Advanced v0.52 evidence");
        expect(component).not.toMatch(/<details[^>]*\bopen/);
        const consumers = Object.entries(modules).filter(([, source]) => /controlledWorkerQueueReceipt|ControlledWorkerQueueReceipt/.test(source)).map(([path]) => path).sort();
        expect(consumers).toEqual([
            "../api/controlledWorkerQueueReceipt.ts",
            "../features/installation/ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions.tsx",
            "../features/installation/ControlledWorkerQueueReceipt.tsx",
            "../types/controlledWorkerQueueReceipt.ts",
        ]);
    });
});
