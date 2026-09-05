import type { FingerprintV1 } from "./installationReadinessReview";
import type { QueueObservationReceiptStatusV1, QueueObservationReceiptV1 } from "./queueObservation";
import type { OneShotLiveEnqueueV1 } from "./oneShotLiveEnqueue";

export type ControlledDequeueAdmissionAuthorityV1 = {
    evidence_only: true;
    reference_only: true;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    executable_payload_allowed: false;
    dequeue_defined: false;
    dequeue_allowed: false;
    dequeue_attempted: false;
    dequeued: false;
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
    controlled_dequeue_admission_recorded?: boolean;
};

export type ControlledDequeueAdmissionBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing"
    | "v043_observation_not_active" | "v043_observation_not_recorded"
    | "v043_receipt_not_contract_eligible" | "v042_enqueue_not_active"
    | "v042_enqueue_not_recorded" | "linkage_mismatch"
    | "queue_identity_mismatch" | "item_identity_mismatch"
    | "observation_receipt_mismatch" | "fingerprint_mismatch"
    | "inherited_limits_mismatch" | "evidence_stale" | "evidence_expired"
    | "ambiguous_state" | "executable_payload" | "unsupported_authority"
    | "reservation_before_effect_failed" | "permanent_subject_reserved"
    | "idempotency_conflict" | "append_indeterminate"
    | "dequeue_not_defined" | "queue_polling_not_defined"
    | "queue_claim_not_defined" | "queue_lease_not_defined"
    | "queue_ack_not_defined" | "worker_start_not_defined"
    | "execution_start_boundary_not_defined";

export type ControlledDequeueAdmissionCreateV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-create-v1";
    queue_observation_receipt_id: string;
    queue_observation_receipt_fingerprint: FingerprintV1;
    queue_observation_receipt_status_fingerprint: FingerprintV1;
    queue_observation_receipt_valid_until: string;
    enqueue_id: string;
    inert_queue_item_id: string;
    inert_queue_item_fingerprint: FingerprintV1;
    queue_identity: "abstract_installation_queue";
    item_identity: "inert_reference_only_queue_item";
    inherited_limits_fingerprint: FingerprintV1;
    requested_scope: "installation_controlled_dequeue_admission_only";
};

export type ControlledDequeueAdmissionDecisionV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-decision-v1";
    decision: "eligible_for_later_dequeue_consideration";
    admission_state: "readiness_gated";
    blockers: ControlledDequeueAdmissionBlockerV1[];
    queue_identity_fingerprint: FingerprintV1;
    item_identity_fingerprint: FingerprintV1;
    lineage_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    decision_fingerprint: FingerprintV1;
};

export type ControlledDequeueAdmissionV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    admission_state: "readiness_gated";
    disposition: "controlled_dequeue_admission_recorded";
    eligibility: "eligible_for_later_dequeue_consideration";
    blockers: ControlledDequeueAdmissionBlockerV1[];
    queue_observation_receipt: QueueObservationReceiptV1;
    queue_observation_receipt_status: QueueObservationReceiptStatusV1;
    inherited_limits: OneShotLiveEnqueueV1["inherited_limits"];
    admission_decision: ControlledDequeueAdmissionDecisionV1;
    queue_identity_fingerprint: FingerprintV1;
    item_identity_fingerprint: FingerprintV1;
    lineage_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    admission_record_fingerprint: FingerprintV1;
    controlled_dequeue_admission_recorded: true;
};

export type ControlledDequeueAdmissionStatusV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-status-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    admission_state: "controlled_dequeue_admission_recorded" | "readiness_gated";
    eligibility: "eligible_for_later_dequeue_consideration";
    blockers: ControlledDequeueAdmissionBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    admission_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    controlled_dequeue_admission_recorded: true;
};

export type ControlledDequeueAdmissionErrorV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-error-v1";
    error_code: ControlledDequeueAdmissionBlockerV1 | "unauthenticated" | "forbidden" | "not_found" | "invalid_request" | "rate_limited" | "quota_exceeded" | "conflict" | "record_too_large" | "store_corrupt" | "internal_error";
    message: "controlled dequeue admission request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    controlled_dequeue_admission_recorded: false;
};

export type ControlledDequeueAdmissionResultV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: ControlledDequeueAdmissionV1 | null;
    status: ControlledDequeueAdmissionStatusV1 | null;
    error: ControlledDequeueAdmissionErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    controlled_dequeue_admission_recorded: boolean;
};

export type ControlledDequeueAdmissionCollectionV1 = ControlledDequeueAdmissionAuthorityV1 & {
    schema: "controlled-dequeue-admission-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: ControlledDequeueAdmissionV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    controlled_dequeue_admission_recorded: false;
};
