import { atlas } from "./atlas";
import type {
    FingerprintV1,
    InstallationReadinessBlockerV1,
    InstallationReadinessEvidenceSummaryV1,
    InstallationReadinessReviewAuditEvidenceV1,
    InstallationReadinessReviewLinkageV1,
    InstallationReadinessReviewResponseV1,
    InstallationReadinessReviewV1,
} from "../types/installationReadinessReview";

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const IDENTITY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const FP_KEYS = ["algorithm", "canonicalization", "value"] as const;
const RESPONSE_KEYS = ["review", "audit_evidence"] as const;
const REVIEW_KEYS = ["schema", "review_id", "candidate_record_id", "operator_id", "observed_at", "readiness", "blockers", "evidence", "linkage", "source", "evidence_only", "read_only", "execution_admission_granted", "execution_authorized", "installation_allowed", "dispatch_allowed", "worker_allowed", "workflow_allowed", "deployment_allowed", "mutation_allowed", "retry_allowed", "replay_allowed", "review_fingerprint"] as const;
const SUMMARY_KEYS = ["release", "evidence_kind", "evidence_id", "evidence_fingerprint", "evidence_state", "valid_until", "evidence_only", "execution_authorized", "installation_allowed"] as const;
const AUDIT_KEYS = ["schema", "review_id", "review_fingerprint", "candidate_record_id", "v033_receipt_fingerprint", "linkage_fingerprint", "operator_fingerprint", "correlation_id", "observed_at", "outcome", "blocker_codes", "source_was_owner_scoped_local_readers", "evidence_only", "read_only", "mutation_attempted", "execution_attempted", "evidence_fingerprint"] as const;
export const EVIDENCE_ORDER = [
    ["v0.20", "candidate_record"], ["v0.21", "approval_intent"],
    ["v0.22", "agent_install_container_validation"], ["v0.23", "execution_request"],
    ["v0.24", "dispatch_handoff"], ["v0.25", "agent_intake_simulation"],
    ["v0.26", "simulated_handoff_delivery"], ["v0.27", "real_agent_intake"],
    ["v0.28", "dormant_delivery_wiring"], ["v0.29", "delivery_activation_preflight"],
    ["v0.30", "operator_delivery_enablement"], ["v0.31", "live_delivery_send"],
    ["v0.32", "agent_live_intake_admission"], ["v0.33", "inert_delivery_receipt"],
] as const;
export const BLOCKER_ORDER: readonly InstallationReadinessBlockerV1[] = [
    "missing_evidence", "ownership_mismatch", "linkage_mismatch", "fingerprint_mismatch",
    "invalid_evidence", "stale_evidence", "expired_evidence", "terminal_ambiguity",
    "agent_evidence_unavailable", "source_unavailable",
    "installation_capability_unsupported", "execution_admission_not_defined",
];
export const LINKAGE_KEYS = [
    "candidate_record_id", "candidate_envelope_fingerprint", "candidate_record_fingerprint",
    "approval_intent_id", "approval_intent_fingerprint", "agent_request_id",
    "agent_request_fingerprint", "agent_validation_fingerprint",
    "agent_audit_evidence_fingerprint", "destination_fingerprint",
    "source_plan_fingerprint", "artifact_policy_fingerprint", "execution_request_id",
    "execution_request_fingerprint", "dispatch_envelope_id", "dispatch_envelope_fingerprint",
    "simulation_request_id", "intake_record_id", "intake_record_fingerprint",
    "intake_simulation_evidence_fingerprint", "simulated_delivery_id",
    "simulated_delivery_fingerprint", "delivery_record_fingerprint",
    "simulated_delivery_evidence_fingerprint", "simulated_acknowledgement_id",
    "simulated_acknowledgement_fingerprint", "simulated_acknowledgement_evidence_fingerprint",
    "intake_request_id", "delivery_attempt_id", "dormant_preparation_fingerprint",
    "delivery_preparation_id", "preparation_fingerprint", "preflight_id",
    "preflight_fingerprint", "enablement_id", "enablement_fingerprint", "send_attempt_id",
    "attempt_fingerprint", "v031_send_receipt_fingerprint", "v032_envelope_fingerprint",
    "v032_agent_result_fingerprint", "v032_admission_id", "v032_admission_fingerprint",
    "v032_acknowledgement_id", "v032_acknowledgement_fingerprint",
    "v032_agent_receipt_exported", "v032_agent_receipt_atomicity_relied_upon",
    "v033_receipt_id", "v033_receipt_fingerprint", "v033_verification_fingerprint",
    "v033_linkage_fingerprint",
] as const;
const ID_KEYS = new Set(LINKAGE_KEYS.filter((key) => key.endsWith("_id")));
const BOOLEAN_KEYS = new Set(["v032_agent_receipt_exported", "v032_agent_receipt_atomicity_relied_upon"]);

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]) { return Object.keys(value).length === keys.length && keys.every((key) => key in value); }
function utc(value: unknown): value is string { if (typeof value !== "string" || !UTC_SECOND.test(value)) return false; const date = new Date(value); return !Number.isNaN(date.getTime()) && date.toISOString() === value.replace("Z", ".000Z"); }
function fingerprint(value: unknown): value is FingerprintV1 { return object(value) && exact(value, FP_KEYS) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && typeof value.value === "string" && HEX64.test(value.value); }
function blockers(value: unknown): value is InstallationReadinessBlockerV1[] { return Array.isArray(value) && value.every((item, index) => BLOCKER_ORDER.includes(item) && BLOCKER_ORDER.indexOf(item) > (index ? BLOCKER_ORDER.indexOf(value[index - 1]) : -1)); }
function linkage(value: unknown): value is InstallationReadinessReviewLinkageV1 {
    if (!object(value) || !exact(value, LINKAGE_KEYS)) return false;
    return LINKAGE_KEYS.every((key) => BOOLEAN_KEYS.has(key)
        ? value[key] === (key === "v032_agent_receipt_atomicity_relied_upon")
        : ID_KEYS.has(key) ? typeof value[key] === "string" && UUID4.test(value[key]) : fingerprint(value[key]));
}
function summary(value: unknown, index: number): value is InstallationReadinessEvidenceSummaryV1 {
    if (!object(value) || !exact(value, SUMMARY_KEYS) || value.release !== EVIDENCE_ORDER[index][0] || value.evidence_kind !== EVIDENCE_ORDER[index][1] || !["current", "missing", "expired", "terminal", "unavailable"].includes(String(value.evidence_state)) || value.evidence_only !== true || value.execution_authorized !== false || value.installation_allowed !== false || (value.valid_until !== null && !utc(value.valid_until))) return false;
    const absent = value.evidence_id === null && value.evidence_fingerprint === null;
    const present = typeof value.evidence_id === "string" && UUID4.test(value.evidence_id) && fingerprint(value.evidence_fingerprint);
    return (absent || present) && (absent === ["missing", "unavailable"].includes(String(value.evidence_state)));
}
function review(value: unknown): value is InstallationReadinessReviewV1 {
    if (!object(value) || !exact(value, REVIEW_KEYS) || value.schema !== "installation-readiness-review-v1" || typeof value.review_id !== "string" || !UUID5.test(value.review_id) || typeof value.candidate_record_id !== "string" || !UUID4.test(value.candidate_record_id) || typeof value.operator_id !== "string" || !IDENTITY.test(value.operator_id) || !utc(value.observed_at) || (value.readiness !== "blocked" && value.readiness !== "readiness_gated") || !blockers(value.blockers) || !Array.isArray(value.evidence) || value.evidence.length !== EVIDENCE_ORDER.length || !value.evidence.every(summary) || (value.linkage !== null && !linkage(value.linkage)) || value.source !== "core_local_owner_scoped_evidence_v1" || value.evidence_only !== true || value.read_only !== true || !fingerprint(value.review_fingerprint)) return false;
    for (const key of ["execution_admission_granted", "execution_authorized", "installation_allowed", "dispatch_allowed", "worker_allowed", "workflow_allowed", "deployment_allowed", "mutation_allowed", "retry_allowed", "replay_allowed"]) if (value[key] !== false) return false;
    return value.readiness === "readiness_gated" ? value.blockers.length === 1 && value.blockers[0] === "execution_admission_not_defined" && value.linkage !== null : value.blockers.length > 0;
}
function audit(value: unknown): value is InstallationReadinessReviewAuditEvidenceV1 {
    return object(value) && exact(value, AUDIT_KEYS) && value.schema === "installation-readiness-review-audit-evidence-v1" && typeof value.review_id === "string" && UUID5.test(value.review_id) && fingerprint(value.review_fingerprint) && typeof value.candidate_record_id === "string" && UUID4.test(value.candidate_record_id) && (value.v033_receipt_fingerprint === null || fingerprint(value.v033_receipt_fingerprint)) && (value.linkage_fingerprint === null || fingerprint(value.linkage_fingerprint)) && ((value.v033_receipt_fingerprint === null) === (value.linkage_fingerprint === null)) && fingerprint(value.operator_fingerprint) && typeof value.correlation_id === "string" && IDENTITY.test(value.correlation_id) && utc(value.observed_at) && (value.outcome === "blocked" || value.outcome === "readiness_gated") && blockers(value.blocker_codes) && value.source_was_owner_scoped_local_readers === true && value.evidence_only === true && value.read_only === true && value.mutation_attempted === false && value.execution_attempted === false && fingerprint(value.evidence_fingerprint);
}

