import { atlas } from "./atlas";
import type { QueueObservationReceiptCollectionV1, QueueObservationReceiptCreateV1, QueueObservationReceiptResultV1, QueueObservationReceiptV1 } from "../types/queueObservation";
import type { OneShotLiveEnqueueStatusV1, OneShotLiveEnqueueV1 } from "../types/oneShotLiveEnqueue";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SUCCESS_BLOCKERS = ["dequeue_not_defined", "queue_polling_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|broker|worker_address|hostname|socket|port)/i;
const ALLOWED_TRUE = new Set(["observation_only", "reference_only", "queue_observation_recorded", "evidence_only", "one_shot_live_enqueue_recorded", "binding_planned", "enabled", "ephemeral_workspace_allowed", "root_filesystem_read_only"]);
const ALLOWED_FALSE_SENSITIVE = new Set(["raw_receipt_persisted", "raw_queue_identity_persisted"]);

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fp = (value: unknown) => object(value) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && /^[a-f0-9]{64}$/.test(String(value.value));
const utc = (value: unknown) => typeof value === "string" && UTC_SECOND.test(value) && new Date(value).toISOString() === value.replace("Z", ".000Z");
const successBlockers = (value: unknown) => Array.isArray(value) && value.length === SUCCESS_BLOCKERS.length && SUCCESS_BLOCKERS.every((item, index) => value[index] === item);
const forbiddenTrue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(forbiddenTrue);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => ((!ALLOWED_TRUE.has(key) && /(allowed|authorized|attempted|present|exists|reachable|contacted|started|dequeued|claimed|leased|executable|serialized|defined|released|consumed|replaceable|supersedable|bypass|polling|authenticated|sent|open|constructed|publish|send|ack|binding|mutation|deployment|rollback)/.test(key) && item === true) || forbiddenTrue(item)));
};
const sensitiveField = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(sensitiveField);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => {
        if (ALLOWED_FALSE_SENSITIVE.has(key) || key === "internal_path_disclosure_allowed") return item !== false;
        if (key === "allowed_endpoint_fingerprints") return !Array.isArray(item) || item.length !== 0;
        return (SENSITIVE.test(key) && item !== false && item !== null && item !== undefined && !(Array.isArray(item) && item.length === 0)) || sensitiveField(item);
    });
};
const authority = (value: Record<string, unknown>, recorded: boolean) => value.observation_only === true && value.reference_only === true && value.payload_schema_defined === false && value.payload_constructed === false && value.payload_serialized === false && value.payload_bytes === 0 && value.executable_payload_allowed === false && value.live_enqueue_allowed === false && value.dequeue_defined === false && value.dequeue_allowed === false && value.queue_polling_allowed === false && value.queue_claim_allowed === false && value.queue_lease_allowed === false && value.queue_ack_allowed === false && value.worker_contact_allowed === false && value.worker_start_allowed === false && value.execution_start_allowed === false && value.dispatch_allowed === false && value.retry_allowed === false && value.resend_allowed === false && value.agent_invocation_allowed === false && value.workflow_start_allowed === false && value.docker_execution_allowed === false && value.podman_execution_allowed === false && value.container_execution_allowed === false && value.shell_execution_allowed === false && value.process_execution_allowed === false && value.provider_mutation_allowed === false && value.repository_mutation_allowed === false && value.in_guest_mutation_allowed === false && value.installation_allowed === false && value.deployment_allowed === false && value.rollback_allowed === false && value.replay_bypass_allowed === false && (!("queue_observation_recorded" in value) || value.queue_observation_recorded === recorded);

