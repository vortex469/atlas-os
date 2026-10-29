import { HealthEvidence } from "../../components/HealthEvidence";
import { HealthEvidenceContext } from "../../components/healthEvidenceContext";
import { record, safeText } from "./overviewEvidence";
import type { OverviewEvidence } from "./useOverviewEvidence";

// Use the dashboard's independently refreshed evidence; never compute a second aggregate.
export function SystemHealthSummary({ evidence, loading = false }: { evidence: OverviewEvidence; loading?: boolean }) {
    const core = record(evidence.health?.data);
    const ace = record(evidence.summary?.data);
    const policy = record(evidence.policyHealth?.data);
    const sources = [
        { title: "Overall service status", evidence: evidence.health, status: core.atlas },
        { title: "System findings", evidence: evidence.summary, status: ace.status, reason: ace.summary },
        { title: "Policy settings check", evidence: evidence.policyHealth, status: policy.status, reason: policy.error, checkedAt: policy.checked_at },
    ];
    return (
        <section aria-label="Health reports" className="min-w-0 space-y-3 [overflow-wrap:anywhere]">
            {sources.map(source => {
                const hasData = source.evidence?.data !== undefined;
                const unavailable = source.evidence?.unavailable === true;
                const checking = loading && !hasData && !unavailable;
                const showHealth = !checking && !(unavailable && !hasData);
                const unavailableMessage = source.evidence?.stale && hasData
                    ? "Refresh failed. Showing the last available information."
                    : "Current information could not be loaded.";
                return (
                    <article key={source.title} aria-label={source.title} className="min-w-0 space-y-1">
                        <h4 className="font-semibold">{source.title}</h4>
                        {checking && <p role="status">Checking…</p>}
                        {unavailable && <p>{unavailableMessage}</p>}
                        {showHealth && <HealthEvidenceContext.Provider value={{ stale: source.evidence?.stale === true }}>
                            <HealthEvidence
                                compact
                                status={unavailable && !source.evidence?.stale ? undefined : safeText(source.status)}
                                reason={safeText(source.reason)}
                                checkedAt={source.checkedAt}
                            />
                        </HealthEvidenceContext.Provider>}
                    </article>
                );
            })}
            <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">How to read health</summary>
                <p>Atlas shows each report separately and doesn't combine them into one score. Each report updates on its own, so check times may differ. Reports more than a minute old are marked out of date.</p>
            </details>
        </section>
    );
}
