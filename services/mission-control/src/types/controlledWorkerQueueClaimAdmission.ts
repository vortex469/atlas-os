import type { FingerprintV1 } from "./installationReadinessReview";
import type { WorkerBindingActivationEvidenceStatusV1, WorkerBindingActivationEvidenceV1 } from "./workerBindingActivationEvidence";

export type ControlledWorkerQueueClaimAdmissionAuthorityV1 = {
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
    queue_claimed: false;
    queue_leased: false;
    queue_acknowledged: false;
    worker_start_admitted: false;
    worker_started: false;
    execution_started: false;
    controlled_worker_queue_claim_admission_recorded?: boolean;
};

export type ControlledWorkerQueueClaimAdmissionBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v048_activation_evidence_not_active"
    | "v048_activation_evidence_not_recorded"
    | "linkage_mismatch" | "fingerprint_mismatch"
    | "inherited_limits_mismatch" | "evidence_stale"
    | "evidence_expired" | "ambiguous_state"
    | "caller_supplied_credential" | "caller_supplied_endpoint"
    | "caller_supplied_command" | "unsupported_authority"
    | "queue_claim_not_defined" | "queue_lease_not_defined"
    | "queue_ack_not_defined" | "worker_activation_runtime_not_defined"
    | "store_contact_not_defined" | "runtime_contact_not_defined"
    | "worker_start_admission_not_defined" | "worker_start_not_defined"
    | "agent_invocation_not_defined"
    | "execution_start_boundary_not_defined";

export type ControlledWorkerQueueClaimAdmissionV1 = ControlledWorkerQueueClaimAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-admission-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    admission_state: "readiness_gated";
    eligibility: "controlled_worker_queue_claim_admission_recorded";
    blockers: ControlledWorkerQueueClaimAdmissionBlockerV1[];
    worker_binding_activation_evidence: WorkerBindingActivationEvidenceV1;
    worker_binding_activation_evidence_status: WorkerBindingActivationEvidenceStatusV1;
    binding_subject_fingerprint: FingerprintV1;
    worker_subject_fingerprint: FingerprintV1;
    queue_item_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    admission_record_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_admission_recorded: true;
};

export type ControlledWorkerQueueClaimAdmissionStatusV1 = ControlledWorkerQueueClaimAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-admission-status-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    admission_state: "controlled_worker_queue_claim_admission_recorded";
    eligibility: "controlled_worker_queue_claim_admission_recorded";
    blockers: ControlledWorkerQueueClaimAdmissionBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    admission_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_admission_recorded: true;
};

export type ControlledWorkerQueueClaimAdmissionErrorV1 = ControlledWorkerQueueClaimAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-admission-error-v1";
    error_code: ControlledWorkerQueueClaimAdmissionBlockerV1 | "reservation_before_effect_failed" | "permanent_subject_reserved" | "idempotency_conflict" | "append_indeterminate" | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "controlled worker queue claim admission request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    controlled_worker_queue_claim_admission_recorded: false;
};

export type ControlledWorkerQueueClaimAdmissionResultV1 = ControlledWorkerQueueClaimAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-admission-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: ControlledWorkerQueueClaimAdmissionV1 | null;
    status: ControlledWorkerQueueClaimAdmissionStatusV1 | null;
    error: ControlledWorkerQueueClaimAdmissionErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_admission_recorded: boolean;
};

export type ControlledWorkerQueueClaimAdmissionCollectionV1 = ControlledWorkerQueueClaimAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-admission-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: ControlledWorkerQueueClaimAdmissionV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_admission_recorded: false;
};