function receiptEvidence(value: unknown): boolean {
    return object(value) && value.schema === "enqueue-receipt-evidence-v1" && UUID5.test(String(value.enqueue_id)) && UUID5.test(String(value.inert_queue_item_id)) && value.enqueue_id === value.inert_queue_item_id && UUID.test(String(value.candidate_record_id)) && value.receipt_state === "receipt_recorded_for_contract_eligible_enqueue" && value.receipt_disposition === "contract_eligible" && utc(value.recorded_at) && utc(value.valid_until) && fp(value.enqueue_record_fingerprint) && fp(value.enqueue_status_fingerprint) && fp(value.inert_queue_item_fingerprint) && fp(value.queue_intake_reference_fingerprint) && fp(value.queue_item_reference_fingerprint) && fp(value.receipt_fingerprint) && value.payload_present === false && value.executable === false && value.effect_attempted === false;
}

function observation(value: unknown): boolean {
    return object(value) && authority(value, false) && value.schema === "queue-observation-v1" && UUID5.test(String(value.observation_id)) && UUID5.test(String(value.enqueue_id)) && value.queue_identity === "abstract_installation_queue" && value.item_identity === "inert_reference_only_queue_item" && value.observation_state === "observed_recorded_not_consumable" && value.lifecycle === "active" && value.disposition === "observation_recorded" && successBlockers(value.blockers) && receiptEvidence(value.receipt_evidence) && utc(value.observed_at) && utc(value.valid_until) && fp(value.observation_fingerprint);
}

