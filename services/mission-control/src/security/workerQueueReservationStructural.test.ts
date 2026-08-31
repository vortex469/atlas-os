import { describe, expect, it } from "vitest";
import api from "../api/workerQueueReservation.ts?raw";
import component from "../features/installation/WorkerQueueReservations.tsx?raw";
import router from "../app/router.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";

describe("v0.39 worker queue reservation presentation boundary", () => {
    it("has only the guarded evidence client and no polling", () => { expect(api).toMatch(/atlas\.get/); expect(api).toMatch(/atlas\.post/); expect(api).not.toMatch(/atlas\.(put|patch|delete)/); expect(component).toMatch(/listWorkerQueueReservations/); expect(component).not.toMatch(/createWorkerQueueReservation|setInterval|setTimeout|atlas\./); });
    it("has no route or navigation", () => { expect(router).not.toMatch(/worker-queue-reservations|WorkerQueueReservation/i); expect(navigation).not.toMatch(/worker queue reservation|worker_queue_reservation/i); });
    it("states the evidence-only authority boundary", () => { expect(component).toMatch(/evidence-only worker queue reservation record/i); expect(component).toMatch(/not live enqueue, dequeue, worker start, dispatch, execution/i); expect(component).toMatch(/Home Assistant.*non-installable and non-executable/is); });
});
