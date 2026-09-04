import type { FingerprintV1 } from "./installationReadinessReview";
import type { OneShotLiveEnqueueStatusV1, OneShotLiveEnqueueV1 } from "./oneShotLiveEnqueue";

export type QueueObservationReceiptAuthorityV1 = {
    observation_only: true;
    reference_only: true;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    payload_bytes: 0;
    executable_payload_allowed: false;
    live_enqueue_allowed: false;
    dequeue_defined: false;
    dequeue_allowed: false;
    queue_polling_allowed: false;
    queue_claim_allowed: false;
    queue_lease_allowed: false;
    queue_ack_allowed: false;
    worker_contact_allowed: false;
    worker_start_allowed: false;
    execution_start_allowed: false;
    dispatch_allowed: false;
    retry_allowed: false;
    resend_allowed: false;
    agent_invocation_allowed: false;
    workflow_start_allowed: false;
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
    queue_observation_recorded?: boolean;
};

export type QueueObservationBlockerV1 =
    | "installation_capability_unsupported" | "evidence_not_found"
    | "ownership_mismatch" | "permission_scope_missing" | "linkage_mismatch"
    | "fingerprint_mismatch" | "evidence_stale" | "evidence_expired"
    | "v042_enqueue_not_active" | "v042_enqueue_not_recorded"
    | "queue_identity_mismatch" | "item_identity_mismatch"
    | "receipt_evidence_invalid" | "observation_malformed" | "ambiguous_state"
    | "executable_payload" | "unsupported_authority" | "dequeue_not_defined"
    | "queue_polling_not_defined" | "worker_start_not_defined"
    | "execution_start_boundary_not_defined";

export type QueueObservationReceiptCreateV1 = {
    schema: "queue-observation-receipt-create-v1";
    enqueue_id: string;
    enqueue_record_fingerprint: FingerprintV1;
    enqueue_status_fingerprint: FingerprintV1;
    enqueue_valid_until: string;
    queue_intake_reference_id: string;
    queue_intake_reference_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    inert_queue_item_id: string;
    inert_queue_item_fingerprint: FingerprintV1;
    observed_queue_identity: "abstract_installation_queue";
    observed_item_identity: "inert_reference_only_queue_item";
    observation_state: "observed_recorded_not_consumable";
    receipt_disposition: "contract_eligible";
    requested_scope: "installation_queue_observation_receipt_only";
    observation_only: true;
    reference_only: true;
    payload_schema_defined: false;
    payload_constructed: false;
    payload_serialized: false;
    executable_payload_allowed: false;
    dequeue_allowed: false;
    queue_polling_allowed: false;
    worker_start_allowed: false;
    execution_authorized: false;
    replay_allowed: false;
};

export type EnqueueReceiptEvidenceV1 = {
    schema: "enqueue-receipt-evidence-v1";
    enqueue_id: string;
    operator_id: string;
    candidate_record_id: string;
    enqueue_record_fingerprint: FingerprintV1;
    enqueue_status_fingerprint: FingerprintV1;
    inert_queue_item_id: string;
    inert_queue_item_fingerprint: FingerprintV1;
    queue_intake_reference_id: string;
    queue_intake_reference_fingerprint: FingerprintV1;
    queue_item_reference_id: string;
    queue_item_reference_fingerprint: FingerprintV1;
    receipt_state: "receipt_recorded_for_contract_eligible_enqueue";
    receipt_disposition: "contract_eligible";
    recorded_at: string;
    valid_until: string;
    receipt_fingerprint: FingerprintV1;
    payload_present: false;
    executable: false;
    effect_attempted: false;
};

export type QueueObservationV1 = QueueObservationReceiptAuthorityV1 & {
    schema: "queue-observation-v1";
    observation_id: string;
    operator_id: string;
    candidate_record_id: string;
    enqueue_id: string;
    queue_identity: "abstract_installation_queue";
    item_identity: "inert_reference_only_queue_item";
    observation_state: "observed_recorded_not_consumable";
    lifecycle: "active";
    disposition: "observation_recorded";
    blockers: QueueObservationBlockerV1[];
    receipt_evidence: EnqueueReceiptEvidenceV1;
    observed_at: string;
    valid_until: string;
    observation_fingerprint: FingerprintV1;
};

export type QueueObservationReceiptV1 = QueueObservationReceiptAuthorityV1 & {
    schema: "queue-observation-receipt-v1";
    receipt_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    lifecycle: "active";
    disposition: "observation_recorded";
    blockers: QueueObservationBlockerV1[];
    v042_enqueue: OneShotLiveEnqueueV1;
    v042_enqueue_status: OneShotLiveEnqueueStatusV1;
    receipt_evidence: EnqueueReceiptEvidenceV1;
    queue_observation: QueueObservationV1;
    lineage_fingerprint: FingerprintV1;
    subject_fingerprint: FingerprintV1;
    receipt_record_fingerprint: FingerprintV1;
};

export type QueueObservationReceiptStatusV1 = QueueObservationReceiptAuthorityV1 & {
    schema: "queue-observation-receipt-status-v1";
    receipt_id: string;
    operator_id: string;
    candidate_record_id: string;
    lifecycle: "active" | "expired";
    disposition: "observation_recorded";
    blockers: QueueObservationBlockerV1[];
    evaluated_at: string;
    valid_until: string;
    receipt_record_fingerprint: FingerprintV1;
    status_fingerprint: FingerprintV1;
    queue_observation_recorded: true;
};

export type QueueObservationReceiptErrorV1 = QueueObservationReceiptAuthorityV1 & {
    schema: "queue-observation-receipt-error-v1";
    error_code: string;
    message: "queue observation receipt request could not be completed";
    retryable: false;
    correlation_fingerprint: FingerprintV1;
    redacted: true;
    queue_observation_recorded: false;
};

export type QueueObservationReceiptResultV1 = QueueObservationReceiptAuthorityV1 & {
    schema: "queue-observation-receipt-result-v1";
    ok: boolean;
    outcome: "success" | "failure" | "indeterminate";
    record: QueueObservationReceiptV1 | null;
    status: QueueObservationReceiptStatusV1 | null;
    error: QueueObservationReceiptErrorV1 | null;
    correlation_fingerprint: FingerprintV1;
    queue_observation_recorded: boolean;
};

export type QueueObservationReceiptCollectionV1 = QueueObservationReceiptAuthorityV1 & {
    schema: "queue-observation-receipt-collection-v1";
    operator_id: string;
    candidate_record_id: string;
    items: QueueObservationReceiptV1[];
    count: number;
    collection_fingerprint: FingerprintV1;
    queue_observation_recorded: false;
};
