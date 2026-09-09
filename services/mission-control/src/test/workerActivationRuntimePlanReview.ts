import { planResult } from "./workerActivationRuntimePlan";
import { parseWorkerActivationRuntimePlan } from "../api/workerActivationRuntimePlan";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
import { fp } from "./installationReadinessReview";
const closed = { ...Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, false])), evidence_only: true, reference_only: true, payload_bytes: 0 };
const prior = planResult.record;
const common = { ...closed, runtime_plan_review_id: "00000000-0000-5000-8000-000000000056",
    runtime_plan_id: prior.runtime_plan_id, runtime_admission_id: prior.runtime_admission_id,
    prerequisite_id: prior.prerequisite_id, admission_id: prior.admission_id,
    profile: "core_owned_reference_only_runtime_plan_review_v1",
    findings: ["exact_plan_lineage", "fixed_design_consistent", "unresolved_interfaces_preserved"],
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    recorded_at: prior.recorded_at, valid_until: prior.valid_until, lifecycle: "active",
    eligibility: "worker_activation_runtime_plan_review_recorded", worker_activation_runtime_plan_review_recorded: true,
    worker_activation_runtime_plan_recorded: true, blockers: prior.blockers, runtime_plan_review_record_fingerprint: fp };
export const reviewRecord = { ...common, schema: "worker-activation-runtime-plan-review-v1",
    subject_fingerprint: fp, idempotency_key_fingerprint: fp,
    worker_activation_runtime_plan: prior, worker_activation_runtime_plan_status: planResult.status };
export const reviewResult = { ...closed, schema: "worker-activation-runtime-plan-review-result-v1", record: reviewRecord,
    exact_duplicate: false, worker_activation_runtime_plan_review_recorded: true, worker_activation_runtime_plan_recorded: true,
    status: { ...common, schema: "worker-activation-runtime-plan-review-status-v1", evaluated_at: prior.recorded_at, status_fingerprint: fp } };
export const reviewCollection = { ...closed, schema: "worker-activation-runtime-plan-review-collection-v1",
    operator_id: prior.operator_id, candidate_record_id: prior.candidate_record_id,
    items: [reviewRecord], count: 1, collection_fingerprint: fp };
export const plan = parseWorkerActivationRuntimePlan(planResult, prior.candidate_record_id, prior.operator_id);
