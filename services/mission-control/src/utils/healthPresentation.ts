import type { AtlasHealth, ServiceHealth } from "../types/health";

export type HealthState = "Healthy" | "Degraded" | "Unavailable" | "Blocked" | "Unknown";

// Presentation aliases only. Never infer health from latency, HTTP, or other subsystems.
const states = new Map<string, HealthState>([
    ["healthy", "Healthy"], ["online", "Healthy"],
    ["warning", "Degraded"], ["degraded", "Degraded"], ["critical", "Degraded"],
    ["error", "Degraded"], ["failed", "Degraded"],
    ["offline", "Unavailable"], ["unavailable", "Unavailable"],
    ["blocked", "Blocked"], ["unknown", "Unknown"],
]);

export function healthState(value: unknown): HealthState {
    return typeof value === "string" ? states.get(value.trim().toLowerCase()) ?? "Unknown" : "Unknown";
}

export function evidenceText(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

// Require a timezone and a real calendar date. Date.parse alone normalizes
// impossible dates (for example February 30) into apparently valid evidence.
export function evidenceTimestamp(value: unknown): number | null {
    if (typeof value !== "string") return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/.exec(value);
    if (!match) return null;
    const [, year, month, day, hour, minute, second, zone] = match;
    const leap = +year % 4 === 0 && (+year % 100 !== 0 || +year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (+month < 1 || +month > 12 || +day < 1 || +day > days[+month - 1]
        || +hour > 23 || +minute > 59 || +second > 59
        || (zone !== "Z" && (+zone.slice(1, 3) > 23 || +zone.slice(4) > 59))) return null;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
}

export function evidenceRecord(value: unknown): Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value)
        ? value as Record<string, unknown> : {};
}

export function normalizeServiceHealth(value: unknown): ServiceHealth {
    const data = evidenceRecord(value);
    const finiteNumber = (value: unknown) => typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
    return {
        provider_id: evidenceText(data.provider_id) ?? "",
        status: evidenceText(data.status) ?? "unknown",
        latency_ms: finiteNumber(data.latency_ms),
        http_status: finiteNumber(data.http_status),
        message: evidenceText(data.message),
        details: evidenceRecord(data.details),
    };
}

export function normalizeAtlasHealth(value: unknown): AtlasHealth {
    const data = evidenceRecord(value);
    return {
        atlas: evidenceText(data.atlas) ?? "unknown",
        services: Object.fromEntries(Object.entries(evidenceRecord(data.services))
            .map(([name, service]) => [name, normalizeServiceHealth(service)])),
    };
}
