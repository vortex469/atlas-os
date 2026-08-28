import { atlas } from "./atlas";
import { INSTALLATION_EXECUTION_REQUEST_STATEMENT, type InstallationExecutionRequestCreateV1, type InstallationExecutionRequestLinkageV1, type InstallationExecutionRequestV1 } from "../types/installationExecutionRequest";

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const FP_KEYS = ["algorithm", "canonicalization", "value"] as const;
const LINK_KEYS = ["candidate_record_id", "candidate_envelope_fingerprint", "admission_fingerprint", "candidate_record_fingerprint", "approval_intent_id", "approval_intent_fingerprint", "agent_request_id", "agent_request_fingerprint", "agent_validation_fingerprint", "agent_evidence_fingerprint", "destination_fingerprint", "source_plan_fingerprint", "artifact_policy_fingerprint"] as const;
const RECORD_KEYS = ["schema", "execution_request_id", "recorded_at", "valid_until", "operation", "mode", "linkage", "statement", "execution_authorized", "dispatch_allowed", "agent_invocation_allowed", "mutation_allowed", "replay_allowed", "execution_request_fingerprint", "lifecycle_state", "evidence_provenance"] as const;

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]) { return Object.keys(value).length === keys.length && keys.every((key) => key in value); }
function utc(value: unknown): value is string {
    if (typeof value !== "string" || !UTC_SECOND.test(value)) return false;
    const date = new Date(value); return !Number.isNaN(date.getTime()) && date.toISOString() === value.replace("Z", ".000Z");
}
function fingerprint(value: unknown): boolean { return object(value) && exact(value, FP_KEYS) && value.algorithm === "sha256" && value.canonicalization === "atlas-jcs-nfc-v1" && typeof value.value === "string" && HEX64.test(value.value); }
function linkage(value: unknown): value is InstallationExecutionRequestLinkageV1 {
    if (!object(value) || !exact(value, LINK_KEYS) || !UUID4.test(String(value.candidate_record_id)) || !UUID4.test(String(value.approval_intent_id)) || !UUID4.test(String(value.agent_request_id)) || !HEX64.test(String(value.destination_fingerprint))) return false;
    return LINK_KEYS.filter((key) => key.endsWith("_fingerprint") && key !== "destination_fingerprint").every((key) => fingerprint(value[key]));
}

export function parseInstallationExecutionRequest(value: unknown): InstallationExecutionRequestV1 {
    if (!object(value) || !exact(value, RECORD_KEYS) || value.schema !== "installation-execution-request-v1" || !UUID4.test(String(value.execution_request_id)) || !utc(value.recorded_at) || !utc(value.valid_until) || value.operation !== "install-container" || value.mode !== "record-only" || !linkage(value.linkage) || value.statement !== INSTALLATION_EXECUTION_REQUEST_STATEMENT || value.execution_authorized !== false || value.dispatch_allowed !== false || value.agent_invocation_allowed !== false || value.mutation_allowed !== false || value.replay_allowed !== false || !fingerprint(value.execution_request_fingerprint) || (value.lifecycle_state !== "recorded" && value.lifecycle_state !== "expired") || value.evidence_provenance !== "operator_submitted_agent_validation_evidence") throw new Error("Invalid installation execution request response.");
    return value as unknown as InstallationExecutionRequestV1;
}

export function parseInstallationExecutionRequestCollection(value: unknown): InstallationExecutionRequestV1[] {
    if (!object(value) || !exact(value, ["execution_requests"]) || !Array.isArray(value.execution_requests)) throw new Error("Invalid installation execution request collection response.");
    return value.execution_requests.map(parseInstallationExecutionRequest);
}

const readConfig = { withCredentials: true };
export async function listInstallationExecutionRequests() { const response = await atlas.get<unknown>("/installation/execution-requests", readConfig); return parseInstallationExecutionRequestCollection(response.data); }
export async function getInstallationExecutionRequest(id: string) { const response = await atlas.get<unknown>(`/installation/execution-requests/${encodeURIComponent(id)}`, readConfig); return parseInstallationExecutionRequest(response.data); }
export async function recordInstallationExecutionRequest(body: InstallationExecutionRequestCreateV1, csrfToken: string, idempotencyKey: string) {
    const response = await atlas.post<unknown>("/installation/execution-requests", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": csrfToken, "Idempotency-Key": idempotencyKey } }); return parseInstallationExecutionRequest(response.data);
}
export function executionRequestIdempotencyKey() { return `mission-control-execution-request-record-${crypto.randomUUID()}`; }
