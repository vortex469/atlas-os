import { admissionResult as historical } from "./workerActivationRuntimeAdmission";
import { parseWorkerActivationRuntimeAdmission } from "../api/workerActivationRuntimeAdmission";
import { parseWorkerActivationRuntimePrerequisite } from "../api/workerActivationRuntimePrerequisite";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
import { fp } from "./installationReadinessReview";
const closed = { ...Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, false])), evidence_only: true, reference_only: true, payload_bytes: 0 };
export const admissionResult = structuredClone(historical);
// The historical UI fixture spread a whole v0.40 record into its status. Remove
// only those ten non-status fields to match Core's status schema, preserving all
// record lineage and every authority field within the unchanged 192 KiB bound.
const intakeStatus = admissionResult.record.worker_activation_runtime_prerequisite
    .controlled_worker_queue_claim_lease_acknowledgement
    .controlled_worker_queue_claim_lease_acknowledgement_admission
    .controlled_worker_queue_claim_lease_acknowledgement_prerequisite
    .controlled_worker_queue_claim_admission.worker_binding_activation_evidence
    .worker_binding_activation_preflight.one_shot_dequeue_worker_binding.worker_intake_admission_status;
for (const key of ["recorded_at", "record_state", "linkage", "worker_identity", "worker_intake_reference", "admission_decision", "inherited_limits", "idempotency_key_fingerprint", "request_fingerprint", "subject_fingerprint"]) {
    delete (intakeStatus as unknown as Record<string, unknown>)[key];
}
const prior = admissionResult.record;
const common = { ...closed, runtime_plan_id: "00000000-0000-5000-8000-000000000055",
    runtime_admission_id: prior.runtime_admission_id, prerequisite_id: prior.prerequisite_id, admission_id: prior.admission_id,
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    recorded_at: prior.recorded_at, valid_until: prior.valid_until, lifecycle: "active",
    eligibility: "worker_activation_runtime_plan_recorded", worker_activation_runtime_plan_recorded: true,
    worker_activation_runtime_admission_recorded: true, blockers: prior.blockers, runtime_plan_record_fingerprint: fp };
export const planRecord = { ...common, schema: "worker-activation-runtime-plan-v1",
    subject_fingerprint: fp, idempotency_key_fingerprint: fp,
    worker_activation_runtime_admission: prior, worker_activation_runtime_admission_status: admissionResult.status,
    design: { ...closed, schema: "worker-activation-runtime-plan-design-v1",
        profile: "core_owned_reference_only_runtime_plan_v1", evidence_owner: "atlas_core",
        admission_reader: "core_owned_runtime_admission_reader", plan_journal: "separate_core_owned_plan_journal",
        presentation: "read_only", inherited_references: "exact_embedded_admission_pair",
        worker_store_contact_interface: "undefined", worker_runtime_contact_interface: "undefined", unresolved_interfaces: prior.blockers } };
export const planResult = { ...closed, schema: "worker-activation-runtime-plan-result-v1", record: planRecord,
    exact_duplicate: false, worker_activation_runtime_plan_recorded: true, worker_activation_runtime_admission_recorded: true,
    status: { ...common, schema: "worker-activation-runtime-plan-status-v1", evaluated_at: prior.recorded_at, status_fingerprint: fp } };
export const planCollection = { ...closed, schema: "worker-activation-runtime-plan-collection-v1",
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    items: [planRecord], count: 1, collection_fingerprint: fp };
export const admissionCollection = { ...closed, schema: "worker-activation-runtime-admission-collection-v1",
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    items: [prior], count: 1, collection_fingerprint: fp };
export const admission = parseWorkerActivationRuntimeAdmission(admissionResult, prior.candidate_record_id, prior.operator_id);
export const prerequisite = parseWorkerActivationRuntimePrerequisite({ ...closed,
    schema: "worker-activation-runtime-prerequisite-result-v1", record: prior.worker_activation_runtime_prerequisite,
    status: prior.worker_activation_runtime_prerequisite_status, exact_duplicate: false,
    worker_activation_runtime_prerequisite_recorded: true,
}, prior.candidate_record_id, prior.operator_id, prior.prerequisite_id, prior.admission_id);
