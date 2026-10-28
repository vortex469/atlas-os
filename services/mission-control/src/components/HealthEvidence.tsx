import { useContext, useEffect, useState } from "react";
import { evidenceText, evidenceTimestamp, healthReason, healthState } from "../utils/healthPresentation";
import { HealthEvidenceContext } from "./healthEvidenceContext";
import { HealthStatusBadge } from "./health/HealthStatusPrimitive";
import type { HealthState } from "./health/HealthStatusPrimitive";

export function HealthEvidence({ status, reason, checkedAt, stale = false, compact = false }: {
    status: unknown;
    reason?: unknown;
    checkedAt?: unknown;
    stale?: boolean;
    compact?: boolean;
}) {
    const snapshot = useContext(HealthEvidenceContext);
    const state = healthState(status);
    const message = healthReason(reason);
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
    const rawState = raw?.trim().toLowerCase();
    const rawAddsMeaning = ["warning", "critical", "error", "failed"].includes(rawState ?? "");
    const showReportedStatus = Boolean(raw && rawState !== state.toLowerCase() && (!compact || rawAddsMeaning));
    const showUnavailableTime = !compact || (checkedAt !== undefined && checkedAt !== null);

    return (
        <div className="min-w-0 space-y-1 break-words text-sm" data-health-state={isStale ? "Unknown" : state}>
            <div className="flex flex-wrap items-center gap-2">
                <HealthStatusBadge state={state.toLowerCase() as HealthState} isStale={isStale} />
                {isStale && <span className="text-mc-text-muted">Last known status: {state} · Current status unknown</span>}
            </div>
            {showReportedStatus && (
                <p className="text-xs text-mc-text-muted">Reported status: {raw}</p>
            )}
            {message && <p className="text-mc-text-secondary">{message}</p>}
            {state === "Unknown" && !message && <p className="text-mc-text-muted">No status information is available.</p>}
            {(validTime || showUnavailableTime) && <p className="text-xs text-mc-text-muted">
                {validTime ? <>{isStale ? "Last checked (UTC)" : "Checked (UTC)"} <time dateTime={timestamp!}>{formatUtcTimestamp(parsed)}</time></>
                    : "Check time unavailable."}
            </p>}
        </div>
    );
}

function formatUtcTimestamp(value: number): string {
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
    }).format(value);
}
