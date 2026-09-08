import { atlas } from "./atlas";
import { parseWorkerActivationRuntimeAdmission } from "./workerActivationRuntimeAdmission";
import type { WorkerActivationRuntimeAdmission } from "../types/workerActivationRuntimeAdmission";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
import type { WorkerActivationRuntimePlan } from "../types/workerActivationRuntimePlan";
import type { FingerprintV1 } from "../types/installationReadinessReview";

const SCHEMA = "worker-activation-runtime-plan";
const MARKER = "worker_activation_runtime_plan_recorded";
const BLOCKERS = ["worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"];
const UUID5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function check(value: unknown): asserts value {
    if (!value) throw new Error("Runtime plan evidence is unavailable.");
}
// Bound the inspected evidence, including the lineage displayed in advanced details.
function bounded(value: unknown) {
    const serialized = JSON.stringify(value);
    check(typeof serialized === "string" && new TextEncoder().encode(serialized).length <= 192 * 1024);
}
// Compare immutable response values without recomputing Core fingerprints.
function sameEvidence(left: unknown, right: unknown): boolean {
    if (left === right) return true;
    if (!left || !right || typeof left !== "object" || typeof right !== "object") return false;
    if (Array.isArray(left) !== Array.isArray(right)) return false;
    const a = left as Record<string, unknown>, b = right as Record<string, unknown>;
    return Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((key) => Object.hasOwn(b, key) && sameEvidence(a[key], b[key]));
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
const DESIGN = {
    profile: "core_owned_reference_only_runtime_plan_v1", evidence_owner: "atlas_core",
    admission_reader: "core_owned_runtime_admission_reader", plan_journal: "separate_core_owned_plan_journal",
    presentation: "read_only", inherited_references: "exact_embedded_admission_pair",
    worker_store_contact_interface: "undefined", worker_runtime_contact_interface: "undefined",
};
function design(value: unknown) {
    const raw = object(value);
    closed(raw, [...Object.keys(DESIGN), "unresolved_interfaces"]);
    check(raw.schema === "worker-activation-runtime-plan-design-v1");
    for (const [key, literal] of Object.entries(DESIGN)) check(raw[key] === literal);
    check(sameEvidence(raw.unresolved_interfaces, BLOCKERS));
}
const COMMON = ["runtime_plan_id", "runtime_admission_id", "prerequisite_id", "operator_id", "candidate_record_id", "admission_id", "recorded_at", "valid_until", "lifecycle", "eligibility", "blockers", "runtime_plan_record_fingerprint", "worker_activation_runtime_admission_recorded", MARKER];
function record(value: unknown, candidateId: string, operatorId: string) {
    const raw = object(value);
    closed(raw, [...COMMON, "subject_fingerprint", "idempotency_key_fingerprint", "worker_activation_runtime_admission", "worker_activation_runtime_admission_status", "design"]);
    check(raw.schema === `${SCHEMA}-v1` && raw.operator_id === operatorId && raw.candidate_record_id === candidateId);
    check(typeof raw.runtime_plan_id === "string" && UUID5.test(raw.runtime_plan_id));
    check(raw.worker_activation_runtime_admission_recorded === true);
    design(raw.design);
    check(typeof raw.runtime_admission_id === "string" && UUID5.test(raw.runtime_admission_id));
    check(typeof raw.prerequisite_id === "string" && UUID5.test(raw.prerequisite_id) && typeof raw.admission_id === "string" && UUID5.test(raw.admission_id));
    check(raw.lifecycle === "active" && raw.eligibility === MARKER && raw[MARKER] === true && JSON.stringify(raw.blockers) === JSON.stringify(BLOCKERS));
    const recordedAt = time(raw.recorded_at), validUntil = time(raw.valid_until);
    check(recordedAt < validUntil && Date.parse(validUntil) - Date.parse(recordedAt) <= 30_000);
    const fingerprints = { subject: fp(raw.subject_fingerprint), idempotency_key: fp(raw.idempotency_key_fingerprint), runtime_plan_record: fp(raw.runtime_plan_record_fingerprint) };
    // Adapter envelope for the pure predecessor parser only; never returned as Core evidence.
    const nested = object(raw.worker_activation_runtime_admission);
    const receipt = parseWorkerActivationRuntimeAdmission({
        ...Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, nested[key]])),
        evidence_only: nested.evidence_only, reference_only: nested.reference_only, payload_bytes: nested.payload_bytes,
        schema: "worker-activation-runtime-admission-result-v1",
        record: nested, status: raw.worker_activation_runtime_admission_status,
        exact_duplicate: false, worker_activation_runtime_admission_recorded: nested.worker_activation_runtime_admission_recorded,
    }, candidateId, operatorId);
    check(receipt.runtimeAdmissionId === raw.runtime_admission_id && receipt.prerequisiteId === raw.prerequisite_id && receipt.admissionId === raw.admission_id);
    check(receipt.lifecycle === "active" && validUntil === receipt.validUntil);
    for (const start of [receipt.recordedAt, receipt.evaluatedAt]) check(start <= recordedAt && Date.parse(recordedAt) - Date.parse(start) <= 30_000);
    check(receipt.evaluatedAt >= receipt.recordedAt && receipt.evaluatedAt < receipt.validUntil);
    return { raw, receipt, runtimePlanId: raw.runtime_plan_id, runtimeAdmissionId: raw.runtime_admission_id, prerequisiteId: raw.prerequisite_id, admissionId: raw.admission_id, candidateId, operatorId, recordedAt, validUntil, fingerprints };
}

