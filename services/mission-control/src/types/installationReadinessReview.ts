export type FingerprintV1 = {
    algorithm: "sha256";
    canonicalization: "atlas-jcs-nfc-v1";
    value: string;
};

export type InstallationReadinessBlockerV1 =
    | "missing_evidence" | "ownership_mismatch" | "linkage_mismatch"
    | "fingerprint_mismatch" | "invalid_evidence" | "stale_evidence"
    | "expired_evidence" | "terminal_ambiguity" | "agent_evidence_unavailable"
    | "source_unavailable" | "installation_capability_unsupported"
    | "execution_admission_not_defined";

export type InstallationReadinessReleaseV1 =
    | "v0.20" | "v0.21" | "v0.22" | "v0.23" | "v0.24" | "v0.25" | "v0.26"
    | "v0.27" | "v0.28" | "v0.29" | "v0.30" | "v0.31" | "v0.32" | "v0.33";

export type InstallationReadinessEvidenceKindV1 =
    | "candidate_record" | "approval_intent" | "agent_install_container_validation"
    | "execution_request" | "dispatch_handoff" | "agent_intake_simulation"
    | "simulated_handoff_delivery" | "real_agent_intake" | "dormant_delivery_wiring"
    | "delivery_activation_preflight" | "operator_delivery_enablement"
    | "live_delivery_send" | "agent_live_intake_admission" | "inert_delivery_receipt";

export type InstallationReadinessEvidenceSummaryV1 = {
    release: InstallationReadinessReleaseV1;
    evidence_kind: InstallationReadinessEvidenceKindV1;
    evidence_id: string | null;
    evidence_fingerprint: FingerprintV1 | null;
    evidence_state: "current" | "missing" | "expired" | "terminal" | "unavailable";
    valid_until: string | null;
    evidence_only: true;
    execution_authorized: false;
    installation_allowed: false;
};

export type InstallationReadinessReviewLinkageV1 = Record<string, string | boolean | FingerprintV1>;

export type InstallationReadinessReviewV1 = {
    schema: "installation-readiness-review-v1";
    review_id: string;
    candidate_record_id: string;
    operator_id: string;
    observed_at: string;
    readiness: "blocked" | "readiness_gated";
    blockers: InstallationReadinessBlockerV1[];
    evidence: InstallationReadinessEvidenceSummaryV1[];
    linkage: InstallationReadinessReviewLinkageV1 | null;
    source: "core_local_owner_scoped_evidence_v1";
    evidence_only: true;
    read_only: true;
    execution_admission_granted: false;
    execution_authorized: false;
    installation_allowed: false;
    dispatch_allowed: false;
    worker_allowed: false;
    workflow_allowed: false;
    deployment_allowed: false;
    mutation_allowed: false;
    retry_allowed: false;
    replay_allowed: false;
    review_fingerprint: FingerprintV1;
};

export type InstallationReadinessReviewAuditEvidenceV1 = {
    schema: "installation-readiness-review-audit-evidence-v1";
    review_id: string;
    review_fingerprint: FingerprintV1;
    candidate_record_id: string;
    v033_receipt_fingerprint: FingerprintV1 | null;
    linkage_fingerprint: FingerprintV1 | null;
    operator_fingerprint: FingerprintV1;
    correlation_id: string;
    observed_at: string;
    outcome: "blocked" | "readiness_gated";
    blocker_codes: InstallationReadinessBlockerV1[];
    source_was_owner_scoped_local_readers: true;
    evidence_only: true;
    read_only: true;
    mutation_attempted: false;
    execution_attempted: false;
    evidence_fingerprint: FingerprintV1;
};

export type InstallationReadinessReviewResponseV1 = {
    review: InstallationReadinessReviewV1;
    audit_evidence: InstallationReadinessReviewAuditEvidenceV1;
};

export type InstallationReadinessReviewRedactedErrorV1 = {
    schema: "installation-readiness-review-error-v1";
    error_code: "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "unavailable";
    safe_message: "Installation readiness review is unavailable.";
    correlation_id: string;
    redacted: true;
    retryable: false;
    execution_authorized: false;
    installation_allowed: false;
    mutation_allowed: false;
};
