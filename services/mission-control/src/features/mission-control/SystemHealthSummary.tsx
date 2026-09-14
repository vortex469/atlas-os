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
        { title: "Atlas Core health aggregate", evidence: evidence.health, status: core.atlas },
        { title: "ACE assessment", evidence: evidence.summary, status: ace.status, reason: ace.summary },
        { title: "Policy reload", evidence: evidence.policyHealth, status: policy.status, reason: policy.error, checkedAt: policy.checked_at },
    ];
    return (
        <section aria-label="System health" className="min-w-0 space-y-3 [overflow-wrap:anywhere]">
            <h3 className="font-semibold text-mc-text-primary">System health</h3>
            <p>Source-reported health from Atlas Core. No combined health score is calculated here. Timestamped evidence older than 60 seconds is marked stale.</p>
            {sources.map(source => (
                <article key={source.title} aria-label={source.title} className="min-w-0 space-y-1">
                    <h4 className="font-semibold">{source.title}</h4>
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
