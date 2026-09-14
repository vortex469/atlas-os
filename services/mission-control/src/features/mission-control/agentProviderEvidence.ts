import { detailPath, record, status } from "./overviewEvidence";

// Public identity fields only; diagnostics and configuration are not overview labels.
export function publicLabel(value: unknown): string | null {
    if (typeof value !== "string" || !value.trim() || value.length > 100
        || !/^[\p{L}\p{N} ._()/-]+$/u.test(value)
        || /(?:bearer|token|secret|password|api[_ -]?key|authorization|sk-)/i.test(value)) return null;
    return value.trim();
}

export function providerDetailPath(id: unknown): string | null {
    return typeof id === "string" && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/.test(id) && publicLabel(id)
        ? detailPath("/providers", id) : null;
}

export function providerObservations(value: unknown) {
    if (!Array.isArray(value)) return null;
    const counts = new Map<unknown, number>();
    for (const entry of value) {
        const id = record(entry).id;
        counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    return value.map(entry => {
        const row = record(entry);
        const name = publicLabel(row.name);
        const path = providerDetailPath(row.id);
        const valid = Boolean(name && path && counts.get(row.id) === 1);
        return {
            name: valid ? name! : "Provider information unavailable",
            path: valid ? path : null,
            status: valid ? record(row.health).status : undefined,
            reason: valid ? record(row.health).message : undefined,
        };
    }).sort((a, b) => Number(status(a.status) === "healthy") - Number(status(b.status) === "healthy"));
}
