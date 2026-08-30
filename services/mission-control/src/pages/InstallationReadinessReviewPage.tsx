import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getInstallationReadinessReview, LINKAGE_KEYS } from "../api/installationReadinessReview";
import { createExecutionPermissionGrant, executionPermissionGrantIdempotencyKey, listExecutionPermissionGrants } from "../api/executionPermissionGrant";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { FingerprintV1, InstallationReadinessReviewResponseV1 } from "../types/installationReadinessReview";
import { EXECUTION_PERMISSION_CONFIRMATION, type ExecutionPermissionGrantCreateV1, type ExecutionPermissionGrantResultV1 } from "../types/executionPermissionGrant";

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
        <PermissionGrants response={response} />
    </div>;
}

function PermissionGrants({ response }: { response: InstallationReadinessReviewResponseV1 }) {
    const session = useOperatorSession();
    const [grants, setGrants] = useState<ExecutionPermissionGrantResultV1[] | null>(null);
    const [error, setError] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const candidateId = response.review.candidate_record_id;

    useEffect(() => {
        let current = true;
        listExecutionPermissionGrants(candidateId)
            .then((value) => { if (current) setGrants(value.grants); })
            .catch(() => { if (current) setError(true); })
        return () => { current = false; };
    }, [candidateId]);

    const begin = () => setConfirming(true);
    const record = async () => {
        if (!session.csrfToken || submitting) return;
        setSubmitting(true); setError(false);
        const body: ExecutionPermissionGrantCreateV1 = {
            schema: "execution-permission-grant-create-v1",
            readiness_review_id: response.review.review_id,
            readiness_review_fingerprint: response.review.review_fingerprint,
            review_observed_at: response.review.observed_at,
            confirmation_text: EXECUTION_PERMISSION_CONFIRMATION,
            permission_scope: "future_execution_admission_consideration_only",
            execution_admission_granted: false, execution_authorized: false,
            installation_allowed: false, dispatch_allowed: false,
            mutation_allowed: false, replay_allowed: false,
        };
        try {
            const result = await createExecutionPermissionGrant(candidateId, body, session.csrfToken, executionPermissionGrantIdempotencyKey());
            setGrants((current) => [result, ...(current ?? [])]); setConfirming(false);
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    const mayCreate = response.review.readiness === "readiness_gated" && session.authenticated &&
        session.principal?.permissions.includes("installation.execution.permission.grant");
    return <section aria-labelledby="permission-grants-heading" className="rounded border border-slate-700 p-4">
        <h2 id="permission-grants-heading" className="font-semibold">Execution permission evidence</h2>
        <p className="mt-2 text-sm">This durable grant records permission evidence only. It is not installation, execution, dispatch, retry or resend, Agent invocation, workflow start, worker execution, Docker, Podman, shell or process execution, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or permission to mutate anything.</p>
        <p className="mt-2 text-sm">Core binds the authenticated operator and exact v0.20–v0.34 evidence/readiness fingerprints. Validity inherits at most 30 seconds; expiry never refreshes evidence. The review subject and idempotency subject are reserved permanently, with no replay.</p>
        {grants === null && !error && <p role="status" className="mt-4">Loading execution permission evidence…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>Execution permission evidence could not be recorded.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, or internal path is shown.</p></div>}
        {grants?.length === 0 && <p role="status" className="mt-4">No execution permission evidence has been recorded.</p>}
        {grants && grants.length > 0 && <ol aria-label="Execution permission grants" className="mt-4 space-y-4">{grants.map((item) => <Grant key={item.grant!.grant_id} result={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" onClick={begin} className="mt-4 rounded border border-blue-400 px-3 py-2 text-sm">Review permission evidence statement</button>}
        {mayCreate && confirming && <div aria-label="Permission evidence confirmation" className="mt-4 rounded border border-amber-400/40 p-4">
            <p className="font-semibold">Step 2 of 2 — explicitly confirm durable evidence</p>
            <p className="mt-2 text-sm">{EXECUTION_PERMISSION_CONFIRMATION}</p>
            <p className="mt-2 text-xs">This creates durable permission evidence only. It grants no execution admission or mutation authority.</p>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Record permission evidence</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
        </div>}
        {!mayCreate && <p className="mt-4 text-sm text-amber-200">Creation remains blocked. A current readiness-gated review, authenticated owner, dedicated permission, and valid CSRF session are required. Home Assistant remains non-installable and non-executable.</p>}
    </section>;
}

function Grant({ result }: { result: ExecutionPermissionGrantResultV1 }) {
    const grant = result.grant!; const status = result.status!; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h3 className="font-semibold">{status.lifecycle === "active" ? "Active permission evidence" : "Expired permission evidence"}</h3>
        <p className="mt-1">Lifecycle: {status.lifecycle}; disposition: {result.disposition}; record state: {grant.record_state}.</p>
        <p className="mt-1">Recorded {grant.recorded_at}; valid until {grant.valid_until}; observed {status.observed_at}. Expiry does not erase or refresh this append-only evidence.</p>
        <p className="mt-2">Confirmation: {grant.confirmation_text}</p>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2"><Value name="Authenticated operator" value={grant.operator_id} /><Value name="Grant ID" value={grant.grant_id} /><Value name="Grant fingerprint" value={grant.grant_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} /><Value name="v0.34 review ID" value={grant.linkage.v034_review_id} /><Value name="v0.34 review fingerprint" value={grant.linkage.v034_review_fingerprint.value} /><Value name="v0.34 audit fingerprint" value={grant.linkage.v034_audit_evidence_fingerprint.value} /><Value name="v0.34 operator fingerprint" value={grant.linkage.v034_operator_fingerprint.value} /><Value name="v0.20–v0.34 linkage fingerprint" value={grant.linkage.linkage_fingerprint.value} /><Value name="Request fingerprint" value={grant.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={grant.idempotency_key_fingerprint.value} /><Value name="Audit evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Audit outcome" value={audit.outcome} /><Value name="Audit correlation ID" value={audit.correlation_id} /></dl>
        <details className="mt-3"><summary>Required v0.20–v0.34 evidence linkage</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">{LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(grant.linkage.readiness_linkage[key])} />)}</dl></details>
        <p className="mt-3 text-xs">Permanent reservation: true · raw idempotency key persisted: false · retry allowed: false · replay allowed: false.</p>
        <dl aria-label="Grant fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Execution admission granted", "Execution authorized", "Installation allowed", "Dispatch allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Retry allowed", "Resend allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
