import { atlas } from "./atlas";
import type { WorkerIntakeAdmissionCollectionV1, WorkerIntakeAdmissionResultV1 } from "../types/workerIntakeAdmission";

const fp = (value: unknown) => typeof value === "object" && value !== null && (value as Record<string, unknown>).algorithm === "sha256" && /^[a-f0-9]{64}$/.test(String((value as Record<string, unknown>).value));
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const forbiddenTrue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.some(forbiddenTrue);
    if (!object(value)) return false;
    return Object.entries(value).some(([key, item]) => (key !== "ephemeral_workspace_allowed" && /(allowed|authorized|attempted|exists|reachable|contacted|started|enqueued|dequeued|claimed|executable|serialized|defined|released|consumed|replaceable|supersedable|bypass|polling|registered|available|authenticated|reserved|sent|open|constructed)/.test(key) && item === true) || forbiddenTrue(item));
};

export function parseWorkerIntakeAdmissionResult(value: unknown): WorkerIntakeAdmissionResultV1 {
    if (!object(value) || value.schema !== "worker-intake-admission-result-v1" || value.evidence_only !== true || forbiddenTrue(value) || value.ok !== (object(value.admission) && value.error === null) || (value.admission === null) === (value.error === null)) throw new Error("Invalid worker intake admission response.");
    if (value.ok) {
        const admission = value.admission;
        if (!object(admission) || admission.schema !== "worker-intake-admission-v1" || admission.eligibility !== "worker_intake_admission_recorded" || forbiddenTrue(admission)) throw new Error("Invalid worker intake admission response.");
    } else if (!object(value.error) || value.error.redacted !== true || forbiddenTrue(value.error)) {
        throw new Error("Invalid worker intake admission response.");
    }
    return value as WorkerIntakeAdmissionResultV1;
}

export function parseWorkerIntakeAdmissionCollection(value: unknown): WorkerIntakeAdmissionCollectionV1 {
    if (!object(value) || value.schema !== "worker-intake-admission-collection-v1" || value.evidence_only !== true || !Array.isArray(value.items) || value.count !== value.items.length || value.items.length > 100 || !fp(value.collection_fingerprint) || forbiddenTrue(value)) throw new Error("Invalid worker intake admission collection.");
    for (const item of value.items) {
        if (!object(item) || item.schema !== "worker-intake-admission-v1" || item.eligibility !== "worker_intake_admission_recorded" || forbiddenTrue(item)) throw new Error("Invalid worker intake admission collection.");
    }
    return value as WorkerIntakeAdmissionCollectionV1;
}

const path = (candidateId: string) => `/installation/candidate-records/${encodeURIComponent(candidateId)}/worker-intake-admissions`;
export async function listWorkerIntakeAdmissions(candidateId: string) { const response = await atlas.get<unknown>(path(candidateId), { withCredentials: true }); return parseWorkerIntakeAdmissionCollection(response.data); }
export async function getWorkerIntakeAdmission(candidateId: string, admissionId: string) { const response = await atlas.get<unknown>(`${path(candidateId)}/${encodeURIComponent(admissionId)}`, { withCredentials: true }); return parseWorkerIntakeAdmissionResult(response.data); }
