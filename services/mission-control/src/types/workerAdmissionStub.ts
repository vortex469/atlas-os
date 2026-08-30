import type { FingerprintV1 } from "./installationReadinessReview";
import type { RunnerBindingLimitsV1, RunnerBindingPlanLinkageV1 } from "./runnerBindingPlan";

export type WorkerAdmissionStubCreateV1 = {
    schema: "worker-admission-stub-create-v1";
    runner_binding_plan_id: string;
    runner_binding_plan_fingerprint: FingerprintV1;
    runner_binding_plan_valid_until: string;
    worker_reference_id: string;
    worker_reference_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1;
    requested_scope: "installation_worker_admission_stub_only";
    evidence_only: true;
    worker_start_allowed: false;
    queue_allowed: false;
    dispatch_allowed: false;
    execution_authorized: false;
    replay_allowed: false;
};

export type WorkerAdmissionIntentV1 = {
    schema: "worker-admission-intent-v1"; intent_id: string; operator_id: string;
    candidate_record_id: string; runner_binding_plan_id: string;
    runner_binding_plan_fingerprint: FingerprintV1; worker_reference_id: string;
    worker_reference_fingerprint: FingerprintV1; inherited_limits_fingerprint: FingerprintV1;
    scope: "installation_worker_admission_stub_only";
    intent: "preserve_non_executing_worker_admission_evidence_only";
    requested_at: string; intent_fingerprint: FingerprintV1;
    queue_requested: false; dispatch_requested: false; worker_start_requested: false;
    execution_requested: false; agent_invocation_requested: false; mutation_requested: false;
};

export type WorkerAdmissionIntakeStubV1 = {
    schema: "worker-admission-intake-stub-v1"; intent_id: string;
    intent_fingerprint: FingerprintV1; worker_reference_id: string;
    worker_reference_fingerprint: FingerprintV1;
    scope: "installation_worker_admission_stub_only"; intake_state: "undefined";
    intake_protocol: "none"; intake_fingerprint: FingerprintV1;
    queue_selected: false; queue_created: false; intake_open: false;
    payload_constructed: false; request_serialized: false; request_sent: false;
    worker_contacted: false; worker_started: false; execution_authorized: false;
};

export type WorkerReferenceV1 = {
    schema: "installation-worker-reference-v1"; worker_reference_id: string;
    owner_operator_id: string; worker_kind: "isolated_installation_worker";
    trust_domain: "atlas-installation"; scope: "installation_worker_admission_stub_only";
    eligibility: "eligible_for_admission_stub_only"; runner_reference_id: string;
    runner_reference_fingerprint: FingerprintV1; identity_fingerprint: FingerprintV1;
    capability_profile_fingerprint: FingerprintV1; inherited_limits: RunnerBindingLimitsV1;
    inherited_limits_fingerprint: FingerprintV1; valid_from: string; valid_until: string;
    reference_fingerprint: FingerprintV1; registered: false; available: false;
    reachable: false; authenticated: false; contacted: false; reserved: false;
    bound: false; queue_known: false; intake_open: false; invocation_allowed: false;
};

export type WorkerAdmissionStubLinkageV1 = {
    schema: "worker-admission-stub-linkage-v1"; operator_id: string;
    candidate_record_id: string; runner_binding_plan_linkage: RunnerBindingPlanLinkageV1;
    v020_v036_chain_fingerprint: FingerprintV1; readiness_review_fingerprint: FingerprintV1;
    permission_grant_fingerprint: FingerprintV1; execution_admission_id: string;
    execution_admission_fingerprint: FingerprintV1; runner_binding_plan_id: string;
    runner_binding_plan_fingerprint: FingerprintV1; runner_binding_plan_status_fingerprint: FingerprintV1;
    runner_reference_id: string; runner_reference_fingerprint: FingerprintV1;
    worker_reference_id: string; worker_reference_fingerprint: FingerprintV1;
    worker_identity_fingerprint: FingerprintV1; worker_capability_profile_fingerprint: FingerprintV1;
    worker_admission_intent_fingerprint: FingerprintV1; worker_admission_intake_fingerprint: FingerprintV1;
    inherited_limits_fingerprint: FingerprintV1; linkage_fingerprint: FingerprintV1;
};

