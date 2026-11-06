import { useEffect, useState } from "react";

import { dispatchHandoffIdempotencyKey, getInstallationDispatchHandoff, listInstallationDispatchHandoffs, preserveInstallationDispatchHandoff } from "../../api/installationDispatchHandoff";
import type { InstallationDispatchHandoffV1 } from "../../types/installationDispatchHandoff";
import type { InstallationExecutionRequestV1 } from "../../types/installationExecutionRequest";
import { DeliveryActivationPreflights } from "./DeliveryActivationPreflights";
import { DeliveryEnablements } from "./DeliveryEnablements";

export function InstallationDispatchHandoffs({ executionRequests, csrfToken }: { executionRequests: InstallationExecutionRequestV1[]; csrfToken: string | null }) {
    const [handoffs, setHandoffs] = useState<InstallationDispatchHandoffV1[]>([]);
    const [reviewed, setReviewed] = useState<InstallationDispatchHandoffV1 | null>(null);
    const [confirming, setConfirming] = useState<InstallationExecutionRequestV1 | null>(null);
    const [loading, setLoading] = useState(true);
    const [listError, setListError] = useState(false);
    const [reviewError, setReviewError] = useState(false);
    const [failedReviewId, setFailedReviewId] = useState<string | null>(null);
    const [saveUncertain, setSaveUncertain] = useState(false);
    const [preserving, setPreserving] = useState(false);
    const [attemptedRequests, setAttemptedRequests] = useState<Set<string>>(() => new Set());
    const [listAttempt, setListAttempt] = useState(0);

    useEffect(() => {
        let current = true;
        listInstallationDispatchHandoffs()
            .then((values) => { if (current) { setHandoffs(values); setListError(false); setSaveUncertain(false); } })
            .catch(() => { if (current) setListError(true); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [listAttempt]);

    const review = async (id: string) => {
        setReviewError(false);
        setFailedReviewId(null);
        try { setReviewed(await getInstallationDispatchHandoff(id)); }
        catch {
            setReviewError(true);
            setFailedReviewId(id);
        }
    };
    const preserve = async () => {
        if (!confirming || !csrfToken || preserving) return;
        const requestId = confirming.execution_request_id;
        setAttemptedRequests((current) => new Set(current).add(requestId));
        setPreserving(true); setSaveUncertain(false);
        try {
            const value = await preserveInstallationDispatchHandoff({ schema: "installation-dispatch-handoff-create-v1", execution_request_id: confirming.execution_request_id }, csrfToken, dispatchHandoffIdempotencyKey());
            setHandoffs((current) => [value, ...current.filter((item) => item.dispatch_envelope_id !== value.dispatch_envelope_id)]);
            setReviewed(value); setConfirming(null);
        } catch { setSaveUncertain(true); setConfirming(null); }
        finally { setPreserving(false); }
    };

    const usedRequests = new Set(handoffs.map((handoff) => handoff.linkage.execution_request_id));
    const eligible = executionRequests.filter((request) => request.lifecycle_state === "recorded" && !usedRequests.has(request.execution_request_id) && !attemptedRequests.has(request.execution_request_id));

    return <section aria-labelledby="dispatch-handoffs-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="dispatch-handoffs-heading" className="font-semibold text-slate-100">Installation handoffs</h5>
        <p className="mt-1 text-sm text-slate-300">Save a handoff record in Atlas for review. Atlas does not send it to Agent or start work.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant cannot be installed or run from Atlas yet.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading dispatch handoff records…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><p>{saveUncertain ? "Atlas couldn’t reload the records. The save is still uncertain. Try again to check; Atlas won’t repeat the save." : "Atlas couldn’t load saved handoff records."}</p><button type="button" onClick={() => { setLoading(true); setListError(false); setListAttempt((attempt) => attempt + 1); }} className="mt-3 rounded border border-slate-500 px-3 py-1.5 font-semibold">Try again</button></div>}
        {saveUncertain && !listError && <div role="alert" className="mt-4 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100"><p>Atlas couldn’t confirm whether it saved this record. Reload the records to check; Atlas won’t retry the save automatically.</p><button type="button" disabled={loading} onClick={() => { setLoading(true); setListAttempt((attempt) => attempt + 1); }} className="mt-3 rounded border border-amber-400/50 px-3 py-1.5 font-semibold disabled:opacity-50">Reload records</button></div>}
        {!loading && !listError && handoffs.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No handoff records have been saved.</p>}
        {!loading && !listError && handoffs.length > 0 && <ul aria-label="Installation handoff records" className="mt-4 space-y-3">
            {handoffs.map((handoff) => <li key={handoff.dispatch_envelope_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">Handoff record · {handoff.lifecycle_state === "prepared" ? "Ready for review" : "Expired"}</p>
                <p className="mt-1 text-sm text-slate-400">Saved {formatUtcTimestamp(handoff.prepared_at)} · Expires {formatUtcTimestamp(handoff.valid_until)}</p>
                {handoff.lifecycle_state === "expired" && <p className="mt-1 text-sm text-amber-200">This record has expired and can’t be reused.</p>}
                <button type="button" disabled={loading} onClick={() => void review(handoff.dispatch_envelope_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review record</button>
            </li>)}
        </ul>}
        {!loading && !listError && eligible.length === 0 && <p className="mt-4 text-sm text-slate-400">No saved execution request is ready for a handoff record.</p>}
        {!loading && !listError && eligible.length > 0 && <ul aria-label="Execution requests eligible for handoff preservation" className="mt-4 space-y-2">
            {eligible.map((request) => <li key={request.execution_request_id} className="rounded-md border border-amber-400/30 p-3">
                <p className="font-semibold text-slate-200">Saved execution request</p>
                <p className="mt-1 text-sm text-slate-400">You can save a handoff record for review. This won’t contact Agent or start work.</p>
                {csrfToken ? <button type="button" onClick={() => setConfirming(request)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Save handoff record</button> : <p className="mt-2 text-sm text-slate-400">Sign in as an Atlas operator to save a handoff record.</p>}
            </li>)}
        </ul>}
        {confirming && <section aria-labelledby="dispatch-handoff-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="dispatch-handoff-confirmation" className="font-semibold text-amber-100">Save this handoff record?</h6>
            <p className="mt-2 text-sm text-slate-200">Atlas will save a record for review. Nothing will be sent to Agent and no work will start.</p>
            <details className="mt-3 text-sm"><summary className="cursor-pointer text-slate-300">Review request details</summary><dl className="mt-3 grid gap-3 sm:grid-cols-2"><Value name="Execution request ID" value={confirming.execution_request_id} /><Value name="Execution request fingerprint" value={confirming.execution_request_fingerprint.value} /></dl></details>
            <div className="mt-3 flex gap-2"><button type="button" disabled={preserving} onClick={() => void preserve()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Save record</button><button type="button" disabled={preserving} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {preserving && <p role="status" className="mt-2 text-sm text-slate-400">Saving handoff record…</p>}
        </section>}
        {reviewError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"><p>Atlas couldn’t load this handoff record.</p><button type="button" disabled={!failedReviewId} onClick={() => { if (failedReviewId) void review(failedReviewId); }} className="mt-3 rounded border border-slate-500 px-3 py-1.5 font-semibold">Try again</button></div>}
        {reviewed && <HandoffDetails handoff={reviewed} />}
        <DeliveryActivationPreflights csrfToken={csrfToken} />
        <DeliveryEnablements csrfToken={csrfToken} />
    </section>;
}

function HandoffDetails({ handoff }: { handoff: InstallationDispatchHandoffV1 }) {
    const link = handoff.linkage;
    return <section aria-labelledby="dispatch-handoff-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="dispatch-handoff-detail" className="font-semibold text-slate-100">Handoff record details</h6>
        <p className="mt-1 text-sm text-slate-300">{handoff.lifecycle_state === "prepared" ? "Saved in Atlas for review. It has not been sent to Agent, and no work has started." : "This record has expired. It can’t be reused, and no work was started."}</p>
        <p className="mt-1 text-sm text-slate-400">Prepared {formatUtcTimestamp(handoff.prepared_at)} · Expires {formatUtcTimestamp(handoff.valid_until)}</p>
        <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-slate-400">Technical details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2"><Value name="Lifecycle" value={handoff.lifecycle_state} /><Value name="Ownership" value="authenticated operator-scoped; not transferable or shared" /><Value name="Mode" value={handoff.mode} /><Value name="Statement" value={handoff.statement} /><Value name="Audit evidence provenance" value={handoff.evidence_provenance} /><Value name="Dispatch envelope ID" value={handoff.dispatch_envelope_id} /><Value name="Dispatch envelope fingerprint" value={handoff.dispatch_envelope_fingerprint.value} /><Value name="Recipient service" value={handoff.recipient.service} /><Value name="Agent intake schema" value={handoff.recipient.intake_contract} /><Value name="Candidate record ID" value={link.candidate_record_id} /><Value name="Candidate envelope fingerprint" value={link.candidate_envelope_fingerprint.value} /><Value name="Admission fingerprint" value={link.admission_fingerprint.value} /><Value name="Candidate record fingerprint" value={link.candidate_record_fingerprint.value} /><Value name="Approval intent ID" value={link.approval_intent_id} /><Value name="Approval intent fingerprint" value={link.approval_intent_fingerprint.value} /><Value name="Agent request ID" value={link.agent_request_id} /><Value name="Agent request fingerprint" value={link.agent_request_fingerprint.value} /><Value name="Agent validation fingerprint" value={link.agent_validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={link.agent_evidence_fingerprint.value} /><Value name="Destination fingerprint" value={link.destination_fingerprint} /><Value name="Source plan fingerprint" value={link.source_plan_fingerprint.value} /><Value name="Artifact policy fingerprint" value={link.artifact_policy_fingerprint.value} /><Value name="Execution request ID" value={link.execution_request_id} /><Value name="Execution request fingerprint" value={link.execution_request_fingerprint.value} /></dl>
            <h6 className="mt-4 font-semibold text-slate-200">Agent admission contract</h6>
            <p className="mt-1 text-slate-400">This describes a contract only. There is no live endpoint, Agent evaluation, receipt, or delivery.</p>
            <dl aria-label="Contract-only Agent admission shape" className="mt-2 grid gap-2 sm:grid-cols-2"><Value name="Schema" value="agent-installation-dispatch-admission-v1" /><Value name="Status" value="valid_but_not_admitted" /><Value name="Reason codes" value="[]" /><Value name="Delivery accepted" value="false" /><Value name="Execution admitted" value="false" /><Value name="Worker allowed" value="false" /><Value name="Mutation allowed" value="false" /><Value name="Replay allowed" value="false" /></dl>
            <dl aria-label="Fixed-false authority flags" className="mt-4 grid gap-2 sm:grid-cols-2"><Value name="Delivery authorized" value={String(handoff.delivery_authorized)} /><Value name="Agent admission authorized" value={String(handoff.agent_admission_authorized)} /><Value name="Execution authorized" value={String(handoff.execution_authorized)} /><Value name="Mutation authorized" value={String(handoff.mutation_authorized)} /><Value name="Replay allowed" value={String(handoff.replay_allowed)} /></dl>
            <p className="mt-3 text-slate-400">One execution request can produce at most one handoff record. A retry can only return the same record; it cannot renew, replay, deliver, or start work.</p>
            <p className="mt-2 text-slate-400">This audit record proves only that Atlas saved the handoff details. It does not prove Agent received them or started work.</p>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
