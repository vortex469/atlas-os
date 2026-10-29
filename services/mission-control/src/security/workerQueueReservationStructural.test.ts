import { describe, expect, it } from "vitest";
import api from "../api/workerQueueReservation.ts?raw";
import component from "../features/installation/WorkerQueueReservations.tsx?raw";
import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

describe("v0.39 worker queue reservation presentation boundary", () => {
    it("has only the guarded evidence client and no polling", () => { expect(api).toMatch(/atlas\.get/); expect(api).toMatch(/atlas\.post/); expect(api).not.toMatch(/atlas\.(put|patch|delete)/); expect(component).toMatch(/listWorkerQueueReservations/); expect(component).not.toMatch(/createWorkerQueueReservation|setInterval|setTimeout|atlas\./); });
    it("has no route or navigation", () => { expect(router).not.toMatch(/worker-queue-reservations|WorkerQueueReservation/i); expect(navigation).not.toMatch(/worker queue reservation|worker_queue_reservation/i); });
    it("states the read-only queue boundary and carries the blocked state forward", () => { expect(component).toMatch(/This record does not connect to a live queue or put work on one/i); expect(component).toMatch(/No queue review record has been saved\. Atlas cannot enqueue or start work/i); expect(component).toContain("homeAssistantBlocked={homeAssistantBlocked}"); });
});
