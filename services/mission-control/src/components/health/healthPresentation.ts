import type { HealthState } from "./HealthStatusPrimitive";

/**
 * Helper to map common service status strings to HealthState.
 * Preserves fail-closed semantics: unknown inputs → unknown state.
 */
export function mapServiceStatusToHealthState(
    status: unknown,
): HealthState {
    if (typeof status !== "string" || !status.trim()) {
        return "unknown";
    }

    const normalized = status.trim().toLowerCase();

    if (
        normalized === "healthy" ||
        normalized === "online" ||
        normalized === "success"
    ) {
        return "healthy";
    }
    if (normalized === "degraded" || normalized === "warning") {
        return "degraded";
    }
    if (normalized === "unavailable" || normalized === "offline") {
        return "unavailable";
    }
    if (normalized === "blocked") {
        return "blocked";
    }
    if (
        normalized === "critical" ||
        normalized === "error" ||
        normalized === "failed"
    ) {
        return "degraded"; // Critical errors are presented as degraded state
    }

    return "unknown";
}

/**
 * Check if evidence timestamp is considered stale.
 * Default: > 5 minutes old is stale.
 */
export function isEvidenceStale(
    timestamp: Date | null | undefined,
    staleThresholdMs: number = 5 * 60 * 1000,
): boolean {
    if (!timestamp || !Number.isFinite(timestamp.getTime())) {
        return true;
    }

    const now = new Date();
    const ageMs = now.getTime() - timestamp.getTime();
    return ageMs < 0 || ageMs > staleThresholdMs;
}
