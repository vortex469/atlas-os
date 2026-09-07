import type { FingerprintV1 } from "./installationReadinessReview";

// Fixed-false fields from Core v0.52 ClosedAuthorityV1.
export const CLOSED_QUEUE_AUTHORITY = [
    "caller_supplied_credentials_allowed",
    "caller_supplied_endpoint_allowed",
    "caller_supplied_command_allowed",
    "caller_supplied_payload_allowed",
    "caller_supplied_queue_selector_allowed",
    "caller_supplied_claim_token_allowed",
    "caller_supplied_lease_token_allowed",
    "caller_supplied_acknowledgement_handle_allowed",
    "credential_material_present",
    "endpoint_material_present",
    "command_material_present",
    "payload_material_present",
    "queue_selector_material_present",
    "claim_token_material_present",
    "lease_token_material_present",
    "acknowledgement_handle_material_present",
    "payload_schema_defined",
    "payload_constructed",
    "payload_serialized",
    "autonomous_queue_polling_allowed",
    "work_discovery_allowed",
    "queue_consume_allowed",
    "queue_requeue_allowed",
    "queue_mutation_allowed",
    "worker_activation_runtime_allowed",
    "worker_store_contact_allowed",
    "worker_runtime_contact_allowed",
    "worker_contact_allowed",
    "worker_start_admission_allowed",
    "worker_start_allowed",
    "worker_invocation_allowed",
    "agent_invocation_allowed",
    "execution_authorization_allowed",
    "execution_start_allowed",
    "process_execution_allowed",
    "store_contact_allowed",
    "runtime_contact_allowed",
    "dispatch_allowed",
    "retry_allowed",
    "resend_allowed",
    "scheduler_allowed",
    "workflow_start_allowed",
    "shell_execution_allowed",
    "provider_mutation_allowed",
    "repository_mutation_allowed",
    "in_guest_mutation_allowed",
    "installation_allowed",
    "deployment_allowed",
    "rollback_allowed",
    "replay_bypass_allowed",
    "artifact_publication_allowed",
    "tag_push_allowed",
    "release_publication_allowed",
    "worker_start_admitted",
    "worker_started",
    "agent_invoked",
    "execution_started"
] as const;

export interface ControlledWorkerQueueReceipt {
    admissionId: string;
    operatorId: string;
    candidateId: string;
    recordedAt: string;
    validUntil: string;
    lifecycle: "active" | "expired";
    evaluatedAt: string;
    blockers: string[];
    fingerprints: Record<string, FingerprintV1>;
    authority: Record<typeof CLOSED_QUEUE_AUTHORITY[number], false>;
    reservationBeforeEffect: true;
}
