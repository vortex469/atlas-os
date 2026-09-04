import type { FingerprintV1 } from "./installationReadinessReview";
import type { LiveEnqueueAdmissionLinkageV1 } from "./liveEnqueueAdmission";
import type { RunnerBindingLimitsV1 } from "./runnerBindingPlan";

export type OneShotLiveEnqueueAuthorityV1 = {
    reference_only: true;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    dequeue_defined: false;
    dequeue_allowed: false;
    queue_polling_allowed: false;
    queue_claim_allowed: false;
    queue_lease_allowed: false;
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
    scheduler_allowed: false;
    docker_execution_allowed: false;
    podman_execution_allowed: false;
    container_execution_allowed: false;
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

export type OneShotLiveEnqueueBlockerV1 =
    | "installation_capability_unsupported"
    | "evidence_not_found"
    | "ownership_mismatch"
    | "permission_scope_missing"
    | "linkage_mismatch"
    | "fingerprint_mismatch"
    | "evidence_stale"
    | "evidence_expired"
    | "live_enqueue_admission_not_active"
    | "live_enqueue_admission_not_recorded"
    | "queue_reservation_not_active"
    | "worker_intake_admission_not_active"
    | "worker_identity_ineligible"
    | "worker_intake_reference_ineligible"
    | "queue_intake_reference_ineligible"
    | "queue_item_reference_ineligible"
    | "inherited_limits_mismatch"
    | "reservation_before_effect_failed"
    | "permanent_subject_reserved"
    | "idempotency_conflict"
    | "append_indeterminate"
    | "dequeue_not_defined"
    | "queue_polling_not_defined"
    | "worker_start_not_defined"
    | "execution_start_boundary_not_defined";

export type OneShotLiveEnqueueQueueItemV1 = {
    schema: "one-shot-live-enqueue-item-v1";
    queue_item_id: string;
    owner_operator_id: string;
    candidate_record_id: string;
    live_enqueue_admission_id: string;
    live_enqueue_admission_fingerprint: FingerprintV1;
    live_enqueue_admission_status_fingerprint: FingerprintV1;
    worker_queue_reservation_id: string;
    worker_queue_reservation_fingerprint: FingerprintV1;
    worker_intake_admission_id: string;
    worker_intake_admission_fingerprint: FingerprintV1;
    worker_identity_id: string;
    worker_identity_fingerprint: FingerprintV1;
    worker_intake_reference_id: string;
    worker_intake_reference_fingerprint: FingerprintV1;
    queue_intake_reference_id: string;
    queue_intake_reference_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    item_kind: "inert_reference_only_queue_item";
    trust_domain: "atlas-installation";
    scope: "installation_one_shot_live_enqueue_only";
    reference_only: true;
    item_state: "recorded";
    recorded_at: string;
    valid_until: string;
    lineage_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    item_fingerprint: FingerprintV1;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    dequeue_defined: false;
    dequeued: false;
    queue_polled: false;
    queue_claimed: false;
    queue_leased: false;
    worker_contacted: false;
    worker_started: false;
    execution_allowed: false;
};

export type OneShotLiveEnqueueLineageV1 = {
    schema: "one-shot-live-enqueue-lineage-v1";
    operator_id: string;
    candidate_record_id: string;
    live_enqueue_admission_linkage: LiveEnqueueAdmissionLinkageV1;
    v020_v040_chain_fingerprint: FingerprintV1;
    v020_v041_chain_fingerprint: FingerprintV1;
    live_enqueue_admission_id: string;
    live_enqueue_admission_fingerprint: FingerprintV1;
    live_enqueue_admission_status_fingerprint: FingerprintV1;
    live_enqueue_admission_subject_fingerprint: FingerprintV1;
    live_enqueue_admission_decision_fingerprint: FingerprintV1;
    queue_reservation_id: string;
    queue_reservation_fingerprint: FingerprintV1;
    queue_reservation_status_fingerprint: FingerprintV1;
    queue_intake_reference_id: string;
    queue_intake_reference_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    worker_intake_admission_id: string;
    worker_intake_admission_fingerprint: FingerprintV1;
    worker_intake_admission_status_fingerprint: FingerprintV1;
    worker_identity_id: string;
    worker_identity_fingerprint: FingerprintV1;
    worker_intake_reference_id: string;
    worker_intake_reference_fingerprint: FingerprintV1;
    one_shot_queue_item_id: string;
    one_shot_queue_item_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    lineage_fingerprint: FingerprintV1;
};

export type OneShotLiveEnqueueV1 = OneShotLiveEnqueueAuthorityV1 & {
    schema: "one-shot-live-enqueue-v1";
    enqueue_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    record_state: "recorded";
    lifecycle: "active";
    outcome: "one_shot_live_enqueue_recorded";
    blockers: OneShotLiveEnqueueBlockerV1[];
    lineage: OneShotLiveEnqueueLineageV1;
    queue_item: OneShotLiveEnqueueQueueItemV1;
    inherited_limits: RunnerBindingLimitsV1;
    idempotency_key_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1;
    item_subject_fingerprint: FingerprintV1;
    record_fingerprint: FingerprintV1;
    one_shot_live_enqueue_recorded: true;
};

export type OneShotLiveEnqueueStatusV1 = OneShotLiveEnqueueAuthorityV1 & {
    schema: "one-shot-live-enqueue-status-v1";
    enqueue_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    outcome: "one_shot_live_enqueue_recorded" | "readiness_gated" | "blocked" | "indeterminate";
    blockers: OneShotLiveEnqueueBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    one_shot_live_enqueue_recorded: boolean;
};

export type OneShotLiveEnqueueErrorV1 = OneShotLiveEnqueueAuthorityV1 & {
    schema: "one-shot-live-enqueue-error-v1";
    error_code: string;
    message: "one-shot live enqueue request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    one_shot_live_enqueue_recorded: false;
};

export type OneShotLiveEnqueueResultV1 = OneShotLiveEnqueueAuthorityV1 & {
    schema: "one-shot-live-enqueue-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: OneShotLiveEnqueueV1 | null;
    status: OneShotLiveEnqueueStatusV1 | null;
    error: OneShotLiveEnqueueErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    one_shot_live_enqueue_recorded: boolean;
};

export type OneShotLiveEnqueueCollectionV1 = OneShotLiveEnqueueAuthorityV1 & {
    schema: "one-shot-live-enqueue-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: OneShotLiveEnqueueV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    one_shot_live_enqueue_recorded: false;
};
