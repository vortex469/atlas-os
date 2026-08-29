import { atlas } from "./atlas";
import type {
    DeliveryEnablementAuditEvidenceV1,
    DeliveryEnablementCreateV1,
    DeliveryEnablementLinkageV1,
    DeliveryEnablementOperationV1,
    DeliveryEnablementRecordV1,
    DeliveryEnablementRedactedErrorV1,
    DeliveryEnablementStatusV1,
} from "../types/deliveryEnablement";
import { DELIVERY_ENABLEMENT_CONFIRMATION } from "../types/deliveryEnablement";

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const IDENTITY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const FP_KEYS = ["algorithm", "canonicalization", "value"] as const;
const LINK_KEYS = ["candidate_record_id", "candidate_envelope_fingerprint", "candidate_record_fingerprint", "approval_intent_id", "approval_intent_fingerprint", "agent_request_id", "agent_request_fingerprint", "agent_validation_fingerprint", "agent_audit_evidence_fingerprint", "destination_fingerprint", "source_plan_fingerprint", "artifact_policy_fingerprint", "execution_request_id", "execution_request_fingerprint", "dispatch_envelope_id", "dispatch_envelope_fingerprint", "simulation_request_id", "intake_record_id", "intake_record_fingerprint", "intake_simulation_evidence_fingerprint", "simulated_delivery_id", "simulated_delivery_fingerprint", "delivery_record_fingerprint", "simulated_delivery_evidence_fingerprint", "simulated_acknowledgement_id", "simulated_acknowledgement_fingerprint", "simulated_acknowledgement_evidence_fingerprint", "intake_request_id", "delivery_attempt_id", "dormant_preparation_fingerprint", "delivery_preparation_id", "preparation_fingerprint", "preflight_id", "preflight_fingerprint"] as const;
const RECORD_KEYS = ["schema", "enablement_id", "enabled_at", "expires_at", "preflight_id", "preflight_fingerprint", "delivery_preparation_id", "preparation_fingerprint", "linkage", "status_at_creation", "confirmation", "statement", "source", "default_enabled", "operator_enabled", "agent_contacted", "credentials_loaded", "production_transport_registered", "delivery_activated", "delivery_sent", "delivery_authorized", "execution_admission_granted", "execution_authorized", "dispatch_allowed", "worker_allowed", "workflow_allowed", "installation_allowed", "deployment_allowed", "mutation_allowed", "replay_allowed", "enablement_fingerprint"] as const;
const STATUS_KEYS = ["schema", "enablement_id", "enablement_fingerprint", "observed_at", "lifecycle", "operator_enabled", "delivery_activated", "delivery_sent", "delivery_authorized", "execution_authorized", "replay_allowed"] as const;
const AUDIT_KEYS = ["schema", "enablement_id", "enablement_fingerprint", "preflight_id", "preflight_fingerprint", "delivery_preparation_id", "preparation_fingerprint", "enabled_at", "expires_at", "lifecycle", "status", "confirmation", "provenance", "delivery_activated", "delivery_sent", "delivery_authorized", "execution_authorized", "mutation_allowed", "replay_allowed", "evidence_fingerprint"] as const;
const OPERATION_KEYS = ["disposition", "record", "status", "audit_evidence", "error", "default_enabled", "agent_contacted", "credentials_loaded", "delivery_activated", "delivery_sent", "delivery_authorized", "execution_attempted", "mutation_attempted", "replay_allowed"] as const;
const ERROR_KEYS = ["schema", "error_code", "correlation_id", "preflight_id", "preflight_fingerprint", "redacted"] as const;
const ERROR_CODES = ["malformed", "not_found", "unauthenticated", "unauthorized", "confirmation_mismatch", "linkage_mismatch", "fingerprint_mismatch", "preflight_not_eligible", "not_current", "replay_conflict", "quota_exceeded", "unavailable"] as const;
const FALSE_RECORD_FLAGS = ["default_enabled", "agent_contacted", "credentials_loaded", "production_transport_registered", "delivery_activated", "delivery_sent", "delivery_authorized", "execution_admission_granted", "execution_authorized", "dispatch_allowed", "worker_allowed", "workflow_allowed", "installation_allowed", "deployment_allowed", "mutation_allowed", "replay_allowed"] as const;

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]) { return Object.keys(value).length === keys.length && keys.every((key) => key in value); }
function utc(value: unknown): value is string { return typeof value === "string" && UTC_SECOND.test(value) && !Number.isNaN(Date.parse(value)); }
function fingerprint(value: unknown) { return object(value) && exact(value, FP_KEYS) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && typeof value.value === "string" && HEX64.test(value.value); }
function ids(value: Record<string, unknown>, keys: readonly string[]) { return keys.every((key) => UUID4.test(String(value[key]))); }
function allFalse(value: Record<string, unknown>, keys: readonly string[]) { return keys.every((key) => value[key] === false); }
function lifecycle(value: unknown) { return ["enabled", "expired", "unavailable"].includes(String(value)); }

