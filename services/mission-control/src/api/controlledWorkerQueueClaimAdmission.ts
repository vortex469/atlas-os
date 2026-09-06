import { atlas } from "./atlas";
import { parseWorkerBindingActivationEvidenceResult } from "./workerBindingActivationEvidence";
import type { ControlledWorkerQueueClaimAdmissionCollectionV1, ControlledWorkerQueueClaimAdmissionResultV1, ControlledWorkerQueueClaimAdmissionV1 } from "../types/controlledWorkerQueueClaimAdmission";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[45][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SUCCESS_BLOCKERS = ["queue_claim_not_defined", "queue_lease_not_defined", "queue_ack_not_defined", "worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"];
const BLOCKER_ORDER = ["installation_capability_unsupported", "evidence_not_found", "ownership_mismatch", "permission_scope_missing", "v048_activation_evidence_not_active", "v048_activation_evidence_not_recorded", "linkage_mismatch", "fingerprint_mismatch", "inherited_limits_mismatch", "evidence_stale", "evidence_expired", "ambiguous_state", "caller_supplied_credential", "caller_supplied_endpoint", "caller_supplied_command", "unsupported_authority", ...SUCCESS_BLOCKERS, "reservation_before_effect_failed", "permanent_subject_reserved", "idempotency_conflict", "append_indeterminate"];
const SENSITIVE = /(credential|secret|token|password|endpoint|address|url|uri|internal_path|command|raw_payload|payload_body|queue_detail|broker|worker_address|hostname|socket|port|consumer|lease_token|ack_token|store|runtime)/i;
const ALLOWED_TRUE = new Set(["evidence_only", "reference_only", "controlled_worker_queue_claim_admission_recorded", "worker_binding_activation_evidence_recorded", "worker_binding_activation_preflight_recorded", "one_shot_dequeue_worker_binding_recorded", "one_shot_controlled_dequeue_recorded", "controlled_dequeue_admission_recorded", "queue_observation_recorded", "one_shot_live_enqueue_recorded", "binding_planned", "enabled", "ephemeral_workspace_allowed", "root_filesystem_read_only"]);

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const fp = (value: unknown) => object(value) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && /^[a-f0-9]{64}$/.test(String(value.value));
const utc = (value: unknown) => typeof value === "string" && UTC_SECOND.test(value) && new Date(value).toISOString() === value.replace("Z", ".000Z");
const successBlockers = (value: unknown) => Array.isArray(value) && value.length === SUCCESS_BLOCKERS.length && SUCCESS_BLOCKERS.every((item, index) => value[index] === item);
const orderedBlockers = (value: unknown) => Array.isArray(value) && value.length > 0 && value.every((item) => BLOCKER_ORDER.includes(String(item))) && new Set(value).size === value.length && value.map((item) => BLOCKER_ORDER.indexOf(String(item))).every((index, position, indexes) => position === 0 || indexes[position - 1] <= index);
const falseAuthority = (value: Record<string, unknown>, recorded?: boolean) => value.evidence_only === true && value.reference_only === true && value.caller_supplied_credentials_allowed === false && value.caller_supplied_endpoint_allowed === false && value.caller_supplied_command_allowed === false && value.caller_supplied_payload_allowed === false && value.credential_material_present === false && value.endpoint_material_present === false && value.command_material_present === false && value.payload_material_present === false && value.payload_schema_defined === false && value.payload_constructed === false && value.payload_serialized === false && value.payload_bytes === 0 && value.queue_polling_allowed === false && value.queue_claim_allowed === false && value.queue_lease_allowed === false && value.queue_ack_allowed === false && value.queue_consume_allowed === false && value.queue_mutation_allowed === false && value.worker_store_contact_allowed === false && value.worker_runtime_contact_allowed === false && value.worker_contact_allowed === false && value.worker_start_admission_allowed === false && value.worker_start_allowed === false && value.worker_invocation_allowed === false && value.agent_invocation_allowed === false && value.execution_authorization_allowed === false && value.execution_start_allowed === false && value.process_execution_allowed === false && value.store_contact_allowed === false && value.runtime_contact_allowed === false && value.dispatch_allowed === false && value.retry_allowed === false && value.resend_allowed === false && value.scheduler_allowed === false && value.workflow_start_allowed === false && value.shell_execution_allowed === false && value.provider_mutation_allowed === false && value.repository_mutation_allowed === false && value.in_guest_mutation_allowed === false && value.installation_allowed === false && value.deployment_allowed === false && value.rollback_allowed === false && value.replay_bypass_allowed === false && value.artifact_publication_allowed === false && value.tag_push_allowed === false && value.release_publication_allowed === false && value.binding_activation_allowed === false && value.worker_activation_runtime_allowed === false && value.queue_claimed === false && value.queue_leased === false && value.queue_acknowledged === false && value.worker_start_admitted === false && value.worker_started === false && value.execution_started === false && (recorded === undefined || value.controlled_worker_queue_claim_admission_recorded === recorded);
const forbiddenTrue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(forbiddenTrue);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => ((!ALLOWED_TRUE.has(key) && /(allowed|authorized|attempted|present|exists|reachable|contacted|started|dequeued|claimed|leased|executable|serialized|defined|released|consumed|replaceable|supersedable|bypass|polling|authenticated|sent|open|constructed|publish|send|ack|activation|mutation|deployment|rollback)/.test(key) && item === true) || forbiddenTrue(item)));
};
const sensitiveField = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(sensitiveField);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => (SENSITIVE.test(key) && item !== false && item !== null && item !== undefined && !(Array.isArray(item) && item.length === 0) && key !== "worker_store_contact_allowed" && key !== "worker_runtime_contact_allowed" && key !== "store_contact_allowed" && key !== "runtime_contact_allowed") || sensitiveField(item));
};

