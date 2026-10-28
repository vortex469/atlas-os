import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getInstallationReadinessReview, LINKAGE_KEYS } from "../api/installationReadinessReview";
import { createExecutionPermissionGrant, executionPermissionGrantIdempotencyKey, listExecutionPermissionGrants } from "../api/executionPermissionGrant";
import { InstallationExecutionAdmissions } from "../features/installation/InstallationExecutionAdmissions";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { FingerprintV1, InstallationReadinessBlockerV1, InstallationReadinessEvidenceKindV1, InstallationReadinessReviewResponseV1 } from "../types/installationReadinessReview";
import { EXECUTION_PERMISSION_CONFIRMATION, type ExecutionPermissionGrantCreateV1, type ExecutionPermissionGrantResultV1 } from "../types/executionPermissionGrant";

const BLOCKER_LABELS: Record<InstallationReadinessBlockerV1, string> = {
    missing_evidence: "Required evidence is missing",
    ownership_mismatch: "The evidence belongs to a different operator",
    linkage_mismatch: "The evidence does not link to this candidate",
    fingerprint_mismatch: "The evidence identity does not match",
    invalid_evidence: "The evidence could not be validated",
    stale_evidence: "The evidence is out of date",
    expired_evidence: "The evidence has expired",
    terminal_ambiguity: "The evidence has an unclear final state",
    agent_evidence_unavailable: "Agent validation evidence is unavailable",
    source_unavailable: "A required evidence source is unavailable",
    installation_capability_unsupported: "Atlas cannot install this application",
    execution_admission_not_defined: "The later execution review is not available",
};

const EVIDENCE_KIND_LABELS: Record<InstallationReadinessEvidenceKindV1, string> = {
    candidate_record: "Saved candidate review",
    approval_intent: "Recorded review decision",
    agent_install_container_validation: "Agent validation record",
    execution_request: "Saved request record",
    dispatch_handoff: "Saved handoff record",
    agent_intake_simulation: "Agent intake simulation",
    simulated_handoff_delivery: "Simulated delivery",
    real_agent_intake: "Agent intake record",
    dormant_delivery_wiring: "Dormant delivery setup",
    delivery_activation_preflight: "Delivery readiness check",
    operator_delivery_enablement: "Operator choice for later review",
    live_delivery_send: "Delivery send record",
    agent_live_intake_admission: "Agent admission record",
    inert_delivery_receipt: "Delivery receipt",
};

const EVIDENCE_STATE_LABELS: Record<InstallationReadinessReviewResponseV1["review"]["evidence"][number]["evidence_state"], string> = {
    current: "Current at last check",
    missing: "Missing",
    expired: "Expired",
    terminal: "Ended",
    unavailable: "Unavailable",
};

export function InstallationReadinessReviewPage() {
    const { candidateRecordId = "" } = useParams<{ candidateRecordId: string }>();
    return <InstallationReadinessReview key={candidateRecordId} candidateRecordId={candidateRecordId} />;
}

function InstallationReadinessReview({ candidateRecordId }: { candidateRecordId: string }) {
    const [response, setResponse] = useState<InstallationReadinessReviewResponseV1 | null>(null);
    const [loading, setLoading] = useState(candidateRecordId.length > 0);
    const [error, setError] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);

    useEffect(() => {
        if (!candidateRecordId) return;
        let current = true;
        void Promise.resolve().then(() => {
            if (!current) return;
            return getInstallationReadinessReview(candidateRecordId)
                .then((value) => {
                    if (!current) return;
                    if (value.review.candidate_record_id !== candidateRecordId.toLowerCase() || value.audit_evidence.candidate_record_id !== candidateRecordId.toLowerCase()) {
                        setError(true);
                        return;
                    }
                    setResponse(value);
                })
                .catch(() => { if (current) setError(true); })
                .finally(() => { if (current) setLoading(false); });
        });
        return () => { current = false; };
    }, [candidateRecordId, readAttempt]);

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
            <button type="button" onClick={() => {
                setResponse(null); setError(false); setLoading(true); setReadAttempt((attempt) => attempt + 1);
            }} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Reload review</button>
        </section>}
        {!loading && !error && response && <Review response={response} />}
    </main>;
}

