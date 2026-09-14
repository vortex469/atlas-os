import { healthState } from "../../utils/healthPresentation";
import type { HealthState } from "./HealthStatusPrimitive";

/**
 * Helper to map common service status strings to HealthState.
 * Preserves fail-closed semantics: unknown inputs → unknown state.
 */
export function mapServiceStatusToHealthState(
    status: unknown,
): HealthState {
    return healthState(status).toLowerCase() as HealthState;
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