function validateRecord(value: unknown): ControlledWorkerQueueClaimAdmissionV1 {
    if (!object(value)) throw new Error("Invalid controlled worker queue claim admission response.");
    if (!falseAuthority(value, true)) throw new Error("Invalid controlled worker queue claim admission response: authority.");
    if (value.schema !== "controlled-worker-queue-claim-admission-v1") throw new Error("Invalid controlled worker queue claim admission response: schema.");
    if (!UUID5.test(String(value.admission_id))) throw new Error("Invalid controlled worker queue claim admission response: id.");
    if (!UUID.test(String(value.candidate_record_id))) throw new Error("Invalid controlled worker queue claim admission response: candidate.");
    if (!utc(value.recorded_at) || !utc(value.valid_until)) throw new Error("Invalid controlled worker queue claim admission response: time.");
    if (value.lifecycle !== "active" || value.admission_state !== "readiness_gated" || value.eligibility !== "controlled_worker_queue_claim_admission_recorded") throw new Error("Invalid controlled worker queue claim admission response: state.");
    if (!successBlockers(value.blockers)) throw new Error("Invalid controlled worker queue claim admission response: blockers.");
    if (!object(value.worker_binding_activation_evidence) || !object(value.worker_binding_activation_evidence_status) || !fp(value.binding_subject_fingerprint) || !fp(value.worker_subject_fingerprint) || !fp(value.queue_item_reference_fingerprint) || !fp(value.inherited_limits_fingerprint) || !fp(value.subject_fingerprint) || !fp(value.idempotency_key_fingerprint) || !fp(value.admission_record_fingerprint)) throw new Error("Invalid controlled worker queue claim admission response: fingerprints.");
    if (forbiddenTrue(value)) throw new Error("Invalid controlled worker queue claim admission response: authority drift.");
    if (sensitiveField(value)) throw new Error("Invalid controlled worker queue claim admission response: sensitive field.");
    const evidence = parseWorkerBindingActivationEvidenceResult({ ...value.worker_binding_activation_evidence, schema: "worker-binding-activation-evidence-result-v1", ok: true, outcome: "success", record: value.worker_binding_activation_evidence, status: value.worker_binding_activation_evidence_status, error: null, correlation_fingerprint: value.subject_fingerprint, worker_binding_activation_evidence_recorded: true }).record;
    const record = value as ControlledWorkerQueueClaimAdmissionV1;
    if (!evidence || record.operator_id !== evidence.operator_id || record.candidate_record_id !== evidence.candidate_record_id || record.valid_until > evidence.valid_until || record.binding_subject_fingerprint.value !== evidence.binding_subject_fingerprint.value || record.worker_subject_fingerprint.value !== evidence.worker_subject_fingerprint.value || record.queue_item_reference_fingerprint.value !== evidence.queue_item_reference_fingerprint.value || record.inherited_limits_fingerprint.value !== evidence.inherited_limits_fingerprint.value) throw new Error("Invalid controlled worker queue claim admission response.");
    return record;
}

