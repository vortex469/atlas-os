import { atlas } from "./atlas";
import type {
    DeliveryActivationPreflightAuditEvidenceV1,
    DeliveryActivationPreflightCreateV1,
    DeliveryActivationPreflightLinkageV1,
    DeliveryActivationPreflightOperationV1,
    DeliveryActivationPreflightResultV1,
    DeliveryActivationPreflightStatusV1,
} from "../types/deliveryActivationPreflight";

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const FP_KEYS = ["algorithm", "canonicalization", "value"] as const;
const LINK_KEYS = ["candidate_record_id", "candidate_envelope_fingerprint", "candidate_record_fingerprint", "approval_intent_id", "approval_intent_fingerprint", "agent_request_id", "agent_request_fingerprint", "agent_validation_fingerprint", "agent_audit_evidence_fingerprint", "destination_fingerprint", "source_plan_fingerprint", "artifact_policy_fingerprint", "execution_request_id", "execution_request_fingerprint", "dispatch_envelope_id", "dispatch_envelope_fingerprint", "simulation_request_id", "intake_record_id", "intake_record_fingerprint", "intake_simulation_evidence_fingerprint", "simulated_delivery_id", "simulated_delivery_fingerprint", "delivery_record_fingerprint", "simulated_delivery_evidence_fingerprint", "simulated_acknowledgement_id", "simulated_acknowledgement_fingerprint", "simulated_acknowledgement_evidence_fingerprint", "intake_request_id", "delivery_attempt_id", "dormant_preparation_fingerprint"] as const;
const RESULT_KEYS = ["schema", "preflight_id", "evaluated_at", "expires_at", "delivery_preparation_id", "preparation_fingerprint", "endpoint_fingerprint", "linkage", "decision", "reason_codes", "lifecycle_at_evaluation", "statement", "source", "default_enabled", "agent_contacted", "credentials_loaded", "production_transport_registered", "delivery_activated", "delivery_authorized", "execution_admission_granted", "execution_authorized", "worker_allowed", "mutation_allowed", "replay_allowed", "preflight_fingerprint"] as const;
const STATUS_KEYS = ["schema", "preflight_id", "preflight_fingerprint", "observed_at", "lifecycle", "delivery_activated", "delivery_authorized", "replay_allowed"] as const;
const AUDIT_KEYS = ["schema", "preflight_id", "preflight_fingerprint", "delivery_preparation_id", "preparation_fingerprint", "intake_request_id", "delivery_attempt_id", "evaluated_at", "expires_at", "lifecycle", "decision", "reason_codes", "provenance", "delivery_activated", "delivery_authorized", "execution_authorized", "mutation_allowed", "replay_allowed", "evidence_fingerprint"] as const;
const OPERATION_KEYS = ["disposition", "result", "status", "audit_evidence", "error", "default_enabled", "agent_contacted", "credentials_loaded", "delivery_activated", "delivery_authorized", "execution_attempted", "mutation_attempted", "replay_allowed"] as const;
const REASONS = ["preflight_feature_disabled", "preparation_not_found", "preparation_fingerprint_mismatch", "ownership_mismatch", "linkage_mismatch", "upstream_fingerprint_mismatch", "upstream_state_invalid", "preparation_not_dormant", "already_admitted", "expired", "clock_invalid", "authority_mismatch", "evidence_unavailable", "evidence_corrupt", "replay_conflict"] as const;

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]) { return Object.keys(value).length === keys.length && keys.every((key) => key in value); }
function utc(value: unknown): value is string { return typeof value === "string" && UTC_SECOND.test(value) && !Number.isNaN(Date.parse(value)); }
function fingerprint(value: unknown) { return object(value) && exact(value, FP_KEYS) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && typeof value.value === "string" && HEX64.test(value.value); }
function allFalse(value: Record<string, unknown>, keys: readonly string[]) { return keys.every((key) => value[key] === false); }
function ids(value: Record<string, unknown>, keys: readonly string[]) { return keys.every((key) => UUID4.test(String(value[key]))); }
function reasons(value: unknown): value is string[] { return Array.isArray(value) && value.every((code) => typeof code === "string" && REASONS.includes(code as typeof REASONS[number])) && value.every((code, index) => REASONS.indexOf(code as typeof REASONS[number]) > (index ? REASONS.indexOf(value[index - 1] as typeof REASONS[number]) : -1)); }

function parseLinkage(value: unknown): DeliveryActivationPreflightLinkageV1 {
    if (!object(value) || !exact(value, LINK_KEYS) || !ids(value, LINK_KEYS.filter((key) => key.endsWith("_id"))) || !LINK_KEYS.filter((key) => key.endsWith("_fingerprint")).every((key) => fingerprint(value[key]))) throw new Error("Invalid delivery activation preflight response.");
    return value as unknown as DeliveryActivationPreflightLinkageV1;
}

