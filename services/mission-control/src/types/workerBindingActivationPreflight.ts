import type { FingerprintV1 } from "./installationReadinessReview";
import type { OneShotDequeueWorkerBindingStatusV1, OneShotDequeueWorkerBindingV1 } from "./oneShotDequeueWorkerBinding";

export type WorkerBindingActivationPreflightAuthorityV1 = {
    evidence_only: true;
    reference_only: true;
    caller_supplied_credentials_allowed: false;
    caller_supplied_endpoint_allowed: false;
    caller_supplied_command_allowed: false;
    caller_supplied_payload_allowed: false;
    credential_material_present: false;
    endpoint_material_present: false;
    command_material_present: false;
    payload_material_present: false;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    queue_polling_allowed: false;
    queue_claim_allowed: false;
    queue_lease_allowed: false;
    queue_ack_allowed: false;
    queue_consume_allowed: false;
    queue_mutation_allowed: false;
    worker_store_contact_allowed: false;
    worker_runtime_contact_allowed: false;
    worker_contact_allowed: false;
    worker_start_allowed: false;
    worker_invocation_allowed: false;
    agent_invocation_allowed: false;
    execution_authorization_allowed: false;
    execution_start_allowed: false;
    process_execution_allowed: false;
    store_contact_allowed: false;
    runtime_contact_allowed: false;
    dispatch_allowed: false;
    retry_allowed: false;
    resend_allowed: false;
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
    artifact_publication_allowed: false;
    tag_push_allowed: false;
    release_publication_allowed: false;
    binding_activation_allowed: false;
    worker_binding_activation_preflight_recorded?: boolean;
};

export type WorkerBindingActivationPreflightBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v046_binding_not_active" | "v046_binding_not_recorded"
    | "linkage_mismatch" | "fingerprint_mismatch"
    | "inherited_limits_mismatch" | "evidence_stale"
    | "evidence_expired" | "ambiguous_state"
    | "caller_supplied_credential" | "caller_supplied_endpoint"
    | "caller_supplied_command" | "unsupported_authority"
    | "worker_binding_activation_not_defined"
    | "store_contact_not_defined" | "runtime_contact_not_defined"
    | "queue_claim_not_defined" | "queue_lease_not_defined"
    | "queue_ack_not_defined" | "worker_start_not_defined"
    | "agent_invocation_not_defined"
    | "execution_start_boundary_not_defined";

export type WorkerBindingActivationPreflightV1 = WorkerBindingActivationPreflightAuthorityV1 & {
    schema: "worker-binding-activation-preflight-v1";
    preflight_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    preflight_state: "readiness_gated";
    eligibility: "worker_binding_activation_preflight_recorded";
    blockers: WorkerBindingActivationPreflightBlockerV1[];
    one_shot_dequeue_worker_binding: OneShotDequeueWorkerBindingV1;
    one_shot_dequeue_worker_binding_status: OneShotDequeueWorkerBindingStatusV1;
    binding_subject_fingerprint: FingerprintV1;
    worker_subject_fingerprint: FingerprintV1;
    queue_item_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    preflight_record_fingerprint: FingerprintV1;
    worker_binding_activation_preflight_recorded: true;
};

export type WorkerBindingActivationPreflightStatusV1 = WorkerBindingActivationPreflightAuthorityV1 & {
    schema: "worker-binding-activation-preflight-status-v1";
    preflight_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    preflight_state: "worker_binding_activation_preflight_recorded";
    eligibility: "worker_binding_activation_preflight_recorded";
    blockers: WorkerBindingActivationPreflightBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    preflight_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    worker_binding_activation_preflight_recorded: true;
};

export type WorkerBindingActivationPreflightErrorV1 = WorkerBindingActivationPreflightAuthorityV1 & {
    schema: "worker-binding-activation-preflight-error-v1";
    error_code: WorkerBindingActivationPreflightBlockerV1 | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "worker binding activation preflight request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    worker_binding_activation_preflight_recorded: false;
};

export type WorkerBindingActivationPreflightResultV1 = WorkerBindingActivationPreflightAuthorityV1 & {
    schema: "worker-binding-activation-preflight-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: WorkerBindingActivationPreflightV1 | null;
    status: WorkerBindingActivationPreflightStatusV1 | null;
    error: WorkerBindingActivationPreflightErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    worker_binding_activation_preflight_recorded: boolean;
};

export type WorkerBindingActivationPreflightCollectionV1 = WorkerBindingActivationPreflightAuthorityV1 & {
    schema: "worker-binding-activation-preflight-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: WorkerBindingActivationPreflightV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    worker_binding_activation_preflight_recorded: false;
};
