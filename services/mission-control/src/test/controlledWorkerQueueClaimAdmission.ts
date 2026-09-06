import { workerBindingActivationEvidenceAuthority, workerBindingActivationEvidenceFixture, workerBindingActivationEvidenceResultFixture } from "./workerBindingActivationEvidence";
import { fp } from "./installationReadinessReview";
import type { ControlledWorkerQueueClaimAdmissionCollectionV1, ControlledWorkerQueueClaimAdmissionResultV1, ControlledWorkerQueueClaimAdmissionV1 } from "../types/controlledWorkerQueueClaimAdmission";

export const controlledWorkerQueueClaimAdmissionAuthority = {
    ...workerBindingActivationEvidenceAuthority,
    queue_claimed: false as const,
    queue_leased: false as const,
    queue_acknowledged: false as const,
    worker_start_admitted: false as const,
    worker_started: false as const,
    execution_started: false as const,
};

const blockers = ["queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"] as const;
const admissionId = "7c4037f7-cf74-577c-8546-fc42c9160d89";

export const controlledWorkerQueueClaimAdmissionFixture: ControlledWorkerQueueClaimAdmissionV1 = {
    ...controlledWorkerQueueClaimAdmissionAuthority,
    schema: "controlled-worker-queue-claim-admission-v1",
    admission_id: admissionId,
    operator_id: workerBindingActivationEvidenceFixture.operator_id,
    candidate_record_id: workerBindingActivationEvidenceFixture.candidate_record_id,
    recorded_at: "2099-08-27T12:00:43Z",
    valid_until: "2099-08-27T12:00:44Z",
    lifecycle: "active",
    admission_state: "readiness_gated",
    eligibility: "controlled_worker_queue_claim_admission_recorded",
    blockers: [...blockers],
    worker_binding_activation_evidence: workerBindingActivationEvidenceFixture,
    worker_binding_activation_evidence_status: workerBindingActivationEvidenceResultFixture.status!,
    binding_subject_fingerprint: workerBindingActivationEvidenceFixture.binding_subject_fingerprint,
    worker_subject_fingerprint: workerBindingActivationEvidenceFixture.worker_subject_fingerprint,
    queue_item_reference_fingerprint: workerBindingActivationEvidenceFixture.queue_item_reference_fingerprint,
    inherited_limits_fingerprint: workerBindingActivationEvidenceFixture.inherited_limits_fingerprint,
    subject_fingerprint: fp,
    idempotency_key_fingerprint: fp,
    admission_record_fingerprint: fp,
    controlled_worker_queue_claim_admission_recorded: true,
};

export const controlledWorkerQueueClaimAdmissionCollectionFixture: ControlledWorkerQueueClaimAdmissionCollectionV1 = {
    ...controlledWorkerQueueClaimAdmissionAuthority,
    schema: "controlled-worker-queue-claim-admission-collection-v1",
    operator_id: controlledWorkerQueueClaimAdmissionFixture.operator_id,
    candidate_record_id: controlledWorkerQueueClaimAdmissionFixture.candidate_record_id,
    items: [controlledWorkerQueueClaimAdmissionFixture],
    count: 1,
    collection_fingerprint: fp,
    controlled_worker_queue_claim_admission_recorded: false,
};

export const controlledWorkerQueueClaimAdmissionResultFixture: ControlledWorkerQueueClaimAdmissionResultV1 = {
    ...controlledWorkerQueueClaimAdmissionAuthority,
    schema: "controlled-worker-queue-claim-admission-result-v1",
    ok: true,
    outcome: "success",
    record: controlledWorkerQueueClaimAdmissionFixture,
    status: {
        ...controlledWorkerQueueClaimAdmissionAuthority,
        schema: "controlled-worker-queue-claim-admission-status-v1",
        admission_id: admissionId,
        operator_id: controlledWorkerQueueClaimAdmissionFixture.operator_id,
        candidate_record_id: controlledWorkerQueueClaimAdmissionFixture.candidate_record_id,
        lifecycle: "active",
        admission_state: "controlled_worker_queue_claim_admission_recorded",
        eligibility: "controlled_worker_queue_claim_admission_recorded",
        blockers: [...blockers],
        evaluated_at: "2099-08-27T12:00:43Z",
        valid_until: "2099-08-27T12:00:44Z",
        admission_record_fingerprint: fp,
        status_fingerprint: fp,
        controlled_worker_queue_claim_admission_recorded: true,
    },
    error: null,
    correlation_fingerprint: fp,
    controlled_worker_queue_claim_admission_recorded: true,
};
