import { atlas } from "./atlas";
import {
    INSTALLATION_APPROVAL_STATEMENT,
    type InstallationApprovalIntentCollectionV1,
    type InstallationApprovalIntentV1,
    type InstallationApprovalSubjectV1,
} from "../types/installationApprovalIntent";

const INTENT_KEYS = [
    "schema", "approval_intent_id", "operator_id", "recorded_at", "approved_subject", "statement", "intent_fingerprint",
] as const;
const SUBJECT_KEYS = [
    "candidate_record_id", "candidate_envelope_fingerprint", "admission_fingerprint", "candidate_record_fingerprint",
] as const;
const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const FINGERPRINT = /^[0-9a-f]{64}$/;
const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

function object(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
    return Object.keys(value).length === keys.length && keys.every((key) => key in value);
}

function operatorId(value: unknown): value is string {
    return typeof value === "string" && value.length >= 1 && value.length <= 200 &&
        /^[\x21-\x7e]+$/.test(value);
}

function utcSecond(value: unknown): value is string {
    if (typeof value !== "string" || !UTC_SECOND.test(value)) return false;
    const parsed = new Date(value);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString() === value.replace("Z", ".000Z");
}

function parseSubject(value: unknown): InstallationApprovalSubjectV1 {
    if (!object(value) || !exact(value, SUBJECT_KEYS) || !UUID4.test(String(value.candidate_record_id)) ||
        !SUBJECT_KEYS.slice(1).every((key) => FINGERPRINT.test(String(value[key])))) {
        throw new Error("Invalid installation approval intent response.");
    }
    return value as unknown as InstallationApprovalSubjectV1;
}

export function parseInstallationApprovalIntent(value: unknown): InstallationApprovalIntentV1 {
    if (!object(value) || !exact(value, INTENT_KEYS) || value.schema !== "installation-approval-intent-v1" ||
        !UUID4.test(String(value.approval_intent_id)) || !operatorId(value.operator_id) ||
        !utcSecond(value.recorded_at) || value.statement !== INSTALLATION_APPROVAL_STATEMENT ||
        !FINGERPRINT.test(String(value.intent_fingerprint))) {
        throw new Error("Invalid installation approval intent response.");
    }
    return { ...value, approved_subject: parseSubject(value.approved_subject) } as unknown as InstallationApprovalIntentV1;
}

export function parseInstallationApprovalIntentCollection(value: unknown): InstallationApprovalIntentCollectionV1 {
    if (!object(value) || !exact(value, ["approval_intents"]) || !Array.isArray(value.approval_intents)) {
        throw new Error("Invalid installation approval intent collection response.");
    }
    return { approval_intents: value.approval_intents.map(parseInstallationApprovalIntent) };
}

const readConfig = { withCredentials: true };

export async function listInstallationApprovalIntents(): Promise<InstallationApprovalIntentV1[]> {
    const response = await atlas.get<unknown>("/installation/candidate-approval-intents", readConfig);
    return parseInstallationApprovalIntentCollection(response.data).approval_intents;
}

export async function getInstallationApprovalIntent(approvalIntentId: string): Promise<InstallationApprovalIntentV1> {
    const response = await atlas.get<unknown>(`/installation/candidate-approval-intents/${encodeURIComponent(approvalIntentId)}`, readConfig);
    return parseInstallationApprovalIntent(response.data);
}

export async function recordInstallationApprovalIntent(
    candidateRecordId: string, csrfToken: string, idempotencyKey: string,
): Promise<InstallationApprovalIntentV1> {
    const response = await atlas.post<unknown>("/installation/candidate-approval-intents", { candidate_record_id: candidateRecordId }, {
        withCredentials: true,
        headers: { "X-Atlas-CSRF-Token": csrfToken, "Idempotency-Key": idempotencyKey },
    });
    return parseInstallationApprovalIntent(response.data);
}

export function approvalIntentIdempotencyKey(): string {
    return `mission-control-approval-evidence-${crypto.randomUUID()}`;
}
