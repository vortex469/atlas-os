import { atlas } from "./atlas";
import { parseControlledWorkerQueueReceipt } from "./controlledWorkerQueueReceipt";
import type { ControlledWorkerQueueReceipt } from "../types/controlledWorkerQueueReceipt";
import { CLOSED_RUNTIME_AUTHORITY, type WorkerActivationRuntimePrerequisite } from "../types/workerActivationRuntimePrerequisite";
import type { FingerprintV1 } from "../types/installationReadinessReview";

const SCHEMA = "worker-activation-runtime-prerequisite";
const MARKER = "worker_activation_runtime_prerequisite_recorded";
const BLOCKERS = ["worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"];
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function check(value: unknown): asserts value {
    if (!value) throw new Error("Runtime prerequisite evidence is unavailable.");
}
function object(value: unknown): Record<string, unknown> {
    check(value !== null && typeof value === "object" && !Array.isArray(value));
    return value as Record<string, unknown>;
}
function fp(value: unknown): FingerprintV1 {
    const raw = object(value);
    check(Object.keys(raw).length === 3 && raw.algorithm === "sha256" && raw.canonicalization === "atlas-jcs-nfc-v1" && typeof raw.value === "string" && /^[a-f0-9]{64}$/.test(raw.value));
    return { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: raw.value };
}
function time(value: unknown): string {
    check(typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value.replace("Z", ".000Z"));
    return value;
}
function closed(raw: Record<string, unknown>, fields: string[]) {
    const allowed = new Set([...CLOSED_RUNTIME_AUTHORITY, "evidence_only", "reference_only", "payload_bytes", "schema", ...fields]);
    check(Object.keys(raw).every((key) => allowed.has(key)));
    check(raw.evidence_only === true && raw.reference_only === true && raw.payload_bytes === 0);
    for (const key of CLOSED_RUNTIME_AUTHORITY) check(raw[key] === false);
}
const COMMON = ["prerequisite_id", "operator_id", "candidate_record_id", "admission_id", "recorded_at", "valid_until", "lifecycle", "eligibility", "blockers", "prerequisite_record_fingerprint", MARKER];
function record(value: unknown, candidateId: string, operatorId: string) {
    const raw = object(value);
    closed(raw, [...COMMON, "subject_fingerprint", "idempotency_key_fingerprint", "controlled_worker_queue_claim_lease_acknowledgement", "controlled_worker_queue_claim_lease_acknowledgement_status"]);
    check(raw.schema === `${SCHEMA}-v1` && raw.operator_id === operatorId && raw.candidate_record_id === candidateId);
    check(typeof raw.prerequisite_id === "string" && UUID5.test(raw.prerequisite_id) && typeof raw.admission_id === "string" && UUID5.test(raw.admission_id));
    check(raw.lifecycle === "active" && raw.eligibility === MARKER && raw[MARKER] === true && JSON.stringify(raw.blockers) === JSON.stringify(BLOCKERS));
    const recordedAt = time(raw.recorded_at), validUntil = time(raw.valid_until);
    check(recordedAt < validUntil && Date.parse(validUntil) - Date.parse(recordedAt) <= 30_000);
    const fingerprints = { subject: fp(raw.subject_fingerprint), idempotency_key: fp(raw.idempotency_key_fingerprint), prerequisite_record: fp(raw.prerequisite_record_fingerprint) };
    // Reuse v0.52 lineage validation; this envelope is only an input to its parser.
    const nested = object(raw.controlled_worker_queue_claim_lease_acknowledgement);
    const receipt = parseControlledWorkerQueueReceipt({
        ...nested, schema: "controlled-worker-queue-claim-lease-acknowledgement-result-v1",
        record: nested, status: raw.controlled_worker_queue_claim_lease_acknowledgement_status,
        ok: true, outcome: "success", error: null, correlation_fingerprint: fingerprints.subject,
    }, candidateId, raw.admission_id, operatorId);
    check(receipt.lifecycle === "active" && validUntil <= receipt.validUntil);
    for (const start of [receipt.recordedAt, receipt.evaluatedAt]) check(start <= recordedAt && Date.parse(recordedAt) - Date.parse(start) <= 30_000);
    check(receipt.evaluatedAt >= receipt.recordedAt && receipt.evaluatedAt < receipt.validUntil);
    return { raw, receipt, prerequisiteId: raw.prerequisite_id, admissionId: raw.admission_id, candidateId, operatorId, recordedAt, validUntil, fingerprints };
}

