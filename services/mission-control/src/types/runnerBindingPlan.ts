import type { InstallationExecutionAdmissionLinkageV1 } from "./installationExecutionAdmission";
import type { FingerprintV1 } from "./installationReadinessReview";

export type RunnerBindingPlanCreateV1 = {
    schema: "runner-binding-plan-create-v1";
    admission_id: string;
    admission_fingerprint: FingerprintV1;
    admission_valid_until: string;
    runner_reference_id: string;
    runner_reference_fingerprint: FingerprintV1;
    limits_fingerprint: FingerprintV1;
    requested_scope: "installation_runner_binding_plan_only";
    evidence_only: true;
    runner_binding_allowed: false;
    execution_authorized: false;
    worker_start_allowed: false;
    dispatch_allowed: false;
    replay_allowed: false;
};

export type RunnerBindingLimitsV1 = {
    schema: "runner-binding-limits-v1";
    sandbox: {
        profile: "atlas-installation-confined-v1";
        privileged: false; privilege_escalation: false;
        host_pid_namespace: false; host_ipc_namespace: false;
        host_network_namespace: false; host_devices: false;
        capabilities_drop_all: true; seccomp_required: true; apparmor_required: true;
    };
    resources: {
        cpu_millis_max: 1000; memory_bytes_max: 536870912; pids_max: 64;
        wall_time_seconds_max: 900; output_bytes_max: 1048576;
    };
    network: {
        mode: "none"; ingress_allowed: false; egress_allowed: false;
        dns_allowed: false; image_pull_allowed: false;
        allowed_endpoint_fingerprints: [];
    };
    filesystem: {
        root_filesystem_read_only: true; host_mounts_allowed: false;
        repository_mount_allowed: false; guest_mount_allowed: false;
        internal_path_disclosure_allowed: false; ephemeral_workspace_allowed: true;
        ephemeral_workspace_bytes_max: 268435456;
        writable_scope: "ephemeral_workspace_only";
    };
    limits_fingerprint: FingerprintV1;
};

export type RunnerReferenceV1 = {
    schema: "installation-runner-reference-v1";
    runner_reference_id: string;
    owner_operator_id: string;
    runner_kind: "isolated_installation_runner";
    trust_domain: "atlas-installation";
    scope: "installation_runner_binding_plan_only";
    eligibility: "eligible_for_binding_plan_only";
    identity_fingerprint: FingerprintV1;
    capability_profile_fingerprint: FingerprintV1;
    limits: RunnerBindingLimitsV1;
    valid_from: string;
    valid_until: string;
    reference_fingerprint: FingerprintV1;
    registered: false; available: false; contacted: false; reserved: false;
    invocation_allowed: false;
};

export type RunnerBindingPlanLinkageV1 = {
    schema: "runner-binding-plan-linkage-v1";
    operator_id: string;
    candidate_record_id: string;
    execution_admission_linkage: InstallationExecutionAdmissionLinkageV1;
    v020_v035_chain_fingerprint: FingerprintV1;
    readiness_review_fingerprint: FingerprintV1;
    permission_grant_fingerprint: FingerprintV1;
    execution_admission_id: string;
    execution_admission_fingerprint: FingerprintV1;
    execution_admission_status_fingerprint: FingerprintV1;
    runner_reference_id: string;
    runner_reference_fingerprint: FingerprintV1;
    runner_identity_fingerprint: FingerprintV1;
    runner_capability_profile_fingerprint: FingerprintV1;
    limits_fingerprint: FingerprintV1;
    linkage_fingerprint: FingerprintV1;
};

export type RunnerBindingAuthorityV1 = {
    evidence_only: true;
    runner_registered: false; runner_contacted: false; runner_reserved: false;
    runner_bound: false; runner_binding_allowed: false;
    execution_start_allowed: false; execution_authorized: false;
    installation_allowed: false; dispatch_allowed: false; retry_allowed: false;
    resend_allowed: false; agent_invocation_allowed: false; worker_allowed: false;
    workflow_allowed: false; docker_allowed: false; podman_allowed: false;
    shell_allowed: false; process_allowed: false;
    provider_mutation_allowed: false; repository_mutation_allowed: false;
    in_guest_mutation_allowed: false; deployment_allowed: false;
    rollback_allowed: false; replay_allowed: false;
};

