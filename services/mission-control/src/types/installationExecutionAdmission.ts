import type { ExecutionPermissionGrantLinkageV1 } from "./executionPermissionGrant";
import type { FingerprintV1 } from "./installationReadinessReview";

export type InstallationExecutionAdmissionCreateV1 = {
    schema: "installation-execution-admission-create-v1";
    permission_grant_id: string;
    permission_grant_fingerprint: FingerprintV1;
    grant_valid_until: string;
    requested_scope: "future_installation_runner_consideration_only";
    runner_eligibility_claim: "evidence_chain_only_no_runner_selected";
    execution_authorized: false;
    installation_allowed: false;
    dispatch_allowed: false;
    worker_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
};

export type InstallationExecutionAdmissionLinkageV1 = {
    permission_grant_linkage: ExecutionPermissionGrantLinkageV1;
    v035_grant_id: string;
    v035_grant_fingerprint: FingerprintV1;
    v035_status_fingerprint: FingerprintV1;
    v035_request_fingerprint: FingerprintV1;
    v035_confirmation_fingerprint: FingerprintV1;
    v035_operator_fingerprint: FingerprintV1;
    v034_review_fingerprint: FingerprintV1;
    v034_audit_evidence_fingerprint: FingerprintV1;
    chain_fingerprint: FingerprintV1;
    linkage_fingerprint: FingerprintV1;
};

export type InstallationRunnerEligibilityV1 = {
    schema: "installation-runner-eligibility-v1";
    evaluation: "evidence_chain_eligible";
    scope: "future_installation_runner_consideration_only";
    evaluated_at: string;
    admission_gated: true;
    runner_selected: false;
    runner_registered: false;
    runner_available: false;
    runner_invocation_allowed: false;
    worker_start_allowed: false;
    workflow_start_allowed: false;
    execution_start_boundary_defined: false;
    evidence_only: true;
    eligibility_fingerprint: FingerprintV1;
};

export type AdmissionAuthorityV1 = {
    evidence_only: true;
    execution_start_allowed: false;
    runner_binding_allowed: false;
    execution_authorized: false;
    installation_allowed: false;
    dispatch_allowed: false;
    retry_allowed: false;
    resend_allowed: false;
    agent_invocation_allowed: false;
    worker_allowed: false;
    workflow_allowed: false;
    docker_allowed: false;
    podman_allowed: false;
    shell_allowed: false;
    process_allowed: false;
    provider_mutation_allowed: false;
    repository_mutation_allowed: false;
    in_guest_mutation_allowed: false;
    deployment_allowed: false;
    rollback_allowed: false;
    replay_allowed: false;
};

export type InstallationExecutionAdmissionV1 = AdmissionAuthorityV1 & {
    schema: "installation-execution-admission-v1";
    admission_id: string;
    operator_id: string;
    candidate_record_id: string;
    recorded_at: string;
    valid_until: string;
    record_state: "recorded";
    readiness: "admission_gated";
    blockers: ["runner_binding_not_defined", "execution_start_boundary_not_defined"];
    scope: "future_installation_runner_consideration_only";
    linkage: InstallationExecutionAdmissionLinkageV1;
    runner_eligibility: InstallationRunnerEligibilityV1;
    idempotency_key_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1;
    admission_evidence_recorded: true;
    admission_fingerprint: FingerprintV1;
};

export type InstallationExecutionAdmissionStatusV1 = {
    schema: "installation-execution-admission-status-v1";
    admission_id: string;
    admission_fingerprint: FingerprintV1;
    observed_at: string;
    lifecycle: "active" | "expired";
    readiness: "admission_gated";
    evidence_only: true;
    execution_authorized: false;
    installation_allowed: false;
    worker_allowed: false;
    replay_allowed: false;
    status_fingerprint: FingerprintV1;
};

export type AdmissionBlockerV1 = "missing_evidence" | "ownership_mismatch" | "linkage_mismatch" | "fingerprint_mismatch" | "invalid_evidence" | "stale_evidence" | "expired_evidence" | "grant_not_active" | "grant_scope_mismatch" | "grant_unavailable" | "permission_denied" | "subject_reserved" | "installation_capability_unsupported" | "runner_binding_not_defined" | "execution_start_boundary_not_defined";

export type InstallationExecutionAdmissionAuditEvidenceV1 = {
    schema: "installation-execution-admission-audit-evidence-v1";
    admission_id: string | null;
    candidate_record_id: string | null;
    operator_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1 | null;
    idempotency_key_fingerprint: FingerprintV1 | null;
    v035_grant_fingerprint: FingerprintV1 | null;
    linkage_fingerprint: FingerprintV1 | null;
    eligibility_fingerprint: FingerprintV1 | null;
    admission_fingerprint: FingerprintV1 | null;
    blocker_codes: AdmissionBlockerV1[];
    correlation_id: string;
    occurred_at: string;
    outcome: "recorded" | "exact_duplicate" | "rejected" | "unavailable";
    evidence_only: true;
    execution_attempted: false;
    dispatch_attempted: false;
    agent_invoked: false;
    worker_started: false;
    workflow_started: false;
    process_started: false;
    mutation_attempted: false;
    retry_attempted: false;
    replay_attempted: false;
    evidence_fingerprint: FingerprintV1;
};

export type InstallationExecutionAdmissionRedactedErrorV1 = {
    schema: "installation-execution-admission-error-v1";
    error_code: "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "not_eligible" | "expired" | "conflict" | "quota_exceeded" | "unavailable";
    safe_message: "Installation execution admission evidence could not be recorded.";
    blocker_codes: AdmissionBlockerV1[];
    correlation_id: string;
    redacted: true;
    retryable: false;
    evidence_only: true;
    execution_authorized: false;
    installation_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
};

export type InstallationExecutionAdmissionResultV1 = {
    disposition: "recorded" | "exact_duplicate" | "rejected" | "unavailable";
    admission: InstallationExecutionAdmissionV1 | null;
    status: InstallationExecutionAdmissionStatusV1 | null;
    audit_evidence: InstallationExecutionAdmissionAuditEvidenceV1 | null;
    error: InstallationExecutionAdmissionRedactedErrorV1 | null;
    evidence_only: true;
    execution_authorized: false;
    installation_allowed: false;
    dispatch_allowed: false;
    agent_invocation_allowed: false;
    worker_allowed: false;
    workflow_allowed: false;
    mutation_allowed: false;
    deployment_allowed: false;
    rollback_allowed: false;
    retry_allowed: false;
    replay_allowed: false;
};

export type InstallationExecutionAdmissionCollectionV1 = {
    admissions: InstallationExecutionAdmissionResultV1[];
    evidence_only: true;
    execution_start_allowed: false;
    runner_binding_allowed: false;
    execution_authorized: false;
    installation_allowed: false;
    dispatch_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
};
