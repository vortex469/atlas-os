import { atlas } from "./atlas";
import { parseQueueObservationResult } from "./queueObservation";
import type { ControlledDequeueAdmissionCollectionV1, ControlledDequeueAdmissionCreateV1, ControlledDequeueAdmissionResultV1, ControlledDequeueAdmissionV1 } from "../types/controlledDequeueAdmission";
import type { QueueObservationReceiptStatusV1, QueueObservationReceiptV1 } from "../types/queueObservation";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SUCCESS_BLOCKERS = ["dequeue_not_defined", "queue_polling_not_defined", "queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const BLOCKER_ORDER = ["installation_capability_unsupported", "evidence_not_found", "ownership_mismatch", "permission_scope_missing", "v043_observation_not_active", "v043_observation_not_recorded", "v043_receipt_not_contract_eligible", "v042_enqueue_not_active", "v042_enqueue_not_recorded", "linkage_mismatch", "queue_identity_mismatch", "item_identity_mismatch", "observation_receipt_mismatch", "fingerprint_mismatch", "inherited_limits_mismatch", "evidence_stale", "evidence_expired", "ambiguous_state", "executable_payload", "unsupported_authority", "reservation_before_effect_failed", "permanent_subject_reserved", "idempotency_conflict", "append_indeterminate", ...SUCCESS_BLOCKERS];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|broker|worker_address|hostname|socket|port|consumer|lease_token|ack_token)/i;
const ALLOWED_TRUE = new Set(["evidence_only", "reference_only", "observation_only", "controlled_dequeue_admission_recorded", "queue_observation_recorded", "one_shot_live_enqueue_recorded", "binding_planned", "enabled", "ephemeral_workspace_allowed", "root_filesystem_read_only"]);

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fp = (value: unknown) => object(value) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && /^[a-f0-9]{64}$/.test(String(value.value));
const utc = (value: unknown) => typeof value === "string" && UTC_SECOND.test(value) && new Date(value).toISOString() === value.replace("Z", ".000Z");
const successBlockers = (value: unknown) => Array.isArray(value) && value.length === SUCCESS_BLOCKERS.length && SUCCESS_BLOCKERS.every((item, index) => value[index] === item);
const orderedBlockers = (value: unknown) => Array.isArray(value) && value.length > 0 && value.every((item) => BLOCKER_ORDER.includes(String(item))) && new Set(value).size === value.length && value.map((item) => BLOCKER_ORDER.indexOf(String(item))).every((index, position, indexes) => position === 0 || indexes[position - 1] <= index);
const forbiddenTrue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(forbiddenTrue);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => ((!ALLOWED_TRUE.has(key) && /(allowed|authorized|attempted|present|exists|reachable|contacted|started|dequeued|claimed|leased|executable|serialized|defined|released|consumed|replaceable|supersedable|bypass|polling|authenticated|sent|open|constructed|publish|send|ack|binding|mutation|deployment|rollback)/.test(key) && item === true) || forbiddenTrue(item)));
};
const sensitiveField = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(sensitiveField);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => (SENSITIVE.test(key) && item !== false && item !== null && item !== undefined && !(Array.isArray(item) && item.length === 0)) || sensitiveField(item));
};
const authority = (value: Record<string, unknown>, recorded?: boolean) => value.evidence_only === true && value.reference_only === true && value.payload_schema_defined === false && value.payload_constructed === false && value.payload_serialized === false && value.payload_bytes === 0 && value.executable_payload_allowed === false && value.dequeue_defined === false && value.dequeue_allowed === false && value.dequeue_attempted === false && value.dequeued === false && value.queue_polling_allowed === false && value.queue_polled === false && value.queue_claim_allowed === false && value.queue_claimed === false && value.queue_lease_allowed === false && value.queue_leased === false && value.queue_ack_allowed === false && value.queue_acked === false && value.queue_consumed === false && value.worker_contact_allowed === false && value.worker_contacted === false && value.worker_start_allowed === false && value.worker_started === false && value.agent_invocation_allowed === false && value.execution_start_allowed === false && value.process_execution_allowed === false && value.dispatch_allowed === false && value.retry_allowed === false && value.resend_allowed === false && value.scheduler_allowed === false && value.workflow_start_allowed === false && value.docker_execution_allowed === false && value.podman_execution_allowed === false && value.container_execution_allowed === false && value.shell_execution_allowed === false && value.provider_mutation_allowed === false && value.repository_mutation_allowed === false && value.in_guest_mutation_allowed === false && value.installation_allowed === false && value.deployment_allowed === false && value.rollback_allowed === false && value.replay_bypass_allowed === false && (recorded === undefined || value.controlled_dequeue_admission_recorded === recorded);