function parseLinkage(value: unknown): DeliveryEnablementLinkageV1 {
    if (!object(value) || !exact(value, LINK_KEYS) || !ids(value, LINK_KEYS.filter((key) => key.endsWith("_id"))) || !LINK_KEYS.filter((key) => key.endsWith("_fingerprint")).every((key) => fingerprint(value[key]))) throw new Error("Invalid delivery enablement response.");
    return value as unknown as DeliveryEnablementLinkageV1;
}

function parseRecord(value: unknown): DeliveryEnablementRecordV1 {
    if (!object(value) || !exact(value, RECORD_KEYS) || value.schema !== "operator-controlled-delivery-enablement-record-v1" || !ids(value, ["enablement_id", "preflight_id", "delivery_preparation_id"]) || !utc(value.enabled_at) || !utc(value.expires_at) || !fingerprint(value.preflight_fingerprint) || !fingerprint(value.preparation_fingerprint) || !fingerprint(value.enablement_fingerprint) || value.status_at_creation !== "operator_enabled_for_later_delivery_consideration" || value.confirmation !== DELIVERY_ENABLEMENT_CONFIRMATION || value.statement !== "operator_enablement_evidence_only_no_delivery_activation" || value.source !== "core_operator_controlled_delivery_enablement_v1" || value.operator_enabled !== true || !allFalse(value, FALSE_RECORD_FLAGS)) throw new Error("Invalid delivery enablement response.");
    const enabled = Date.parse(value.enabled_at); const expires = Date.parse(value.expires_at);
    if (!(enabled < expires && expires <= enabled + 30_000)) throw new Error("Invalid delivery enablement response.");
    const link = parseLinkage(value.linkage);
    if (link.preflight_id !== value.preflight_id || link.preflight_fingerprint.value !== (value.preflight_fingerprint as { value: string }).value || link.delivery_preparation_id !== value.delivery_preparation_id || link.preparation_fingerprint.value !== (value.preparation_fingerprint as { value: string }).value) throw new Error("Invalid delivery enablement response.");
    return value as unknown as DeliveryEnablementRecordV1;
}

function parseStatus(value: unknown): DeliveryEnablementStatusV1 {
    if (!object(value) || !exact(value, STATUS_KEYS) || value.schema !== "operator-controlled-delivery-enablement-status-v1" || !UUID4.test(String(value.enablement_id)) || !fingerprint(value.enablement_fingerprint) || !utc(value.observed_at) || !lifecycle(value.lifecycle) || value.operator_enabled !== true || !allFalse(value, ["delivery_activated", "delivery_sent", "delivery_authorized", "execution_authorized", "replay_allowed"])) throw new Error("Invalid delivery enablement response.");
    return value as unknown as DeliveryEnablementStatusV1;
}