export type WorkerAdmissionStubV1 = {
    schema: "worker-admission-stub-v1"; stub_id: string; operator_id: string;
    candidate_record_id: string; recorded_at: string; valid_until: string;
    record_state: "recorded"; lifecycle: "active"; eligibility: "worker_admission_stubbed";
    blockers: ["worker_not_started", "queue_boundary_not_defined", "execution_start_boundary_not_defined"];
    linkage: WorkerAdmissionStubLinkageV1; worker_admission_intent: WorkerAdmissionIntentV1;
    worker_admission_intake: WorkerAdmissionIntakeStubV1; worker_reference: WorkerReferenceV1;
    inherited_limits: RunnerBindingLimitsV1; idempotency_key_fingerprint: FingerprintV1;
    request_fingerprint: FingerprintV1; stub_fingerprint: FingerprintV1;
    evidence_only: true; runner_binding_allowed: false; worker_registered: false;
    worker_contacted: false; worker_reserved: false; worker_bound: false; worker_started: false;
    queue_created: false; queue_allowed: false; work_enqueued: false; enqueue_allowed: false;
    dispatch_allowed: false; execution_start_allowed: false; execution_authorized: false;
    installation_allowed: false; retry_allowed: false; resend_allowed: false;
    agent_invocation_allowed: false; workflow_allowed: false; docker_allowed: false;
    podman_allowed: false; shell_allowed: false; process_allowed: false;
    provider_mutation_allowed: false; repository_mutation_allowed: false;
    in_guest_mutation_allowed: false; deployment_allowed: false; rollback_allowed: false;
    replay_allowed: false;
};

export type WorkerAdmissionStubStatusV1 = {
    schema: "worker-admission-stub-status-v1"; stub_id: string; observed_at: string;
    lifecycle: "active" | "expired"; eligibility: "worker_admission_stubbed";
    blockers: ["worker_not_started", "queue_boundary_not_defined", "execution_start_boundary_not_defined"];
    status_fingerprint: FingerprintV1; evidence_only: true; worker_started: false;
    work_enqueued: false; execution_authorized: false; replay_allowed: false;
};

export type WorkerAdmissionStubAuditEvidenceV1 = {
    schema: "worker-admission-stub-audit-evidence-v1";
    event: "worker_admission_stub_recorded" | "worker_admission_stub_read";
    outcome: "recorded" | "exact_duplicate" | "read" | "blocked";
    operator_fingerprint: FingerprintV1; candidate_record_fingerprint: FingerprintV1;
    stub_fingerprint: FingerprintV1 | null; correlation_fingerprint: FingerprintV1;
    occurred_at: string; audit_fingerprint: FingerprintV1; evidence_only: true;
    worker_contact_attempted: false; worker_start_attempted: false; enqueue_attempted: false;
    dispatch_attempted: false; execution_start_attempted: false; agent_invocation_attempted: false;
    workflow_start_attempted: false; process_execution_attempted: false;
    mutation_attempted: false; replay_attempted: false; effect_attempted: false;
};

export type WorkerAdmissionStubRedactedErrorV1 = {
    schema: "worker-admission-stub-redacted-error-v1";
    error_code: "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "not_eligible" | "expired" | "conflict" | "quota_exceeded" | "unavailable";
    message: "worker admission stub request could not be completed";
    correlation_fingerprint: FingerprintV1; retryable: false; redacted: true;
    evidence_only: true; worker_start_allowed: false; enqueue_allowed: false;
    dispatch_allowed: false; execution_authorized: false; mutation_allowed: false;
    replay_allowed: false;
};

export type WorkerAdmissionStubResultV1 = {
    schema: "worker-admission-stub-result-v1";
    disposition: "recorded" | "exact_duplicate" | "read" | "blocked";
    stub: WorkerAdmissionStubV1 | null; status: WorkerAdmissionStubStatusV1 | null;
    audit_evidence: WorkerAdmissionStubAuditEvidenceV1 | null;
    error: WorkerAdmissionStubRedactedErrorV1 | null; evidence_only: true;
    worker_registration_allowed: false; worker_contact_allowed: false;
    worker_reservation_allowed: false; worker_binding_allowed: false;
    worker_start_allowed: false; queue_allowed: false; enqueue_allowed: false;
    dispatch_allowed: false; execution_start_allowed: false; execution_authorized: false;
    installation_allowed: false; agent_invocation_allowed: false; workflow_allowed: false;
    mutation_allowed: false; deployment_allowed: false; rollback_allowed: false;
    retry_allowed: false; replay_allowed: false;
};

export type WorkerAdmissionStubCollectionV1 = {
    schema: "worker-admission-stub-collection-v1"; stubs: WorkerAdmissionStubResultV1[];
    evidence_only: true; worker_start_allowed: false; enqueue_allowed: false;
    execution_authorized: false; mutation_allowed: false;
};
