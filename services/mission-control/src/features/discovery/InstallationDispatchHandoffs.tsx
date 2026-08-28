import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import { dispatchHandoffIdempotencyKey, getInstallationDispatchHandoff, listInstallationDispatchHandoffs, preserveInstallationDispatchHandoff } from "../../api/installationDispatchHandoff";
import type { InstallationDispatchHandoffV1 } from "../../types/installationDispatchHandoff";
import type { InstallationExecutionRequestV1 } from "../../types/installationExecutionRequest";

export function InstallationDispatchHandoffs({ executionRequests, csrfToken }: { executionRequests: InstallationExecutionRequestV1[]; csrfToken: string | null }) {
    const [handoffs, setHandoffs] = useState<InstallationDispatchHandoffV1[]>([]);
    const [reviewed, setReviewed] = useState<InstallationDispatchHandoffV1 | null>(null);
    const [confirming, setConfirming] = useState<InstallationExecutionRequestV1 | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [preserving, setPreserving] = useState(false);

    useEffect(() => {
        let current = true;
        listInstallationDispatchHandoffs()
            .then((values) => { if (current) setHandoffs(values); })
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Dispatch handoff records are currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getInstallationDispatchHandoff(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The dispatch handoff record is currently unavailable.")); }
    };
    const preserve = async () => {
        if (!confirming || !csrfToken || preserving) return;
        setPreserving(true); setError(null);
        try {
            const value = await preserveInstallationDispatchHandoff({ schema: "installation-dispatch-handoff-create-v1", execution_request_id: confirming.execution_request_id }, csrfToken, dispatchHandoffIdempotencyKey());
            setHandoffs((current) => [value, ...current.filter((item) => item.dispatch_envelope_id !== value.dispatch_envelope_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The non-delivering handoff record could not be preserved.")); }
        finally { setPreserving(false); }
    };

    const usedRequests = new Set(handoffs.map((handoff) => handoff.linkage.execution_request_id));
    const eligible = executionRequests.filter((request) => request.lifecycle_state === "recorded" && !usedRequests.has(request.execution_request_id));

    return <section aria-labelledby="dispatch-handoffs-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="dispatch-handoffs-heading" className="font-semibold text-slate-100">Installation dispatch handoff records</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Prepared only; not sent to Agent; no work has started.</p>
        <p className="mt-1 text-sm text-slate-300">Operator-owned, immutable preparation evidence only. This is not live Agent invocation, dispatch delivery, worker execution, workflow start, Docker, Podman, shell or process execution, installation, deployment, rollback, provider mutation, repository mutation, or in-guest mutation.</p>
        <p className="mt-1 text-sm text-slate-400">Default-disabled and non-authorizing. Home Assistant remains blocked and non-executable; no deployment artifact or execution path is introduced.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading dispatch handoff records…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && handoffs.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No installation dispatch handoff records.</p>}
        {!loading && !error && handoffs.length > 0 && <ul aria-label="Installation dispatch handoff records" className="mt-4 space-y-3">
            {handoffs.map((handoff) => <li key={handoff.dispatch_envelope_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">Non-delivering handoff record · {handoff.lifecycle_state}</p>
                <p className="mt-1 break-all text-xs text-slate-400">Envelope ID: {handoff.dispatch_envelope_id}</p>
                <p className="mt-1 text-xs text-slate-400">Fresh until {handoff.valid_until}; expiry is terminal and performs no work.</p>
                <button type="button" onClick={() => void review(handoff.dispatch_envelope_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review immutable handoff record</button>
            </li>)}
        </ul>}
        {!loading && eligible.length === 0 && <p className="mt-4 text-sm text-slate-400">No fresh execution request record is eligible for handoff preservation.</p>}
        {!loading && eligible.length > 0 && <ul aria-label="Execution requests eligible for handoff preservation" className="mt-4 space-y-2">
            {eligible.map((request) => <li key={request.execution_request_id} className="rounded-md border border-amber-400/30 p-3">
                <p className="break-all text-xs text-slate-300">Exact execution request {request.execution_request_id} · fingerprint {request.execution_request_fingerprint.value}</p>
                {csrfToken ? <button type="button" onClick={() => setConfirming(request)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Preserve non-delivering handoff record only</button> : <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required.</p>}
            </li>)}
        </ul>}
        {confirming && <section aria-labelledby="dispatch-handoff-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="dispatch-handoff-confirmation" className="font-semibold text-amber-100">Confirm preservation of a non-delivering handoff record only</h6>
            <p className="mt-2 text-sm text-slate-200">Confirm the exact execution request identity. Core only prepares an inert record; it does not deliver, invoke Agent, admit work, authorize execution, or permit replay.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Execution request ID" value={confirming.execution_request_id} /><Value name="Execution request fingerprint" value={confirming.execution_request_fingerprint.value} /></dl>
            <div className="mt-3 flex gap-2"><button type="button" disabled={preserving} onClick={() => void preserve()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm handoff record preservation only</button><button type="button" disabled={preserving} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
            {preserving && <p role="status" className="mt-2 text-sm text-slate-400">Preserving immutable non-delivering handoff record…</p>}
        </section>}
        {reviewed && <HandoffDetails handoff={reviewed} />}
    </section>;
}

function HandoffDetails({ handoff }: { handoff: InstallationDispatchHandoffV1 }) {
    const link = handoff.linkage;
    return <section aria-labelledby="dispatch-handoff-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="dispatch-handoff-detail" className="font-semibold text-slate-100">Immutable non-delivering handoff evidence</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">Prepared only; not sent to Agent; no work has started.</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle" value={handoff.lifecycle_state} /><Value name="Ownership" value="authenticated operator-scoped; not transferable or shared" /><Value name="Prepared at" value={handoff.prepared_at} /><Value name="Valid until" value={handoff.valid_until} /><Value name="Freshness posture" value={handoff.lifecycle_state === "prepared" ? "fresh preparation record; still not delivered or admitted" : "expired terminally; no renew, retry, replay, delivery, or work"} /><Value name="Mode" value={handoff.mode} /><Value name="Statement" value={handoff.statement} /><Value name="Audit evidence provenance" value={handoff.evidence_provenance} /><Value name="Dispatch envelope ID" value={handoff.dispatch_envelope_id} /><Value name="Dispatch envelope fingerprint" value={handoff.dispatch_envelope_fingerprint.value} /><Value name="Recipient service" value={handoff.recipient.service} /><Value name="Agent intake schema" value={handoff.recipient.intake_contract} /><Value name="Candidate record ID" value={link.candidate_record_id} /><Value name="Candidate envelope fingerprint" value={link.candidate_envelope_fingerprint.value} /><Value name="Admission fingerprint" value={link.admission_fingerprint.value} /><Value name="Candidate record fingerprint" value={link.candidate_record_fingerprint.value} /><Value name="Approval intent ID" value={link.approval_intent_id} /><Value name="Approval intent fingerprint" value={link.approval_intent_fingerprint.value} /><Value name="Agent request ID" value={link.agent_request_id} /><Value name="Agent request fingerprint" value={link.agent_request_fingerprint.value} /><Value name="Agent validation fingerprint" value={link.agent_validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={link.agent_evidence_fingerprint.value} /><Value name="Destination fingerprint" value={link.destination_fingerprint} /><Value name="Source plan fingerprint" value={link.source_plan_fingerprint.value} /><Value name="Artifact policy fingerprint" value={link.artifact_policy_fingerprint.value} /><Value name="Execution request ID" value={link.execution_request_id} /><Value name="Execution request fingerprint" value={link.execution_request_fingerprint.value} /></dl>
        <p className="mt-4 text-sm font-semibold text-slate-200">Frozen Agent admission shape only; no live endpoint, evaluation, receipt, or Core audit result exists.</p>
        <dl aria-label="Contract-only Agent admission shape" className="mt-2 grid gap-2 text-sm sm:grid-cols-2"><Value name="Schema" value="agent-installation-dispatch-admission-v1" /><Value name="Status" value="valid_but_not_admitted" /><Value name="Reason codes" value="[]" /><Value name="Delivery accepted" value="false" /><Value name="Execution admitted" value="false" /><Value name="Worker allowed" value="false" /><Value name="Mutation allowed" value="false" /><Value name="Replay allowed" value="false" /></dl>
        <dl aria-label="Fixed-false authority flags" className="mt-4 grid gap-2 text-sm sm:grid-cols-2"><Value name="Delivery authorized" value={String(handoff.delivery_authorized)} /><Value name="Agent admission authorized" value={String(handoff.agent_admission_authorized)} /><Value name="Execution authorized" value={String(handoff.execution_authorized)} /><Value name="Mutation authorized" value={String(handoff.mutation_authorized)} /><Value name="Replay allowed" value={String(handoff.replay_allowed)} /></dl>
        <p className="mt-3 text-sm text-slate-400">The operator-scoped idempotency reservation permits only an exact create retry returning the original record. It performs no re-resolution, time extension, parser evaluation, delivery, admission, or other work; one execution request can produce at most one envelope forever.</p>
        <p className="mt-2 text-sm text-slate-400">Audit evidence proves only that Core prepared this non-executing handoff. It is not evidence of delivery, Agent receipt, admission, worker activity, or execution.</p>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
