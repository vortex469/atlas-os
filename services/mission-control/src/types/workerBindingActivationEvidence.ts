import type { FingerprintV1 } from "./installationReadinessReview";
import type { WorkerBindingActivationPreflightStatusV1, WorkerBindingActivationPreflightV1 } from "./workerBindingActivationPreflight";

export type WorkerBindingActivationEvidenceAuthorityV1 = {
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
    worker_start_admission_allowed: false;
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
    worker_activation_runtime_allowed: false;
    worker_binding_activation_evidence_recorded?: boolean;
};

export type WorkerBindingActivationEvidenceBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v047_preflight_not_active" | "v047_preflight_not_recorded"
    | "linkage_mismatch" | "fingerprint_mismatch"
    | "inherited_limits_mismatch" | "evidence_stale"
    | "evidence_expired" | "ambiguous_state"
    | "caller_supplied_credential" | "caller_supplied_endpoint"
    | "caller_supplied_command" | "unsupported_authority"
    | "worker_activation_runtime_not_defined"
    | "store_contact_not_defined" | "runtime_contact_not_defined"
    | "queue_claim_not_defined" | "queue_lease_not_defined"
    | "queue_ack_not_defined" | "worker_start_admission_not_defined"
    | "worker_start_not_defined" | "agent_invocation_not_defined"
    | "execution_start_boundary_not_defined";

export type WorkerBindingActivationEvidenceV1 = WorkerBindingActivationEvidenceAuthorityV1 & {
    schema: "worker-binding-activation-evidence-v1";
    activation_evidence_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    activation_evidence_state: "readiness_gated";
    eligibility: "worker_binding_activation_evidence_recorded";
    blockers: WorkerBindingActivationEvidenceBlockerV1[];
    worker_binding_activation_preflight: WorkerBindingActivationPreflightV1;
    worker_binding_activation_preflight_status: WorkerBindingActivationPreflightStatusV1;
    binding_subject_fingerprint: FingerprintV1;
    worker_subject_fingerprint: FingerprintV1;
    queue_item_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    activation_evidence_record_fingerprint: FingerprintV1;
    worker_binding_activation_evidence_recorded: true;
};

export type WorkerBindingActivationEvidenceStatusV1 = WorkerBindingActivationEvidenceAuthorityV1 & {
    schema: "worker-binding-activation-evidence-status-v1";
    activation_evidence_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    activation_evidence_state: "worker_binding_activation_evidence_recorded";
    eligibility: "worker_binding_activation_evidence_recorded";
    blockers: WorkerBindingActivationEvidenceBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    activation_evidence_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    worker_binding_activation_evidence_recorded: true;
};

export type WorkerBindingActivationEvidenceErrorV1 = WorkerBindingActivationEvidenceAuthorityV1 & {
    schema: "worker-binding-activation-evidence-error-v1";
    error_code: WorkerBindingActivationEvidenceBlockerV1 | "reservation_before_effect_failed" | "permanent_subject_reserved" | "idempotency_conflict" | "append_indeterminate" | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "worker binding activation evidence request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    worker_binding_activation_evidence_recorded: false;
};

export type WorkerBindingActivationEvidenceResultV1 = WorkerBindingActivationEvidenceAuthorityV1 & {
    schema: "worker-binding-activation-evidence-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: WorkerBindingActivationEvidenceV1 | null;
    status: WorkerBindingActivationEvidenceStatusV1 | null;
    error: WorkerBindingActivationEvidenceErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    worker_binding_activation_evidence_recorded: boolean;
};

export type WorkerBindingActivationEvidenceCollectionV1 = WorkerBindingActivationEvidenceAuthorityV1 & {
    schema: "worker-binding-activation-evidence-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: WorkerBindingActivationEvidenceV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    worker_binding_activation_evidence_recorded: false;
};
