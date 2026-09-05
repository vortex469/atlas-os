import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { createOneShotControlledDequeue, getOneShotControlledDequeue, listOneShotControlledDequeues, oneShotControlledDequeueCreateFromAdmission, parseOneShotControlledDequeueCollection, parseOneShotControlledDequeueResult } from "./oneShotControlledDequeue";
import { controlledDequeueAdmissionFixture, controlledDequeueAdmissionResultFixture } from "../test/controlledDequeueAdmission";
import { blockedOneShotControlledDequeueResultFixture, oneShotControlledDequeueCollectionFixture, oneShotControlledDequeueResultFixture } from "../test/oneShotControlledDequeue";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

describe("one-shot controlled dequeue API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded list/get/create endpoints", async () => {
        const body = oneShotControlledDequeueCreateFromAdmission(controlledDequeueAdmissionFixture, controlledDequeueAdmissionResultFixture.status!);
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: oneShotControlledDequeueCollectionFixture }).mockResolvedValueOnce({ data: oneShotControlledDequeueResultFixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: oneShotControlledDequeueResultFixture });
        await listOneShotControlledDequeues("candidate/id");
        await getOneShotControlledDequeue("candidate/id", "dequeue/id");
        await createOneShotControlledDequeue("candidate/id", body, "csrf", "one-shot-controlled-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/one-shot-controlled-dequeues", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/one-shot-controlled-dequeues/dequeue%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records/candidate%2Fid/one-shot-controlled-dequeues", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "one-shot-controlled-key" } });
    });

    it("builds create request only from exact v0.44 admission readback evidence", () => {
        const body = oneShotControlledDequeueCreateFromAdmission(controlledDequeueAdmissionFixture, controlledDequeueAdmissionResultFixture.status!);
        expect(body).toMatchObject({
            schema: "one-shot-controlled-dequeue-create-v1",
            controlled_dequeue_admission_id: controlledDequeueAdmissionFixture.admission_id,
            controlled_dequeue_admission_fingerprint: controlledDequeueAdmissionFixture.admission_record_fingerprint,
            controlled_dequeue_admission_status_fingerprint: controlledDequeueAdmissionResultFixture.status!.status_fingerprint,
            queue_observation_receipt_id: controlledDequeueAdmissionFixture.queue_observation_receipt.receipt_id,
            enqueue_id: controlledDequeueAdmissionFixture.queue_observation_receipt.v042_enqueue.enqueue_id,
            inert_queue_item_id: controlledDequeueAdmissionFixture.queue_observation_receipt.v042_enqueue.queue_item.queue_item_id,
            queue_identity: "abstract_installation_queue",
            item_identity: "inert_reference_only_queue_item",
            requested_scope: "installation_one_shot_controlled_dequeue_only",
            evidence_only: true,
            dequeue_allowed: false,
            queue_polling_allowed: false,
            queue_claim_allowed: false,
            queue_lease_allowed: false,
            queue_ack_allowed: false,
            worker_start_allowed: false,
        });
        expect(JSON.stringify(body)).not.toMatch(/credential|secret|endpoint|command|payload_body|broker|worker_address|lease_token|ack_token/i);
    });

    it("strictly parses success and blocked states without downstream authority", () => {
        expect(parseOneShotControlledDequeueCollection(oneShotControlledDequeueCollectionFixture).items).toHaveLength(1);
        expect(parseOneShotControlledDequeueResult(oneShotControlledDequeueResultFixture).record?.disposition).toBe("exact_inert_item_dequeued");
        expect(parseOneShotControlledDequeueResult(blockedOneShotControlledDequeueResultFixture).error?.error_code).toBe("ambiguous_state");
        expect(parseOneShotControlledDequeueResult({ ...blockedOneShotControlledDequeueResultFixture, error: { ...blockedOneShotControlledDequeueResultFixture.error!, error_code: "dequeue_adapter_unavailable" }, outcome: "indeterminate" }).error?.error_code).toBe("dequeue_adapter_unavailable");
        expect(() => parseOneShotControlledDequeueResult({ ...oneShotControlledDequeueResultFixture, record: { ...oneShotControlledDequeueResultFixture.record!, worker_started: true } })).toThrow();
        expect(() => parseOneShotControlledDequeueResult({ ...oneShotControlledDequeueResultFixture, record: { ...oneShotControlledDequeueResultFixture.record!, bounded_receipt: { ...oneShotControlledDequeueResultFixture.record!.bounded_receipt, broker: "amqp://secret" } } })).toThrow();
        expect(() => parseOneShotControlledDequeueCollection({ ...oneShotControlledDequeueCollectionFixture, items: Array.from({ length: 17 }, () => oneShotControlledDequeueCollectionFixture.items[0]), count: 17 })).toThrow();
    });
});