function AuthorityNotice() {
    return <aside aria-label="Read-only authority boundary" className="mt-4 rounded border border-amber-400/40 bg-amber-400/5 p-4 text-sm text-amber-100">
        <p className="font-semibold">This page reviews saved evidence. It does not install anything or start work.</p>
        <p className="mt-1">Passing this check does not approve or authorize installation. Any later review is separate.</p>
    </aside>;
}

function Review({ response }: { response: InstallationReadinessReviewResponseV1 }) {
    const { review, audit_evidence: audit } = response;
    return <div className="mt-6 space-y-6">
        <section aria-labelledby="readiness-state-heading" className="rounded border border-slate-700 p-4">
            <h2 id="readiness-state-heading" className="font-semibold">{review.readiness === "blocked" ? "Blocked" : "Evidence check complete"}</h2>
            <p className="mt-2 text-sm">{review.readiness === "blocked"
                ? "The issues below prevent this candidate from reaching a later permission review."
                : "The evidence passed this check. Any later permission review is separate, and installation is still not authorized."}</p>
            <p className="mt-1 text-xs text-slate-400">Checked {review.observed_at}.</p>
            <h3 className="mt-4 text-sm font-semibold">What needs attention</h3>
            {review.blockers.length === 0
                ? <p className="mt-2 text-sm text-slate-300">No blocking issues were found in this check.</p>
                : <ol aria-label="Readiness issues" className="mt-2 list-disc pl-5 text-sm">
                    {review.blockers.map((blocker) => <li key={blocker}>{BLOCKER_LABELS[blocker]}</li>)}
                </ol>}
            <details className="mt-4 rounded border border-slate-800 p-3">
                <summary className="cursor-pointer text-sm font-medium">Review identity and technical codes</summary>
                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                    <Value name="Candidate record ID" value={review.candidate_record_id} />
                    <Value name="Authenticated operator" value={review.operator_id} />
                    <Value name="Review ID" value={review.review_id} />
                    <Value name="Review fingerprint" value={review.review_fingerprint.value} />
                </dl>
                {review.blockers.length > 0 && <ul aria-label="Technical readiness issue codes" className="mt-3 list-disc pl-5 text-xs text-slate-400">
                    {review.blockers.map((blocker) => <li key={blocker}><code>{blocker}</code></li>)}
                </ul>}
            </details>
        </section>

        <details className="rounded border border-slate-700 p-4">
            <summary className="cursor-pointer font-semibold">Evidence chain ({review.evidence.length} records)</summary>
            <p className="mt-2 text-sm text-slate-300">Statuses describe the last check. Expired or stale evidence stays recorded but blocks readiness; this review does not extend or refresh it.</p>
            <ol aria-label="Installation evidence chain" className="mt-4 space-y-3">
                {review.evidence.map((item) => <li key={item.release} className="rounded border border-slate-800 p-3 text-sm">
                    <p className="font-semibold">{EVIDENCE_KIND_LABELS[item.evidence_kind]} · {EVIDENCE_STATE_LABELS[item.evidence_state]}</p>
                    <details className="mt-2 text-xs text-slate-400">
                        <summary className="cursor-pointer">Record identity and expiry</summary>
                        <p className="mt-1">Release: {item.release} · Evidence kind: {item.evidence_kind} · Status: {item.evidence_state}</p>
                        <p className="mt-1 break-all">Evidence ID: {item.evidence_id ?? "Not available"}</p>
                        <p className="mt-1 break-all">Fingerprint: {item.evidence_fingerprint?.value ?? "Not available"}</p>
                        <p className="mt-1">Valid until: {item.valid_until ?? "No released expiry"}</p>
                    </details>
                </li>)}
            </ol>
        </details>

        <details className="rounded border border-slate-700 p-4">
            <summary className="cursor-pointer font-semibold">Technical evidence links</summary>
            {!review.linkage && <p className="mt-2 text-sm">Some evidence links are unavailable; the review remains blocked.</p>}
            {review.linkage && <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                {LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(review.linkage?.[key])} />)}
            </dl>}
        </details>

        <details className="rounded border border-slate-700 p-4">
            <summary className="cursor-pointer font-semibold">Audit record and authority flags</summary>
            <dl aria-label="Readiness audit record" className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Outcome code" value={audit.outcome} />
                <Value name="Correlation ID" value={audit.correlation_id} />
                <Value name="Operator fingerprint" value={audit.operator_fingerprint.value} />
                <Value name="Audit fingerprint" value={audit.evidence_fingerprint.value} />
                <Value name="Receipt fingerprint" value={audit.v033_receipt_fingerprint?.value ?? "Not available"} />
                <Value name="Linkage fingerprint" value={audit.linkage_fingerprint?.value ?? "Not available"} />
                <Value name="Owner-scoped local readers" value={String(audit.source_was_owner_scoped_local_readers)} />
                <Value name="Mutation attempted" value={String(audit.mutation_attempted)} />
                <Value name="Execution attempted" value={String(audit.execution_attempted)} />
            </dl>
            <dl aria-label="Non-authorizing authority fields" className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                <Value name="Evidence only" value="true" /><Value name="Read only" value="true" />
                <Value name="Execution admission granted" value="false" /><Value name="Execution authorized" value="false" />
                <Value name="Installation allowed" value="false" /><Value name="Dispatch allowed" value="false" />
                <Value name="Worker allowed" value="false" /><Value name="Workflow allowed" value="false" />
                <Value name="Deployment allowed" value="false" /><Value name="Mutation allowed" value="false" />
                <Value name="Retry allowed" value="false" /><Value name="Replay allowed" value="false" />
            </dl>
        </details>
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
            setGrants((current) => [
                result,
                ...(current ?? []).filter((item) => item.grant?.grant_id !== result.grant?.grant_id),
            ]);
            setConfirming(false);
        } catch { setError(true); }
        finally { setSubmitting(false); }
    };

    const mayCreate = response.review.readiness === "readiness_gated" && session.authenticated &&
        session.principal?.permissions.includes("installation.execution.permission.grant");
    return <><section aria-labelledby="permission-grants-heading" className="rounded border border-slate-700 p-4">
        <h2 id="permission-grants-heading" className="font-semibold">Save a choice for a future review</h2>
        <p className="mt-2 text-sm">This records your permission for this exact evidence chain to be considered later. It does not authorize or start installation or execution.</p>
        <p className="mt-2 text-sm text-slate-400">The record expires with the readiness review, within 30 seconds. It cannot be renewed or replayed.</p>
        {grants === null && !error && <p role="status" className="mt-4">Loading saved permission records…</p>}
        {error && <div role="alert" className="mt-4 rounded border border-red-500/40 p-3"><p>The permission record is unavailable or could not be saved.</p><p className="text-xs text-slate-400">The error is redacted; no credential, payload, command, log, address, or internal path is shown.</p></div>}
        {grants?.length === 0 && <p role="status" className="mt-4">No permission records saved yet.</p>}
        {grants && grants.length > 0 && <ol aria-label="Execution permission grants" className="mt-4 space-y-4">{grants.map((item) => <Grant key={item.grant!.grant_id} result={item} />)}</ol>}
        {mayCreate && !confirming && <button type="button" aria-label="Review permission choice" onClick={begin} className="mt-4 rounded border border-blue-400 px-3 py-2 text-sm">Review permission choice</button>}
        {mayCreate && confirming && <div aria-label="Permission evidence confirmation" className="mt-4 rounded border border-amber-400/40 p-4">
            <p className="font-semibold">Confirm saving your choice</p>
            <p className="mt-2 text-sm">{EXECUTION_PERMISSION_CONFIRMATION}</p>
            <p className="mt-2 text-xs">This saves evidence for a later review only. It does not grant execution permission or start work.</p>
            <details className="mt-3 text-xs text-slate-400"><summary className="cursor-pointer">Verify the exact review</summary>
                <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                    <Value name="Candidate record ID" value={candidateId} />
                    <Value name="Readiness review ID" value={response.review.review_id} />
                    <Value name="Review fingerprint" value={response.review.review_fingerprint.value} />
                    <Value name="Review checked at" value={response.review.observed_at} />
                </dl>
            </details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={submitting} onClick={record} className="rounded border border-amber-300 px-3 py-2 text-sm">Save permission record</button><button type="button" disabled={submitting} onClick={() => setConfirming(false)} className="rounded border border-slate-500 px-3 py-2 text-sm">Cancel</button></div>
            {submitting && <p role="status" className="mt-2 text-sm">Saving permission record…</p>}
        </div>}
        {!mayCreate && <p className="mt-4 text-sm text-amber-200">You cannot save this record yet. It requires a current review, an authenticated operator with dedicated permission, and a valid session. Home Assistant remains blocked because Atlas cannot install it.</p>}
    </section><InstallationExecutionAdmissions
        candidateId={candidateId}
        grants={grants ?? []}
        homeAssistantBlocked={response.review.readiness === "blocked" && response.review.blockers.includes("installation_capability_unsupported")}
    /></>;
}

