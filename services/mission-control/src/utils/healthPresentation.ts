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

export function healthReason(value: unknown): string | null {
    const text = evidenceText(value);
    if (!text) return null;
    const { errno, message } = parseHealthError(text);
    switch (message.toLowerCase()) {
        case "connection refused": return "Atlas Core's connection to this address was refused.";
        case "no route to host": return "The service could not be reached over the network.";
        case "network is unreachable": return "Atlas Core has no reachable network path to the service host.";
        case "name or service not known":
        case "temporary failure in name resolution":
        case "getaddrinfo failed": return "Atlas Core could not resolve the service host name.";
        case "connection timed out":
        case "timed out": return "Atlas Core got no response before the check timed out.";
        default: return errno ? message || "The connection failed." : text;
    }
}

export function healthNextCheck(value: unknown): string | null {
    const text = evidenceText(value);
    if (!text) return null;
    const { message } = parseHealthError(text);
    switch (message.toLowerCase()) {
        case "connection refused":
            return "On the service computer, confirm the app is listening on this port. If it runs in Docker, check PORTS with docker ps; if blank, publish the port unless the container uses host networking. Then test from Atlas Core.";
        case "no route to host":
            return "Check the target address and the network or firewall route from Atlas Core to the service host.";
        case "network is unreachable":
            return "Check the target address and routing between Atlas Core and the service host.";
        case "name or service not known":
        case "temporary failure in name resolution":
        case "getaddrinfo failed":
            return "Check that the host name is correct and resolves from the machine running Atlas Core.";
        case "connection timed out":
        case "timed out":
            return "Check that the service is responding and that network or firewall rules allow access from Atlas Core.";
        default:
            return null;
    }
}

function parseHealthError(text: string): { errno: boolean; message: string } {
    const trimmed = text.trim();
    const errnoMessage = /^\[Errno -?\d+\]\s*(.*)$/i.exec(trimmed);
    return {
        errno: errnoMessage !== null,
        message: errnoMessage ? errnoMessage[1].trim() : trimmed,
    };
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
