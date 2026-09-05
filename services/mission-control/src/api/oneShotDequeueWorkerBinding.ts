import { atlas } from "./atlas";
import { parseOneShotControlledDequeueResult } from "./oneShotControlledDequeue";
import { parseWorkerIntakeAdmissionResult } from "./workerIntakeAdmission";
import type { OneShotDequeueWorkerBindingCollectionV1, OneShotDequeueWorkerBindingResultV1, OneShotDequeueWorkerBindingV1 } from "../types/oneShotDequeueWorkerBinding";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SUCCESS_BLOCKERS = ["store_contact_not_defined", "runtime_contact_not_defined", "worker_start_not_defined", "execution_start_boundary_not_defined"];
const BLOCKER_ORDER = ["installation_capability_unsupported", "evidence_not_found", "ownership_mismatch", "permission_scope_missing", "v045_dequeue_not_active", "v045_dequeue_not_recorded", "v045_dequeue_not_successful", "v040_worker_intake_not_active", "v040_worker_intake_not_recorded", "linkage_mismatch", "worker_subject_mismatch", "queue_item_reference_mismatch", "fingerprint_mismatch", "inherited_limits_mismatch", "evidence_stale", "evidence_expired", "ambiguous_state", "caller_supplied_credential", "caller_supplied_endpoint", "caller_supplied_command", "unsupported_authority", ...SUCCESS_BLOCKERS, "reservation_before_effect_failed", "permanent_subject_reserved", "idempotency_conflict", "append_indeterminate"];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|broker|worker_address|hostname|socket|port|consumer|lease_token|ack_token)/i;
const ALLOWED_TRUE = new Set(["evidence_only", "reference_only", "one_shot_dequeue_worker_binding_recorded", "one_shot_controlled_dequeue_recorded", "controlled_dequeue_admission_recorded", "queue_observation_recorded", "one_shot_live_enqueue_recorded", "binding_planned", "enabled", "ephemeral_workspace_allowed", "root_filesystem_read_only"]);

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fp = (value: unknown) => object(value) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && /^[a-f0-9]{64}$/.test(String(value.value));
const utc = (value: unknown) => typeof value === "string" && UTC_SECOND.test(value) && new Date(value).toISOString() === value.replace("Z", ".000Z");
const successBlockers = (value: unknown) => Array.isArray(value) && value.length === SUCCESS_BLOCKERS.length && SUCCESS_BLOCKERS.every((item, index) => value[index] === item);
const orderedBlockers = (value: unknown) => Array.isArray(value) && value.length > 0 && value.every((item) => BLOCKER_ORDER.includes(String(item))) && new Set(value).size === value.length && value.map((item) => BLOCKER_ORDER.indexOf(String(item))).every((index, position, indexes) => position === 0 || indexes[position - 1] <= index);
const falseAuthority = (value: Record<string, unknown>, recorded?: boolean) => value.evidence_only === true && value.reference_only === true && value.caller_supplied_credentials_allowed === false && value.caller_supplied_endpoint_allowed === false && value.caller_supplied_command_allowed === false && value.credential_material_present === false && value.endpoint_material_present === false && value.command_material_present === false && value.payload_schema_defined === false && value.payload_constructed === false && value.payload_serialized === false && value.payload_bytes === 0 && value.queue_polling_allowed === false && value.queue_claim_allowed === false && value.queue_lease_allowed === false && value.queue_ack_allowed === false && value.queue_mutation_allowed === false && value.worker_contact_allowed === false && value.worker_start_allowed === false && value.agent_invocation_allowed === false && value.execution_start_allowed === false && value.process_execution_allowed === false && value.store_contact_allowed === false && value.runtime_contact_allowed === false && value.dispatch_allowed === false && value.retry_allowed === false && value.scheduler_allowed === false && value.workflow_start_allowed === false && value.shell_execution_allowed === false && value.provider_mutation_allowed === false && value.repository_mutation_allowed === false && value.in_guest_mutation_allowed === false && value.installation_allowed === false && value.deployment_allowed === false && value.rollback_allowed === false && value.replay_bypass_allowed === false && (recorded === undefined || value.one_shot_dequeue_worker_binding_recorded === recorded);
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

