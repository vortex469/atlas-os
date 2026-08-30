import { admissionResultFixture } from "./installationExecutionAdmission";
import type { FingerprintV1 } from "../types/installationReadinessReview";
import type { RunnerBindingPlanResultV1 } from "../types/runnerBindingPlan";

const fp = (value: string): FingerprintV1 => ({ algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: value.repeat(64) });
const admission = admissionResultFixture.admission!;
const limits = {
    schema: "runner-binding-limits-v1" as const,
    sandbox: { profile: "atlas-installation-confined-v1" as const, privileged: false as const, privilege_escalation: false as const, host_pid_namespace: false as const, host_ipc_namespace: false as const, host_network_namespace: false as const, host_devices: false as const, capabilities_drop_all: true as const, seccomp_required: true as const, apparmor_required: true as const },
    resources: { cpu_millis_max: 1000 as const, memory_bytes_max: 536870912 as const, pids_max: 64 as const, wall_time_seconds_max: 900 as const, output_bytes_max: 1048576 as const },
    network: { mode: "none" as const, ingress_allowed: false as const, egress_allowed: false as const, dns_allowed: false as const, image_pull_allowed: false as const, allowed_endpoint_fingerprints: [] as [] },
    filesystem: { root_filesystem_read_only: true as const, host_mounts_allowed: false as const, repository_mount_allowed: false as const, guest_mount_allowed: false as const, internal_path_disclosure_allowed: false as const, ephemeral_workspace_allowed: true as const, ephemeral_workspace_bytes_max: 268435456 as const, writable_scope: "ephemeral_workspace_only" as const },
    limits_fingerprint: fp("1"),
};
const authority = {
    evidence_only: true as const, runner_registered: false as const, runner_contacted: false as const, runner_reserved: false as const, runner_bound: false as const, runner_binding_allowed: false as const, execution_start_allowed: false as const, execution_authorized: false as const, installation_allowed: false as const, dispatch_allowed: false as const, retry_allowed: false as const, resend_allowed: false as const, agent_invocation_allowed: false as const, worker_allowed: false as const, workflow_allowed: false as const, docker_allowed: false as const, podman_allowed: false as const, shell_allowed: false as const, process_allowed: false as const, provider_mutation_allowed: false as const, repository_mutation_allowed: false as const, in_guest_mutation_allowed: false as const, deployment_allowed: false as const, rollback_allowed: false as const, replay_allowed: false as const,
};
const planFingerprint = fp("2");
const resultAuthority = { evidence_only: true as const, runner_registration_allowed: false as const, runner_contact_allowed: false as const, runner_reservation_allowed: false as const, runner_binding_allowed: false as const, runner_bound: false as const, execution_start_allowed: false as const, execution_authorized: false as const, installation_allowed: false as const, dispatch_allowed: false as const, agent_invocation_allowed: false as const, worker_allowed: false as const, workflow_allowed: false as const, mutation_allowed: false as const, deployment_allowed: false as const, rollback_allowed: false as const, retry_allowed: false as const, replay_allowed: false as const };

export const runnerBindingPlanResultFixture: RunnerBindingPlanResultV1 = {
    schema: "runner-binding-plan-result-v1", disposition: "recorded",
    plan: {
        schema: "runner-binding-plan-v1", plan_id: "40f029e7-3b29-4e85-b89f-c3add6f1793d", operator_id: admission.operator_id, candidate_record_id: admission.candidate_record_id,
        recorded_at: "2026-08-27T12:00:32Z", valid_until: "2026-08-27T12:00:45Z", record_state: "recorded", lifecycle: "active", eligibility: "binding_planned", blockers: ["runner_not_bound", "execution_start_boundary_not_defined"],
        linkage: {
            schema: "runner-binding-plan-linkage-v1", operator_id: admission.operator_id, candidate_record_id: admission.candidate_record_id, execution_admission_linkage: admission.linkage,
            v020_v035_chain_fingerprint: admission.linkage.chain_fingerprint, readiness_review_fingerprint: admission.linkage.v034_review_fingerprint, permission_grant_fingerprint: admission.linkage.v035_grant_fingerprint,
            execution_admission_id: admission.admission_id, execution_admission_fingerprint: admission.admission_fingerprint, execution_admission_status_fingerprint: fp("3"), runner_reference_id: "524238cb-02a3-4ff2-8e7a-dd8c53523a82", runner_reference_fingerprint: fp("4"), runner_identity_fingerprint: fp("5"), runner_capability_profile_fingerprint: fp("6"), limits_fingerprint: limits.limits_fingerprint, linkage_fingerprint: fp("7"),
        },
        runner_reference: { schema: "installation-runner-reference-v1", runner_reference_id: "524238cb-02a3-4ff2-8e7a-dd8c53523a82", owner_operator_id: admission.operator_id, runner_kind: "isolated_installation_runner", trust_domain: "atlas-installation", scope: "installation_runner_binding_plan_only", eligibility: "eligible_for_binding_plan_only", identity_fingerprint: fp("5"), capability_profile_fingerprint: fp("6"), limits, valid_from: "2026-08-27T12:00:20Z", valid_until: "2026-08-27T12:00:45Z", reference_fingerprint: fp("4"), registered: false, available: false, contacted: false, reserved: false, invocation_allowed: false },
        limits, idempotency_key_fingerprint: fp("8"), request_fingerprint: fp("9"), plan_fingerprint: planFingerprint, ...authority,
    },
    status: { schema: "runner-binding-plan-status-v1", plan_id: "40f029e7-3b29-4e85-b89f-c3add6f1793d", observed_at: "2026-08-27T12:00:32Z", lifecycle: "active", eligibility: "binding_planned", blockers: ["runner_not_bound", "execution_start_boundary_not_defined"], status_fingerprint: fp("a"), evidence_only: true, runner_bound: false, execution_authorized: false, replay_allowed: false },
    audit_evidence: { schema: "runner-binding-plan-audit-evidence-v1", event: "runner_binding_plan_recorded", outcome: "recorded", operator_fingerprint: fp("b"), candidate_record_fingerprint: fp("c"), plan_fingerprint: planFingerprint, correlation_fingerprint: fp("d"), occurred_at: "2026-08-27T12:00:32Z", audit_fingerprint: fp("e"), evidence_only: true, runner_contact_attempted: false, runner_binding_attempted: false, worker_start_attempted: false, execution_start_attempted: false, dispatch_attempted: false, agent_invocation_attempted: false, workflow_start_attempted: false, process_execution_attempted: false, mutation_attempted: false, effect_attempted: false, replay_attempted: false },
    error: null, ...resultAuthority,
};
