import { workerBindingActivationPreflightAuthority, workerBindingActivationPreflightFixture, workerBindingActivationPreflightResultFixture } from "./workerBindingActivationPreflight";
import { fp } from "./installationReadinessReview";
import type { WorkerBindingActivationEvidenceCollectionV1, WorkerBindingActivationEvidenceResultV1, WorkerBindingActivationEvidenceV1 } from "../types/workerBindingActivationEvidence";

export const workerBindingActivationEvidenceAuthority = {
    ...workerBindingActivationPreflightAuthority,
    worker_start_admission_allowed: false as const,
    worker_activation_runtime_allowed: false as const,
};

const blockers = ["worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"] as const;
const activationEvidenceId = "2b93d23d-ae7a-5960-a081-f32cf2c106d1";

export const workerBindingActivationEvidenceFixture: WorkerBindingActivationEvidenceV1 = {
    ...workerBindingActivationEvidenceAuthority,
    schema: "worker-binding-activation-evidence-v1",
    activation_evidence_id: activationEvidenceId,
    operator_id: workerBindingActivationPreflightFixture.operator_id,
    candidate_record_id: workerBindingActivationPreflightFixture.candidate_record_id,
    recorded_at: "2099-08-27T12:00:43Z",
    valid_until: "2099-08-27T12:00:44Z",
    lifecycle: "active",
    activation_evidence_state: "readiness_gated",
    eligibility: "worker_binding_activation_evidence_recorded",
    blockers: [...blockers],
    worker_binding_activation_preflight: workerBindingActivationPreflightFixture,
    worker_binding_activation_preflight_status: workerBindingActivationPreflightResultFixture.status!,
    binding_subject_fingerprint: workerBindingActivationPreflightFixture.binding_subject_fingerprint,
    worker_subject_fingerprint: workerBindingActivationPreflightFixture.worker_subject_fingerprint,
    queue_item_reference_fingerprint: workerBindingActivationPreflightFixture.queue_item_reference_fingerprint,
    inherited_limits_fingerprint: workerBindingActivationPreflightFixture.inherited_limits_fingerprint,
    subject_fingerprint: fp,
    idempotency_key_fingerprint: fp,
    activation_evidence_record_fingerprint: fp,
    worker_binding_activation_evidence_recorded: true,
};

export const workerBindingActivationEvidenceCollectionFixture: WorkerBindingActivationEvidenceCollectionV1 = {
    ...workerBindingActivationEvidenceAuthority,
    schema: "worker-binding-activation-evidence-collection-v1",
    operator_id: workerBindingActivationEvidenceFixture.operator_id,
    candidate_record_id: workerBindingActivationEvidenceFixture.candidate_record_id,
    items: [workerBindingActivationEvidenceFixture],
    count: 1,
    collection_fingerprint: fp,
    worker_binding_activation_evidence_recorded: false,
};

export const workerBindingActivationEvidenceResultFixture: WorkerBindingActivationEvidenceResultV1 = {
    ...workerBindingActivationEvidenceAuthority,
    schema: "worker-binding-activation-evidence-result-v1",
    ok: true,
    outcome: "success",
    record: workerBindingActivationEvidenceFixture,
    status: {
        ...workerBindingActivationEvidenceAuthority,
        schema: "worker-binding-activation-evidence-status-v1",
        activation_evidence_id: activationEvidenceId,
        operator_id: workerBindingActivationEvidenceFixture.operator_id,
        candidate_record_id: workerBindingActivationEvidenceFixture.candidate_record_id,
        lifecycle: "active",
        activation_evidence_state: "worker_binding_activation_evidence_recorded",
        eligibility: "worker_binding_activation_evidence_recorded",
        blockers: [...blockers],
        evaluated_at: "2099-08-27T12:00:43Z",
        valid_until: "2099-08-27T12:00:44Z",
        activation_evidence_record_fingerprint: fp,
        status_fingerprint: fp,
        worker_binding_activation_evidence_recorded: true,
    },
    error: null,
    correlation_fingerprint: fp,
    worker_binding_activation_evidence_recorded: true,
};
