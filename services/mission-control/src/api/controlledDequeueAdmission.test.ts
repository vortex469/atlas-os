import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { controlledDequeueAdmissionCreateFromObservation, createControlledDequeueAdmission, getControlledDequeueAdmission, listControlledDequeueAdmissions, parseControlledDequeueAdmissionCollection, parseControlledDequeueAdmissionResult } from "./controlledDequeueAdmission";
import { ambiguousControlledDequeueAdmissionResultFixture, controlledDequeueAdmissionCollectionFixture, controlledDequeueAdmissionResultFixture } from "../test/controlledDequeueAdmission";
import { queueObservationReceiptFixture, queueObservationResultFixture } from "../test/queueObservation";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

describe("controlled dequeue admission API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded list/get/create endpoints", async () => {
        const body = controlledDequeueAdmissionCreateFromObservation(queueObservationReceiptFixture, queueObservationResultFixture.status!);
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: controlledDequeueAdmissionCollectionFixture }).mockResolvedValueOnce({ data: controlledDequeueAdmissionResultFixture });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: controlledDequeueAdmissionResultFixture });
        await listControlledDequeueAdmissions("candidate/id");
        await getControlledDequeueAdmission("candidate/id", "admission/id");
        await createControlledDequeueAdmission("candidate/id", body, "csrf", "controlled-dequeue-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/controlled-dequeue-admissions", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/controlled-dequeue-admissions/admission%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records/candidate%2Fid/controlled-dequeue-admissions", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "controlled-dequeue-key" } });
    });

    it("builds the create request only from exact v0.43 queue observation readback evidence", () => {
        const body = controlledDequeueAdmissionCreateFromObservation(queueObservationReceiptFixture, queueObservationResultFixture.status!);
        expect(body).toMatchObject({
            schema: "controlled-dequeue-admission-create-v1",
            queue_observation_receipt_id: queueObservationReceiptFixture.receipt_id,
            queue_observation_receipt_fingerprint: queueObservationReceiptFixture.receipt_record_fingerprint,
            queue_observation_receipt_status_fingerprint: queueObservationResultFixture.status!.status_fingerprint,
            enqueue_id: queueObservationReceiptFixture.v042_enqueue.enqueue_id,
            inert_queue_item_id: queueObservationReceiptFixture.v042_enqueue.queue_item.queue_item_id,
            queue_identity: "abstract_installation_queue",
            item_identity: "inert_reference_only_queue_item",
            requested_scope: "installation_controlled_dequeue_admission_only",
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

    it("strictly parses valid, blocked, stale, and ambiguous states without effect authority", () => {
        expect(parseControlledDequeueAdmissionCollection(controlledDequeueAdmissionCollectionFixture).items).toHaveLength(1);
        expect(parseControlledDequeueAdmissionResult(controlledDequeueAdmissionResultFixture).record?.eligibility).toBe("eligible_for_later_dequeue_consideration");
        expect(parseControlledDequeueAdmissionResult(ambiguousControlledDequeueAdmissionResultFixture).error?.error_code).toBe("ambiguous_state");
        expect(parseControlledDequeueAdmissionResult({ ...ambiguousControlledDequeueAdmissionResultFixture, error: { ...ambiguousControlledDequeueAdmissionResultFixture.error!, error_code: "evidence_stale" } }).error?.error_code).toBe("evidence_stale");
        expect(() => parseControlledDequeueAdmissionResult({ ...controlledDequeueAdmissionResultFixture, record: { ...controlledDequeueAdmissionResultFixture.record!, dequeue_allowed: true } })).toThrow();
        expect(() => parseControlledDequeueAdmissionResult({ ...controlledDequeueAdmissionResultFixture, record: { ...controlledDequeueAdmissionResultFixture.record!, queue_observation_receipt: { ...controlledDequeueAdmissionResultFixture.record!.queue_observation_receipt, receipt_evidence: { ...controlledDequeueAdmissionResultFixture.record!.queue_observation_receipt.receipt_evidence, endpoint: "amqp://secret" } } } })).toThrow();
        expect(() => parseControlledDequeueAdmissionCollection({ ...controlledDequeueAdmissionCollectionFixture, items: Array.from({ length: 17 }, () => controlledDequeueAdmissionCollectionFixture.items[0]), count: 17 })).toThrow();
    });
});
