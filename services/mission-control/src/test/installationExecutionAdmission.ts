import { grantResultFixture } from "./executionPermissionGrant";
import { fp, uuid4 } from "./installationReadinessReview";
import type { AdmissionAuthorityV1, InstallationExecutionAdmissionResultV1 } from "../types/installationExecutionAdmission";

const authority: AdmissionAuthorityV1 = {
    evidence_only: true, execution_start_allowed: false, runner_binding_allowed: false,
    execution_authorized: false, installation_allowed: false, dispatch_allowed: false,
    retry_allowed: false, resend_allowed: false, agent_invocation_allowed: false,
    worker_allowed: false, workflow_allowed: false, docker_allowed: false,
    podman_allowed: false, shell_allowed: false, process_allowed: false,
    provider_mutation_allowed: false, repository_mutation_allowed: false,
    in_guest_mutation_allowed: false, deployment_allowed: false,
    rollback_allowed: false, replay_allowed: false,
};

const resultAuthority = {
    evidence_only: true as const, execution_authorized: false as const,
    installation_allowed: false as const, dispatch_allowed: false as const,
    agent_invocation_allowed: false as const, worker_allowed: false as const,
    workflow_allowed: false as const, mutation_allowed: false as const,
    deployment_allowed: false as const, rollback_allowed: false as const,
    retry_allowed: false as const, replay_allowed: false as const,
};

export const admissionResultFixture: InstallationExecutionAdmissionResultV1 = {
    ...resultAuthority, disposition: "recorded", error: null,
    admission: {
        ...authority, schema: "installation-execution-admission-v1",
        admission_id: uuid4, operator_id: "operator-a", candidate_record_id: uuid4,
        recorded_at: "2026-08-27T12:00:19Z", valid_until: "2026-08-27T12:00:30Z",
        record_state: "recorded", readiness: "admission_gated",
        blockers: ["runner_binding_not_defined", "execution_start_boundary_not_defined"],
        scope: "future_installation_runner_consideration_only",
        linkage: {
            permission_grant_linkage: grantResultFixture.grant!.linkage,
            v035_grant_id: uuid4, v035_grant_fingerprint: fp,
            v035_status_fingerprint: fp, v035_request_fingerprint: fp,
            v035_confirmation_fingerprint: fp, v035_operator_fingerprint: fp,
            v034_review_fingerprint: fp, v034_audit_evidence_fingerprint: fp,
            chain_fingerprint: fp, linkage_fingerprint: fp,
        },
        runner_eligibility: {
            schema: "installation-runner-eligibility-v1",
            evaluation: "evidence_chain_eligible",
            scope: "future_installation_runner_consideration_only",
            evaluated_at: "2026-08-27T12:00:19Z", admission_gated: true,
            runner_selected: false, runner_registered: false, runner_available: false,
            runner_invocation_allowed: false, worker_start_allowed: false,
            workflow_start_allowed: false, execution_start_boundary_defined: false,
            evidence_only: true, eligibility_fingerprint: fp,
        },
        idempotency_key_fingerprint: fp, request_fingerprint: fp,
        admission_evidence_recorded: true, admission_fingerprint: fp,
    },
    status: {
        schema: "installation-execution-admission-status-v1", admission_id: uuid4,
        admission_fingerprint: fp, observed_at: "2026-08-27T12:00:20Z",
        lifecycle: "active", readiness: "admission_gated", evidence_only: true,
        execution_authorized: false, installation_allowed: false,
        worker_allowed: false, replay_allowed: false, status_fingerprint: fp,
    },
    audit_evidence: {
        schema: "installation-execution-admission-audit-evidence-v1",
        admission_id: uuid4, candidate_record_id: uuid4, operator_fingerprint: fp,
        request_fingerprint: fp, idempotency_key_fingerprint: fp,
        v035_grant_fingerprint: fp, linkage_fingerprint: fp,
        eligibility_fingerprint: fp, admission_fingerprint: fp,
        blocker_codes: ["runner_binding_not_defined", "execution_start_boundary_not_defined"],
        correlation_id: "admission-request-1", occurred_at: "2026-08-27T12:00:19Z",
        outcome: "recorded", evidence_only: true, execution_attempted: false,
        dispatch_attempted: false, agent_invoked: false, worker_started: false,
        workflow_started: false, process_started: false, mutation_attempted: false,
        retry_attempted: false, replay_attempted: false, evidence_fingerprint: fp,
    },
};
