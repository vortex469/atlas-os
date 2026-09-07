import receipt from "./controlledWorkerQueueReceipt";
import { fp } from "./installationReadinessReview";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";

const closed = { ...Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, false])), evidence_only: true, reference_only: true, payload_bytes: 0 };
export const runtimeRecord = {
    ...closed, schema: "worker-activation-runtime-prerequisite-v1",
    prerequisite_id: "00000000-0000-5000-8000-000000000053",
    operator_id: receipt.record.operator_id, candidate_record_id: receipt.record.candidate_record_id,
    admission_id: receipt.record.admission_id,
    recorded_at: receipt.record.recorded_at, valid_until: receipt.record.valid_until,
    lifecycle: "active", eligibility: "worker_activation_runtime_prerequisite_recorded",
    blockers: receipt.record.blockers, worker_activation_runtime_prerequisite_recorded: true,
    controlled_worker_queue_claim_lease_acknowledgement: receipt.record,
    controlled_worker_queue_claim_lease_acknowledgement_status: receipt.status,
    subject_fingerprint: fp, idempotency_key_fingerprint: fp, prerequisite_record_fingerprint: fp,
};
export const runtimeCollection = {
    ...closed, schema: "worker-activation-runtime-prerequisite-collection-v1",
    operator_id: runtimeRecord.operator_id, candidate_record_id: runtimeRecord.candidate_record_id,
    items: [runtimeRecord], count: 1, collection_fingerprint: fp,
};
export const runtimeResult = {
    ...closed, schema: "worker-activation-runtime-prerequisite-result-v1",
    record: runtimeRecord, exact_duplicate: false, worker_activation_runtime_prerequisite_recorded: true,
    status: {
        ...closed, schema: "worker-activation-runtime-prerequisite-status-v1",
        prerequisite_id: runtimeRecord.prerequisite_id, operator_id: runtimeRecord.operator_id,
        candidate_record_id: runtimeRecord.candidate_record_id, admission_id: runtimeRecord.admission_id,
        recorded_at: runtimeRecord.recorded_at, valid_until: runtimeRecord.valid_until,
        evaluated_at: runtimeRecord.recorded_at, lifecycle: "active",
        eligibility: runtimeRecord.eligibility, blockers: runtimeRecord.blockers,
        prerequisite_record_fingerprint: fp, status_fingerprint: fp,
        worker_activation_runtime_prerequisite_recorded: true,
    },
};
