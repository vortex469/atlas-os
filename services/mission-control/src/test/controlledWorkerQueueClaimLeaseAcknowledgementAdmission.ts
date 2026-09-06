import { controlledWorkerQueueClaimAdmissionAuthority, controlledWorkerQueueClaimAdmissionFixture, controlledWorkerQueueClaimAdmissionResultFixture } from "./controlledWorkerQueueClaimAdmission";
import { fp } from "./installationReadinessReview";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1, ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultV1, ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1, ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1, ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1 } from "../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";

export const controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority = {
    ...controlledWorkerQueueClaimAdmissionAuthority,
    caller_supplied_queue_selector_allowed: false as const,
    caller_supplied_claim_token_allowed: false as const,
    caller_supplied_lease_token_allowed: false as const,
    caller_supplied_acknowledgement_handle_allowed: false as const,
    queue_selector_material_present: false as const,
    claim_token_material_present: false as const,
    lease_token_material_present: false as const,
    acknowledgement_handle_material_present: false as const,
    queue_adapter_defined: false as const,
    queue_requeue_allowed: false as const,
    agent_invoked: false as const,
};

const blockers = ["queue_adapter_not_defined", "queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"] as const;
const prerequisiteId = "9d602f89-f61a-5be6-9f49-0dcc884591fe";
const admissionId = "86274b9c-683d-5d06-b342-82498e2a572c";

export const controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1 = {
    ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority,
    schema: "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1",
    prerequisite_id: prerequisiteId,
    operator_id: controlledWorkerQueueClaimAdmissionFixture.operator_id,
    candidate_record_id: controlledWorkerQueueClaimAdmissionFixture.candidate_record_id,
    recorded_at: "2099-08-27T12:00:43Z",
    valid_until: "2099-08-27T12:00:44Z",
    lifecycle: "active",
    prerequisite_state: "frozen",
    eligibility: "v0.50_prerequisite_frozen",
    blockers: [...blockers],
    controlled_worker_queue_claim_admission: controlledWorkerQueueClaimAdmissionFixture,
    controlled_worker_queue_claim_admission_status: controlledWorkerQueueClaimAdmissionResultFixture.status!,
    admission_id: controlledWorkerQueueClaimAdmissionFixture.admission_id,
    admission_record_fingerprint: controlledWorkerQueueClaimAdmissionFixture.admission_record_fingerprint,
    admission_status_fingerprint: controlledWorkerQueueClaimAdmissionResultFixture.status!.status_fingerprint,
    binding_subject_fingerprint: controlledWorkerQueueClaimAdmissionFixture.binding_subject_fingerprint,
    worker_subject_fingerprint: controlledWorkerQueueClaimAdmissionFixture.worker_subject_fingerprint,
    queue_item_reference_fingerprint: controlledWorkerQueueClaimAdmissionFixture.queue_item_reference_fingerprint,
    inherited_limits_fingerprint: controlledWorkerQueueClaimAdmissionFixture.inherited_limits_fingerprint,
    subject_fingerprint: fp,
    idempotency_key_fingerprint: fp,
    prerequisite_record_fingerprint: fp,
    v0_50_prerequisite_frozen: true,
};

export const controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusFixture: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1 = {
    ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority,
    schema: "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-status-v1",
    prerequisite_id: prerequisiteId,
    operator_id: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.operator_id,
    candidate_record_id: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.candidate_record_id,
    lifecycle: "active",
    prerequisite_state: "v0.50_prerequisite_frozen",
    eligibility: "v0.50_prerequisite_frozen",
    blockers: [...blockers],
    evaluated_at: "2099-08-27T12:00:43Z",
    valid_until: "2099-08-27T12:00:44Z",
    prerequisite_record_fingerprint: fp,
    status_fingerprint: fp,
    v0_50_prerequisite_frozen: true,
};

export const controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 = {
    ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority,
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-v1",
    admission_id: admissionId,
    operator_id: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.operator_id,
    candidate_record_id: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.candidate_record_id,
    recorded_at: "2099-08-27T12:00:43Z",
    valid_until: "2099-08-27T12:00:44Z",
    lifecycle: "active",
    admission_state: "recorded",
    eligibility: "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
    blockers: [...blockers],
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture,
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusFixture,
    prerequisite_id: prerequisiteId,
    prerequisite_record_fingerprint: fp,
    prerequisite_status_fingerprint: fp,
    v049_admission_record_fingerprint: controlledWorkerQueueClaimAdmissionFixture.admission_record_fingerprint,
    v049_admission_status_fingerprint: controlledWorkerQueueClaimAdmissionResultFixture.status!.status_fingerprint,
    binding_subject_fingerprint: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.binding_subject_fingerprint,
    worker_subject_fingerprint: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.worker_subject_fingerprint,
    queue_item_reference_fingerprint: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.queue_item_reference_fingerprint,
    inherited_limits_fingerprint: controlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteFixture.inherited_limits_fingerprint,
    subject_fingerprint: fp,
    idempotency_key_fingerprint: fp,
    admission_record_fingerprint: fp,
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: true,
};

export const controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 = {
    ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority,
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-collection-v1",
    operator_id: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture.operator_id,
    candidate_record_id: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture.candidate_record_id,
    items: [controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture],
    count: 1,
    collection_fingerprint: fp,
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: false,
};

export const controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultV1 = {
    ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority,
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-result-v1",
    ok: true,
    outcome: "success",
    record: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture,
    status: {
        ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthority,
        schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-status-v1",
        admission_id: admissionId,
        operator_id: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture.operator_id,
        candidate_record_id: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionFixture.candidate_record_id,
        lifecycle: "active",
        admission_state: "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        eligibility: "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        blockers: [...blockers],
        evaluated_at: "2099-08-27T12:00:43Z",
        valid_until: "2099-08-27T12:00:44Z",
        admission_record_fingerprint: fp,
        status_fingerprint: fp,
        controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: true,
    },
    error: null,
    correlation_fingerprint: fp,
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: true,
};
