import { HealthEvidence } from "../../components/HealthEvidence";
import { HealthEvidenceContext } from "../../components/healthEvidenceContext";
import { record, safeText } from "./overviewEvidence";
import type { OverviewEvidence } from "./useOverviewEvidence";

// Use the dashboard's independently refreshed evidence; never compute a second aggregate.
export function SystemHealthSummary({ evidence }: { evidence: OverviewEvidence }) {
    const core = record(evidence.health?.data);
    const ace = record(evidence.summary?.data);
    const policy = record(evidence.policyHealth?.data);
    const sources = [
        { id: "atlas-health", title: "Atlas health", evidence: evidence.health, status: core.atlas },
        { id: "system-assessment", title: "System assessment", evidence: evidence.summary, status: ace.status, reason: ace.summary },
        { id: "policy-status", title: "Policy status", evidence: evidence.policyHealth, status: policy.status, reason: policy.error, checkedAt: policy.checked_at },
    ];
    return (
        <section aria-label="System health" className="min-w-0 space-y-3 [overflow-wrap:anywhere]">
            <p>Health reported by Atlas Core.</p>
            <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">How to read health</summary>
                <p>No combined health score is calculated here. Timestamped evidence older than 60 seconds is marked stale.</p>
                <p>Policy status reports whether the policy rules loaded successfully.</p>
                <p>Core aggregate update time is not supplied.</p>
            </details>
            {sources.map(source => (
                <article key={source.title} id={source.id} tabIndex={-1} aria-label={source.title} className="scroll-mt-24 min-w-0 space-y-1">
                    <h3 className="font-semibold">{source.title}</h3>
                    {source.evidence?.unavailable && <p>Evidence unavailable.{source.evidence.stale ? " Last-known observations only." : ""}</p>}
                    <HealthEvidenceContext.Provider value={{ stale: source.evidence?.stale === true }}>
                        <HealthEvidence
                            status={source.evidence?.unavailable && !source.evidence.stale ? undefined : safeText(source.status)}
                            reason={safeText(source.reason)}
                            checkedAt={source.checkedAt}
                        />
                    </HealthEvidenceContext.Provider>
                </article>
            ))}
            {Object.keys(record(core.services)).length === 0 && <p>No subsystem health evidence returned.</p>}
        </section>
    );
}
