import type { InstallationPlan } from "../../types/installationPlan";

const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function InstallationPlanReview({
    plan,
    isLoading,
    unavailable,
}: {
    plan: InstallationPlan | null;
    isLoading: boolean;
    unavailable: boolean;
}) {
    return (
        <section aria-labelledby="installation-plan-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 id="installation-plan-heading" className="text-xl font-semibold text-white">Installation plan review</h2>
            <p className="mt-1 text-sm text-slate-400">
                Informational only. This plan is not approval, authorization, an execution candidate, or an executable workflow.
            </p>
            {isLoading && <p className="mt-4 text-sm text-slate-400">Loading installation plan…</p>}
            {!isLoading && unavailable && <p role="status" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">Installation plan is currently unavailable.</p>}
            {!isLoading && !unavailable && plan && <PlanDetails plan={plan} />}
        </section>
    );
}

function PlanDetails({ plan }: { plan: InstallationPlan }) {
    const nullable = (value: string | null) => value ?? "None";
    return (
        <div className="mt-5 space-y-5">
            <div className={`rounded-lg border p-4 ${plan.blockers.length === 0 ? "border-blue-500/30 bg-blue-500/10" : "border-amber-500/30 bg-amber-500/10"}`}>
                <p className="font-semibold text-slate-100">{label(plan.status)}</p>
                <p className="mt-1 text-sm text-slate-300">
                    {plan.blockers.length === 0
                        ? "Ready for operator review only; no execution authority has been granted."
                        : `${plan.blockers.length} unresolved blocker${plan.blockers.length === 1 ? "" : "s"}; this plan is not executable.`}
                </p>
            </div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Fingerprint algorithm" value={plan.fingerprint.algorithm} />
                <Value name="Fingerprint canonicalization" value={plan.fingerprint.canonicalization} />
                <Value name="Plan fingerprint" value={plan.fingerprint.value} />
                <Value name="Fingerprint purpose" value="Integrity linkage only — not approval" />
                <Value name="Application item" value={plan.application.item_id} />
                <Value name="Application catalog entry ID" value={plan.application.catalog_entry_id} />
                <Value name="Application display name" value={plan.application.display_name} />
                <Value name="Application release version" value={nullable(plan.application.release_version)} />
                <Value name="Deployment artifact state" value={label(plan.deployment_artifact.state)} />
                <Value name="Deployment artifact kind" value={plan.deployment_artifact.kind} />
                <Value name="Deployment repository path" value={nullable(plan.deployment_artifact.repository_path)} />
                <Value name="Deployment artifact service" value={nullable(plan.deployment_artifact.service)} />
                <Value name="Deployment artifact content digest" value={nullable(plan.deployment_artifact.content_digest)} />
                <Value name="Image state" value={label(plan.image.state)} />
                <Value name="Image reference" value={nullable(plan.image.reference)} />
                <Value name="Image digest" value={nullable(plan.image.digest)} />
                <Value name="Image release version" value={nullable(plan.image.release_version)} />
                <Value name="Schema" value={plan.schema_version} />
            </dl>
            <ReviewList title="Compatibility" empty="No compatibility records." rows={plan.compatibility.map((row) => `Environment: ${row.environment} · Result: ${label(row.result)} · Reason code: ${row.reason_code}`)} />
            <ReviewList title="Accepted evidence" empty="No accepted evidence records." rows={plan.accepted_evidence.map((row) => `Evidence ID: ${row.evidence_id} · Source class: ${row.source_class} · Source ID: ${row.source_id} · Subject: ${row.subject} · Claim: ${row.claim} · Immutable identity: ${row.immutable_identity} · Observed at: ${nullable(row.observed_at)} · Attested at: ${row.attested_at} · Freshness window seconds: ${row.freshness_window_seconds} · Trust: ${row.trust}`)} />
            <ReviewList title="Relationships" empty="No relationships listed." rows={plan.relationships.map((row) => `Kind: ${row.kind} · Item: ${row.item_id} · Required: ${row.required ? "Yes" : "No"} · Minimum version: ${nullable(row.minimum_version)} · Maximum version: ${nullable(row.maximum_version)}`)} />
            <ReviewList title="Blockers" empty="No unresolved blockers." rows={plan.blockers.map((row) => `${label(row.code)} — ${row.subject}`)} />
            <ReviewList title="Required operator confirmations" empty="No operator confirmations required." rows={plan.required_operator_confirmations.map((row) => `${label(row.code)} — ${row.prompt} (${row.subject})`)} />
            <ReviewList title="Risks" empty="No risks reported." rows={plan.risks.map((row) => `${label(row.severity)} · ${label(row.code)} — ${row.subject}`)} />
            <ReviewList title="Missing facts" empty="No missing facts." rows={plan.missing_facts.map((row) => `${label(row.code)} — ${row.subject}`)} />
            <ReviewList title="Prerequisites" empty="No prerequisites listed." rows={plan.prerequisites.map((row) => `Prerequisite ID: ${row.prerequisite_id} · Kind: ${row.kind} · State: ${row.state} · Description: ${row.description}`)} />
            <ReviewList title="Assumptions" empty="No assumptions listed." rows={plan.assumptions.map((row) => `Assumption ID: ${row.assumption_id} · Kind: ${row.kind} · Statement: ${row.statement}`)} />
            <ReviewList title="Provenance" empty="No provenance records." rows={plan.provenance.map((row) => `Claim: ${row.claim} · Source class: ${row.source_class} · Source ID: ${row.source_id} · Immutable identity: ${row.immutable_identity} · Observed at: ${nullable(row.observed_at)} · Attested at: ${nullable(row.attested_at)}`)} />
        </div>
    );
}

function ReviewList({ title, empty, rows }: { title: string; empty: string; rows: string[] }) {
    return <div><h3 className="text-sm font-semibold text-slate-200">{title}</h3>{rows.length === 0 ? <p className="mt-2 text-sm text-slate-500">{empty}</p> : <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">{rows.map((row, index) => <li className="break-all" key={`${index}-${row}`}>{row}</li>)}</ul>}</div>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