function parseAudit(value: unknown): DeliveryEnablementAuditEvidenceV1 {
    if (!object(value) || !exact(value, AUDIT_KEYS) || value.schema !== "operator-controlled-delivery-enablement-audit-evidence-v1" || !ids(value, ["enablement_id", "preflight_id", "delivery_preparation_id"]) || !fingerprint(value.enablement_fingerprint) || !fingerprint(value.preflight_fingerprint) || !fingerprint(value.preparation_fingerprint) || !fingerprint(value.evidence_fingerprint) || !utc(value.enabled_at) || !utc(value.expires_at) || !lifecycle(value.lifecycle) || value.status !== "operator_enabled_for_later_delivery_consideration" || value.confirmation !== DELIVERY_ENABLEMENT_CONFIRMATION || value.provenance !== "core_operator_controlled_delivery_enablement_v1" || !allFalse(value, ["delivery_activated", "delivery_sent", "delivery_authorized", "execution_authorized", "mutation_allowed", "replay_allowed"])) throw new Error("Invalid delivery enablement response.");
    return value as unknown as DeliveryEnablementAuditEvidenceV1;
}

export function parseDeliveryEnablement(value: unknown): DeliveryEnablementOperationV1 {
    if (!object(value) || !exact(value, OPERATION_KEYS) || !["created", "exact_replay"].includes(String(value.disposition)) || value.error !== null || !allFalse(value, ["default_enabled", "agent_contacted", "credentials_loaded", "delivery_activated", "delivery_sent", "delivery_authorized", "execution_attempted", "mutation_attempted", "replay_allowed"])) throw new Error("Invalid delivery enablement response.");
    const record = parseRecord(value.record); const status = parseStatus(value.status); const audit = parseAudit(value.audit_evidence);
    if (status.enablement_id !== record.enablement_id || audit.enablement_id !== record.enablement_id || status.enablement_fingerprint.value !== record.enablement_fingerprint.value || audit.enablement_fingerprint.value !== record.enablement_fingerprint.value || audit.lifecycle !== status.lifecycle || audit.preflight_id !== record.preflight_id || audit.preflight_fingerprint.value !== record.preflight_fingerprint.value || audit.delivery_preparation_id !== record.delivery_preparation_id || audit.preparation_fingerprint.value !== record.preparation_fingerprint.value || audit.enabled_at !== record.enabled_at || audit.expires_at !== record.expires_at || audit.confirmation !== record.confirmation) throw new Error("Invalid delivery enablement response.");
    return value as unknown as DeliveryEnablementOperationV1;
}

export function parseDeliveryEnablementCollection(value: unknown) {
    if (!object(value) || !exact(value, ["enablements", "next_cursor"]) || !Array.isArray(value.enablements) || (value.next_cursor !== null && !UUID4.test(String(value.next_cursor)))) throw new Error("Invalid delivery enablement collection response.");
    return { enablements: value.enablements.map(parseDeliveryEnablement), nextCursor: value.next_cursor as string | null };
}

export function parseDeliveryEnablementError(value: unknown): DeliveryEnablementRedactedErrorV1 {
    if (!object(value) || !exact(value, ERROR_KEYS) || value.schema !== "operator-controlled-delivery-enablement-error-v1" || !ERROR_CODES.includes(value.error_code as typeof ERROR_CODES[number]) || typeof value.correlation_id !== "string" || !IDENTITY.test(value.correlation_id) || (value.preflight_id !== null && !UUID4.test(String(value.preflight_id))) || (value.preflight_fingerprint !== null && !fingerprint(value.preflight_fingerprint)) || value.redacted !== true) throw new Error("Invalid delivery enablement error.");
    return value as unknown as DeliveryEnablementRedactedErrorV1;
}

const readConfig = { withCredentials: true };
export async function listDeliveryEnablements() { const response = await atlas.get<unknown>("/installation-delivery-enablements", readConfig); return parseDeliveryEnablementCollection(response.data); }
export async function getDeliveryEnablement(id: string) { const response = await atlas.get<unknown>(`/installation-delivery-enablements/${encodeURIComponent(id)}`, readConfig); return parseDeliveryEnablement(response.data); }
export async function createDeliveryEnablement(body: DeliveryEnablementCreateV1, csrfToken: string, idempotencyKey: string) { const response = await atlas.post<unknown>("/installation-delivery-enablements", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrfToken, "Idempotency-Key": idempotencyKey } }); return parseDeliveryEnablement(response.data); }
export function deliveryEnablementIdempotencyKey() { return `mission-control-delivery-enablement-${crypto.randomUUID()}`; }
