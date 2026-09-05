import { oneShotDequeueWorkerBindingFixture, oneShotDequeueWorkerBindingResultFixture, oneShotDequeueWorkerBindingAuthority } from "./oneShotDequeueWorkerBinding";
import { fp } from "./installationReadinessReview";
import type { WorkerBindingActivationPreflightCollectionV1, WorkerBindingActivationPreflightResultV1, WorkerBindingActivationPreflightV1 } from "../types/workerBindingActivationPreflight";

export const workerBindingActivationPreflightAuthority = {
    ...oneShotDequeueWorkerBindingAuthority,
    caller_supplied_payload_allowed: false as const,
    payload_material_present: false as const,
    queue_consume_allowed: false as const,
    worker_store_contact_allowed: false as const,
    worker_runtime_contact_allowed: false as const,
    worker_invocation_allowed: false as const,
    execution_authorization_allowed: false as const,
    resend_allowed: false as const,
    artifact_publication_allowed: false as const,
    tag_push_allowed: false as const,
    release_publication_allowed: false as const,
    binding_activation_allowed: false as const,
};

const blockers = ["worker_binding_activation_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"] as const;
const preflightId = "f83d7de2-6e64-59fd-9960-cf12ef4f964a";

export const workerBindingActivationPreflightFixture: WorkerBindingActivationPreflightV1 = {
    ...workerBindingActivationPreflightAuthority,
    schema: "worker-binding-activation-preflight-v1",
    preflight_id: preflightId,
    operator_id: oneShotDequeueWorkerBindingFixture.operator_id,
    candidate_record_id: oneShotDequeueWorkerBindingFixture.candidate_record_id,
    recorded_at: "2099-08-27T12:00:43Z",
    valid_until: "2099-08-27T12:00:44Z",
    lifecycle: "active",
    preflight_state: "readiness_gated",
    eligibility: "worker_binding_activation_preflight_recorded",
    blockers: [...blockers],
    one_shot_dequeue_worker_binding: oneShotDequeueWorkerBindingFixture,
    one_shot_dequeue_worker_binding_status: oneShotDequeueWorkerBindingResultFixture.status!,
    binding_subject_fingerprint: oneShotDequeueWorkerBindingFixture.subject_fingerprint,
    worker_subject_fingerprint: oneShotDequeueWorkerBindingFixture.worker_subject_fingerprint,
    queue_item_reference_fingerprint: oneShotDequeueWorkerBindingFixture.queue_item_reference_fingerprint,
    inherited_limits_fingerprint: oneShotDequeueWorkerBindingFixture.inherited_limits_fingerprint,
    subject_fingerprint: fp,
    idempotency_key_fingerprint: fp,
    preflight_record_fingerprint: fp,
    worker_binding_activation_preflight_recorded: true,
};

export const workerBindingActivationPreflightCollectionFixture: WorkerBindingActivationPreflightCollectionV1 = {
    ...workerBindingActivationPreflightAuthority,
    schema: "worker-binding-activation-preflight-collection-v1",
    operator_id: workerBindingActivationPreflightFixture.operator_id,
    candidate_record_id: workerBindingActivationPreflightFixture.candidate_record_id,
    items: [workerBindingActivationPreflightFixture],
    count: 1,
    collection_fingerprint: fp,
    worker_binding_activation_preflight_recorded: false,
};

export const workerBindingActivationPreflightResultFixture: WorkerBindingActivationPreflightResultV1 = {
    ...workerBindingActivationPreflightAuthority,
    schema: "worker-binding-activation-preflight-result-v1",
    ok: true,
    outcome: "success",
    record: workerBindingActivationPreflightFixture,
    status: {
        ...workerBindingActivationPreflightAuthority,
        schema: "worker-binding-activation-preflight-status-v1",
        preflight_id: preflightId,
        operator_id: workerBindingActivationPreflightFixture.operator_id,
        candidate_record_id: workerBindingActivationPreflightFixture.candidate_record_id,
        lifecycle: "active",
        preflight_state: "worker_binding_activation_preflight_recorded",
        eligibility: "worker_binding_activation_preflight_recorded",
        blockers: [...blockers],
        evaluated_at: "2099-08-27T12:00:43Z",
        valid_until: "2099-08-27T12:00:44Z",
        preflight_record_fingerprint: fp,
        status_fingerprint: fp,
        worker_binding_activation_preflight_recorded: true,
    },
    error: null,
    correlation_fingerprint: fp,
    worker_binding_activation_preflight_recorded: true,
};
