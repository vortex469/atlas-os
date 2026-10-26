import type { DoctorCheck, DoctorReport } from "../types/doctor";
import { evidenceTimestamp } from "../utils/healthPresentation";

export class DoctorResponseError extends Error {
    constructor() {
        super("The health-check report is incomplete or unreadable. Run Doctor to try again.");
    }
}

function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

function strings(value: unknown): value is string[] {
    return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function parseCheck(value: unknown): DoctorCheck {
    if (!record(value) || typeof value.name !== "string" || !value.name.trim()
        || typeof value.passed !== "boolean") throw new DoctorResponseError();
    const error = value.error === undefined ? null : value.error;
    if (error !== null && typeof error !== "string") throw new DoctorResponseError();
    return { name: value.name, passed: value.passed, error };
}

export function parseDoctorReport(value: unknown): DoctorReport {
    if (!record(value)) throw new DoctorResponseError();
    // These optional arrays have defaults in Core's published Doctor DTO.
    const data: Record<string, unknown> = { checks: [], critical: [], warnings: [], information: [], ...value };
    if ((data.status !== "healthy" && data.status !== "degraded" && data.status !== "critical")
        || typeof data.score !== "number" || !Number.isInteger(data.score) || data.score < 0 || data.score > 100
        || typeof data.checked_at !== "string" || evidenceTimestamp(data.checked_at) === null
        || typeof data.configuration_ok !== "boolean" || !Array.isArray(data.checks)
        || !strings(data.critical) || !strings(data.warnings) || !strings(data.information)) {
        throw new DoctorResponseError();
    }
    return {
        status: data.status, score: data.score, checked_at: data.checked_at, configuration_ok: data.configuration_ok,
        checks: data.checks.map(parseCheck), critical: data.critical, warnings: data.warnings, information: data.information,
    };
}