function parseResult(value: unknown): DeliveryActivationPreflightResultV1 {
    if (!object(value) || !exact(value, RESULT_KEYS) || value.schema !== "delivery-activation-preflight-result-v1" || !ids(value, ["preflight_id", "delivery_preparation_id"]) || !utc(value.evaluated_at) || !utc(value.expires_at) || !fingerprint(value.preparation_fingerprint) || !fingerprint(value.endpoint_fingerprint) || !fingerprint(value.preflight_fingerprint) || !reasons(value.reason_codes) || (value.decision !== "eligible_for_later_activation" && value.decision !== "ineligible") || (value.lifecycle_at_evaluation !== "eligible" && value.lifecycle_at_evaluation !== "ineligible") || value.statement !== "local_evidence_preflight_only_no_delivery_activation" || value.source !== "core_delivery_activation_preflight_v1" || !allFalse(value, ["default_enabled", "agent_contacted", "credentials_loaded", "production_transport_registered", "delivery_activated", "delivery_authorized", "execution_admission_granted", "execution_authorized", "worker_allowed", "mutation_allowed", "replay_allowed"])) throw new Error("Invalid delivery activation preflight response.");
    const evaluated = Date.parse(value.evaluated_at); const expires = Date.parse(value.expires_at);
    if (expires < evaluated || expires > evaluated + 30_000 || (value.decision === "eligible_for_later_activation") !== (expires > evaluated && value.lifecycle_at_evaluation === "eligible" && value.reason_codes.length === 0) || (value.decision === "ineligible" && (expires !== evaluated || value.reason_codes.length === 0))) throw new Error("Invalid delivery activation preflight response.");
    parseLinkage(value.linkage);
    return value as unknown as DeliveryActivationPreflightResultV1;
}

function parseStatus(value: unknown): DeliveryActivationPreflightStatusV1 {
    if (!object(value) || !exact(value, STATUS_KEYS) || value.schema !== "delivery-activation-preflight-status-v1" || !UUID4.test(String(value.preflight_id)) || !fingerprint(value.preflight_fingerprint) || !utc(value.observed_at) || !["eligible", "expired", "ineligible", "unavailable"].includes(String(value.lifecycle)) || !allFalse(value, ["delivery_activated", "delivery_authorized", "replay_allowed"])) throw new Error("Invalid delivery activation preflight response.");
    return value as unknown as DeliveryActivationPreflightStatusV1;
}

function parseAudit(value: unknown): DeliveryActivationPreflightAuditEvidenceV1 {
    if (!object(value) || !exact(value, AUDIT_KEYS) || value.schema !== "delivery-activation-preflight-audit-evidence-v1" || !ids(value, ["preflight_id", "delivery_preparation_id", "intake_request_id", "delivery_attempt_id"]) || !fingerprint(value.preflight_fingerprint) || !fingerprint(value.preparation_fingerprint) || !fingerprint(value.evidence_fingerprint) || !utc(value.evaluated_at) || !utc(value.expires_at) || !reasons(value.reason_codes) || !["eligible", "expired", "ineligible", "unavailable"].includes(String(value.lifecycle)) || !["eligible_for_later_activation", "ineligible"].includes(String(value.decision)) || value.provenance !== "core_delivery_activation_preflight_v1" || !allFalse(value, ["delivery_activated", "delivery_authorized", "execution_authorized", "mutation_allowed", "replay_allowed"])) throw new Error("Invalid delivery activation preflight response.");
    return value as unknown as DeliveryActivationPreflightAuditEvidenceV1;
}

export function parseDeliveryActivationPreflight(value: unknown): DeliveryActivationPreflightOperationV1 {
    if (!object(value) || !exact(value, OPERATION_KEYS) || !["created", "exact_replay"].includes(String(value.disposition)) || value.error !== null || !allFalse(value, ["default_enabled", "agent_contacted", "credentials_loaded", "delivery_activated", "delivery_authorized", "execution_attempted", "mutation_attempted", "replay_allowed"])) throw new Error("Invalid delivery activation preflight response.");
    const result = parseResult(value.result); const status = parseStatus(value.status); const audit = parseAudit(value.audit_evidence);
    if (status.preflight_id !== result.preflight_id || audit.preflight_id !== result.preflight_id || status.preflight_fingerprint.value !== result.preflight_fingerprint.value || audit.preflight_fingerprint.value !== result.preflight_fingerprint.value || audit.lifecycle !== status.lifecycle || audit.delivery_preparation_id !== result.delivery_preparation_id || audit.preparation_fingerprint.value !== result.preparation_fingerprint.value || audit.intake_request_id !== result.linkage.intake_request_id || audit.delivery_attempt_id !== result.linkage.delivery_attempt_id || audit.evaluated_at !== result.evaluated_at || audit.expires_at !== result.expires_at || audit.decision !== result.decision || audit.reason_codes.join("|") !== result.reason_codes.join("|")) throw new Error("Invalid delivery activation preflight response.");
    return value as unknown as DeliveryActivationPreflightOperationV1;
}

export function parseDeliveryActivationPreflightCollection(value: unknown) {
    if (!object(value) || !exact(value, ["preflights", "next_cursor"]) || !Array.isArray(value.preflights) || (value.next_cursor !== null && !UUID4.test(String(value.next_cursor)))) throw new Error("Invalid delivery activation preflight collection response.");
    return { preflights: value.preflights.map(parseDeliveryActivationPreflight), nextCursor: value.next_cursor as string | null };
}

const readConfig = { withCredentials: true };
export async function listDeliveryActivationPreflights() { const response = await atlas.get<unknown>("/installation-delivery-preflights", readConfig); return parseDeliveryActivationPreflightCollection(response.data); }
export async function getDeliveryActivationPreflight(id: string) { const response = await atlas.get<unknown>(`/installation-delivery-preflights/${encodeURIComponent(id)}`, readConfig); return parseDeliveryActivationPreflight(response.data); }
export async function createDeliveryActivationPreflight(body: DeliveryActivationPreflightCreateV1, csrfToken: string, idempotencyKey: string) { const response = await atlas.post<unknown>("/installation-delivery-preflights", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrfToken, "Idempotency-Key": idempotencyKey } }); return parseDeliveryActivationPreflight(response.data); }
export function deliveryActivationPreflightIdempotencyKey() { return `mission-control-delivery-preflight-${crypto.randomUUID()}`; }
