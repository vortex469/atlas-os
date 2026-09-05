import { controlledDequeueAdmissionAuthority, controlledDequeueAdmissionFixture, controlledDequeueAdmissionResultFixture } from "./controlledDequeueAdmission";
import { fp } from "./installationReadinessReview";
import type { OneShotControlledDequeueCollectionV1, OneShotControlledDequeueResultV1, OneShotControlledDequeueV1 } from "../types/oneShotControlledDequeue";

const blockers = ["queue_polling_not_defined", "queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"] as const;
const dequeueId = "4b3beb58-c4b9-5b2b-9995-4f629abefaf7";

export const oneShotControlledDequeueFixture: OneShotControlledDequeueV1 = {
    ...controlledDequeueAdmissionAuthority,
    schema: "one-shot-controlled-dequeue-v1",
    dequeue_id: dequeueId,
    operator_id: controlledDequeueAdmissionFixture.operator_id,
    candidate_record_id: controlledDequeueAdmissionFixture.candidate_record_id,
    recorded_at: "2099-08-27T12:00:50Z",
    valid_until: "2099-08-27T12:01:12Z",
    lifecycle: "active",
    dequeue_state: "one_shot_controlled_dequeue_recorded",
    outcome: "success",
    disposition: "exact_inert_item_dequeued",
    blockers: [...blockers],
    controlled_dequeue_admission: controlledDequeueAdmissionFixture,
    controlled_dequeue_admission_status: controlledDequeueAdmissionResultFixture.status!,
    inherited_limits: controlledDequeueAdmissionFixture.inherited_limits,
    bounded_receipt: {
        ...controlledDequeueAdmissionAuthority,
        schema: "bounded-one-shot-controlled-dequeue-receipt-v1",
        outcome: "success",
        disposition: "exact_inert_item_dequeued",
        exact_admitted_item_only: true,
        adapter_receipt_redacted: true,
        adapter_receipt_fingerprint: fp,
        queue_identity_fingerprint: controlledDequeueAdmissionFixture.queue_identity_fingerprint,
        item_identity_fingerprint: controlledDequeueAdmissionFixture.item_identity_fingerprint,
        receipt_fingerprint: fp,
    },
    queue_identity_fingerprint: controlledDequeueAdmissionFixture.queue_identity_fingerprint,
    item_identity_fingerprint: controlledDequeueAdmissionFixture.item_identity_fingerprint,
    lineage_fingerprint: controlledDequeueAdmissionFixture.lineage_fingerprint,
    subject_fingerprint: fp,
    idempotency_key_fingerprint: fp,
    dequeue_record_fingerprint: fp,
    one_shot_controlled_dequeue_recorded: true,
};

export const oneShotControlledDequeueCollectionFixture: OneShotControlledDequeueCollectionV1 = {
    ...controlledDequeueAdmissionAuthority,
    schema: "one-shot-controlled-dequeue-collection-v1",
    operator_id: oneShotControlledDequeueFixture.operator_id,
    candidate_record_id: oneShotControlledDequeueFixture.candidate_record_id,
    items: [oneShotControlledDequeueFixture],
    count: 1,
    collection_fingerprint: fp,
    one_shot_controlled_dequeue_recorded: false,
};

export const oneShotControlledDequeueResultFixture: OneShotControlledDequeueResultV1 = {
    ...controlledDequeueAdmissionAuthority,
    schema: "one-shot-controlled-dequeue-result-v1",
    ok: true,
    outcome: "success",
    record: oneShotControlledDequeueFixture,
    status: {
        ...controlledDequeueAdmissionAuthority,
        schema: "one-shot-controlled-dequeue-status-v1",
        dequeue_id: dequeueId,
        operator_id: oneShotControlledDequeueFixture.operator_id,
        candidate_record_id: oneShotControlledDequeueFixture.candidate_record_id,
        lifecycle: "active",
        dequeue_state: "one_shot_controlled_dequeue_recorded",
        outcome: "success",
        disposition: "exact_inert_item_dequeued",
        blockers: [...blockers],
        evaluated_at: "2099-08-27T12:00:51Z",
        valid_until: "2099-08-27T12:01:12Z",
        dequeue_record_fingerprint: fp,
        status_fingerprint: fp,
        one_shot_controlled_dequeue_recorded: true,
    },
    error: null,
    correlation_fingerprint: fp,
    one_shot_controlled_dequeue_recorded: true,
};

export const blockedOneShotControlledDequeueResultFixture: OneShotControlledDequeueResultV1 = {
    ...controlledDequeueAdmissionAuthority,
    schema: "one-shot-controlled-dequeue-result-v1",
    ok: false,
    outcome: "failure",
    record: null,
    status: null,
    error: {
        ...controlledDequeueAdmissionAuthority,
        schema: "one-shot-controlled-dequeue-error-v1",
        error_code: "ambiguous_state",
        message: "one-shot controlled dequeue request could not be completed",
        retryable: false,
        correlation_fingerprint: fp,
        redacted: true,
        one_shot_controlled_dequeue_recorded: false,
    },
    correlation_fingerprint: fp,
    one_shot_controlled_dequeue_recorded: false,
};
