import type { OneShotControlledDequeueStatusV1, OneShotControlledDequeueV1 } from "./oneShotControlledDequeue";
import type { FingerprintV1 } from "./installationReadinessReview";
import type { WorkerIntakeAdmissionStatusV1, WorkerIntakeAdmissionV1 } from "./workerIntakeAdmission";

export type OneShotDequeueWorkerBindingAuthorityV1 = {
    evidence_only: true;
    reference_only: true;
    caller_supplied_credentials_allowed: false;
    caller_supplied_endpoint_allowed: false;
    caller_supplied_command_allowed: false;
    credential_material_present: false;
    endpoint_material_present: false;
    command_material_present: false;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    queue_polling_allowed: false;
    queue_claim_allowed: false;
    queue_lease_allowed: false;
    queue_ack_allowed: false;
    queue_mutation_allowed: false;
    worker_contact_allowed: false;
    worker_start_allowed: false;
    agent_invocation_allowed: false;
    execution_start_allowed: false;
    process_execution_allowed: false;
    store_contact_allowed: false;
    runtime_contact_allowed: false;
    dispatch_allowed: false;
    retry_allowed: false;
    scheduler_allowed: false;
    workflow_start_allowed: false;
    shell_execution_allowed: false;
    provider_mutation_allowed: false;
    repository_mutation_allowed: false;
    in_guest_mutation_allowed: false;
    installation_allowed: false;
    deployment_allowed: false;
    rollback_allowed: false;
    replay_bypass_allowed: false;
    one_shot_dequeue_worker_binding_recorded?: boolean;
};

export type OneShotDequeueWorkerBindingBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v045_dequeue_not_active" | "v045_dequeue_not_recorded"
    | "v045_dequeue_not_successful" | "v040_worker_intake_not_active"
    | "v040_worker_intake_not_recorded" | "linkage_mismatch"
    | "worker_subject_mismatch" | "queue_item_reference_mismatch"
    | "fingerprint_mismatch" | "inherited_limits_mismatch"
    | "evidence_stale" | "evidence_expired" | "ambiguous_state"
    | "caller_supplied_credential" | "caller_supplied_endpoint"
    | "caller_supplied_command" | "unsupported_authority"
    | "store_contact_not_defined" | "runtime_contact_not_defined"
    | "worker_start_not_defined" | "execution_start_boundary_not_defined"
    | "reservation_before_effect_failed" | "permanent_subject_reserved"
    | "idempotency_conflict" | "append_indeterminate";

export type OneShotDequeueWorkerBindingV1 = OneShotDequeueWorkerBindingAuthorityV1 & {
    schema: "one-shot-dequeue-worker-binding-v1";
    binding_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    binding_state: "readiness_gated";
    eligibility: "one_shot_dequeue_worker_binding_recorded";
    blockers: OneShotDequeueWorkerBindingBlockerV1[];
    one_shot_controlled_dequeue: OneShotControlledDequeueV1;
    one_shot_controlled_dequeue_status: OneShotControlledDequeueStatusV1;
    worker_intake_admission: WorkerIntakeAdmissionV1;
    worker_intake_admission_status: WorkerIntakeAdmissionStatusV1;
    worker_subject_fingerprint: FingerprintV1;
    queue_item_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    binding_record_fingerprint: FingerprintV1;
    one_shot_dequeue_worker_binding_recorded: true;
};

export type OneShotDequeueWorkerBindingStatusV1 = OneShotDequeueWorkerBindingAuthorityV1 & {
    schema: "one-shot-dequeue-worker-binding-status-v1";
    binding_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    binding_state: "one_shot_dequeue_worker_binding_recorded";
    eligibility: "one_shot_dequeue_worker_binding_recorded";
    blockers: OneShotDequeueWorkerBindingBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    binding_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    one_shot_dequeue_worker_binding_recorded: true;
};

export type OneShotDequeueWorkerBindingErrorV1 = OneShotDequeueWorkerBindingAuthorityV1 & {
    schema: "one-shot-dequeue-worker-binding-error-v1";
    error_code: OneShotDequeueWorkerBindingBlockerV1 | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "one-shot dequeue worker binding request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    one_shot_dequeue_worker_binding_recorded: false;
};

export type OneShotDequeueWorkerBindingResultV1 = OneShotDequeueWorkerBindingAuthorityV1 & {
    schema: "one-shot-dequeue-worker-binding-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: OneShotDequeueWorkerBindingV1 | null;
    status: OneShotDequeueWorkerBindingStatusV1 | null;
    error: OneShotDequeueWorkerBindingErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    one_shot_dequeue_worker_binding_recorded: boolean;
};

export type OneShotDequeueWorkerBindingCollectionV1 = OneShotDequeueWorkerBindingAuthorityV1 & {
    schema: "one-shot-dequeue-worker-binding-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: OneShotDequeueWorkerBindingV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    one_shot_dequeue_worker_binding_recorded: false;
};