// Core decides lifecycle and computes fingerprints. The browser checks shape and
// linkage only, never hashes evidence or derives readiness from its own clock.
export async function getWorkerActivationRuntimePrerequisite(receipt: ControlledWorkerQueueReceipt): Promise<WorkerActivationRuntimePrerequisite | null> {
    const { candidateId, operatorId, admissionId } = receipt;
    check(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(candidateId) && UUID5.test(admissionId));
    const path = `/installation/candidate-records/${encodeURIComponent(candidateId)}/worker-activation-runtime-prerequisites`;
    const response = await atlas.get<unknown>(path, { withCredentials: true });
    const collection = object(response.data);
    closed(collection, ["operator_id", "candidate_record_id", "items", "count", "collection_fingerprint"]);
    check(collection.schema === `${SCHEMA}-collection-v1` && collection.operator_id === operatorId && collection.candidate_record_id === candidateId);
    fp(collection.collection_fingerprint);
    check(Array.isArray(collection.items) && collection.count === collection.items.length && collection.items.length <= 16);
    const records = collection.items.map((item) => record(item, candidateId, operatorId));
    check(new Set(records.map((item) => item.prerequisiteId)).size === records.length);
    const matches = records.filter((item) => item.admissionId === admissionId);
    check(matches.length <= 1);
    if (!matches.length) return null;
    const selected = matches[0];
    check(selected.receipt.fingerprints.receipt_record.value === receipt.fingerprints.receipt_record.value);
    const detail = await atlas.get<unknown>(`${path}/${encodeURIComponent(selected.prerequisiteId)}`, { withCredentials: true });
    const parsed = parseWorkerActivationRuntimePrerequisite(detail.data, candidateId, operatorId, selected.prerequisiteId, admissionId, receipt.fingerprints.receipt_record.value);
    check(parsed.fingerprints.prerequisite_record.value === selected.fingerprints.prerequisite_record.value);
    return { ...parsed, fingerprints: { ...parsed.fingerprints, collection: fp(collection.collection_fingerprint) } };
}

// Pure recursive envelope validation, also used by the exact v0.54 successor.
export function parseWorkerActivationRuntimePrerequisite(value: unknown, candidateId: string, operatorId: string, prerequisiteId: string, admissionId: string, receiptFingerprint?: string): WorkerActivationRuntimePrerequisite {
    const result = object(value);
    closed(result, ["record", "status", "exact_duplicate", MARKER]);
    check(result.schema === `${SCHEMA}-result-v1` && result[MARKER] === true && typeof result.exact_duplicate === "boolean");
    const parsed = record(result.record, candidateId, operatorId);
    check(parsed.prerequisiteId === prerequisiteId && parsed.admissionId === admissionId);
    if (receiptFingerprint) check(parsed.receipt.fingerprints.receipt_record.value === receiptFingerprint);
    const status = object(result.status);
    closed(status, [...COMMON, "evaluated_at", "status_fingerprint"]);
    check(status.schema === `${SCHEMA}-status-v1` && status[MARKER] === true);
    for (const key of COMMON) {
        if (key !== "lifecycle" && key !== "prerequisite_record_fingerprint") check(JSON.stringify(status[key]) === JSON.stringify(parsed.raw[key]));
    }
    check(fp(status.prerequisite_record_fingerprint).value === parsed.fingerprints.prerequisite_record.value);
    const evaluatedAt = time(status.evaluated_at);
    check(evaluatedAt >= parsed.recordedAt && (status.lifecycle === "active" || status.lifecycle === "expired"));
    check(status.lifecycle === (evaluatedAt >= parsed.validUntil ? "expired" : "active"));
    return {
        prerequisiteId: parsed.prerequisiteId, admissionId, candidateId, operatorId,
        recordedAt: parsed.recordedAt, validUntil: parsed.validUntil, evaluatedAt,
        lifecycle: status.lifecycle, exactDuplicate: result.exact_duplicate, blockers: [...BLOCKERS],
        fingerprints: { ...parsed.fingerprints, status: fp(status.status_fingerprint), v052_receipt_record: parsed.receipt.fingerprints.receipt_record, v052_receipt_status: parsed.receipt.fingerprints.status },
        authority: Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, status[key]])) as WorkerActivationRuntimePrerequisite["authority"],
    };
}