export type RunnerBindingPlanV1 = RunnerBindingAuthorityV1 & {
    schema: "runner-binding-plan-v1";
    plan_id: string; operator_id: string; candidate_record_id: string;
    recorded_at: string; valid_until: string; record_state: "recorded";
    lifecycle: "active"; eligibility: "binding_planned";
    blockers: ["runner_not_bound", "execution_start_boundary_not_defined"];
    linkage: RunnerBindingPlanLinkageV1;
    runner_reference: RunnerReferenceV1;
    limits: RunnerBindingLimitsV1;
    idempotency_key_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1;
    plan_fingerprint: FingerprintV1;
};

export type RunnerBindingPlanStatusV1 = {
    schema: "runner-binding-plan-status-v1";
    plan_id: string; observed_at: string; lifecycle: "active" | "expired";
    eligibility: "binding_planned";
    blockers: ["runner_not_bound", "execution_start_boundary_not_defined"];
    status_fingerprint: FingerprintV1;
    evidence_only: true; runner_bound: false; execution_authorized: false;
    replay_allowed: false;
};

export type RunnerBindingPlanAuditEvidenceV1 = {
    schema: "runner-binding-plan-audit-evidence-v1";
    event: "runner_binding_plan_recorded" | "runner_binding_plan_read";
    outcome: "recorded" | "exact_duplicate" | "read" | "blocked";
    operator_fingerprint: FingerprintV1;
    candidate_record_fingerprint: FingerprintV1;
    plan_fingerprint: FingerprintV1 | null;
    correlation_fingerprint: FingerprintV1;
    occurred_at: string;
    audit_fingerprint: FingerprintV1;
    evidence_only: true; runner_contact_attempted: false;
    runner_binding_attempted: false; worker_start_attempted: false;
    execution_start_attempted: false; dispatch_attempted: false;
    agent_invocation_attempted: false; workflow_start_attempted: false;
    process_execution_attempted: false; mutation_attempted: false;
    effect_attempted: false; replay_attempted: false;
};

export type RunnerBindingPlanRedactedErrorV1 = {
    schema: "runner-binding-plan-redacted-error-v1";
    error_code: "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "not_eligible" | "expired" | "conflict" | "quota_exceeded" | "unavailable";
    message: "runner binding plan request could not be completed";
    correlation_fingerprint: FingerprintV1;
    retryable: false; redacted: true; evidence_only: true;
    runner_binding_allowed: false; execution_authorized: false;
    mutation_allowed: false; replay_allowed: false;
};

export type RunnerBindingPlanResultV1 = {
    schema: "runner-binding-plan-result-v1";
    disposition: "recorded" | "exact_duplicate" | "read" | "blocked";
    plan: RunnerBindingPlanV1 | null;
    status: RunnerBindingPlanStatusV1 | null;
    audit_evidence: RunnerBindingPlanAuditEvidenceV1 | null;
    error: RunnerBindingPlanRedactedErrorV1 | null;
    evidence_only: true; runner_registration_allowed: false;
    runner_contact_allowed: false; runner_reservation_allowed: false;
    runner_binding_allowed: false; runner_bound: false;
    execution_start_allowed: false; execution_authorized: false;
    installation_allowed: false; dispatch_allowed: false;
    agent_invocation_allowed: false; worker_allowed: false;
    workflow_allowed: false; mutation_allowed: false; deployment_allowed: false;
    rollback_allowed: false; retry_allowed: false; replay_allowed: false;
};

export type RunnerBindingPlanCollectionV1 = {
    schema: "runner-binding-plan-collection-v1";
    plans: RunnerBindingPlanResultV1[];
    evidence_only: true; execution_authorized: false; mutation_allowed: false;
};