function validateRecord(value: unknown): ControlledDequeueAdmissionV1 {
    if (!object(value) || !authority(value, true) || value.schema !== "controlled-dequeue-admission-v1" || !UUID5.test(String(value.admission_id)) || !UUID.test(String(value.candidate_record_id)) || !utc(value.recorded_at) || !utc(value.valid_until) || value.lifecycle !== "active" || value.admission_state !== "readiness_gated" || value.disposition !== "controlled_dequeue_admission_recorded" || value.eligibility !== "eligible_for_later_dequeue_consideration" || !successBlockers(value.blockers) || !object(value.queue_observation_receipt) || !object(value.queue_observation_receipt_status) || !object(value.inherited_limits) || !fp(value.inherited_limits.limits_fingerprint) || !object(value.admission_decision) || !successBlockers(value.admission_decision.blockers) || value.admission_decision.schema !== "controlled-dequeue-admission-decision-v1" || value.admission_decision.decision !== "eligible_for_later_dequeue_consideration" || value.admission_decision.admission_state !== "readiness_gated" || !fp(value.queue_identity_fingerprint) || !fp(value.item_identity_fingerprint) || !fp(value.lineage_fingerprint) || !fp(value.subject_fingerprint) || !fp(value.admission_record_fingerprint) || !fp(value.admission_decision.queue_identity_fingerprint) || !fp(value.admission_decision.item_identity_fingerprint) || !fp(value.admission_decision.lineage_fingerprint) || !fp(value.admission_decision.inherited_limits_fingerprint) || !fp(value.admission_decision.decision_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid controlled dequeue admission response.");
    const receiptResult = parseQueueObservationResult({
        ...value.queue_observation_receipt,
        schema: "queue-observation-receipt-result-v1",
        ok: true,
        outcome: "success",
        record: value.queue_observation_receipt,
        status: value.queue_observation_receipt_status,
        error: null,
        correlation_fingerprint: value.lineage_fingerprint,
        queue_observation_recorded: true,
    });
    const receipt = receiptResult.record;
    const status = receiptResult.status;
    const record = value as ControlledDequeueAdmissionV1;
    const decision = record.admission_decision;
    if (!receipt || !status || record.operator_id !== receipt.operator_id || record.operator_id !== status.operator_id || record.candidate_record_id !== receipt.candidate_record_id || record.candidate_record_id !== status.candidate_record_id || status.receipt_id !== receipt.receipt_id || record.valid_until > receipt.valid_until || record.queue_identity_fingerprint.value !== decision.queue_identity_fingerprint.value || record.item_identity_fingerprint.value !== decision.item_identity_fingerprint.value || record.lineage_fingerprint.value !== decision.lineage_fingerprint.value || decision.inherited_limits_fingerprint.value !== record.inherited_limits.limits_fingerprint.value) throw new Error("Invalid controlled dequeue admission response.");
    return record;
}

export function parseControlledDequeueAdmissionResult(value: unknown): ControlledDequeueAdmissionResultV1 {
    if (!object(value) || !authority(value) || value.schema !== "controlled-dequeue-admission-result-v1" || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid controlled dequeue admission response.");
    if (value.ok) {
        if (value.outcome !== "success" || value.error !== null || value.controlled_dequeue_admission_recorded !== true || !object(value.status) || !authority(value.status, true) || value.status.schema !== "controlled-dequeue-admission-status-v1" || !["active", "expired"].includes(String(value.status.lifecycle)) || !["controlled_dequeue_admission_recorded", "readiness_gated"].includes(String(value.status.admission_state)) || value.status.eligibility !== "eligible_for_later_dequeue_consideration" || !successBlockers(value.status.blockers) || !utc(value.status.evaluated_at) || !utc(value.status.valid_until) || !fp(value.status.admission_record_fingerprint) || !fp(value.status.status_fingerprint) || validateRecord(value.record).admission_id !== value.status.admission_id) throw new Error("Invalid controlled dequeue admission response.");
    } else if (!["failure", "indeterminate"].includes(String(value.outcome)) || value.record !== null || value.status !== null || value.controlled_dequeue_admission_recorded !== false || !object(value.error) || !authority(value.error, false) || value.error.schema !== "controlled-dequeue-admission-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "controlled dequeue admission request could not be completed" || !fp(value.error.correlation_fingerprint) || !orderedBlockers([value.error.error_code])) {
        throw new Error("Invalid controlled dequeue admission response.");
    }
    return value as ControlledDequeueAdmissionResultV1;
}

export function parseControlledDequeueAdmissionCollection(value: unknown): ControlledDequeueAdmissionCollectionV1 {
    if (!object(value) || !authority(value, false) || value.schema !== "controlled-dequeue-admission-collection-v1" || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 16 || !fp(value.collection_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid controlled dequeue admission collection.");
    return { ...value, items: value.items.map(validateRecord) } as ControlledDequeueAdmissionCollectionV1;
}

export function controlledDequeueAdmissionCreateFromObservation(receipt: QueueObservationReceiptV1, status: QueueObservationReceiptStatusV1): ControlledDequeueAdmissionCreateV1 {
    return {
        schema: "controlled-dequeue-admission-create-v1",
        queue_observation_receipt_id: receipt.receipt_id,
        queue_observation_receipt_fingerprint: receipt.receipt_record_fingerprint,
        queue_observation_receipt_status_fingerprint: status.status_fingerprint,
        queue_observation_receipt_valid_until: receipt.valid_until,
        enqueue_id: receipt.v042_enqueue.enqueue_id,
        inert_queue_item_id: receipt.v042_enqueue.queue_item.queue_item_id,
        inert_queue_item_fingerprint: receipt.v042_enqueue.queue_item.item_fingerprint,
        queue_identity: "abstract_installation_queue",
        item_identity: "inert_reference_only_queue_item",
        inherited_limits_fingerprint: receipt.v042_enqueue.inherited_limits.limits_fingerprint,
        requested_scope: "installation_controlled_dequeue_admission_only",
        evidence_only: true,
        reference_only: true,
        payload_schema_defined: false,
        payload_constructed: false,
        payload_serialized: false,
        payload_bytes: 0,
        executable_payload_allowed: false,
        dequeue_defined: false,
        dequeue_allowed: false,
        dequeue_attempted: false,
        dequeued: false,
        queue_polling_allowed: false,
        queue_polled: false,
        queue_claim_allowed: false,
        queue_claimed: false,
        queue_lease_allowed: false,
        queue_leased: false,
        queue_ack_allowed: false,
        queue_acked: false,
        queue_consumed: false,
        worker_contact_allowed: false,
        worker_contacted: false,
        worker_start_allowed: false,
        worker_started: false,
        agent_invocation_allowed: false,
        execution_start_allowed: false,
        process_execution_allowed: false,
        dispatch_allowed: false,
        retry_allowed: false,
        resend_allowed: false,
        scheduler_allowed: false,
        workflow_start_allowed: false,
        docker_execution_allowed: false,
        podman_execution_allowed: false,
        container_execution_allowed: false,
        shell_execution_allowed: false,
        provider_mutation_allowed: false,
        repository_mutation_allowed: false,
        in_guest_mutation_allowed: false,
        installation_allowed: false,
        deployment_allowed: false,
        rollback_allowed: false,
        replay_bypass_allowed: false,
    };
}

export function controlledDequeueAdmissionIdempotencyKey() {
    return `controlled-dequeue-admission-${crypto.randomUUID()}`;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/controlled-dequeue-admissions`;
export async function listControlledDequeueAdmissions(candidateId: string) {
    const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true });
    return parseControlledDequeueAdmissionCollection(response.data);
}
export async function getControlledDequeueAdmission(candidateId: string, admissionId: string) {
    const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(admissionId)}`, { withCredentials: true });
    return parseControlledDequeueAdmissionResult(response.data);
}
export async function createControlledDequeueAdmission(candidateId: string, body: ControlledDequeueAdmissionCreateV1, csrf: string, key: string) {
    const response = await atlas.post<unknown>(path(candidateId), body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrf, "Idempotency-Key": key } });
    return parseControlledDequeueAdmissionResult(response.data);
}
