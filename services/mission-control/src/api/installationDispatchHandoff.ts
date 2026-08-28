import { atlas } from "./atlas";
import type { InstallationDispatchHandoffCreateV1, InstallationDispatchHandoffV1, InstallationDispatchLinkageV1 } from "../types/installationDispatchHandoff";

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const FP_KEYS = ["algorithm", "canonicalization", "value"] as const;
const RECIPIENT_KEYS = ["service", "intake_contract"] as const;
const LINK_KEYS = ["candidate_record_id", "candidate_envelope_fingerprint", "admission_fingerprint", "candidate_record_fingerprint", "approval_intent_id", "approval_intent_fingerprint", "agent_request_id", "agent_request_fingerprint", "agent_validation_fingerprint", "agent_evidence_fingerprint", "destination_fingerprint", "source_plan_fingerprint", "artifact_policy_fingerprint", "execution_request_id", "execution_request_fingerprint"] as const;
const RECORD_KEYS = ["schema", "dispatch_envelope_id", "prepared_at", "valid_until", "operation", "mode", "recipient", "linkage", "statement", "delivery_authorized", "agent_admission_authorized", "execution_authorized", "mutation_authorized", "replay_allowed", "dispatch_envelope_fingerprint", "lifecycle_state", "evidence_provenance"] as const;

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]) { return Object.keys(value).length === keys.length && keys.every((key) => key in value); }
function utc(value: unknown): value is string {
    if (typeof value !== "string" || !UTC_SECOND.test(value)) return false;
    const date = new Date(value);
    return !Number.isNaN(date.getTime()) && date.toISOString() === value.replace("Z", ".000Z");
}
function fingerprint(value: unknown): boolean { return object(value) && exact(value, FP_KEYS) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && typeof value.value === "string" && HEX64.test(value.value); }
function linkage(value: unknown): value is InstallationDispatchLinkageV1 {
    if (!object(value) || !exact(value, LINK_KEYS) || !UUID4.test(String(value.candidate_record_id)) || !UUID4.test(String(value.approval_intent_id)) || !UUID4.test(String(value.agent_request_id)) || !UUID4.test(String(value.execution_request_id)) || !HEX64.test(String(value.destination_fingerprint))) return false;
    return LINK_KEYS.filter((key) => key.endsWith("_fingerprint") && key !== "destination_fingerprint").every((key) => fingerprint(value[key]));
}

export function parseInstallationDispatchHandoff(value: unknown): InstallationDispatchHandoffV1 {
    if (!object(value) || !exact(value, RECORD_KEYS) || value.schema !== "installation-dispatch-envelope-v1" || !UUID4.test(String(value.dispatch_envelope_id)) || !utc(value.prepared_at) || !utc(value.valid_until) || value.operation !== "install-container" || value.mode !== "handoff-only" || !object(value.recipient) || !exact(value.recipient, RECIPIENT_KEYS) || value.recipient.service !== "atlas-agent" || value.recipient.intake_contract !== "agent-installation-dispatch-intake-v1" || !linkage(value.linkage) || value.statement !== "core_prepared_non_executing_agent_handoff" || value.delivery_authorized !== false || value.agent_admission_authorized !== false || value.execution_authorized !== false || value.mutation_authorized !== false || value.replay_allowed !== false || !fingerprint(value.dispatch_envelope_fingerprint) || (value.lifecycle_state !== "prepared" && value.lifecycle_state !== "expired") || value.evidence_provenance !== "core_prepared_not_delivered") throw new Error("Invalid installation dispatch handoff response.");
    const prepared = Date.parse(value.prepared_at); const validUntil = Date.parse(value.valid_until);
    if (validUntil <= prepared || validUntil > prepared + 60_000) throw new Error("Invalid installation dispatch handoff response.");
    return value as unknown as InstallationDispatchHandoffV1;
}

export function parseInstallationDispatchHandoffCollection(value: unknown): InstallationDispatchHandoffV1[] {
    if (!object(value) || !exact(value, ["dispatch_handoffs"]) || !Array.isArray(value.dispatch_handoffs)) throw new Error("Invalid installation dispatch handoff collection response.");
    return value.dispatch_handoffs.map(parseInstallationDispatchHandoff);
}

const readConfig = { withCredentials: true };
export async function listInstallationDispatchHandoffs() { const response = await atlas.get<unknown>("/installation/dispatch-handoffs", readConfig); return parseInstallationDispatchHandoffCollection(response.data); }
export async function getInstallationDispatchHandoff(id: string) { const response = await atlas.get<unknown>(`/installation/dispatch-handoffs/${encodeURIComponent(id)}`, readConfig); return parseInstallationDispatchHandoff(response.data); }
export async function preserveInstallationDispatchHandoff(body: InstallationDispatchHandoffCreateV1, csrfToken: string, idempotencyKey: string) {
    const response = await atlas.post<unknown>("/installation/dispatch-handoffs", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrfToken, "Idempotency-Key": idempotencyKey } });
    return parseInstallationDispatchHandoff(response.data);
}
export function dispatchHandoffIdempotencyKey() { return `mission-control-dispatch-handoff-preserve-${crypto.randomUUID()}`; }
