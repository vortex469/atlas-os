import type { WorkerBindingActivationEvidenceBlockerV1 } from "../../types/workerBindingActivationEvidence";
import type { WorkerBindingActivationPreflightBlockerV1 } from "../../types/workerBindingActivationPreflight";
import type { ControlledWorkerQueueClaimAdmissionBlockerV1 } from "../../types/controlledWorkerQueueClaimAdmission";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1 } from "../../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";

type WorkerBindingBlocker = WorkerBindingActivationEvidenceBlockerV1 | WorkerBindingActivationPreflightBlockerV1 | ControlledWorkerQueueClaimAdmissionBlockerV1 | ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionBlockerV1;

const BLOCKER_LABELS: Record<WorkerBindingBlocker, string> = {
    installation_capability_unsupported: "Atlas cannot install this application",
    evidence_not_found: "Matching evidence was not found",
    ownership_mismatch: "The evidence belongs to a different owner",
    permission_scope_missing: "A required permission is missing",
    v046_binding_not_active: "The worker binding is no longer active",
    v046_binding_not_recorded: "The worker binding has not been recorded",
    v047_preflight_not_active: "The preflight is no longer active",
    v047_preflight_not_recorded: "The preflight has not been recorded",
    v048_activation_evidence_not_active: "The activation evidence is no longer active",
    v048_activation_evidence_not_recorded: "The activation evidence has not been recorded",
    v050_prerequisite_not_active: "The queue readiness requirements are no longer active",
    v050_prerequisite_not_frozen: "The queue readiness requirements have not been confirmed",
    linkage_mismatch: "The related records do not match",
    fingerprint_mismatch: "A record check does not match",
    inherited_limits_mismatch: "The worker safety limits do not match",
    evidence_stale: "The evidence is out of date",
    evidence_expired: "The evidence has expired",
    ambiguous_state: "The current state is unclear",
    caller_supplied_credential: "Caller-provided credentials are not allowed",
    caller_supplied_endpoint: "Caller-provided endpoints are not allowed",
    caller_supplied_command: "Caller-provided commands are not allowed",
    caller_supplied_queue_selector: "Caller-provided queue selections are not allowed",
    caller_supplied_claim_token: "Caller-provided claim tokens are not allowed",
    caller_supplied_lease_token: "Caller-provided lease tokens are not allowed",
    caller_supplied_acknowledgement_handle: "Caller-provided acknowledgement handles are not allowed",
    unsupported_authority: "The requested permission is not supported",
    worker_binding_activation_not_defined: "Worker binding activation is not available",
    queue_adapter_not_defined: "The queue connection is not available",
    worker_activation_runtime_not_defined: "The worker activation runtime is not available",
    store_contact_not_defined: "Contact with the worker store is not available",
    runtime_contact_not_defined: "Contact with the worker runtime is not available",
    queue_claim_not_defined: "Taking work from the queue is not available",
    queue_lease_not_defined: "Holding work from the queue is not available",
    queue_ack_not_defined: "Acknowledging queue work is not available",
    worker_start_admission_not_defined: "Worker start approval is not available",
    worker_start_not_defined: "Starting a worker is not available",
    agent_invocation_not_defined: "Calling Atlas Agent is not available",
    execution_start_boundary_not_defined: "Starting execution is not available",
};

export function workerBindingActivationBlockerLabel(blocker: WorkerBindingBlocker) {
    return BLOCKER_LABELS[blocker];
}
