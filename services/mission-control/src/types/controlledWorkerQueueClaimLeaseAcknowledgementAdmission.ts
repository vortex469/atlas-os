import type { ControlledWorkerQueueClaimAdmissionStatusV1, ControlledWorkerQueueClaimAdmissionV1 } from "./controlledWorkerQueueClaimAdmission";
import type { FingerprintV1 } from "./installationReadinessReview";

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 = {
    evidence_only: true;
    reference_only: true;
    caller_supplied_credentials_allowed: false;
    caller_supplied_endpoint_allowed: false;
    caller_supplied_command_allowed: false;
    caller_supplied_payload_allowed: false;
    caller_supplied_queue_selector_allowed: false;
    caller_supplied_claim_token_allowed: false;
    caller_supplied_lease_token_allowed: false;
    caller_supplied_acknowledgement_handle_allowed: false;
    credential_material_present: false;
    endpoint_material_present: false;
    command_material_present: false;
    payload_material_present: false;
    queue_selector_material_present: false;
    claim_token_material_present: false;
    lease_token_material_present: false;
    acknowledgement_handle_material_present: false;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    queue_adapter_defined: false;
    queue_polling_allowed: false;
    queue_claim_allowed: false;
    queue_lease_allowed: false;
    queue_ack_allowed: false;
    queue_consume_allowed: false;
    queue_requeue_allowed: false;
    queue_mutation_allowed: false;
    worker_activation_runtime_allowed: false;
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
    queue_claimed: false;
    queue_leased: false;
    queue_acknowledged: false;
    worker_start_admitted: false;
    worker_started: false;
    agent_invoked: false;
    execution_started: false;
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded?: boolean;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v050_prerequisite_not_active" | "v050_prerequisite_not_frozen"
    | "linkage_mismatch" | "fingerprint_mismatch"
    | "inherited_limits_mismatch" | "evidence_stale"
    | "evidence_expired" | "ambiguous_state"
    | "caller_supplied_credential" | "caller_supplied_endpoint"
    | "caller_supplied_command" | "caller_supplied_queue_selector"
    | "caller_supplied_claim_token" | "caller_supplied_lease_token"
    | "caller_supplied_acknowledgement_handle" | "unsupported_authority"
    | "queue_adapter_not_defined" | "queue_claim_not_defined"
    | "queue_lease_not_defined" | "queue_ack_not_defined"
    | "worker_activation_runtime_not_defined"
    | "store_contact_not_defined" | "runtime_contact_not_defined"
    | "worker_start_admission_not_defined" | "worker_start_not_defined"
    | "agent_invocation_not_defined"
    | "execution_start_boundary_not_defined";

export type ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1";
    prerequisite_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    prerequisite_state: "frozen";
    eligibility: "v0.50_prerequisite_frozen";
    blockers: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1[];
    controlled_worker_queue_claim_admission: ControlledWorkerQueueClaimAdmissionV1;
    controlled_worker_queue_claim_admission_status: ControlledWorkerQueueClaimAdmissionStatusV1;
    admission_id: string;
    admission_record_fingerprint: FingerprintV1;
    admission_status_fingerprint: FingerprintV1;
    binding_subject_fingerprint: FingerprintV1;
    worker_subject_fingerprint: FingerprintV1;
    queue_item_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    prerequisite_record_fingerprint: FingerprintV1;
    v0_50_prerequisite_frozen: true;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-prerequisite-status-v1";
    prerequisite_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    prerequisite_state: "v0.50_prerequisite_frozen";
    eligibility: "v0.50_prerequisite_frozen";
    blockers: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    prerequisite_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    v0_50_prerequisite_frozen: true;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    admission_state: "recorded";
    eligibility: "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded";
    blockers: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1[];
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteV1;
    controlled_worker_queue_claim_lease_acknowledgement_prerequisite_status: ControlledWorkerQueueClaimLeaseAcknowledgementPrerequisiteStatusV1;
    prerequisite_id: string;
    prerequisite_record_fingerprint: FingerprintV1;
    prerequisite_status_fingerprint: FingerprintV1;
    v049_admission_record_fingerprint: FingerprintV1;
    v049_admission_status_fingerprint: FingerprintV1;
    binding_subject_fingerprint: FingerprintV1;
    worker_subject_fingerprint: FingerprintV1;
    queue_item_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    admission_record_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: true;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-status-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    admission_state: "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded";
    eligibility: "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded";
    blockers: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    admission_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: true;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionErrorV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-error-v1";
    error_code: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1 | "reservation_before_effect_failed" | "permanent_subject_reserved" | "idempotency_conflict" | "append_indeterminate" | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "controlled worker queue claim lease acknowledgement admission request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: false;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1 | null;
    status: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1 | null;
    error: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: boolean;
};

export type ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionAuthorityV1 & {
    schema: "controlled-worker-queue-claim-lease-acknowledgement-admission-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: false;
};