function Grant({ result }: { result: ExecutionPermissionGrantResultV1 }) {
    const grant = result.grant!; const status = result.status!; const audit = result.audit_evidence!;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <h3 className="font-semibold">{status.lifecycle === "active" ? "Current record for later review" : "Expired permission record"}</h3>
        <p className="mt-1">This record stores a past choice. It does not authorize or start installation or execution.</p>
        <p className="mt-1">Saved {grant.recorded_at}; expires {grant.valid_until}.</p>
        <details className="mt-3 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Record and evidence details</summary>
            <p className="mt-2">Confirmation: {grant.confirmation_text}</p>
            <dl className="mt-3 grid gap-2 sm:grid-cols-2"><Value name="Lifecycle code" value={status.lifecycle} /><Value name="Record state code" value={grant.record_state} /><Value name="Disposition code" value={result.disposition} /><Value name="Observed at" value={status.observed_at} /><Value name="Authenticated operator" value={grant.operator_id} /><Value name="Candidate record ID" value={grant.candidate_record_id} /><Value name="Grant ID" value={grant.grant_id} /><Value name="Grant fingerprint" value={grant.grant_fingerprint.value} /><Value name="Status fingerprint" value={status.status_fingerprint.value} /><Value name="v0.34 review ID" value={grant.linkage.v034_review_id} /><Value name="v0.34 review fingerprint" value={grant.linkage.v034_review_fingerprint.value} /><Value name="v0.34 audit fingerprint" value={grant.linkage.v034_audit_evidence_fingerprint.value} /><Value name="v0.34 operator fingerprint" value={grant.linkage.v034_operator_fingerprint.value} /><Value name="v0.20–v0.34 linkage fingerprint" value={grant.linkage.linkage_fingerprint.value} /><Value name="Request fingerprint" value={grant.request_fingerprint.value} /><Value name="Idempotency-key fingerprint" value={grant.idempotency_key_fingerprint.value} /><Value name="Audit evidence fingerprint" value={audit.evidence_fingerprint.value} /><Value name="Audit outcome code" value={audit.outcome} /><Value name="Audit correlation ID" value={audit.correlation_id} /></dl>
        </details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Earlier evidence linked to this record</summary><dl className="mt-2 grid gap-2 sm:grid-cols-2">{LINKAGE_KEYS.map((key) => <Value key={key} name={key} value={display(grant.linkage.readiness_linkage[key])} />)}</dl></details>
        <details className="mt-2 rounded border border-slate-700 p-3"><summary className="cursor-pointer">Authority and retry details</summary>
            <p className="mt-2 text-xs">Permanent reservation: true · raw idempotency key persisted: false · retry allowed: false · replay allowed: false.</p>
            <dl aria-label="Grant fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">{["Execution admission granted", "Execution authorized", "Installation allowed", "Dispatch allowed", "Agent invocation allowed", "Worker allowed", "Workflow allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Deployment allowed", "Rollback allowed", "Retry allowed", "Resend allowed", "Docker allowed", "Podman allowed", "Shell allowed", "Process allowed", "Replay allowed"].map((name) => <Value key={name} name={name} value="false" />)}</dl>
        </details>
    </li>;
}

function display(value: string | boolean | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