export function parseControlledWorkerQueueClaimAdmissionResult(value: unknown): ControlledWorkerQueueClaimAdmissionResultV1 {
    if (!object(value) || !falseAuthority(value) || value.schema !== "controlled-worker-queue-claim-admission-result-v1" || !fp(value.correlation_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid controlled worker queue claim admission response.");
    if (value.record) {
        const record = validateRecord(value.record);
        const status = value.status;
        if (value.ok !== true || value.outcome !== "success" || value.error !== null || value.controlled_worker_queue_claim_admission_recorded !== true || !object(status) || !falseAuthority(status, true) || status.schema !== "controlled-worker-queue-claim-admission-status-v1" || !["active", "expired"].includes(String(status.lifecycle)) || status.admission_state !== "controlled_worker_queue_claim_admission_recorded" || status.eligibility !== "controlled_worker_queue_claim_admission_recorded" || !successBlockers(status.blockers) || !utc(status.evaluated_at) || !utc(status.valid_until) || !fp(status.admission_record_fingerprint) || !fp(status.status_fingerprint)) throw new Error("Invalid controlled worker queue claim admission response.");
        const statusRecordFingerprint = status.admission_record_fingerprint;
        if (!fp(statusRecordFingerprint)) throw new Error("Invalid controlled worker queue claim admission response.");
        const statusRecordFingerprintValue = (statusRecordFingerprint as { value: string }).value;
        if (record.admission_id !== status.admission_id || record.operator_id !== status.operator_id || record.candidate_record_id !== status.candidate_record_id || record.valid_until !== status.valid_until || record.admission_record_fingerprint.value !== statusRecordFingerprintValue) throw new Error("Invalid controlled worker queue claim admission response.");
    } else if (value.ok !== false || !["failure", "indeterminate"].includes(String(value.outcome)) || value.status !== null || value.controlled_worker_queue_claim_admission_recorded !== false || !object(value.error) || !falseAuthority(value.error, false) || value.error.schema !== "controlled-worker-queue-claim-admission-error-v1" || value.error.redacted !== true || value.error.retryable !== false || value.error.message !== "controlled worker queue claim admission request could not be completed" || !fp(value.error.correlation_fingerprint) || !orderedBlockers([value.error.error_code])) {
        throw new Error("Invalid controlled worker queue claim admission response.");
    }
    return value as ControlledWorkerQueueClaimAdmissionResultV1;
}

export function parseControlledWorkerQueueClaimAdmissionCollection(value: unknown): ControlledWorkerQueueClaimAdmissionCollectionV1 {
    if (!object(value) || !falseAuthority(value, false) || value.schema !== "controlled-worker-queue-claim-admission-collection-v1" || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 100 || !fp(value.collection_fingerprint) || forbiddenTrue(value) || sensitiveField(value)) throw new Error("Invalid controlled worker queue claim admission collection.");
    const items = value.items.map(validateRecord);
    const ordered = [...items].sort((left, right) => `${left.recorded_at}:${left.admission_id}`.localeCompare(`${right.recorded_at}:${right.admission_id}`));
    if (items.some((item, index) => item !== ordered[index] || item.operator_id !== value.operator_id || item.candidate_record_id !== value.candidate_record_id)) throw new Error("Invalid controlled worker queue claim admission collection.");
    return { ...value, items } as ControlledWorkerQueueClaimAdmissionCollectionV1;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/controlled-worker-queue-claim-admissions`;
export async function listControlledWorkerQueueClaimAdmissions(candidateId: string) {
    const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true });
    return parseControlledWorkerQueueClaimAdmissionCollection(response.data);
}
export async function getControlledWorkerQueueClaimAdmission(candidateId: string, admissionId: string) {
    const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(admissionId)}`, { withCredentials: true });
    return parseControlledWorkerQueueClaimAdmissionResult(response.data);
}
