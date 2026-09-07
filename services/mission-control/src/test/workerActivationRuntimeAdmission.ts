import { runtimeRecord, runtimeResult } from "./workerActivationRuntimePrerequisite";
import { parseWorkerActivationRuntimePrerequisite } from "../api/workerActivationRuntimePrerequisite";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
import { fp } from "./installationReadinessReview";
const closed = { ...Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, false])), evidence_only: true, reference_only: true, payload_bytes: 0 };
export const prerequisite = parseWorkerActivationRuntimePrerequisite(runtimeResult, runtimeRecord.candidate_record_id, runtimeRecord.operator_id, runtimeRecord.prerequisite_id, runtimeRecord.admission_id);
const common = {
    ...closed, runtime_admission_id: "00000000-0000-5000-8000-000000000054",
    prerequisite_id: runtimeRecord.prerequisite_id, admission_id: runtimeRecord.admission_id,
    operator_id: runtimeRecord.operator_id, candidate_record_id: runtimeRecord.candidate_record_id,
    recorded_at: runtimeRecord.recorded_at, valid_until: runtimeRecord.valid_until,
    lifecycle: "active", eligibility: "worker_activation_runtime_admission_recorded",
    worker_activation_runtime_admission_recorded: true, blockers: runtimeRecord.blockers,
    runtime_admission_record_fingerprint: fp,
};
export const admissionRecord = {
    ...common, schema: "worker-activation-runtime-admission-v1",
    subject_fingerprint: fp, idempotency_key_fingerprint: fp,
    worker_activation_runtime_prerequisite: runtimeRecord,
    worker_activation_runtime_prerequisite_status: runtimeResult.status,
};
export const admissionCollection = {
    ...closed, schema: "worker-activation-runtime-admission-collection-v1",
    operator_id: common.operator_id, candidate_record_id: common.candidate_record_id,
    count: 1, items: [admissionRecord], collection_fingerprint: fp,
};
export const admissionResult = {
    ...closed, schema: "worker-activation-runtime-admission-result-v1",
    record: admissionRecord, exact_duplicate: false, worker_activation_runtime_admission_recorded: true,
    status: { ...common, schema: "worker-activation-runtime-admission-status-v1", evaluated_at: common.recorded_at, status_fingerprint: fp },
};
