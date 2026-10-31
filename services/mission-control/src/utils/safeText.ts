// Bound operator-facing text and suppress common credential and URL patterns.
export function safeText(value: unknown): string {
    if (typeof value !== "string") return "";
    if (/(?:bearer\s|token|secret|password|api[_ -]?key|authorization|cookie|https?:\/\/|sk-[a-z0-9])/i.test(value)) {
        return "[Sensitive text withheld]";
    }
    return value.slice(0, 240);
}
