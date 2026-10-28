import { describe, expect, it } from "vitest";
import api from "../api/workerQueueReservation.ts?raw";
import component from "../features/installation/WorkerQueueReservations.tsx?raw";
import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

describe("v0.39 worker queue reservation presentation boundary", () => {
    it("has only the guarded evidence client and no polling", () => { expect(api).toMatch(/atlas\.get/); expect(api).toMatch(/atlas\.post/); expect(api).not.toMatch(/atlas\.(put|patch|delete)/); expect(component).toMatch(/listWorkerQueueReservations/); expect(component).not.toMatch(/createWorkerQueueReservation|setInterval|setTimeout|atlas\./); });
    it("has no route or navigation", () => { expect(router).not.toMatch(/worker-queue-reservations|WorkerQueueReservation/i); expect(navigation).not.toMatch(/worker queue reservation|worker_queue_reservation/i); });
    it("states the plain saved-record boundary, safety limits, and Home Assistant block", () => {
        expect(component).toMatch(/saves a queue reference for later review/i);
        expect(component).toMatch(/does not create or contact a live queue, add work, or start a worker/i);
        expect(component).toMatch(/No network access or live queue contact/i);
        expect(component).toMatch(/Exact safety limits and earlier evidence/i);
        expect(component).toMatch(/Audit and authority details/i);
        expect(component).toMatch(/Atlas cannot install Home Assistant, so it cannot be queued for installation/i);
    });
});