function record(value: unknown): QueueObservationReceiptV1 {
    if (!object(value) || !authority(value, false) || value.schema !== "queue-observation-receipt-v1" || !UUID5.test(String(value.receipt_id)) || !UUID.test(String(value.candidate_record_id)) || !utc(value.recorded_at) || !utc(value.valid_until) || value.lifecycle !== "active" || value.disposition !== "observation_recorded" || !successBlockers(value.blockers) || !object(value.v042_enqueue) || !object(value.v042_enqueue_status) || !receiptEvidence(value.receipt_evidence) || !observation(value.queue_observation) || !fp(value.lineage_fingerprint) || !fp(value.subject_fingerprint) || !fp(value.receipt_record_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid queue observation response.");
    const enqueue = value.v042_enqueue;
    const enqueueStatus = value.v042_enqueue_status;
    const receipt = value.receipt_evidence;
    const observed = value.queue_observation;
    const queueItem = object(enqueue.queue_item) ? enqueue.queue_item : null;
    const enqueueRecord = object(enqueue.record_fingerprint) ? enqueue.record_fingerprint : null;
    const statusFingerprint = object(enqueueStatus.status_fingerprint) ? enqueueStatus.status_fingerprint : null;
    const receiptRecord = object(receipt) && object(receipt.enqueue_record_fingerprint) ? receipt.enqueue_record_fingerprint : null;
    const receiptStatus = object(receipt) && object(receipt.enqueue_status_fingerprint) ? receipt.enqueue_status_fingerprint : null;
    const receiptItem = object(receipt) && object(receipt.inert_queue_item_fingerprint) ? receipt.inert_queue_item_fingerprint : null;
    const itemFingerprint = queueItem && object(queueItem.item_fingerprint) ? queueItem.item_fingerprint : null;
    if (!object(receipt) || !object(observed) || !queueItem || !enqueueRecord || !statusFingerprint || !receiptRecord || !receiptStatus || !receiptItem || !itemFingerprint || value.receipt_id !== observed.observation_id || value.operator_id !== enqueue.operator_id || value.operator_id !== receipt.operator_id || value.operator_id !== observed.operator_id || value.candidate_record_id !== enqueue.candidate_record_id || value.candidate_record_id !== enqueueStatus.candidate_record_id || value.candidate_record_id !== receipt.candidate_record_id || value.candidate_record_id !== observed.candidate_record_id || enqueue.enqueue_id !== enqueueStatus.enqueue_id || enqueue.enqueue_id !== receipt.enqueue_id || enqueue.enqueue_id !== observed.enqueue_id || enqueueRecord.value !== receiptRecord.value || statusFingerprint.value !== receiptStatus.value || itemFingerprint.value !== receiptItem.value) throw new Error("Invalid queue observation response.");
    return value as QueueObservationReceiptV1;
}

export function parseQueueObservationResult(value: unknown): QueueObservationReceiptResultV1 {
    if (!object(value) || value.schema !== "queue-observation-receipt-result-v1" || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid queue observation response.");
    if (value.ok) {
        if (value.outcome !== "success" || value.error !== null || value.queue_observation_recorded !== true || !object(value.status) || !authority(value.status, true) || value.status.schema !== "queue-observation-receipt-status-v1" || !UUID5.test(String(value.status.receipt_id)) || !["active", "expired"].includes(String(value.status.lifecycle)) || value.status.disposition !== "observation_recorded" || !successBlockers(value.status.blockers) || !utc(value.status.evaluated_at) || !utc(value.status.valid_until) || !fp(value.status.receipt_record_fingerprint) || !fp(value.status.status_fingerprint) || record(value.record).receipt_id !== value.status.receipt_id) throw new Error("Invalid queue observation response.");
    } else if (!["failure", "indeterminate"].includes(String(value.outcome)) || value.record !== null || value.status !== null || value.queue_observation_recorded !== false || !object(value.error) || !authority(value.error, false) || value.error.schema !== "queue-observation-receipt-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "queue observation receipt request could not be completed" || !fp(value.error.correlation_fingerprint)) {
        throw new Error("Invalid queue observation response.");
    }
    return value as QueueObservationReceiptResultV1;
}

export function parseQueueObservationCollection(value: unknown): QueueObservationReceiptCollectionV1 {
    if (!object(value) || !authority(value, false) || value.schema !== "queue-observation-receipt-collection-v1" || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 16 || !fp(value.collection_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid queue observation collection.");
    return { ...value, items: value.items.map(record) } as QueueObservationReceiptCollectionV1;
}

export function queueObservationCreateFromOneShot(item: OneShotLiveEnqueueV1, status: OneShotLiveEnqueueStatusV1): QueueObservationReceiptCreateV1 {
    return {
        schema: "queue-observation-receipt-create-v1",
        enqueue_id: item.enqueue_id,
        enqueue_record_fingerprint: item.record_fingerprint,
        enqueue_status_fingerprint: status.status_fingerprint,
        enqueue_valid_until: item.valid_until,
        queue_intake_reference_id: item.queue_item.queue_intake_reference_id,
        queue_intake_reference_fingerprint: item.queue_item.queue_intake_reference_fingerprint,
        queue_item_reference_id: item.queue_item.queue_item_reference_id,
        queue_item_reference_fingerprint: item.queue_item.queue_item_reference_fingerprint,
        inert_queue_item_id: item.queue_item.queue_item_id,
        inert_queue_item_fingerprint: item.queue_item.item_fingerprint,
        observed_queue_identity: "abstract_installation_queue",
        observed_item_identity: "inert_reference_only_queue_item",
        observation_state: "observed_recorded_not_consumable",
        receipt_disposition: "contract_eligible",
        requested_scope: "installation_queue_observation_receipt_only",
        observation_only: true,
        reference_only: true,
        payload_schema_defined: false,
        payload_constructed: false,
        payload_serialized: false,
        executable_payload_allowed: false,
        dequeue_allowed: false,
        queue_polling_allowed: false,
        worker_start_allowed: false,
        execution_authorized: false,
        replay_allowed: false,
    };
}

export function queueObservationIdempotencyKey() {
    return `queue-observation-${crypto.randomUUID()}`;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/queue-observations`;
export async function listQueueObservations(candidateId: string) {
    const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true });
    return parseQueueObservationCollection(response.data);
}
export async function getQueueObservation(candidateId: string, observationId: string) {
    const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(observationId)}`, { withCredentials: true });
    return parseQueueObservationResult(response.data);
}
export async function createQueueObservation(candidateId: string, body: QueueObservationReceiptCreateV1, csrf: string, key: string) {
    const response = await atlas.post<unknown>(path(candidateId), body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrf, "Idempotency-Key": key } });
    return parseQueueObservationResult(response.data);
}
