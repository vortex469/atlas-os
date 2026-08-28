import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import { executionRequestIdempotencyKey, getInstallationExecutionRequest, listInstallationExecutionRequests, recordInstallationExecutionRequest } from "../../api/installationExecutionRequest";
import type { InstallationApprovalIntentV1 } from "../../types/installationApprovalIntent";
import type { AgentInstallContainerRequestV1, InstallationExecutionRequestCreateV1, InstallationExecutionRequestV1 } from "../../types/installationExecutionRequest";
import type { InstallContainerValidation } from "../../types/atlasAgent";
import { InstallationDispatchHandoffs } from "./InstallationDispatchHandoffs";

export interface ExecutionEvidenceBundle {
    agent_request: AgentInstallContainerRequestV1;
    agent_validation: InstallContainerValidation;
}

export function InstallationExecutionRequests({ intents, csrfToken, evidenceBundles = [] }: {
    intents: InstallationApprovalIntentV1[];
    csrfToken: string | null;
    evidenceBundles?: ExecutionEvidenceBundle[];
}) {
    const [requests, setRequests] = useState<InstallationExecutionRequestV1[]>([]);
    const [reviewed, setReviewed] = useState<InstallationExecutionRequestV1 | null>(null);
    const [confirming, setConfirming] = useState<InstallationExecutionRequestCreateV1 | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [recording, setRecording] = useState(false);

    useEffect(() => {
        let current = true;
        listInstallationExecutionRequests()
            .then((values) => { if (current) setRequests(values); })
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Execution request records are currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getInstallationExecutionRequest(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The execution request record is currently unavailable.")); }
    };
    const record = async () => {
        if (!confirming || !csrfToken || recording) return;
        setRecording(true); setError(null);
        try {
            const value = await recordInstallationExecutionRequest(confirming, csrfToken, executionRequestIdempotencyKey());
            setRequests((current) => [value, ...current.filter((item) => item.execution_request_id !== value.execution_request_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The non-executing execution request record could not be preserved.")); }
        finally { setRecording(false); }
    };

    const recordedApprovals = new Set(requests.map((request) => request.linkage.approval_intent_id));
    const eligible = evidenceBundles.flatMap((bundle) => {
        const intent = intents.find((value) => value.approval_intent_id === bundle.agent_request.approval.approval_intent_id && value.approved_subject.candidate_record_id === bundle.agent_request.approval.candidate_record_id);
        if (!intent || recordedApprovals.has(intent.approval_intent_id) || bundle.agent_validation.status !== "valid_but_unsupported") return [];
        return [{ intent, bundle }];
    });

    return <section aria-labelledby="execution-requests-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="execution-requests-heading" className="font-semibold text-slate-100">Installation execution request records</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Non-executing; Agent evidence is operator-submitted; no work has started.</p>
        <p className="mt-1 text-sm text-slate-300">Immutable, authenticated operator-scoped evidence only. This is not install, execution, dispatch, deployment, rollback, worker invocation, Agent invocation, provider mutation, repository mutation, or in-guest mutation.</p>
        <p className="mt-1 text-sm text-slate-400">Default-disabled and non-authorizing. Home Assistant remains blocked and non-executable because its required deployment artifact and proof chain are absent.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading execution request records…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && requests.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No installation execution request records.</p>}
        {!loading && !error && requests.length > 0 && <ul aria-label="Installation execution request records" className="mt-4 space-y-3">
            {requests.map((request) => <li key={request.execution_request_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">Non-executing request record · {request.lifecycle_state}</p>
                <p className="mt-1 break-all text-xs text-slate-400">Request ID: {request.execution_request_id}</p>
                <p className="mt-1 text-xs text-slate-400">Fresh until {request.valid_until}; expiry is terminal and performs no work.</p>
                <button type="button" onClick={() => void review(request.execution_request_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review immutable request record</button>
            </li>)}
        </ul>}
        {!loading && eligible.length === 0 && <p className="mt-4 text-sm text-slate-400">No exact fresh operator-submitted validation evidence is available for record preservation.</p>}
        {!loading && eligible.length > 0 && <ul aria-label="Evidence eligible for request recording" className="mt-4 space-y-2">
            {eligible.map(({ intent, bundle }) => <li key={intent.approval_intent_id} className="rounded-md border border-amber-400/30 p-3">
                <p className="break-all text-xs text-slate-300">Exact candidate {intent.approved_subject.candidate_record_id} · approval {intent.approval_intent_id} · Agent request {bundle.agent_request.request_id}</p>
                {csrfToken ? <button type="button" onClick={() => setConfirming({ schema: "installation-execution-request-create-v1", candidate_record_id: intent.approved_subject.candidate_record_id, approval_intent_id: intent.approval_intent_id, agent_request: bundle.agent_request, agent_validation: bundle.agent_validation })} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Preserve non-executing execution request record only</button> : <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required.</p>}
            </li>)}
        </ul>}
        {confirming && <Confirmation value={confirming} recording={recording} onConfirm={() => void record()} onCancel={() => setConfirming(null)} />}
        {reviewed && <RequestDetails request={reviewed} />}
        <InstallationDispatchHandoffs executionRequests={requests} csrfToken={csrfToken} />
    </section>;
}

function Confirmation({ value, recording, onConfirm, onCancel }: { value: InstallationExecutionRequestCreateV1; recording: boolean; onConfirm: () => void; onCancel: () => void }) {
    return <section aria-labelledby="execution-request-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
        <h6 id="execution-request-confirmation" className="font-semibold text-amber-100">Confirm preservation of a non-executing execution request record only</h6>
        <p className="mt-2 text-sm text-slate-200">Confirm the exact candidate, approval, Agent request, validation, and evidence identities. This creates an inert record; it grants no authority and starts no work.</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Candidate record ID" value={value.candidate_record_id} /><Value name="Approval intent ID" value={value.approval_intent_id} /><Value name="Agent request ID" value={value.agent_request.request_id} /><Value name="Agent request fingerprint" value={value.agent_request.request_fingerprint.value} /><Value name="Agent validation fingerprint" value={value.agent_validation.validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={value.agent_validation.evidence.evidence_fingerprint.value} /></dl>
        <div className="mt-3 flex gap-2"><button type="button" disabled={recording} onClick={onConfirm} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm record preservation only</button><button type="button" disabled={recording} onClick={onCancel} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
        {recording && <p role="status" className="mt-2 text-sm text-slate-400">Preserving immutable non-executing request record…</p>}
    </section>;
}

function RequestDetails({ request }: { request: InstallationExecutionRequestV1 }) {
    const link = request.linkage;
    return <section aria-labelledby="execution-request-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="execution-request-detail" className="font-semibold text-slate-100">Immutable non-executing request evidence</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">Non-executing; Agent evidence is operator-submitted; no work has started.</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle" value={request.lifecycle_state} /><Value name="Ownership" value="authenticated operator-scoped" /><Value name="Recorded at" value={request.recorded_at} /><Value name="Valid until" value={request.valid_until} /><Value name="Freshness posture" value={request.lifecycle_state === "recorded" ? "evidence chain was fresh when accepted" : "expired terminally; no renewal, replay, or work"} /><Value name="Mode" value={request.mode} /><Value name="Statement" value={request.statement} /><Value name="Evidence provenance" value={request.evidence_provenance} /><Value name="Execution request ID" value={request.execution_request_id} /><Value name="Execution request fingerprint" value={request.execution_request_fingerprint.value} /><Value name="Candidate record ID" value={link.candidate_record_id} /><Value name="Candidate envelope fingerprint" value={link.candidate_envelope_fingerprint.value} /><Value name="Admission fingerprint" value={link.admission_fingerprint.value} /><Value name="Candidate record fingerprint" value={link.candidate_record_fingerprint.value} /><Value name="Approval intent ID" value={link.approval_intent_id} /><Value name="Approval intent fingerprint" value={link.approval_intent_fingerprint.value} /><Value name="Agent request ID" value={link.agent_request_id} /><Value name="Agent request fingerprint" value={link.agent_request_fingerprint.value} /><Value name="Agent validation fingerprint" value={link.agent_validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={link.agent_evidence_fingerprint.value} /><Value name="Destination fingerprint" value={link.destination_fingerprint} /><Value name="Source plan fingerprint" value={link.source_plan_fingerprint.value} /><Value name="Artifact policy fingerprint" value={link.artifact_policy_fingerprint.value} /></dl>
        <dl aria-label="Fixed-false authority flags" className="mt-4 grid gap-2 text-sm sm:grid-cols-2"><Value name="Execution authorized" value={String(request.execution_authorized)} /><Value name="Dispatch allowed" value={String(request.dispatch_allowed)} /><Value name="Agent invocation allowed" value={String(request.agent_invocation_allowed)} /><Value name="Mutation allowed" value={String(request.mutation_allowed)} /><Value name="Replay allowed" value={String(request.replay_allowed)} /></dl>
        <p className="mt-3 text-sm text-slate-400">Exact replay returns only this original record without revalidation, time extension, or work. It is never permission to consume or execute.</p>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