export function parseInstallationReadinessReview(value: unknown): InstallationReadinessReviewResponseV1 {
    if (!object(value) || !exact(value, RESPONSE_KEYS) || !review(value.review) || !audit(value.audit_evidence)) throw new Error("Invalid installation readiness review response.");
    const reviewValue = value.review; const auditValue = value.audit_evidence;
    if (auditValue.review_id !== reviewValue.review_id || auditValue.candidate_record_id !== reviewValue.candidate_record_id || auditValue.observed_at !== reviewValue.observed_at || auditValue.outcome !== reviewValue.readiness || JSON.stringify(auditValue.blocker_codes) !== JSON.stringify(reviewValue.blockers) || auditValue.review_fingerprint.value !== reviewValue.review_fingerprint.value) throw new Error("Invalid installation readiness review response.");
    if (new TextEncoder().encode(JSON.stringify(value)).length > 128 * 1024) throw new Error("Invalid installation readiness review response.");
    return value as unknown as InstallationReadinessReviewResponseV1;
}

export async function getInstallationReadinessReview(candidateRecordId: string) {
    const response = await atlas.get<unknown>(`/installation/candidate-records/${encodeURIComponent(candidateRecordId)}/readiness-review`, { withCredentials: true });
    return parseInstallationReadinessReview(response.data);
}
