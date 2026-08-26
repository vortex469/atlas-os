export type InstallationPlanStatus =
    | "conflicted"
    | "missing_deployment_artifact"
    | "incompatible"
    | "stale_evidence"
    | "insufficient_information"
    | "plan_ready_for_review";

export type InstallationPlanRelationshipKind =
    | "depends_on" | "provides" | "consumes" | "requires" | "integrates_with"
    | "conflicts_with" | "runs_on" | "deployed_by" | "compatible_with" | "incompatible_with";

export type InstallationPlanBlockerCode =
    | "missing_deployment_binding" | "missing_deployment_artifact" | "invalid_deployment_artifact"
    | "unsafe_deployment_artifact" | "unknown_deployment_artifact" | "missing_immutable_image_identity"
    | "mutable_image_reference" | "untrusted_evidence" | "image_conflict" | "image_mismatch"
    | "unknown_image_state" | "missing_accepted_evidence" | "stale_evidence" | "malformed_evidence"
    | "provenance_conflict" | "incompatible_application_environment" | "unknown_compatibility"
    | "missing_prerequisite" | "missing_prerequisite_fact" | "missing_target_identity"
    | "required_operator_confirmation" | "malformed_source_fact";

export type InstallationPlanMissingFactCode =
    | "deployment_binding" | "deployment_artifact" | "immutable_image_identity" | "accepted_evidence"
    | "prerequisite_fact" | "target_identity" | "compatibility_fact" | "source_fact";

export type InstallationPlanCompatibilityReasonCode =
    | "target_free_catalog_compatible" | "target_free_catalog_warning"
    | "target_free_catalog_incompatible" | "target_required"
    | "compatibility_fact_missing" | "compatibility_fact_malformed";

export type InstallationPlan = {
    schema_version: "installation-plan-v1";
    fingerprint: {
        algorithm: "sha256";
        canonicalization: "atlas-jcs-nfc-v1";
        value: string;
    };
    application: {
        item_id: string;
        catalog_entry_id: string;
        display_name: string;
        release_version: string | null;
    };
    status: InstallationPlanStatus;
    deployment_artifact: {
        state: "present" | "missing" | "invalid" | "unsafe" | "unknown";
        kind: "docker-compose";
        repository_path: string | null;
        service: string | null;
        content_digest: string | null;
    };
    image: {
        state: "grounded" | "missing" | "mutable" | "untrusted" | "conflicted" | "mismatched" | "unknown";
        reference: string | null;
        digest: string | null;
        release_version: string | null;
    };
    accepted_evidence: Array<{
        evidence_id: string;
        source_class: "curated" | "registry_attested" | "upstream_signed";
        source_id: string;
        subject: string;
        claim: string;
        immutable_identity: string;
        observed_at: null;
        attested_at: string;
        freshness_window_seconds: number;
        trust: "accepted";
    }>;
    provenance: Array<{
        claim: string;
        source_class: "curated_catalog" | "deployment_binding" | "repository_observation" | "image_release_evidence" | "compatibility_evaluation" | "prerequisite_source" | "policy_evaluation";
        source_id: string;
        immutable_identity: string;
        observed_at: string | null;
        attested_at: string | null;
    }>;
    compatibility: Array<{
        environment: "item-scoped";
        result: "compatible" | "compatible_with_warnings" | "incompatible" | "unknown";
        reason_code: InstallationPlanCompatibilityReasonCode;
    }>;
    prerequisites: Array<{
        prerequisite_id: string;
        kind: "storage" | "network" | "platform" | "application" | "operator";
        state: "satisfied" | "missing" | "unknown";
        description: string;
    }>;
    relationships: Array<{
        kind: InstallationPlanRelationshipKind;
        item_id: string;
        required: boolean;
        minimum_version: string | null;
        maximum_version: string | null;
    }>;
    assumptions: Array<{ assumption_id: string; kind: "catalog" | "environment" | "operator"; statement: string }>;
    blockers: Array<{ code: InstallationPlanBlockerCode; subject: string }>;
    risks: Array<{ code: "evidence_approaching_expiry" | "compatibility_warning"; severity: "low" | "medium" | "high" | "critical"; subject: string }>;
    missing_facts: Array<{ code: InstallationPlanMissingFactCode; subject: string }>;
    required_operator_confirmations: Array<{
        code: "accept_assumption" | "confirm_prerequisite" | "confirm_risk";
        subject: string;
        prompt: string;
    }>;
};
