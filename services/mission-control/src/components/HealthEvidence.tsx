import { useContext, useEffect, useState } from "react";
import { evidenceText, evidenceTimestamp, healthState } from "../utils/healthPresentation";
import { HealthEvidenceContext } from "./healthEvidenceContext";
import { HealthStatusBadge } from "./health/HealthStatusPrimitive";
import type { HealthState } from "./health/HealthStatusPrimitive";

export function HealthEvidence({ status, reason, checkedAt, stale = false }: {
    status: unknown;
    reason?: unknown;
    checkedAt?: unknown;
    stale?: boolean;
}) {
    const snapshot = useContext(HealthEvidenceContext);
    const state = healthState(status);
    const message = evidenceText(reason);
    const timestamp = evidenceText(checkedAt);
    const parsed = evidenceTimestamp(timestamp);
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        const timer = window.setInterval(() => setNow(Date.now()), 30_000);
        return () => window.clearInterval(timer);
    }, []);
    const validTime = parsed !== null && parsed <= now;
    // Age is a UI freshness hint (two refresh intervals), not a Core health decision.
    const isStale = stale || snapshot.stale || (validTime && now - parsed > 60_000);
    const raw = evidenceText(status);

    return (
        <div className="min-w-0 space-y-1 break-words text-sm" data-health-state={isStale ? "Unknown" : state}>
            <div className="flex flex-wrap items-center gap-2">
                <HealthStatusBadge state={state.toLowerCase() as HealthState} isStale={isStale} />
                {isStale && <span className="text-mc-text-muted">Last-known status: {state} · Current state unknown</span>}
            </div>
            {raw && raw.trim().toLowerCase() !== state.toLowerCase() && (
                <p className="text-xs text-mc-text-muted">Source status: {raw}</p>
            )}
            {message && <p className="text-mc-text-secondary">{message}</p>}
            {state === "Unknown" && !message && <p className="text-mc-text-muted">No recognized health evidence.</p>}
            <p className="text-xs text-mc-text-muted">
                {validTime ? <>{isStale ? "Last checked" : "Current evidence · Checked"} <time dateTime={timestamp!}>{new Date(parsed).toISOString()}</time></>
                    : "Evidence age unknown · No valid source timestamp"}
            </p>
        </div>
    );
}
