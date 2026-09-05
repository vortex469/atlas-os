import { atlas } from "./atlas";
import { parseControlledDequeueAdmissionResult } from "./controlledDequeueAdmission";
import type { ControlledDequeueAdmissionStatusV1, ControlledDequeueAdmissionV1 } from "../types/controlledDequeueAdmission";
import type { OneShotControlledDequeueCollectionV1, OneShotControlledDequeueCreateV1, OneShotControlledDequeueResultV1, OneShotControlledDequeueV1 } from "../types/oneShotControlledDequeue";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SUCCESS_BLOCKERS = ["queue_polling_not_defined", "queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const BLOCKER_ORDER = ["installation_capability_unsupported", "evidence_not_found", "ownership_mismatch", "permission_scope_missing", "v044_admission_not_active", "v044_admission_not_recorded", "v044_admission_not_eligible", "v043_observation_not_active", "v043_observation_not_recorded", "v043_receipt_not_contract_eligible", "v042_enqueue_not_active", "v042_enqueue_not_recorded", "linkage_mismatch", "queue_identity_mismatch", "item_identity_mismatch", "observation_receipt_mismatch", "fingerprint_mismatch", "inherited_limits_mismatch", "evidence_stale", "evidence_expired", "ambiguous_state", "executable_payload", "unsupported_authority", "dequeue_adapter_unavailable", "dequeue_receipt_mismatch", "reservation_before_effect_failed", "permanent_subject_reserved", "idempotency_conflict", "append_indeterminate", "dequeue_indeterminate", ...SUCCESS_BLOCKERS];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|broker|worker_address|hostname|socket|port|consumer|lease_token|ack_token)/i;
const ALLOWED_TRUE = new Set(["evidence_only", "reference_only", "exact_admitted_item_only", "adapter_receipt_redacted", "one_shot_controlled_dequeue_recorded", "controlled_dequeue_admission_recorded", "queue_observation_recorded", "one_shot_live_enqueue_recorded", "binding_planned", "enabled", "ephemeral_workspace_allowed", "root_filesystem_read_only"]);

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
const authority = (value: Record<string, unknown>, recorded?: boolean) => value.evidence_only === true && value.reference_only === true && value.payload_schema_defined === false && value.payload_constructed === false && value.payload_serialized === false && value.payload_bytes === 0 && value.executable_payload_allowed === false && value.dequeue_defined === false && value.dequeue_allowed === false && value.queue_polling_allowed === false && value.queue_polled === false && value.queue_claim_allowed === false && value.queue_claimed === false && value.queue_lease_allowed === false && value.queue_leased === false && value.queue_ack_allowed === false && value.queue_acked === false && value.queue_consumed === false && value.worker_contact_allowed === false && value.worker_contacted === false && value.worker_start_allowed === false && value.worker_started === false && value.agent_invocation_allowed === false && value.execution_start_allowed === false && value.process_execution_allowed === false && value.dispatch_allowed === false && value.retry_allowed === false && value.resend_allowed === false && value.scheduler_allowed === false && value.workflow_start_allowed === false && value.docker_execution_allowed === false && value.podman_execution_allowed === false && value.container_execution_allowed === false && value.shell_execution_allowed === false && value.provider_mutation_allowed === false && value.repository_mutation_allowed === false && value.in_guest_mutation_allowed === false && value.installation_allowed === false && value.deployment_allowed === false && value.rollback_allowed === false && value.replay_bypass_allowed === false && (recorded === undefined || value.one_shot_controlled_dequeue_recorded === recorded);

function dispositionFor(outcome: unknown) {
    if (outcome === "success") return "exact_inert_item_dequeued";
    if (outcome === "failure") return "exact_inert_item_not_dequeued";
    if (outcome === "indeterminate") return "dequeue_completion_indeterminate";
    return null;
}

function boundedReceipt(value: unknown, outcome: unknown, queueIdentity: unknown, itemIdentity: unknown): boolean {
    if (!object(value) || !object(queueIdentity) || !object(itemIdentity)) return false;
    const queueFingerprint = value.queue_identity_fingerprint;
    const itemFingerprint = value.item_identity_fingerprint;
    return authority(value) && value.schema === "bounded-one-shot-controlled-dequeue-receipt-v1" && value.outcome === outcome && value.disposition === dispositionFor(outcome) && value.exact_admitted_item_only === true && value.adapter_receipt_redacted === true && fp(value.adapter_receipt_fingerprint) && fp(queueFingerprint) && fp(itemFingerprint) && fp(value.receipt_fingerprint) && String((queueFingerprint as Record<string, unknown>).value) === String(queueIdentity.value) && String((itemFingerprint as Record<string, unknown>).value) === String(itemIdentity.value);
}

function validateRecord(value: unknown): OneShotControlledDequeueV1 {
    if (!object(value) || !authority(value, true) || value.schema !== "one-shot-controlled-dequeue-v1" || !UUID5.test(String(value.dequeue_id)) || !UUID.test(String(value.candidate_record_id)) || !utc(value.recorded_at) || !utc(value.valid_until) || value.lifecycle !== "active" || value.dequeue_state !== "one_shot_controlled_dequeue_recorded" || !["success", "failure", "indeterminate"].includes(String(value.outcome)) || value.disposition !== dispositionFor(value.outcome) || !successBlockers(value.blockers) || !object(value.controlled_dequeue_admission) || !object(value.controlled_dequeue_admission_status) || !object(value.inherited_limits) || !fp(value.inherited_limits.limits_fingerprint) || !fp(value.queue_identity_fingerprint) || !fp(value.item_identity_fingerprint) || !fp(value.lineage_fingerprint) || !fp(value.subject_fingerprint) || !fp(value.idempotency_key_fingerprint) || !fp(value.dequeue_record_fingerprint) || !boundedReceipt(value.bounded_receipt, value.outcome, value.queue_identity_fingerprint, value.item_identity_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot controlled dequeue response.");
    const admissionResult = parseControlledDequeueAdmissionResult({
        ...value.controlled_dequeue_admission,
        schema: "controlled-dequeue-admission-result-v1",
        ok: true,
        outcome: "success",
        record: value.controlled_dequeue_admission,
        status: value.controlled_dequeue_admission_status,
        error: null,
        correlation_fingerprint: value.lineage_fingerprint,
        controlled_dequeue_admission_recorded: true,
    });
    const admission = admissionResult.record;
    const status = admissionResult.status;
    const record = value as OneShotControlledDequeueV1;
    if (!admission || !status || record.operator_id !== admission.operator_id || record.operator_id !== status.operator_id || record.candidate_record_id !== admission.candidate_record_id || record.candidate_record_id !== status.candidate_record_id || status.admission_id !== admission.admission_id || record.valid_until > admission.valid_until || record.inherited_limits.limits_fingerprint.value !== admission.inherited_limits.limits_fingerprint.value || record.queue_identity_fingerprint.value !== admission.queue_identity_fingerprint.value || record.item_identity_fingerprint.value !== admission.item_identity_fingerprint.value) throw new Error("Invalid one-shot controlled dequeue response.");
    return record;
}

export function parseOneShotControlledDequeueResult(value: unknown): OneShotControlledDequeueResultV1 {
    if (!object(value) || !authority(value) || value.schema !== "one-shot-controlled-dequeue-result-v1" || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot controlled dequeue response.");
    if (value.record) {
        if (value.ok !== true || value.error !== null || value.one_shot_controlled_dequeue_recorded !== true || !object(value.status) || !authority(value.status, true) || value.status.schema !== "one-shot-controlled-dequeue-status-v1" || !["active", "expired"].includes(String(value.status.lifecycle)) || value.status.dequeue_state !== "one_shot_controlled_dequeue_recorded" || !["success", "failure", "indeterminate"].includes(String(value.status.outcome)) || value.status.disposition !== dispositionFor(value.status.outcome) || !successBlockers(value.status.blockers) || !utc(value.status.evaluated_at) || !utc(value.status.valid_until) || !fp(value.status.dequeue_record_fingerprint) || !fp(value.status.status_fingerprint) || validateRecord(value.record).dequeue_id !== value.status.dequeue_id || value.outcome !== value.status.outcome) throw new Error("Invalid one-shot controlled dequeue response.");
    } else if (value.ok !== false || !["failure", "indeterminate"].includes(String(value.outcome)) || value.status !== null || value.one_shot_controlled_dequeue_recorded !== false || !object(value.error) || !authority(value.error, false) || value.error.schema !== "one-shot-controlled-dequeue-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "one-shot controlled dequeue request could not be completed" || !fp(value.error.correlation_fingerprint) || !orderedBlockers([value.error.error_code])) {
        throw new Error("Invalid one-shot controlled dequeue response.");
    }
    return value as OneShotControlledDequeueResultV1;
}

export function parseOneShotControlledDequeueCollection(value: unknown): OneShotControlledDequeueCollectionV1 {
    if (!object(value) || !authority(value, false) || value.schema !== "one-shot-controlled-dequeue-collection-v1" || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 16 || !fp(value.collection_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot controlled dequeue collection.");
    return { ...value, items: value.items.map(validateRecord) } as OneShotControlledDequeueCollectionV1;
}

export function oneShotControlledDequeueCreateFromAdmission(admission: ControlledDequeueAdmissionV1, status: ControlledDequeueAdmissionStatusV1): OneShotControlledDequeueCreateV1 {
    const receipt = admission.queue_observation_receipt;
    const enqueue = receipt.v042_enqueue;
    return {
        schema: "one-shot-controlled-dequeue-create-v1",
        controlled_dequeue_admission_id: admission.admission_id,
        controlled_dequeue_admission_fingerprint: admission.admission_record_fingerprint,
        controlled_dequeue_admission_status_fingerprint: status.status_fingerprint,
        controlled_dequeue_admission_valid_until: admission.valid_until,
        queue_observation_receipt_id: receipt.receipt_id,
        queue_observation_receipt_fingerprint: receipt.receipt_record_fingerprint,
        queue_observation_receipt_status_fingerprint: admission.queue_observation_receipt_status.status_fingerprint,
        enqueue_id: enqueue.enqueue_id,
        inert_queue_item_id: enqueue.queue_item.queue_item_id,
        inert_queue_item_fingerprint: enqueue.queue_item.item_fingerprint,
        queue_identity_fingerprint: admission.queue_identity_fingerprint,
        item_identity_fingerprint: admission.item_identity_fingerprint,
        lineage_fingerprint: admission.lineage_fingerprint,
        inherited_limits_fingerprint: admission.inherited_limits.limits_fingerprint,
        queue_identity: "abstract_installation_queue",
        item_identity: "inert_reference_only_queue_item",
        requested_scope: "installation_one_shot_controlled_dequeue_only",
        evidence_only: true,
        reference_only: true,
        payload_schema_defined: false,
        payload_constructed: false,
        payload_serialized: false,
        payload_bytes: 0,
        executable_payload_allowed: false,
        dequeue_defined: false,
        dequeue_allowed: false,
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

export function oneShotControlledDequeueIdempotencyKey() {
    return `one-shot-controlled-dequeue-${crypto.randomUUID()}`;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/one-shot-controlled-dequeues`;
export async function listOneShotControlledDequeues(candidateId: string) {
    const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true });
    return parseOneShotControlledDequeueCollection(response.data);
}
export async function getOneShotControlledDequeue(candidateId: string, dequeueId: string) {
    const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(dequeueId)}`, { withCredentials: true });
    return parseOneShotControlledDequeueResult(response.data);
}
export async function createOneShotControlledDequeue(candidateId: string, body: OneShotControlledDequeueCreateV1, csrf: string, key: string) {
    const response = await atlas.post<unknown>(path(candidateId), body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrf, "Idempotency-Key": key } });
    return parseOneShotControlledDequeueResult(response.data);
}
