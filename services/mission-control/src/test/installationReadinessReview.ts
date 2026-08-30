import { EVIDENCE_ORDER, LINKAGE_KEYS } from "../api/installationReadinessReview";
import type { FingerprintV1, InstallationReadinessReviewResponseV1 } from "../types/installationReadinessReview";

export const uuid4 = "00000000-0000-4000-8000-000000000001";
const uuid5 = "00000000-0000-5000-8000-000000000001";
export const fp: FingerprintV1 = { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: "a".repeat(64) };
const linkage = Object.fromEntries(LINKAGE_KEYS.map((key) => [key,
    key === "v032_agent_receipt_exported" ? false
        : key === "v032_agent_receipt_atomicity_relied_upon" ? true
            : key.endsWith("_id") ? uuid4 : fp,
]));

export const readinessGatedFixture: InstallationReadinessReviewResponseV1 = {
    review: {
        schema: "installation-readiness-review-v1", review_id: uuid5,
        candidate_record_id: uuid4, operator_id: "operator-a", observed_at: "2026-08-27T12:00:16Z",
        readiness: "readiness_gated", blockers: ["execution_admission_not_defined"],
        evidence: EVIDENCE_ORDER.map(([release, evidence_kind]) => ({
            release, evidence_kind, evidence_id: uuid4, evidence_fingerprint: fp,
            evidence_state: "current", valid_until: "2026-08-27T12:00:30Z",
            evidence_only: true, execution_authorized: false, installation_allowed: false,
        })),
        linkage, source: "core_local_owner_scoped_evidence_v1", evidence_only: true,
        read_only: true, execution_admission_granted: false, execution_authorized: false,
        installation_allowed: false, dispatch_allowed: false, worker_allowed: false,
        workflow_allowed: false, deployment_allowed: false, mutation_allowed: false,
        retry_allowed: false, replay_allowed: false, review_fingerprint: fp,
    },
    audit_evidence: {
        schema: "installation-readiness-review-audit-evidence-v1", review_id: uuid5,
        review_fingerprint: fp, candidate_record_id: uuid4, v033_receipt_fingerprint: fp,
        linkage_fingerprint: fp, operator_fingerprint: fp, correlation_id: "review-request-1",
        observed_at: "2026-08-27T12:00:16Z", outcome: "readiness_gated",
        blocker_codes: ["execution_admission_not_defined"], source_was_owner_scoped_local_readers: true,
        evidence_only: true, read_only: true, mutation_attempted: false,
        execution_attempted: false, evidence_fingerprint: fp,
    },
};

export const blockedFixture: InstallationReadinessReviewResponseV1 = {
    review: {
        ...readinessGatedFixture.review,
        readiness: "blocked",
        blockers: ["stale_evidence", "installation_capability_unsupported"],
    },
    audit_evidence: {
        ...readinessGatedFixture.audit_evidence,
        outcome: "blocked",
        blocker_codes: ["stale_evidence", "installation_capability_unsupported"],
    },
};
