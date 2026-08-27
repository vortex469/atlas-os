import { atlas } from "./atlas";
import type {
    InstallationCandidateAdmissionReason,
    InstallationCandidateAdmissionV1,
} from "../types/installationCandidateAdmission";

const REASONS: readonly InstallationCandidateAdmissionReason[] = [
    "input_invalid", "input_unavailable", "installation_plan_not_review_ready",
    "destination_selection_not_active", "destination_selection_expired",
    "destination_identity_unavailable", "destination_replaced_or_moved",
    "capability_assessment_stale", "capability_assessment_mismatched",
    "capability_assessment_not_admissible", "authority_invariant_violated",
];
const ADMISSION_KEYS = [
    "schema", "plan_fingerprint", "selection_fingerprint",
    "selected_destination_fingerprint", "current_destination_fingerprint",
    "capability_assessment_fingerprint", "provider_fact_set_fingerprint",
    "evaluated_at", "status", "reason_codes", "candidate_record", "approved",
    "executable", "deployable", "dispatchable", "agent_execution_supported",
    "candidate_creation_allowed", "admission_fingerprint",
] as const;
const RECORD_KEYS = [
    "schema", "item_id", "catalog_entry_id", "plan_fingerprint", "selection_id",
    "selected_destination_fingerprint", "current_destination_fingerprint",
    "capability_assessment_fingerprint", "provider_fact_set_fingerprint",
    "evaluated_at", "valid_until", "approved", "executable", "deployable",
    "dispatchable", "agent_execution_supported", "record_fingerprint",
] as const;
const FALSE_FLAGS = ["approved", "executable", "deployable", "dispatchable", "agent_execution_supported"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
    return Object.keys(value).length === keys.length && keys.every((key) => key in value);
}

function strings(value: Record<string, unknown>, keys: readonly string[]): boolean {
    return keys.every((key) => typeof value[key] === "string");
}

export function parseInstallationCandidateAdmission(value: unknown): InstallationCandidateAdmissionV1 {
    if (!isRecord(value) || !hasExactKeys(value, ADMISSION_KEYS) || value.schema !== "installation-candidate-admission-v1") {
        throw new Error("Invalid installation candidate admission response.");
    }
    const stringKeys = ADMISSION_KEYS.filter((key) => !["reason_codes", "candidate_record", "approved", "executable", "deployable", "dispatchable", "agent_execution_supported", "candidate_creation_allowed"].includes(key));
    const reasons = value.reason_codes;
    if (!strings(value, stringKeys) || !Array.isArray(reasons) || reasons.some((reason) => !REASONS.includes(reason as InstallationCandidateAdmissionReason))) {
        throw new Error("Invalid installation candidate admission response.");
    }
    const expectedOrder = REASONS.filter((reason) => reasons.includes(reason));
    if (reasons.length !== expectedOrder.length || reasons.some((reason, index) => reason !== expectedOrder[index])) {
        throw new Error("Installation candidate admission reasons are not canonically ordered.");
    }
    if (!["admitted_but_non_executable", "not_admitted"].includes(String(value.status)) ||
        FALSE_FLAGS.some((flag) => value[flag] !== false) || value.candidate_creation_allowed !== false) {
        throw new Error("Invalid non-authorizing installation candidate admission response.");
    }
    const candidate = value.candidate_record;
    if (candidate !== null) {
        if (!isRecord(candidate) || !hasExactKeys(candidate, RECORD_KEYS) || candidate.schema !== "installation-candidate-record-v1" ||
            !strings(candidate, RECORD_KEYS.filter((key) => !FALSE_FLAGS.includes(key as typeof FALSE_FLAGS[number]))) ||
            FALSE_FLAGS.some((flag) => candidate[flag] !== false)) {
            throw new Error("Invalid non-executable installation candidate record response.");
        }
    }
    const admitted = value.status === "admitted_but_non_executable";
    if (admitted !== (reasons.length === 0 && candidate !== null)) {
        throw new Error("Installation candidate admission status is inconsistent.");
    }
    return value as unknown as InstallationCandidateAdmissionV1;
}

export async function getInstallationCandidateAdmission(itemId: string, selectionId: string): Promise<InstallationCandidateAdmissionV1> {
    const response = await atlas.get<unknown>(
        `/installation/candidate-admissions/${encodeURIComponent(itemId)}/${encodeURIComponent(selectionId)}`,
        { withCredentials: true },
    );
    return parseInstallationCandidateAdmission(response.data);
}
