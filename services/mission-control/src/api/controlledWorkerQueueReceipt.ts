import { atlas } from "./atlas";
import { parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult } from "./controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { CLOSED_QUEUE_AUTHORITY, type ControlledWorkerQueueReceipt } from "../types/controlledWorkerQueueReceipt";
import type { FingerprintV1 } from "../types/installationReadinessReview";

const SCHEMA = "controlled-worker-queue-claim-lease-acknowledgement";
const RECORDED = "controlled_worker_queue_claim_lease_acknowledgement_recorded";
const BLOCKERS = ["worker_activation_runtime_not_defined", "store_contact_not_defined", "runtime_contact_not_defined", "worker_start_admission_not_defined", "worker_start_not_defined", "agent_invocation_not_defined", "execution_start_boundary_not_defined"];
const FINGERPRINTS = ["v051_admission_record", "v051_admission_status", "v050_prerequisite_record", "v050_prerequisite_status", "v049_admission_record", "v049_admission_status", "binding_subject", "worker_subject", "queue_item_reference", "inherited_limits", "adapter_identity", "queue_subject", "claim_receipt", "lease_receipt", "acknowledgement_receipt", "subject", "idempotency_key", "receipt_record"];
function check(condition: unknown): asserts condition {
    if (!condition) throw new Error("Queue receipt evidence is unavailable.");
}
function object(value: unknown): Record<string, unknown> {
    check(typeof value === "object" && value !== null && !Array.isArray(value));
    return value as Record<string, unknown>;
}
function fingerprint(value: unknown): FingerprintV1 {
    const raw = object(value);
    check(raw.algorithm === "sha256" && raw.canonicalization === "atlas-jcs-nfc-v1" && typeof raw.value === "string" && /^[a-f0-9]{64}$/.test(raw.value));
    return { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: raw.value };
}
function timestamp(value: unknown): string {
    check(typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value.replace("Z", ".000Z"));
    return value;
}
function closed(value: Record<string, unknown>) {
    check(value.evidence_only === true && value.reference_only === true && value.payload_bytes === 0);
    for (const field of CLOSED_QUEUE_AUTHORITY) check(value[field] === false);
}

// Project only validated presentation fields. Core owns all authorization, hashing,
// reservation, and lifecycle decisions; raw nested evidence is never rendered.
export function parseControlledWorkerQueueReceipt(value: unknown, candidateId: string, admissionId: string, operatorId: string): ControlledWorkerQueueReceipt {
    const result = object(value);
    closed(result);
    check(result.schema === `${SCHEMA}-result-v1` && result.ok === true && result.outcome === "success" && result.error === null && result[RECORDED] === true);
    fingerprint(result.correlation_fingerprint);
    const record = object(result.record);
    const status = object(result.status);
    for (const item of [record, status]) {
        closed(item);
        check(item.candidate_record_id === candidateId && item.admission_id === admissionId && item.operator_id === operatorId);
        check(item.eligibility === RECORDED && item[RECORDED] === true);
        for (const field of ["controlled_queue_claim_recorded", "controlled_queue_lease_recorded", "controlled_queue_acknowledgement_recorded"]) check(item[field] === true);
        check(JSON.stringify(item.blockers) === JSON.stringify(BLOCKERS));
    }
    check(record.schema === `${SCHEMA}-v1` && record.receipt_state === "recorded" && record.lifecycle === "active");
    check(status.schema === `${SCHEMA}-status-v1` && status.receipt_state === RECORDED && (status.lifecycle === "active" || status.lifecycle === "expired"));
    const recordedAt = timestamp(record.recorded_at);
    const validUntil = timestamp(record.valid_until);
    const evaluatedAt = timestamp(status.evaluated_at);
    check(recordedAt < validUntil && status.valid_until === validUntil);
    const fingerprints: Record<string, FingerprintV1> = {};
    for (const field of FINGERPRINTS) fingerprints[field] = fingerprint(record[`${field}_fingerprint`]);
    check(fingerprint(status.receipt_record_fingerprint).value === fingerprints.receipt_record.value);
    fingerprints.status = fingerprint(status.status_fingerprint);
    const admission = object(record.controlled_worker_queue_claim_lease_acknowledgement_admission);
    const admissionStatus = object(record.controlled_worker_queue_claim_lease_acknowledgement_admission_status);
    for (const item of [admission, admissionStatus]) {
        check(item.operator_id === operatorId && item.candidate_record_id === candidateId && item.admission_id === admissionId);
    }
    check(fingerprint(admission.admission_record_fingerprint).value === fingerprints.v051_admission_record.value);
    check(fingerprint(admissionStatus.status_fingerprint).value === fingerprints.v051_admission_status.value);
    // Reuse the existing v0.51 boundary validation for the complete inherited lineage.
    parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult({
        ...admission,
        schema: `${SCHEMA}-admission-result-v1`, ok: true, outcome: "success",
        record: admission, status: admissionStatus, error: null,
        correlation_fingerprint: result.correlation_fingerprint,
        controlled_worker_queue_claim_lease_acknowledgement_admission_recorded: true,
    });
    check(admissionStatus.lifecycle === "active" && validUntil <= timestamp(admission.valid_until) && validUntil <= timestamp(admissionStatus.valid_until));
    for (const [field, inherited] of Object.entries({
        v050_prerequisite_record: "prerequisite_record", v050_prerequisite_status: "prerequisite_status",
        v049_admission_record: "v049_admission_record", v049_admission_status: "v049_admission_status",
        binding_subject: "binding_subject", worker_subject: "worker_subject",
        queue_item_reference: "queue_item_reference", inherited_limits: "inherited_limits",
    })) check(fingerprint(admission[`${inherited}_fingerprint`]).value === fingerprints[field].value);
    const adapter = object(record.adapter_receipt);
    check(adapter.schema === `${SCHEMA}-adapter-receipt-facts-v1` && adapter.reservation_before_effect === true && adapter.single_subject === true && adapter.terminal_acknowledgement === true && adapter.redacted === true && adapter.secret_free === true);
    for (const field of ["replay_detected", "ambiguity_detected", "corruption_detected"]) check(adapter[field] === false);
    for (const field of ["adapter_identity", "queue_subject", "claim_receipt", "lease_receipt", "acknowledgement_receipt"]) check(fingerprint(adapter[`${field}_fingerprint`]).value === fingerprints[field].value);
    return { admissionId, candidateId, operatorId, recordedAt, validUntil, evaluatedAt, lifecycle: status.lifecycle, blockers: [...BLOCKERS], fingerprints, reservationBeforeEffect: adapter.reservation_before_effect, authority: Object.fromEntries(CLOSED_QUEUE_AUTHORITY.map((field) => [field, record[field]])) as ControlledWorkerQueueReceipt["authority"] };
}

export async function getControlledWorkerQueueReceipt(candidateId: string, admissionId: string, operatorId: string) {
    check(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(candidateId));
    check(/^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(admissionId));
    const response = await atlas.get<unknown>(`/installation/candidate-records/${encodeURIComponent(candidateId)}/controlled-worker-queue-claim-lease-acknowledgements/${encodeURIComponent(admissionId)}`, { withCredentials: true });
    return parseControlledWorkerQueueReceipt(response.data, candidateId, admissionId, operatorId);
}
