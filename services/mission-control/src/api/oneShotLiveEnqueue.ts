import { atlas } from "./atlas";
import type { OneShotLiveEnqueueCollectionV1, OneShotLiveEnqueueResultV1, OneShotLiveEnqueueV1 } from "../types/oneShotLiveEnqueue";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const OUTCOMES = new Set(["one_shot_live_enqueue_recorded", "readiness_gated", "blocked", "indeterminate"]);
const BLOCKER_ORDER = ["installation_capability_unsupported", "evidence_not_found", "ownership_mismatch", "permission_scope_missing", "linkage_mismatch", "fingerprint_mismatch", "evidence_stale", "evidence_expired", "live_enqueue_admission_not_active", "live_enqueue_admission_not_recorded", "queue_reservation_not_active", "worker_intake_admission_not_active", "worker_identity_ineligible", "worker_intake_reference_ineligible", "queue_intake_reference_ineligible", "queue_item_reference_ineligible", "inherited_limits_mismatch", "reservation_before_effect_failed", "permanent_subject_reserved", "idempotency_conflict", "append_indeterminate", "dequeue_not_defined", "queue_polling_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const FIXED_BLOCKERS = ["dequeue_not_defined", "queue_polling_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|broker|worker_address)/i;
const ALLOWED_TRUE_FIELDS = new Set(["evidence_only", "reference_only", "one_shot_live_enqueue_recorded", "binding_planned", "enabled", "ephemeral_workspace_allowed", "root_filesystem_read_only"]);

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fp = (value: unknown) => object(value) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && /^[a-f0-9]{64}$/.test(String(value.value));
const orderedBlockers = (value: unknown) => Array.isArray(value) && value.length > 0 && value.every((item) => BLOCKER_ORDER.includes(String(item))) && new Set(value).size === value.length && value.map((item) => BLOCKER_ORDER.indexOf(String(item))).every((index, position, indexes) => position === 0 || indexes[position - 1] <= index);
const fixedBlockers = (value: unknown) => Array.isArray(value) && value.length === FIXED_BLOCKERS.length && FIXED_BLOCKERS.every((item, index) => value[index] === item);
const forbiddenTrue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(forbiddenTrue);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => ((!ALLOWED_TRUE_FIELDS.has(key) && /(allowed|authorized|attempted|exists|reachable|contacted|started|dequeued|claimed|leased|executable|serialized|defined|released|consumed|replaceable|supersedable|bypass|polling|authenticated|sent|open|constructed|publish|send|ack|binding|mutation|deployment|rollback)/.test(key) && item === true) || forbiddenTrue(item)));
};
const sensitiveField = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(sensitiveField);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => (SENSITIVE.test(key) && item !== false && item !== null && item !== undefined && !(Array.isArray(item) && item.length === 0)) || sensitiveField(item));
};

function validateRecord(value: unknown): OneShotLiveEnqueueV1 {
    if (!object(value) || value.schema !== "one-shot-live-enqueue-v1" || value.reference_only !== true || value.one_shot_live_enqueue_recorded !== true || value.record_state !== "recorded" || value.lifecycle !== "active" || value.outcome !== "one_shot_live_enqueue_recorded" || !UUID.test(String(value.enqueue_id)) || !fixedBlockers(value.blockers) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot live enqueue response.");
    const item = value.queue_item;
    const lineage = value.lineage;
    const limits = value.inherited_limits;
    if (!object(item) || item.schema !== "one-shot-live-enqueue-item-v1" || item.item_kind !== "inert_reference_only_queue_item" || item.scope !== "installation_one_shot_live_enqueue_only" || item.reference_only !== true || item.item_state !== "recorded" || item.queue_item_id !== value.enqueue_id || !object(lineage) || lineage.schema !== "one-shot-live-enqueue-lineage-v1" || lineage.live_enqueue_admission_id !== item.live_enqueue_admission_id || lineage.one_shot_queue_item_id !== value.enqueue_id || !object(limits) || !object(limits.limits_fingerprint) || !fp(value.record_fingerprint) || !fp(value.request_fingerprint) || !fp(value.idempotency_key_fingerprint) || !fp(value.item_subject_fingerprint) || !fp(item.item_fingerprint) || !fp(lineage.v020_v041_chain_fingerprint) || !fp(lineage.lineage_fingerprint) || !fp(limits.limits_fingerprint)) throw new Error("Invalid one-shot live enqueue response.");
    return value as OneShotLiveEnqueueV1;
}

export function parseOneShotLiveEnqueueResult(value: unknown): OneShotLiveEnqueueResultV1 {
    if (!object(value) || value.schema !== "one-shot-live-enqueue-result-v1" || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot live enqueue response.");
    if (value.ok) {
        if (value.outcome !== "success" || value.error !== null || !object(value.status) || value.status.schema !== "one-shot-live-enqueue-status-v1" || !OUTCOMES.has(String(value.status.outcome)) || !orderedBlockers(value.status.blockers) || !fp(value.status.status_fingerprint) || validateRecord(value.record).enqueue_id !== value.status.enqueue_id) throw new Error("Invalid one-shot live enqueue response.");
    } else if (!["failure", "indeterminate"].includes(String(value.outcome)) || value.record !== null || value.status !== null || !object(value.error) || value.error.schema !== "one-shot-live-enqueue-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "one-shot live enqueue request could not be completed" || !fp(value.error.correlation_fingerprint) || forbiddenTrue(value.error) || sensitiveField(value.error)) {
        throw new Error("Invalid one-shot live enqueue response.");
    }
    return value as OneShotLiveEnqueueResultV1;
}

export function parseOneShotLiveEnqueueCollection(value: unknown): OneShotLiveEnqueueCollectionV1 {
    if (!object(value) || value.schema !== "one-shot-live-enqueue-collection-v1" || value.reference_only !== true || value.one_shot_live_enqueue_recorded !== false || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 100 || !fp(value.collection_fingerprint)) throw new Error("Invalid one-shot live enqueue collection.");
    if (forbiddenTrue(value)) throw new Error("Invalid one-shot live enqueue collection authority.");
    if (sensitiveField(value)) throw new Error("Invalid one-shot live enqueue collection sensitive field.");
    return { ...value, items: value.items.map(validateRecord) } as OneShotLiveEnqueueCollectionV1;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/one-shot-live-enqueues`;
export async function listOneShotLiveEnqueues(candidateId: string) {
    const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true });
    return parseOneShotLiveEnqueueCollection(response.data);
}
export async function getOneShotLiveEnqueue(candidateId: string, enqueueId: string) {
    const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(enqueueId)}`, { withCredentials: true });
    return parseOneShotLiveEnqueueResult(response.data);
}
