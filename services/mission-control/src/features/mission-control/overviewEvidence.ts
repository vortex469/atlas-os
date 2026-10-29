import { mapServiceStatusToHealthState } from "../../components/health/healthPresentation";
import { evidenceTimestamp } from "../../utils/healthPresentation";

export const record = (value: unknown): Record<string, unknown> =>
    value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
export const rows = (value: unknown): Record<string, unknown>[] =>
    Array.isArray(value) ? value.map(record) : [];

// Display only allowlisted fields, never arbitrary configuration/details/error bodies.
// Suppress sensitive free text as a whole rather than partially exposing credentials.
export function safeText(value: unknown): string {
    if (typeof value !== "string") return "";
    if (/(?:bearer\s|token|secret|password|api[_ -]?key|authorization|cookie|https?:\/\/|sk-[a-z0-9])/i.test(value)) return "[Sensitive text withheld]";
    return value.slice(0, 240);
}
export function timestamp(value: unknown): Date | null {
    const parsed = evidenceTimestamp(value);
    return parsed === null ? null : new Date(parsed);
}
export const status = (value: unknown) => mapServiceStatusToHealthState(value);
export function healthPriority(value: unknown): number {
    switch (status(value)) {
        case "blocked": return 0;
        case "unavailable": return 1;
        case "degraded": return 2;
        case "unknown": return 3;
        default: return 4;
    }
}
export function detailPath(prefix: string, id: unknown): string | null {
    if (typeof id !== "string" || !id || id === "." || id === "..") return null;
    try {
        return `${prefix}/${encodeURIComponent(id)}`;
    } catch {
        // JSON can contain unpaired Unicode surrogates; never crash navigation.
        return null;
    }
}

// Compare full evidence before display redaction/truncation; distinct conditions must survive.
export function conditionKey(...parts: unknown[]): string {
    return JSON.stringify(parts);
}
