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
            .catch((requestError: unknown) => { if (current) setError(getAtlasErrorMessage(requestError, "Saved request records are currently unavailable.")); })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const review = async (id: string) => {
        setError(null);
        try { setReviewed(await getInstallationExecutionRequest(id)); }
        catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The saved request record is currently unavailable.")); }
    };
    const record = async () => {
        if (!confirming || !csrfToken || recording) return;
        setRecording(true); setError(null);
        try {
            const value = await recordInstallationExecutionRequest(confirming, csrfToken, executionRequestIdempotencyKey());
            setRequests((current) => [value, ...current.filter((item) => item.execution_request_id !== value.execution_request_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) { setError(getAtlasErrorMessage(requestError, "The request record could not be saved.")); }
        finally { setRecording(false); }
    };

    const recordedApprovals = new Set(requests.map((request) => request.linkage.approval_intent_id));
    const eligible = evidenceBundles.flatMap((bundle) => {
        const intent = intents.find((value) => value.approval_intent_id === bundle.agent_request.approval.approval_intent_id && value.approved_subject.candidate_record_id === bundle.agent_request.approval.candidate_record_id);
        if (!intent || recordedApprovals.has(intent.approval_intent_id) || bundle.agent_validation.status !== "valid_but_unsupported") return [];
        return [{ intent, bundle }];
    });

    return <section aria-labelledby="execution-requests-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="execution-requests-heading" className="font-semibold text-slate-100">Future installation request records</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Saving a record does not approve or start installation.</p>
        <p className="mt-1 text-sm text-slate-300">It stores the exact candidate and operator-submitted Agent validation evidence. Saving does not call Agent, dispatch work, or change a guest.</p>
        <p className="mt-1 text-sm text-slate-400">Home Assistant remains blocked because its deployment artifact and required proof are missing.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading saved request records…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && requests.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No saved request records.</p>}
        {!loading && !error && requests.length > 0 && <ul aria-label="Saved installation request records" className="mt-4 space-y-3">
            {requests.map((request) => <li key={request.execution_request_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">{lifecycleLabel(request.lifecycle_state)} · No installation started</p>
                <details className="mt-1 text-xs text-slate-400">
                    <summary className="cursor-pointer">Request ID, candidate, and expiry</summary>
                    <p className="mt-1 break-all">Request ID: {request.execution_request_id}</p>
                    <p className="break-all">Candidate record ID: {request.linkage.candidate_record_id}</p>
                    <p>Valid until {request.valid_until}</p>
                </details>
                <button type="button" aria-label={`Review request for candidate record ${request.linkage.candidate_record_id}, request ${request.execution_request_id}`} onClick={() => void review(request.execution_request_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review details</button>
            </li>)}
        </ul>}
        {!loading && eligible.length === 0 && <p className="mt-4 text-sm text-slate-400">No fresh, operator-submitted Agent validation evidence is available for a request record.</p>}
        {!loading && eligible.length > 0 && <ul aria-label="Candidate evidence available for a request record" className="mt-4 space-y-2">
            {eligible.map(({ intent, bundle }) => <li key={intent.approval_intent_id} className="rounded-md border border-amber-400/30 p-3">
                <p className="font-semibold text-slate-200">Validated request evidence is available to save</p>
                <details className="mt-1 text-xs text-slate-400"><summary className="cursor-pointer">Candidate, approval, and Agent request IDs</summary>
                    <p className="mt-1 break-all">Candidate record: {intent.approved_subject.candidate_record_id}</p>
                    <p className="break-all">Approval statement: {intent.approval_intent_id}</p>
                    <p className="break-all">Agent request: {bundle.agent_request.request_id}</p>
                </details>
                {csrfToken ? <button type="button" aria-label={`Save request record for candidate ${intent.approved_subject.candidate_record_id}`} onClick={() => setConfirming({ schema: "installation-execution-request-create-v1", candidate_record_id: intent.approved_subject.candidate_record_id, approval_intent_id: intent.approval_intent_id, agent_request: bundle.agent_request, agent_validation: bundle.agent_validation })} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100">Save request record</button> : <p className="mt-2 text-xs text-slate-400">Sign in with a protected operator session to save this record.</p>}
            </li>)}
        </ul>}
        {confirming && <Confirmation value={confirming} recording={recording} onConfirm={() => void record()} onCancel={() => setConfirming(null)} />}
        {reviewed && <RequestDetails request={reviewed} />}
        <InstallationDispatchHandoffs executionRequests={requests} csrfToken={csrfToken} />
    </section>;
}

function Confirmation({ value, recording, onConfirm, onCancel }: { value: InstallationExecutionRequestCreateV1; recording: boolean; onConfirm: () => void; onCancel: () => void }) {
    return <section aria-labelledby="execution-request-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
        <h6 id="execution-request-confirmation" className="font-semibold text-amber-100">Confirm saving this request record</h6>
        <p className="mt-2 text-sm text-slate-200">This stores the candidate, approval statement, and exact Agent request and validation. It does not authorize or start installation, dispatch, or Agent work.</p>
        <p className="mt-2 break-all text-sm font-semibold text-slate-200">Candidate record ID: {value.candidate_record_id}</p>
        <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Verify request and evidence fingerprints</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Approval intent ID" value={value.approval_intent_id} /><Value name="Agent request ID" value={value.agent_request.request_id} /><Value name="Agent request fingerprint" value={value.agent_request.request_fingerprint.value} /><Value name="Agent validation fingerprint" value={value.agent_validation.validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={value.agent_validation.evidence.evidence_fingerprint.value} /></dl>
        </details>
        <div className="mt-3 flex gap-2"><button type="button" disabled={recording} onClick={onConfirm} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Save this request record</button><button type="button" disabled={recording} onClick={onCancel} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Cancel</button></div>
        {recording && <p role="status" className="mt-2 text-sm text-slate-400">Saving request record…</p>}
    </section>;
}

function RequestDetails({ request }: { request: InstallationExecutionRequestV1 }) {
    const link = request.linkage;
    return <section aria-labelledby="execution-request-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="execution-request-detail" className="font-semibold text-slate-100">Saved request details</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">This record never runs installation. Agent evidence was supplied by the operator.</p>
        <p className="mt-1 text-sm text-slate-300">{request.lifecycle_state === "recorded" ? "The request was saved while its evidence was current." : "This request has expired. It cannot be renewed or used to start work."} Replaying it returns only this record.</p>
        <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Technical request and evidence details</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Lifecycle status code" value={request.lifecycle_state} /><Value name="Ownership" value="authenticated operator-scoped" /><Value name="Recorded at" value={request.recorded_at} /><Value name="Valid until" value={request.valid_until} /><Value name="Mode" value={request.mode} /><Value name="Statement" value={request.statement} /><Value name="Evidence provenance" value={request.evidence_provenance} /><Value name="Execution request ID" value={request.execution_request_id} /><Value name="Execution request fingerprint" value={request.execution_request_fingerprint.value} /><Value name="Candidate record ID" value={link.candidate_record_id} /><Value name="Candidate envelope fingerprint" value={link.candidate_envelope_fingerprint.value} /><Value name="Admission fingerprint" value={link.admission_fingerprint.value} /><Value name="Candidate record fingerprint" value={link.candidate_record_fingerprint.value} /><Value name="Approval intent ID" value={link.approval_intent_id} /><Value name="Approval intent fingerprint" value={link.approval_intent_fingerprint.value} /><Value name="Agent request ID" value={link.agent_request_id} /><Value name="Agent request fingerprint" value={link.agent_request_fingerprint.value} /><Value name="Agent validation fingerprint" value={link.agent_validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={link.agent_evidence_fingerprint.value} /><Value name="Destination fingerprint" value={link.destination_fingerprint} /><Value name="Source plan fingerprint" value={link.source_plan_fingerprint.value} /><Value name="Artifact policy fingerprint" value={link.artifact_policy_fingerprint.value} /></dl>
        </details>
        <details className="mt-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-300">Authority flags</summary>
            <dl aria-label="Fixed-false authority flags" className="mt-2 grid gap-2 text-sm sm:grid-cols-2"><Value name="Execution authorized" value={String(request.execution_authorized)} /><Value name="Dispatch allowed" value={String(request.dispatch_allowed)} /><Value name="Agent invocation allowed" value={String(request.agent_invocation_allowed)} /><Value name="Mutation allowed" value={String(request.mutation_allowed)} /><Value name="Replay allowed" value={String(request.replay_allowed)} /></dl>
        </details>
    </section>;
}

function lifecycleLabel(state: InstallationExecutionRequestV1["lifecycle_state"]): string {
    return state === "recorded" ? "Saved while evidence was current" : "Expired";
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }
