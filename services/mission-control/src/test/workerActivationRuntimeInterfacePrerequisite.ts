import { reviewResult } from "./workerActivationRuntimePlanReview";
import { parseWorkerActivationRuntimePlanReview } from "../api/workerActivationRuntimePlanReview";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
import { fp } from "./installationReadinessReview";
const closed = { ...Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, false])), evidence_only: true, reference_only: true, payload_bytes: 0 };
const prior = reviewResult.record;
const common = { ...closed, runtime_interface_prerequisite_id: "00000000-0000-5000-8000-000000000057",
    runtime_plan_id: prior.runtime_plan_id, runtime_plan_review_id: prior.runtime_plan_review_id, runtime_admission_id: prior.runtime_admission_id,
    prerequisite_id: prior.prerequisite_id, admission_id: prior.admission_id,
    profile: "core_owned_reference_only_runtime_interface_prerequisite_v1",
    inventory: [
    {
        "blocker": "worker_activation_runtime_not_defined",
        "owner": "core_installation_authority",
        "required_proof": "installation_runtime_identity_capability_composition_lifecycle"
    },
    {
        "blocker": "store_contact_not_defined",
        "owner": "worker_storage_authority",
        "required_proof": "authenticated_store_subject_protocol_operations_recovery"
    },
    {
        "blocker": "runtime_contact_not_defined",
        "owner": "worker_runtime_authority",
        "required_proof": "authenticated_runtime_peer_request_effect_limits_uncertainty"
    },
    {
        "blocker": "worker_start_admission_not_defined",
        "owner": "core_admission_authority",
        "required_proof": "validated_runtime_contact_prerequisites_exact_subject_admission"
    },
    {
        "blocker": "worker_start_not_defined",
        "owner": "worker_authority",
        "required_proof": "one_shot_start_reservation_durability_no_replay_uncertainty"
    },
    {
        "blocker": "agent_invocation_not_defined",
        "owner": "agent_authority",
        "required_proof": "installation_intent_authentication_exact_approvals"
    },
    {
        "blocker": "execution_start_boundary_not_defined",
        "owner": "execution_authority",
        "required_proof": "exact_execution_request_capability_approval_durable_ledger"
    }
],
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    recorded_at: prior.recorded_at, valid_until: prior.valid_until, lifecycle: "active",
    eligibility: "worker_activation_runtime_interface_prerequisite_recorded", worker_activation_runtime_interface_prerequisite_recorded: true,
    worker_activation_runtime_plan_recorded: true, worker_activation_runtime_plan_review_recorded: true, blockers: prior.blockers, runtime_interface_prerequisite_record_fingerprint: fp };
export const inventoryRecord = { ...common, schema: "worker-activation-runtime-interface-prerequisite-v1",
    subject_fingerprint: fp, idempotency_key_fingerprint: fp,
    worker_activation_runtime_plan_review: prior, worker_activation_runtime_plan_review_status: reviewResult.status };
export const inventoryResult = { ...closed, schema: "worker-activation-runtime-interface-prerequisite-result-v1", record: inventoryRecord,
    exact_duplicate: false, worker_activation_runtime_interface_prerequisite_recorded: true, worker_activation_runtime_plan_recorded: true, worker_activation_runtime_plan_review_recorded: true,
    status: { ...common, schema: "worker-activation-runtime-interface-prerequisite-status-v1", evaluated_at: prior.recorded_at, status_fingerprint: fp } };
export const inventoryCollection = { ...closed, schema: "worker-activation-runtime-interface-prerequisite-collection-v1",
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    items: [inventoryRecord], count: 1, collection_fingerprint: fp };
export const review = parseWorkerActivationRuntimePlanReview(reviewResult, prior.candidate_record_id, prior.operator_id);
