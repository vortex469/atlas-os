import { atlas } from "./atlas";
import { parseInstallationCandidateRecord } from "./installationCandidateAdmission";
import type {
    InstallationCandidateRecordCollectionV1,
    InstallationCandidateRecordEnvelopeV1,
} from "../types/installationCandidateLifecycle";

const ENVELOPE_KEYS = [
    "schema", "candidate_record_id", "created_at", "admission_fingerprint",
    "candidate_record", "envelope_fingerprint", "lifecycle_state",
] as const;

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
    return Object.keys(value).length === keys.length && keys.every((key) => key in value);
}

export function parseInstallationCandidateRecordEnvelope(value: unknown): InstallationCandidateRecordEnvelopeV1 {
    if (!isObject(value) || !exact(value, ENVELOPE_KEYS) ||
        value.schema !== "installation-candidate-record-envelope-v1" ||
        !["candidate_record_id", "created_at", "admission_fingerprint", "envelope_fingerprint"].every((key) => typeof value[key] === "string") ||
        !["active", "expired"].includes(String(value.lifecycle_state))) {
        throw new Error("Invalid installation candidate record envelope response.");
    }
    const candidateRecord = parseInstallationCandidateRecord(value.candidate_record);
    return { ...value, candidate_record: candidateRecord } as unknown as InstallationCandidateRecordEnvelopeV1;
}

export function parseInstallationCandidateRecordCollection(value: unknown): InstallationCandidateRecordCollectionV1 {
    if (!isObject(value) || !exact(value, ["records"]) || !Array.isArray(value.records)) {
        throw new Error("Invalid installation candidate record collection response.");
    }
    return { records: value.records.map(parseInstallationCandidateRecordEnvelope) };
}

const readConfig = { withCredentials: true };
const mutationConfig = (csrfToken: string) => ({
    withCredentials: true,
    headers: { "X-Atlas-CSRF-Token": csrfToken },
});

export async function listInstallationCandidateRecords(): Promise<InstallationCandidateRecordEnvelopeV1[]> {
    const response = await atlas.get<unknown>("/installation/candidate-records", readConfig);
    return parseInstallationCandidateRecordCollection(response.data).records;
}

export async function getInstallationCandidateRecord(candidateRecordId: string): Promise<InstallationCandidateRecordEnvelopeV1> {
    const response = await atlas.get<unknown>(`/installation/candidate-records/${encodeURIComponent(candidateRecordId)}`, readConfig);
    return parseInstallationCandidateRecordEnvelope(response.data);
}

export async function preserveInstallationCandidateRecord(
    input: { item_id: string; selection_id: string }, csrfToken: string, idempotencyKey: string,
): Promise<InstallationCandidateRecordEnvelopeV1> {
    const response = await atlas.post<unknown>("/installation/candidate-records", input, {
        ...mutationConfig(csrfToken), headers: { ...mutationConfig(csrfToken).headers, "Idempotency-Key": idempotencyKey },
    });
    return parseInstallationCandidateRecordEnvelope(response.data);
}

export async function deleteInstallationCandidateRecord(candidateRecordId: string, csrfToken: string): Promise<void> {
    await atlas.delete(`/installation/candidate-records/${encodeURIComponent(candidateRecordId)}`, mutationConfig(csrfToken));
}

export function candidateRecordIdempotencyKey(): string {
    return `mission-control-preserve-${crypto.randomUUID()}`;
}
