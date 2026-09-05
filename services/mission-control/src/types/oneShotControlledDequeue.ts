import type { ControlledDequeueAdmissionStatusV1, ControlledDequeueAdmissionV1 } from "./controlledDequeueAdmission";
import type { FingerprintV1 } from "./installationReadinessReview";

export type OneShotControlledDequeueAuthorityV1 = {
    evidence_only: true;
    reference_only: true;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    executable_payload_allowed: false;
    dequeue_defined: false;
    dequeue_allowed: false;
    queue_polling_allowed: false;
    queue_polled: false;
    queue_claim_allowed: false;
    queue_claimed: false;
    queue_lease_allowed: false;
    queue_leased: false;
    queue_ack_allowed: false;
    queue_acked: false;
    queue_consumed: false;
    worker_contact_allowed: false;
    worker_contacted: false;
    worker_start_allowed: false;
    worker_started: false;
    agent_invocation_allowed: false;
    execution_start_allowed: false;
    process_execution_allowed: false;
    dispatch_allowed: false;
    retry_allowed: false;
    resend_allowed: false;
    scheduler_allowed: false;
    workflow_start_allowed: false;
    docker_execution_allowed: false;
    podman_execution_allowed: false;
    container_execution_allowed: false;
    shell_execution_allowed: false;
    provider_mutation_allowed: false;
    repository_mutation_allowed: false;
    in_guest_mutation_allowed: false;
    installation_allowed: false;
    deployment_allowed: false;
    rollback_allowed: false;
    replay_bypass_allowed: false;
    one_shot_controlled_dequeue_recorded?: boolean;
};

export type OneShotControlledDequeueBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v044_admission_not_active" | "v044_admission_not_recorded"
    | "v044_admission_not_eligible" | "v043_observation_not_active"
    | "v043_observation_not_recorded" | "v043_receipt_not_contract_eligible"
    | "v042_enqueue_not_active" | "v042_enqueue_not_recorded"
    | "linkage_mismatch" | "queue_identity_mismatch"
    | "item_identity_mismatch" | "observation_receipt_mismatch"
    | "fingerprint_mismatch" | "inherited_limits_mismatch"
    | "evidence_stale" | "evidence_expired" | "ambiguous_state"
    | "executable_payload" | "unsupported_authority"
    | "dequeue_adapter_unavailable" | "dequeue_receipt_mismatch"
    | "reservation_before_effect_failed" | "permanent_subject_reserved"
    | "idempotency_conflict" | "append_indeterminate"
    | "dequeue_indeterminate" | "queue_polling_not_defined"
    | "queue_claim_not_defined" | "queue_lease_not_defined"
    | "queue_ack_not_defined" | "worker_start_not_defined"
    | "execution_start_boundary_not_defined";

export type OneShotControlledDequeueCreateV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "one-shot-controlled-dequeue-create-v1";
    controlled_dequeue_admission_id: string;
    controlled_dequeue_admission_fingerprint: FingerprintV1;
    controlled_dequeue_admission_status_fingerprint: FingerprintV1;
    controlled_dequeue_admission_valid_until: string;
    queue_observation_receipt_id: string;
    queue_observation_receipt_fingerprint: FingerprintV1;
    queue_observation_receipt_status_fingerprint: FingerprintV1;
    enqueue_id: string;
    inert_queue_item_id: string;
    inert_queue_item_fingerprint: FingerprintV1;
    queue_identity_fingerprint: FingerprintV1;
    item_identity_fingerprint: FingerprintV1;
    lineage_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    queue_identity: "abstract_installation_queue";
    item_identity: "inert_reference_only_queue_item";
    requested_scope: "installation_one_shot_controlled_dequeue_only";
};

export type BoundedDequeueReceiptEvidenceV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "bounded-one-shot-controlled-dequeue-receipt-v1";
    outcome: "success" | "failure" | "indeterminate";
    disposition: "exact_inert_item_dequeued" | "exact_inert_item_not_dequeued" | "dequeue_completion_indeterminate";
    exact_admitted_item_only: true;
    adapter_receipt_redacted: true;
    adapter_receipt_fingerprint: FingerprintV1;
    queue_identity_fingerprint: FingerprintV1;
    item_identity_fingerprint: FingerprintV1;
    receipt_fingerprint: FingerprintV1;
};

export type OneShotControlledDequeueV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "one-shot-controlled-dequeue-v1";
    dequeue_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    dequeue_state: "one_shot_controlled_dequeue_recorded";
    outcome: "success" | "failure" | "indeterminate";
    disposition: "exact_inert_item_dequeued" | "exact_inert_item_not_dequeued" | "dequeue_completion_indeterminate";
    blockers: OneShotControlledDequeueBlockerV1[];
    controlled_dequeue_admission: ControlledDequeueAdmissionV1;
    controlled_dequeue_admission_status: ControlledDequeueAdmissionStatusV1;
    inherited_limits: ControlledDequeueAdmissionV1["inherited_limits"];
    bounded_receipt: BoundedDequeueReceiptEvidenceV1;
    queue_identity_fingerprint: FingerprintV1;
    item_identity_fingerprint: FingerprintV1;
    lineage_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    idempotency_key_fingerprint: FingerprintV1;
    dequeue_record_fingerprint: FingerprintV1;
    one_shot_controlled_dequeue_recorded: true;
};

export type OneShotControlledDequeueStatusV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "one-shot-controlled-dequeue-status-v1";
    dequeue_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    dequeue_state: "one_shot_controlled_dequeue_recorded";
    outcome: "success" | "failure" | "indeterminate";
    disposition: OneShotControlledDequeueV1["disposition"];
    blockers: OneShotControlledDequeueBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    dequeue_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    one_shot_controlled_dequeue_recorded: true;
};

export type OneShotControlledDequeueErrorV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "one-shot-controlled-dequeue-error-v1";
    error_code: OneShotControlledDequeueBlockerV1 | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "one-shot controlled dequeue request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    one_shot_controlled_dequeue_recorded: false;
};

export type OneShotControlledDequeueResultV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "one-shot-controlled-dequeue-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: OneShotControlledDequeueV1 | null;
    status: OneShotControlledDequeueStatusV1 | null;
    error: OneShotControlledDequeueErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    one_shot_controlled_dequeue_recorded: boolean;
};

export type OneShotControlledDequeueCollectionV1 = OneShotControlledDequeueAuthorityV1 & {
    schema: "one-shot-controlled-dequeue-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: OneShotControlledDequeueV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    one_shot_controlled_dequeue_recorded: false;
};