// Core decides lifecycle and computes fingerprints. The browser checks shape and
// linkage only, never hashes evidence or derives readiness from its own clock.
export async function getWorkerActivationRuntimePlan(prerequisite: WorkerActivationRuntimeAdmission): Promise<WorkerActivationRuntimePlan | null> {
    const { candidateId, operatorId, admissionId, prerequisiteId, runtimeAdmissionId } = prerequisite;
    check(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(candidateId) && UUID5.test(admissionId) && UUID5.test(prerequisiteId) && UUID5.test(runtimeAdmissionId));
    const path = `/installation/candidate-records/${encodeURIComponent(candidateId)}/worker-activation-runtime-plans`;
    const response = await atlas.get<unknown>(path, { withCredentials: true });
    bounded(response.data);
    const collection = object(response.data);
    closed(collection, ["operator_id", "candidate_record_id", "items", "count", "collection_fingerprint"]);
    check(collection.schema === `${SCHEMA}-collection-v1` && collection.operator_id === operatorId && collection.candidate_record_id === candidateId);
    fp(collection.collection_fingerprint);
    check(Array.isArray(collection.items) && collection.count === collection.items.length && collection.items.length <= 16);
    const records = collection.items.map((item) => record(item, candidateId, operatorId));
    check(new Set(records.map((item) => item.runtimePlanId)).size === records.length);
    const matches = records.filter((item) => item.runtimeAdmissionId === runtimeAdmissionId);
    check(matches.length <= 1);
    if (!matches.length) return null;
    const selected = matches[0];
    function parentMatches(item: ReturnType<typeof record>) {
        check(item.admissionId === admissionId && item.prerequisiteId === prerequisiteId);
        check(item.runtimeAdmissionId === runtimeAdmissionId);
        check(sameEvidence(item.receipt.exactRecord, prerequisite.exactRecord));
    }
    parentMatches(selected);
    const detail = await atlas.get<unknown>(`${path}/${encodeURIComponent(selected.runtimePlanId)}`, { withCredentials: true });
    const parsed = parseWorkerActivationRuntimePlan(detail.data, candidateId, operatorId);
    check(sameEvidence(parsed.exactRecord, selected.raw));
    return { ...parsed, fingerprints: { ...parsed.fingerprints, collection: fp(collection.collection_fingerprint) } };
}

function parseWorkerActivationRuntimePlan(value: unknown, candidateId: string, operatorId: string): WorkerActivationRuntimePlan {
    bounded(value);
    const result = object(value);
    closed(result, ["record", "status", "exact_duplicate", "worker_activation_runtime_admission_recorded", MARKER]);
    check(result.schema === `${SCHEMA}-result-v1` && result[MARKER] === true && result.worker_activation_runtime_admission_recorded === true && typeof result.exact_duplicate === "boolean");
    const parsed = record(result.record, candidateId, operatorId);
    const { prerequisiteId, admissionId } = parsed;
    const status = object(result.status);
    closed(status, [...COMMON, "evaluated_at", "status_fingerprint"]);
    check(status.schema === `${SCHEMA}-status-v1` && status[MARKER] === true);
    for (const key of COMMON) {
        if (key !== "lifecycle" && key !== "runtime_plan_record_fingerprint") check(JSON.stringify(status[key]) === JSON.stringify(parsed.raw[key]));
    }
    check(fp(status.runtime_plan_record_fingerprint).value === parsed.fingerprints.runtime_plan_record.value);
    const evaluatedAt = time(status.evaluated_at);
    check(evaluatedAt >= parsed.recordedAt && (status.lifecycle === "active" || status.lifecycle === "expired"));
    check(status.lifecycle === (evaluatedAt >= parsed.validUntil ? "expired" : "active"));
    return {
        runtimePlanId: parsed.runtimePlanId, design: parsed.raw.design, runtimeAdmissionId: parsed.runtimeAdmissionId, prerequisiteId, admissionId, candidateId, operatorId, exactRecord: parsed.raw,
        recordedAt: parsed.recordedAt, validUntil: parsed.validUntil, evaluatedAt,
        lifecycle: status.lifecycle, exactDuplicate: result.exact_duplicate, blockers: [...BLOCKERS],
        fingerprints: { ...parsed.fingerprints, status: fp(status.status_fingerprint), v054_admission_record: parsed.receipt.fingerprints.runtime_admission_record, v054_admission_status: parsed.receipt.fingerprints.status },
        authority: Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, status[key]])) as WorkerActivationRuntimePlan["authority"],
        lineage: { record: parsed.raw.worker_activation_runtime_admission, status: parsed.raw.worker_activation_runtime_admission_status },
    };
}
