import type { FingerprintV1, InstallationReadinessReviewLinkageV1 } from "./installationReadinessReview";

export const EXECUTION_PERMISSION_CONFIRMATION = "I confirm that Atlas may record my permission for this exact evidence chain to be considered by a future execution-admission boundary. This does not install or execute anything." as const;

export type ExecutionPermissionGrantCreateV1 = {
    schema: "execution-permission-grant-create-v1";
    readiness_review_id: string;
    readiness_review_fingerprint: FingerprintV1;
    review_observed_at: string;
    confirmation_text: typeof EXECUTION_PERMISSION_CONFIRMATION;
    permission_scope: "future_execution_admission_consideration_only";
    execution_admission_granted: false;
    execution_authorized: false;
    installation_allowed: false;
    dispatch_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
};

export type ExecutionPermissionGrantLinkageV1 = {
    readiness_linkage: InstallationReadinessReviewLinkageV1;
    v034_review_id: string;
    v034_review_fingerprint: FingerprintV1;
    v034_audit_evidence_fingerprint: FingerprintV1;
    v034_operator_fingerprint: FingerprintV1;
    linkage_fingerprint: FingerprintV1;
};

export type ExecutionPermissionGrantV1 = {
    schema: "execution-permission-grant-v1"; grant_id: string; operator_id: string;
    candidate_record_id: string; recorded_at: string; valid_until: string;
    record_state: "recorded"; permission_scope: "future_execution_admission_consideration_only";
    confirmation_text: typeof EXECUTION_PERMISSION_CONFIRMATION;
    confirmation_fingerprint: FingerprintV1; linkage: ExecutionPermissionGrantLinkageV1;
    idempotency_key_fingerprint: FingerprintV1; request_fingerprint: FingerprintV1;
    statement: "operator_recorded_exact_non_executing_permission_evidence";
    permission_evidence_recorded: true; grant_fingerprint: FingerprintV1;
} & NonAuthorizingV1;

export type ExecutionPermissionGrantStatusV1 = {
    schema: "execution-permission-grant-status-v1"; grant_id: string;
    grant_fingerprint: FingerprintV1; observed_at: string; lifecycle: "active" | "expired";
    permission_evidence_recorded: true; evidence_only: true;
    execution_admission_granted: false; execution_authorized: false;
    installation_allowed: false; mutation_allowed: false; replay_allowed: false;
    status_fingerprint: FingerprintV1;
};

export type ExecutionPermissionGrantAuditEvidenceV1 = {
    schema: "execution-permission-grant-audit-evidence-v1"; grant_id: string | null;
    candidate_record_id: string | null; operator_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1 | null; idempotency_key_fingerprint: FingerprintV1 | null;
    confirmation_fingerprint: FingerprintV1 | null; v034_review_fingerprint: FingerprintV1 | null;
    linkage_fingerprint: FingerprintV1 | null; grant_fingerprint: FingerprintV1 | null;
    correlation_id: string; occurred_at: string;
    outcome: "recorded" | "exact_duplicate" | "rejected" | "unavailable";
    evidence_only: true; execution_attempted: false; dispatch_attempted: false;
    agent_invoked: false; worker_started: false; workflow_started: false;
    process_started: false; mutation_attempted: false; retry_attempted: false;
    replay_attempted: false; evidence_fingerprint: FingerprintV1;
};

export type ExecutionPermissionGrantRedactedErrorV1 = {
    schema: "execution-permission-grant-error-v1";
    error_code: "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "confirmation_mismatch" | "not_readiness_gated" | "expired" | "conflict" | "quota_exceeded" | "unavailable";
    safe_message: "Execution permission evidence could not be recorded.";
    correlation_id: string; redacted: true; retryable: false;
    execution_admission_granted: false; execution_authorized: false;
    installation_allowed: false; mutation_allowed: false; replay_allowed: false;
};

export type NonAuthorizingV1 = {
    evidence_only: true; execution_admission_granted: false; execution_authorized: false;
    installation_allowed: false; dispatch_allowed: false; agent_invocation_allowed: false;
    worker_allowed: false; workflow_allowed: false; provider_mutation_allowed: false;
    repository_mutation_allowed: false; in_guest_mutation_allowed: false;
    deployment_allowed: false; rollback_allowed: false; retry_allowed: false;
    resend_allowed: false; docker_allowed: false; podman_allowed: false;
    shell_allowed: false; process_allowed: false; replay_allowed: false;
};

export type ExecutionPermissionGrantResultV1 = NonAuthorizingV1 & {
    disposition: "recorded" | "exact_duplicate" | "rejected" | "unavailable";
    grant: ExecutionPermissionGrantV1 | null; status: ExecutionPermissionGrantStatusV1 | null;
    audit_evidence: ExecutionPermissionGrantAuditEvidenceV1 | null;
    error: ExecutionPermissionGrantRedactedErrorV1 | null;
};

export type ExecutionPermissionGrantCollectionV1 = {
    grants: ExecutionPermissionGrantResultV1[]; evidence_only: true;
    execution_authorized: false; installation_allowed: false;
    mutation_allowed: false; replay_allowed: false;
};
