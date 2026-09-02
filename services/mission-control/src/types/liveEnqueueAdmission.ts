import type { FingerprintV1 } from "./installationReadinessReview";
import type { RunnerBindingLimitsV1 } from "./runnerBindingPlan";
import type { WorkerIntakeAdmissionLinkageV1 } from "./workerIntakeAdmission";

export type LiveEnqueueAdmissionCreateV1 = {
    schema: "live-enqueue-admission-create-v1";
    worker_intake_admission_id: string;
    worker_intake_admission_fingerprint: FingerprintV1;
    worker_intake_admission_valid_until: string;
    worker_queue_reservation_id: string;
    worker_queue_reservation_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    worker_identity_id: string;
    worker_identity_fingerprint: FingerprintV1;
    worker_intake_reference_id: string;
    worker_intake_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    requested_scope: "installation_live_enqueue_admission_only";
    evidence_only: true;
    enqueue_operation_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    live_enqueue_allowed: false;
    dequeue_allowed: false;
    worker_start_allowed: false;
    execution_authorized: false;
    replay_allowed: false;
};

export type LiveEnqueueAuthorityV1 = {
    evidence_only: true;
    live_enqueue_allowed: false;
    enqueue_operation_defined: false;
    queue_item_payload_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    queue_publish_allowed: false;
    queue_send_allowed: false;
    dequeue_allowed: false;
    queue_polling_allowed: false;
    queue_claim_allowed: false;
    queue_ack_allowed: false;
    worker_contact_allowed: false;
    worker_authentication_allowed: false;
    worker_binding_allowed: false;
    worker_start_allowed: false;
    execution_start_allowed: false;
    runner_binding_allowed: false;
    dispatch_allowed: false;
    retry_allowed: false;
    resend_allowed: false;
    agent_invocation_allowed: false;
    workflow_start_allowed: false;
    docker_execution_allowed: false;
    podman_execution_allowed: false;
    shell_execution_allowed: false;
    process_execution_allowed: false;
    provider_mutation_allowed: false;
    repository_mutation_allowed: false;
    in_guest_mutation_allowed: false;
    installation_allowed: false;
    deployment_allowed: false;
    rollback_allowed: false;
    replay_bypass_allowed: false;
};

export type LiveEnqueueBlockerV1 =
    | "installation_capability_unsupported"
    | "evidence_not_found"
    | "ownership_mismatch"
    | "permission_scope_missing"
    | "linkage_mismatch"
    | "fingerprint_mismatch"
    | "evidence_stale"
    | "evidence_expired"
    | "worker_intake_admission_not_active"
    | "queue_reservation_not_active"
    | "queue_item_reference_invalid"
    | "worker_identity_ineligible"
    | "worker_intake_reference_ineligible"
    | "inherited_limits_mismatch"
    | "permanent_subject_reserved"
    | "enqueue_operation_not_defined"
    | "dequeue_not_defined"
    | "worker_start_not_defined"
    | "execution_start_boundary_not_defined";

export type LiveEnqueueAdmissionDecisionV1 = LiveEnqueueAuthorityV1 & {
    schema: "live-enqueue-admission-decision-v1";
    decision_id: string;
    owner_operator_id: string;
    candidate_record_id: string;
    worker_intake_admission_id: string;
    worker_intake_admission_fingerprint: FingerprintV1;
    worker_queue_reservation_id: string;
    worker_queue_reservation_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    worker_identity_id: string;
    worker_identity_fingerprint: FingerprintV1;
    worker_intake_reference_id: string;
    worker_intake_reference_fingerprint: FingerprintV1;
    scope: "installation_live_enqueue_admission_only";
    decision: "preserve_non_enqueueing_live_enqueue_admission_evidence_only";
    evaluated_at: string;
    eligibility: "live_enqueue_admission_recorded";
    blockers: LiveEnqueueBlockerV1[];
    inherited_limits_fingerprint: FingerprintV1;
    decision_fingerprint: FingerprintV1;
    queue_item_constructed: false;
    payload_constructed: false;
    request_serialized: false;
    request_sent: false;
    queue_enqueued: false;
    queue_dequeued: false;
    worker_contacted: false;
    worker_started: false;
    execution_authorized: false;
};

export type LiveEnqueueAdmissionLinkageV1 = {
    schema: "live-enqueue-admission-linkage-v1";
    operator_id: string;
    candidate_record_id: string;
    worker_intake_admission_linkage: WorkerIntakeAdmissionLinkageV1;
    v020_v039_chain_fingerprint: FingerprintV1;
    readiness_review_fingerprint: FingerprintV1;
    permission_grant_fingerprint: FingerprintV1;
    execution_admission_id: string;
    execution_admission_fingerprint: FingerprintV1;
    runner_binding_plan_id: string;
    runner_binding_plan_fingerprint: FingerprintV1;
    runner_binding_plan_status_fingerprint: FingerprintV1;
    runner_reference_id: string;
    runner_reference_fingerprint: FingerprintV1;
    worker_admission_stub_id: string;
    worker_admission_stub_fingerprint: FingerprintV1;
    worker_admission_stub_status_fingerprint: FingerprintV1;
    worker_reference_id: string;
    worker_reference_fingerprint: FingerprintV1;
    queue_reservation_id: string;
    queue_reservation_fingerprint: FingerprintV1;
    queue_reservation_status_fingerprint: FingerprintV1;
    queue_intake_reference_id: string;
    queue_intake_reference_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    worker_identity_id: string;
    worker_identity_fingerprint: FingerprintV1;
    worker_intake_reference_id: string;
    worker_intake_reference_fingerprint: FingerprintV1;
    worker_intake_admission_id: string;
    worker_intake_admission_fingerprint: FingerprintV1;
    worker_intake_admission_status_fingerprint: FingerprintV1;
    live_enqueue_admission_decision_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    linkage_fingerprint: FingerprintV1;
};

export type LiveEnqueueAdmissionV1 = LiveEnqueueAuthorityV1 & {
    schema: "live-enqueue-admission-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    record_state: "recorded";
    lifecycle: "active";
    eligibility: "live_enqueue_admission_recorded";
    blockers: LiveEnqueueBlockerV1[];
    scope: "installation_live_enqueue_admission_only";
    linkage: LiveEnqueueAdmissionLinkageV1;
    admission_decision: LiveEnqueueAdmissionDecisionV1;
    inherited_limits: RunnerBindingLimitsV1;
    idempotency_key_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    record_fingerprint: FingerprintV1;
};

export type LiveEnqueueAdmissionStatusV1 = LiveEnqueueAuthorityV1 & {
    schema: "live-enqueue-admission-status-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    evaluated_at: string;
    valid_until: string;
    lifecycle: "active" | "expired";
    eligibility: "live_enqueue_admission_recorded" | "readiness_gated" | "blocked";
    blockers: LiveEnqueueBlockerV1[];
    record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
};

export type LiveEnqueueAdmissionErrorV1 = LiveEnqueueAuthorityV1 & {
    schema: "live-enqueue-admission-error-v1";
    error_code: string;
    message: "live enqueue admission request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
};

export type LiveEnqueueAdmissionResultV1 = LiveEnqueueAuthorityV1 & {
    schema: "live-enqueue-admission-result-v1";
    ok: boolean;
    admission: LiveEnqueueAdmissionV1 | null;
    status: LiveEnqueueAdmissionStatusV1 | null;
    error: LiveEnqueueAdmissionErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
};

export type LiveEnqueueAdmissionCollectionV1 = LiveEnqueueAuthorityV1 & {
    schema: "live-enqueue-admission-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: LiveEnqueueAdmissionV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
};
