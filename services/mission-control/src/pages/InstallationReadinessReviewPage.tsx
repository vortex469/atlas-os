import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getInstallationReadinessReview, LINKAGE_KEYS } from "../api/installationReadinessReview";
import type { FingerprintV1, InstallationReadinessReviewResponseV1 } from "../types/installationReadinessReview";

const BLOCKER_LABELS: Record<string, string> = {
    missing_evidence: "Missing evidence", ownership_mismatch: "Ownership mismatch",
    linkage_mismatch: "Linkage mismatch", fingerprint_mismatch: "Fingerprint mismatch",
    invalid_evidence: "Invalid evidence", stale_evidence: "Stale evidence",
    expired_evidence: "Expired evidence", terminal_ambiguity: "Terminal ambiguity",
    agent_evidence_unavailable: "Agent evidence unavailable", source_unavailable: "Source unavailable",
    installation_capability_unsupported: "Installation capability unsupported",
    execution_admission_not_defined: "Execution admission is not defined",
};

export function InstallationReadinessReviewPage() {
    const { candidateRecordId = "" } = useParams<{ candidateRecordId: string }>();
    const [response, setResponse] = useState<InstallationReadinessReviewResponseV1 | null>(null);
    const [loading, setLoading] = useState(candidateRecordId.length > 0);
    const [error, setError] = useState(false);

    useEffect(() => {
        if (!candidateRecordId) return;
        let current = true;
        getInstallationReadinessReview(candidateRecordId)
            .then((value) => { if (current) setResponse(value); })
            .catch(() => { if (current) setError(true); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [candidateRecordId]);

    return <main className="mx-auto max-w-6xl p-6 text-slate-200">
        <Link to="/discovery" className="text-sm text-blue-300">← Discovery</Link>
        <h1 className="mt-4 text-2xl font-semibold">Installation readiness review</h1>
        <p className="mt-2 text-sm text-slate-300">Authenticated, operator-owned, Core-local evidence review. This read does not refresh or consume evidence.</p>
        <AuthorityNotice />
        {!candidateRecordId && <p role="status" className="mt-6">No candidate record selected.</p>}
        {loading && <p role="status" className="mt-6">Loading installation readiness review…</p>}
        {!loading && error && <section role="alert" className="mt-6 rounded border border-red-500/40 p-4">
            <h2 className="font-semibold text-red-200">Review unavailable</h2>
            <p className="mt-1 text-sm">Installation readiness review is unavailable.</p>
            <p className="mt-1 text-xs text-slate-400">No candidate, operator, evidence, endpoint, credential, or internal source detail is disclosed.</p>
        </section>}
        {!loading && !error && response && <Review response={response} />}
    </main>;
}

function AuthorityNotice() {
    return <aside aria-label="Read-only authority boundary" className="mt-4 rounded border border-amber-400/40 bg-amber-400/5 p-4 text-sm text-amber-100">
        <p className="font-semibold">Read-only evidence — no authority is granted.</p>
        <p className="mt-1">This review is not installation, execution, dispatch, retry or resend, Agent invocation, workflow start, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or permission to mutate anything.</p>
        <p className="mt-1">Readiness gated is not approval, admission, authorization, installability, or executability. Execution admission remains undefined.</p>
    </aside>;
}

function Review({ response }: { response: InstallationReadinessReviewResponseV1 }) {
    const { review, audit_evidence: audit } = response;
    return <div className="mt-6 space-y-6">
        <section aria-labelledby="readiness-state-heading" className="rounded border border-slate-700 p-4">
            <h2 id="readiness-state-heading" className="font-semibold">{review.readiness === "blocked" ? "Blocked" : "Readiness gated — execution admission is not defined"}</h2>
            <p className="mt-2 text-sm">Observed {review.observed_at}. Source: Core-local owner-scoped evidence.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Candidate record ID" value={review.candidate_record_id} />
                <Value name="Authenticated operator" value={review.operator_id} />
                <Value name="Review ID" value={review.review_id} />
                <Value name="Review fingerprint" value={review.review_fingerprint.value} />
            </dl>
            <h3 className="mt-4 text-sm font-semibold">Ordered blockers</h3>
            <ol aria-label="Ordered readiness blockers" className="mt-2 list-decimal pl-6 text-sm">
                {review.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker]} <code className="text-xs text-slate-400">{blocker}</code></li>)}
            </ol>
        </section>

        <section aria-labelledby="evidence-chain-heading" className="rounded border border-slate-700 p-4">
            <h2 id="evidence-chain-heading" className="font-semibold">v0.20–v0.33 evidence chain</h2>
            <p className="mt-1 text-sm text-slate-300">Current means valid at the review time under the released evidence contract. Expired or stale evidence remains evidence only and blocks readiness; this page never extends, refreshes, or restarts a validity window.</p>
            <ol aria-label="Installation evidence chain" className="mt-4 space-y-3">
                {review.evidence.map((item) => <li key={item.release} className="rounded border border-slate-800 p-3 text-sm">
                    <p className="font-semibold">{item.release} · {item.evidence_kind} · {item.evidence_state}</p>
                    <p className="mt-1 break-all text-xs">Evidence ID: {item.evidence_id ?? "Not available"}</p>
                    <p className="mt-1 break-all text-xs">Fingerprint: {item.evidence_fingerprint?.value ?? "Not available"}</p>
                    <p className="mt-1 text-xs">Valid until: {item.valid_until ?? "No released expiry"}</p>
                </li>)}
            </ol>
        </section>

        <section aria-labelledby="linkage-heading" className="rounded border border-slate-700 p-4">
            <h2 id="linkage-heading" className="font-semibold">Required linkage and fingerprints</h2>
            {!review.linkage && <p className="mt-2 text-sm">Exact linkage is unavailable; the review remains blocked.</p>}
            {review.linkage && <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                {LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(review.linkage?.[key])} />)}
            </dl>}
        </section>

        <section aria-labelledby="audit-heading" className="rounded border border-slate-700 p-4">
            <h2 id="audit-heading" className="font-semibold">Read-only audit evidence</h2>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Outcome" value={audit.outcome} />
                <Value name="Correlation ID" value={audit.correlation_id} />
                <Value name="Operator fingerprint" value={audit.operator_fingerprint.value} />
                <Value name="Audit fingerprint" value={audit.evidence_fingerprint.value} />
                <Value name="Receipt fingerprint" value={audit.v033_receipt_fingerprint?.value ?? "Not available"} />
                <Value name="Linkage fingerprint" value={audit.linkage_fingerprint?.value ?? "Not available"} />
                <Value name="Owner-scoped local readers" value={String(audit.source_was_owner_scoped_local_readers)} />
                <Value name="Mutation attempted" value={String(audit.mutation_attempted)} />
                <Value name="Execution attempted" value={String(audit.execution_attempted)} />
            </dl>
        </section>

        <section aria-labelledby="flags-heading" className="rounded border border-slate-700 p-4">
            <h2 id="flags-heading" className="font-semibold">Fixed authority fields</h2>
            <dl aria-label="Non-authorizing authority fields" className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <Value name="Evidence only" value="true" /><Value name="Read only" value="true" />
                <Value name="Execution admission granted" value="false" /><Value name="Execution authorized" value="false" />
                <Value name="Installation allowed" value="false" /><Value name="Dispatch allowed" value="false" />
                <Value name="Worker allowed" value="false" /><Value name="Workflow allowed" value="false" />
                <Value name="Deployment allowed" value="false" /><Value name="Mutation allowed" value="false" />
                <Value name="Retry allowed" value="false" /><Value name="Replay allowed" value="false" />
            </dl>
        </section>
    </div>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
