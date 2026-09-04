import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { createQueueObservation, getQueueObservation, listQueueObservations, parseQueueObservationCollection, parseQueueObservationResult, queueObservationCreateFromOneShot } from "./queueObservation";
import { oneShotLiveEnqueueFixture, oneShotLiveEnqueueStatusFixture } from "../test/oneShotLiveEnqueue";
import { ambiguousQueueObservationResultFixture, queueObservationCollectionFixture, queueObservationResultFixture } from "../test/queueObservation";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

describe("queue observation API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only the guarded P3 list/get/create endpoints", async () => {
        const body = queueObservationCreateFromOneShot(oneShotLiveEnqueueFixture, oneShotLiveEnqueueStatusFixture);
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: queueObservationCollectionFixture }).mockResolvedValueOnce({ data: queueObservationResultFixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: queueObservationResultFixture });
        await listQueueObservations("candidate/id");
        await getQueueObservation("candidate/id", "observation/id");
        await createQueueObservation("candidate/id", body, "csrf", "queue-observation-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/queue-observations", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/queue-observations/observation%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records/candidate%2Fid/queue-observations", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "queue-observation-key" } });
    });

    it("builds the create request only from exact v0.42 enqueue readback evidence", () => {
        const body = queueObservationCreateFromOneShot(oneShotLiveEnqueueFixture, oneShotLiveEnqueueStatusFixture);
        expect(body).toMatchObject({
            schema: "queue-observation-receipt-create-v1",
            enqueue_id: oneShotLiveEnqueueFixture.enqueue_id,
            enqueue_status_fingerprint: oneShotLiveEnqueueStatusFixture.status_fingerprint,
            inert_queue_item_id: oneShotLiveEnqueueFixture.queue_item.queue_item_id,
            observed_queue_identity: "abstract_installation_queue",
            observed_item_identity: "inert_reference_only_queue_item",
            observation_state: "observed_recorded_not_consumable",
            requested_scope: "installation_queue_observation_receipt_only",
            observation_only: true,
            dequeue_allowed: false,
            queue_polling_allowed: false,
            worker_start_allowed: false,
            execution_authorized: false,
        });
        expect(JSON.stringify(body)).not.toMatch(/credential|secret|endpoint|command|payload_body|broker|worker_address/i);
    });

    it("strictly parses observed, blocked, and ambiguous states without effect authority", () => {
        expect(parseQueueObservationCollection(queueObservationCollectionFixture).items).toHaveLength(1);
        expect(parseQueueObservationResult(queueObservationResultFixture).record?.queue_observation.observation_state).toBe("observed_recorded_not_consumable");
        expect(parseQueueObservationResult(ambiguousQueueObservationResultFixture).error?.error_code).toBe("ambiguous_state");
        expect(() => parseQueueObservationResult({ ...queueObservationResultFixture, record: { ...queueObservationResultFixture.record!, dequeue_allowed: true } })).toThrow();
        expect(() => parseQueueObservationResult({ ...queueObservationResultFixture, record: { ...queueObservationResultFixture.record!, receipt_evidence: { ...queueObservationResultFixture.record!.receipt_evidence, endpoint: "amqp://secret" } } })).toThrow();
        expect(() => parseQueueObservationCollection({ ...queueObservationCollectionFixture, items: Array.from({ length: 17 }, () => queueObservationCollectionFixture.items[0]), count: 17 })).toThrow();
    });
});