function validateRecord(value: unknown): OneShotDequeueWorkerBindingV1 {
    if (!object(value) || !falseAuthority(value, true) || value.schema !== "one-shot-dequeue-worker-binding-v1" || !UUID5.test(String(value.binding_id)) || !UUID.test(String(value.candidate_record_id)) || !utc(value.recorded_at) || !utc(value.valid_until) || value.lifecycle !== "active" || value.binding_state !== "readiness_gated" || value.eligibility !== "one_shot_dequeue_worker_binding_recorded" || !successBlockers(value.blockers) || !object(value.one_shot_controlled_dequeue) || !object(value.one_shot_controlled_dequeue_status) || !object(value.worker_intake_admission) || !object(value.worker_intake_admission_status) || !fp(value.worker_subject_fingerprint) || !fp(value.queue_item_reference_fingerprint) || !fp(value.inherited_limits_fingerprint) || !fp(value.subject_fingerprint) || !fp(value.idempotency_key_fingerprint) || !fp(value.binding_record_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot dequeue worker binding response.");
    const dequeue = parseOneShotControlledDequeueResult({ ...value.one_shot_controlled_dequeue, schema: "one-shot-controlled-dequeue-result-v1", ok: true, outcome: value.one_shot_controlled_dequeue.outcome, record: value.one_shot_controlled_dequeue, status: value.one_shot_controlled_dequeue_status, error: null, correlation_fingerprint: value.subject_fingerprint, one_shot_controlled_dequeue_recorded: true }).record;
    const worker = parseWorkerIntakeAdmissionResult({ ...value.worker_intake_admission, schema: "worker-intake-admission-result-v1", ok: true, admission: value.worker_intake_admission, error: null, correlation_fingerprint: value.subject_fingerprint }).admission;
    const record = value as OneShotDequeueWorkerBindingV1;
    if (!dequeue || !worker || record.operator_id !== dequeue.operator_id || record.operator_id !== worker.operator_id || record.candidate_record_id !== dequeue.candidate_record_id || record.candidate_record_id !== worker.candidate_record_id || record.valid_until > dequeue.valid_until || record.valid_until > worker.valid_until || record.worker_subject_fingerprint.value !== worker.subject_fingerprint.value || record.queue_item_reference_fingerprint.value !== worker.linkage.queue_item_reference_fingerprint.value || record.inherited_limits_fingerprint.value !== dequeue.inherited_limits.limits_fingerprint.value || record.inherited_limits_fingerprint.value !== worker.inherited_limits.limits_fingerprint.value) throw new Error("Invalid one-shot dequeue worker binding response.");
    return record;
}

export function parseOneShotDequeueWorkerBindingResult(value: unknown): OneShotDequeueWorkerBindingResultV1 {
    if (!object(value) || !falseAuthority(value) || value.schema !== "one-shot-dequeue-worker-binding-result-v1" || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot dequeue worker binding response.");
    if (value.record) {
        if (value.ok !== true || value.outcome !== "success" || value.error !== null || value.one_shot_dequeue_worker_binding_recorded !== true || !object(value.status) || !falseAuthority(value.status, true) || value.status.schema !== "one-shot-dequeue-worker-binding-status-v1" || !["active", "expired"].includes(String(value.status.lifecycle)) || value.status.binding_state !== "one_shot_dequeue_worker_binding_recorded" || value.status.eligibility !== "one_shot_dequeue_worker_binding_recorded" || !successBlockers(value.status.blockers) || !utc(value.status.evaluated_at) || !utc(value.status.valid_until) || !fp(value.status.binding_record_fingerprint) || !fp(value.status.status_fingerprint) || validateRecord(value.record).binding_id !== value.status.binding_id) throw new Error("Invalid one-shot dequeue worker binding response.");
    } else if (value.ok !== false || !["failure", "indeterminate"].includes(String(value.outcome)) || value.status !== null || value.one_shot_dequeue_worker_binding_recorded !== false || !object(value.error) || !falseAuthority(value.error, false) || value.error.schema !== "one-shot-dequeue-worker-binding-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "one-shot dequeue worker binding request could not be completed" || !fp(value.error.correlation_fingerprint) || !orderedBlockers([value.error.error_code])) {
        throw new Error("Invalid one-shot dequeue worker binding response.");
    }
    return value as OneShotDequeueWorkerBindingResultV1;
}

export function parseOneShotDequeueWorkerBindingCollection(value: unknown): OneShotDequeueWorkerBindingCollectionV1 {
    if (!object(value) || !falseAuthority(value, false) || value.schema !== "one-shot-dequeue-worker-binding-collection-v1" || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 16 || !fp(value.collection_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid one-shot dequeue worker binding collection.");
    return { ...value, items: value.items.map(validateRecord) } as OneShotDequeueWorkerBindingCollectionV1;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/one-shot-dequeue-worker-bindings`;
export async function listOneShotDequeueWorkerBindings(candidateId: string) {
    const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true });
    return parseOneShotDequeueWorkerBindingCollection(response.data);
}
export async function getOneShotDequeueWorkerBinding(candidateId: string, bindingId: string) {
    const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(bindingId)}`, { withCredentials: true });
    return parseOneShotDequeueWorkerBindingResult(response.data);
}
