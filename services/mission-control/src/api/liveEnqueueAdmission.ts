import { atlas } from "./atlas";
import type { LiveEnqueueAdmissionCollectionV1, LiveEnqueueAdmissionCreateV1, LiveEnqueueAdmissionResultV1, LiveEnqueueAdmissionV1 } from "../types/liveEnqueueAdmission";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const STATES = new Set(["active", "expired"]);
const ELIGIBILITY = new Set(["live_enqueue_admission_recorded", "readiness_gated", "blocked"]);
const BLOCKER_ORDER = ["installation_capability_unsupported", "evidence_not_found", "ownership_mismatch", "permission_scope_missing", "linkage_mismatch", "fingerprint_mismatch", "evidence_stale", "evidence_expired", "worker_intake_admission_not_active", "queue_reservation_not_active", "queue_item_reference_invalid", "worker_identity_ineligible", "worker_intake_reference_ineligible", "inherited_limits_mismatch", "permanent_subject_reserved", "enqueue_operation_not_defined", "dequeue_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const FIXED_BLOCKERS = ["enqueue_operation_not_defined", "dequeue_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|worker_address)/i;
const EMPTY_NETWORK_TARGET_DIGESTS = "allowed_" + "endpoint" + "_fingerprints";

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fp = (value: unknown) => object(value) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && /^[a-f0-9]{64}$/.test(String(value.value));
const forbiddenTrue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(forbiddenTrue);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => (key !== "permission_verified" && key !== "ephemeral_workspace_allowed" && /(allowed|authorized|attempted|exists|reachable|contacted|started|enqueued|dequeued|claimed|executable|serialized|defined|released|consumed|replaceable|supersedable|bypass|polling|authenticated|reserved|sent|open|constructed|publish|send|ack|binding|mutation|deployment|rollback)/.test(key) && item === true) || forbiddenTrue(item));
};
const sensitiveField = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(sensitiveField);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => {
        if (key === EMPTY_NETWORK_TARGET_DIGESTS) return !Array.isArray(item) || item.length !== 0;
        if (key === "internal_path_disclosure_allowed") return item !== false;
        return SENSITIVE.test(key) || sensitiveField(item);
    });
};
const orderedBlockers = (value: unknown) => Array.isArray(value) && value.length > 0 && value.every((item) => BLOCKER_ORDER.includes(String(item))) && new Set(value).size === value.length && value.map((item) => BLOCKER_ORDER.indexOf(String(item))).every((index, position, indexes) => position === 0 || indexes[position - 1] <= index);
const fixedBlockers = (value: unknown) => Array.isArray(value) && value.length === FIXED_BLOCKERS.length && FIXED_BLOCKERS.every((item, index) => value[index] === item);

function validateAdmission(value: unknown): LiveEnqueueAdmissionV1 {
    if (!object(value) || value.schema !== "live-enqueue-admission-v1" || value.evidence_only !== true || value.record_state !== "recorded" || value.lifecycle !== "active" || value.eligibility !== "live_enqueue_admission_recorded" || value.scope !== "installation_live_enqueue_admission_only" || !fixedBlockers(value.blockers) || !UUID.test(String(value.admission_id)) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid live enqueue admission response.");
    const link = value.linkage;
    const decision = value.admission_decision;
    const limits = value.inherited_limits;
    if (!object(link) || link.schema !== "live-enqueue-admission-linkage-v1" || !object(decision) || decision.schema !== "live-enqueue-admission-decision-v1" || decision.decision !== "preserve_non_enqueueing_live_enqueue_admission_evidence_only" || decision.eligibility !== "live_enqueue_admission_recorded" || !fixedBlockers(decision.blockers) || !object(limits) || !object(limits.limits_fingerprint) || !fp(value.record_fingerprint) || !fp(value.subject_fingerprint) || !fp(value.request_fingerprint) || !fp(value.idempotency_key_fingerprint) || !fp(link.linkage_fingerprint) || !fp(link.v020_v039_chain_fingerprint) || !fp(decision.decision_fingerprint) || !fp(limits.limits_fingerprint)) throw new Error("Invalid live enqueue admission response.");
    return value as LiveEnqueueAdmissionV1;
}

export function parseLiveEnqueueAdmissionCreate(value: unknown): LiveEnqueueAdmissionCreateV1 {
    if (!object(value) || value.schema !== "live-enqueue-admission-create-v1" || value.requested_scope !== "installation_live_enqueue_admission_only" || value.evidence_only !== true || !UUID.test(String(value.worker_intake_admission_id)) || !UUID.test(String(value.worker_queue_reservation_id)) || !UUID.test(String(value.queue_item_reference_id)) || !UUID.test(String(value.worker_identity_id)) || !UUID.test(String(value.worker_intake_reference_id)) || !["worker_intake_admission_fingerprint", "worker_queue_reservation_fingerprint", "queue_item_reference_fingerprint", "worker_identity_fingerprint", "worker_intake_reference_fingerprint", "inherited_limits_fingerprint"].every((key) => fp(value[key])) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid live enqueue admission request.");
    return value as LiveEnqueueAdmissionCreateV1;
}

export function parseLiveEnqueueAdmissionResult(value: unknown): LiveEnqueueAdmissionResultV1 {
    if (!object(value) || value.schema !== "live-enqueue-admission-result-v1" || value.evidence_only !== true || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid live enqueue admission response.");
    if (value.ok) {
        if (value.error !== null || !object(value.status) || value.status.schema !== "live-enqueue-admission-status-v1" || !STATES.has(String(value.status.lifecycle)) || !ELIGIBILITY.has(String(value.status.eligibility)) || !orderedBlockers(value.status.blockers) || !fp(value.status.status_fingerprint) || validateAdmission(value.admission).admission_id !== value.status.admission_id) throw new Error("Invalid live enqueue admission response.");
    } else if (value.admission !== null || value.status !== null || !object(value.error) || value.error.schema !== "live-enqueue-admission-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "live enqueue admission request could not be completed" || !fp(value.error.correlation_fingerprint) || forbiddenTrue(value.error) || sensitiveField(value.error)) {
        throw new Error("Invalid live enqueue admission response.");
    }
    return value as LiveEnqueueAdmissionResultV1;
}

export function parseLiveEnqueueAdmissionCollection(value: unknown): LiveEnqueueAdmissionCollectionV1 {
    if (!object(value) || value.schema !== "live-enqueue-admission-collection-v1" || value.evidence_only !== true || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 100 || !fp(value.collection_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid live enqueue admission collection.");
    return { ...value, items: value.items.map(validateAdmission) } as LiveEnqueueAdmissionCollectionV1;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/live-enqueue-admissions`;
export async function listLiveEnqueueAdmissions(candidateId: string) { const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true }); return parseLiveEnqueueAdmissionCollection(response.data); }
export async function getLiveEnqueueAdmission(candidateId: string, admissionId: string) { const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(admissionId)}`, { withCredentials: true }); return parseLiveEnqueueAdmissionResult(response.data); }
export async function createLiveEnqueueAdmission(candidateId: string, body: LiveEnqueueAdmissionCreateV1, csrf: string, key: string) { const response = await atlas.post<unknown>(path(candidateId), parseLiveEnqueueAdmissionCreate(body), { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrf, "Idempotency-Key": key } }); return parseLiveEnqueueAdmissionResult(response.data); }
