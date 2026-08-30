import { readinessGatedFixture, fp, uuid4 } from "./installationReadinessReview";
import { EXECUTION_PERMISSION_CONFIRMATION, type ExecutionPermissionGrantResultV1 } from "../types/executionPermissionGrant";

const falseAuthority = {
    evidence_only: true as const, execution_admission_granted: false as const,
    execution_authorized: false as const, installation_allowed: false as const,
    dispatch_allowed: false as const, agent_invocation_allowed: false as const,
    worker_allowed: false as const, workflow_allowed: false as const,
    provider_mutation_allowed: false as const, repository_mutation_allowed: false as const,
    in_guest_mutation_allowed: false as const, deployment_allowed: false as const,
    rollback_allowed: false as const, retry_allowed: false as const, resend_allowed: false as const,
    docker_allowed: false as const, podman_allowed: false as const, shell_allowed: false as const,
    process_allowed: false as const, replay_allowed: false as const,
};

export const grantResultFixture: ExecutionPermissionGrantResultV1 = {
    ...falseAuthority, disposition: "recorded", error: null,
    grant: {
        ...falseAuthority, schema: "execution-permission-grant-v1", grant_id: uuid4,
        operator_id: "operator-a", candidate_record_id: uuid4,
        recorded_at: "2026-08-27T12:00:17Z", valid_until: "2026-08-27T12:00:30Z",
        record_state: "recorded", permission_scope: "future_execution_admission_consideration_only",
        confirmation_text: EXECUTION_PERMISSION_CONFIRMATION, confirmation_fingerprint: fp,
        linkage: { readiness_linkage: readinessGatedFixture.review.linkage!, v034_review_id: readinessGatedFixture.review.review_id, v034_review_fingerprint: fp, v034_audit_evidence_fingerprint: fp, v034_operator_fingerprint: fp, linkage_fingerprint: fp },
        idempotency_key_fingerprint: fp, request_fingerprint: fp,
        statement: "operator_recorded_exact_non_executing_permission_evidence",
        permission_evidence_recorded: true, grant_fingerprint: fp,
    },
    status: { schema: "execution-permission-grant-status-v1", grant_id: uuid4, grant_fingerprint: fp, observed_at: "2026-08-27T12:00:18Z", lifecycle: "active", permission_evidence_recorded: true, evidence_only: true, execution_admission_granted: false, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false, status_fingerprint: fp },
    audit_evidence: { schema: "execution-permission-grant-audit-evidence-v1", grant_id: uuid4, candidate_record_id: uuid4, operator_fingerprint: fp, request_fingerprint: fp, idempotency_key_fingerprint: fp, confirmation_fingerprint: fp, v034_review_fingerprint: fp, linkage_fingerprint: fp, grant_fingerprint: fp, correlation_id: "grant-request-1", occurred_at: "2026-08-27T12:00:17Z", outcome: "recorded", evidence_only: true, execution_attempted: false, dispatch_attempted: false, agent_invoked: false, worker_started: false, workflow_started: false, process_started: false, mutation_attempted: false, retry_attempted: false, replay_attempted: false, evidence_fingerprint: fp },
};
