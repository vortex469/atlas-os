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
    const [listError, setListError] = useState<string | null>(null);
    const [listTechnicalDetail, setListTechnicalDetail] = useState<string | null>(null);
    const [listAttempt, setListAttempt] = useState(0);
    const [reviewingId, setReviewingId] = useState<string | null>(null);
    const [reviewError, setReviewError] = useState<{ requestId: string; technicalDetail: string } | null>(null);
    const [recordError, setRecordError] = useState<{ approvalIntentId: string; technicalDetail: string } | null>(null);
    const [recordCheckError, setRecordCheckError] = useState<string | null>(null);
    const [recordRecoveryMessage, setRecordRecoveryMessage] = useState<string | null>(null);
    const [checkingRecord, setCheckingRecord] = useState(false);
    const [recording, setRecording] = useState(false);
    const [attemptedApprovals, setAttemptedApprovals] = useState<Set<string>>(() => new Set());

    useEffect(() => {
        let current = true;
        listInstallationExecutionRequests()
            .then((values) => { if (current) setRequests(values); })
            .catch((requestError: unknown) => {
                if (current) {
                    setListError("Atlas could not load the saved request records.");
                    setListTechnicalDetail(getAtlasErrorMessage(requestError, "Saved request records are currently unavailable."));
                }
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [listAttempt]);

    const retryList = () => {
        setLoading(true);
        setListError(null);
        setListTechnicalDetail(null);
        setListAttempt((attempt) => attempt + 1);
    };

    const review = async (id: string) => {
        setReviewed(null);
        setReviewError(null);
        setReviewingId(id);
        try { setReviewed(await getInstallationExecutionRequest(id)); }
        catch (requestError: unknown) {
            setReviewError({ requestId: id, technicalDetail: getAtlasErrorMessage(requestError, "The request record is currently unavailable.") });
        } finally { setReviewingId(null); }
    };
    const record = async () => {
        if (!confirming || !csrfToken || recording) return;
        const approvalIntentId = confirming.approval_intent_id;
        setAttemptedApprovals((current) => new Set(current).add(approvalIntentId));
        setRecording(true);
        setReviewed(null);
        setReviewError(null);
        setRecordError(null);
        setRecordCheckError(null);
        setRecordRecoveryMessage(null);
        try {
            const value = await recordInstallationExecutionRequest(confirming, csrfToken, executionRequestIdempotencyKey());
            setRequests((current) => [value, ...current.filter((item) => item.execution_request_id !== value.execution_request_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) {
            setRecordError({ approvalIntentId, technicalDetail: getAtlasErrorMessage(requestError, "The request record could not be saved.") });
            setConfirming(null);
        }
        finally { setRecording(false); }
    };

    const checkSavedRecord = async () => {
        if (!recordError || checkingRecord) return;
        setCheckingRecord(true);
        setRecordCheckError(null);
        setRecordRecoveryMessage(null);
        try {
            const current = await listInstallationExecutionRequests();
            setRequests(current);
            const matching = current.find((request) => request.linkage.approval_intent_id === recordError.approvalIntentId);
            if (matching) {
                setReviewed(matching);
                setRecordError(null);
                setRecordRecoveryMessage("Atlas found the saved request record. Review its details below.");
            } else {
                setRecordRecoveryMessage("No matching request record was found. The previous save is still uncertain. This screen will not send it again.");
            }
        } catch (requestError: unknown) {
            setRecordCheckError(getAtlasErrorMessage(requestError, "Saved request records are currently unavailable."));
        } finally { setCheckingRecord(false); }
    };

    const recordedApprovals = new Set(requests.map((request) => request.linkage.approval_intent_id));
    const eligible = evidenceBundles.flatMap((bundle) => {
        const intent = intents.find((value) => value.approval_intent_id === bundle.agent_request.approval.approval_intent_id && value.approved_subject.candidate_record_id === bundle.agent_request.approval.candidate_record_id);
        if (!intent || recordedApprovals.has(intent.approval_intent_id) || attemptedApprovals.has(intent.approval_intent_id) || bundle.agent_validation.status !== "valid_but_unsupported") return [];
        return [{ intent, bundle }];
    });

    return <section aria-labelledby="execution-requests-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="execution-requests-heading" className="font-semibold text-slate-100">Installation request records</h5>
        <p className="mt-1 text-sm text-slate-300">Saving a record preserves the exact approved request and validation for review. It does not send the request, install anything, or run work.</p>
        <p className="mt-1 text-sm text-amber-200">Atlas cannot install Home Assistant yet because its deployment package and required evidence are missing.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Checking saved request records…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <h6 className="font-semibold">Request records unavailable</h6>
            <p className="mt-1">{listError}</p>
            {listTechnicalDetail && <details className="mt-2"><summary className="cursor-pointer text-xs">Technical details</summary><p className="mt-2 break-all text-xs">{listTechnicalDetail}</p></details>}
            <button type="button" onClick={retryList} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Retry request records</button>
        </div>}
        {!loading && !listError && requests.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No saved request records.</p>}
        {!loading && !listError && requests.length > 0 && <ul aria-label="Saved installation request records" className="mt-4 space-y-3">
            {requests.map((request) => <li key={request.execution_request_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">{request.lifecycle_state === "recorded" ? "Saved request record" : "Expired request record"}</p>
                <p className="mt-1 text-sm text-slate-300">Saved {formatUtcTimestamp(request.recorded_at)} · valid until {formatUtcTimestamp(request.valid_until)}. Expiry does not start work.</p>
                <button type="button" disabled={reviewingId !== null} onClick={() => void review(request.execution_request_id)} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold disabled:opacity-50">{reviewingId === request.execution_request_id ? "Loading request…" : "View request record"}</button>
            </li>)}
        </ul>}
        {!loading && !listError && eligible.length === 0 && <p className="mt-4 text-sm text-slate-400">No new request is ready to save.</p>}
        {!loading && !listError && eligible.length > 0 && <ul aria-label="Requests ready to save" className="mt-4 space-y-2">
            {eligible.map(({ intent, bundle }) => <li key={intent.approval_intent_id} className="rounded-md border border-amber-400/30 p-3">
                <p className="font-semibold text-slate-200">Approved candidate is ready for a saved record</p>
                <details className="mt-2"><summary className="cursor-pointer text-xs text-slate-400">Technical details</summary><p className="mt-2 break-all text-xs text-slate-400">Candidate {intent.approved_subject.candidate_record_id} · approval {intent.approval_intent_id} · Agent request {bundle.agent_request.request_id}</p></details>
                {csrfToken ? <button type="button" onClick={() => setConfirming({ schema: "installation-execution-request-create-v1", candidate_record_id: intent.approved_subject.candidate_record_id, approval_intent_id: intent.approval_intent_id, agent_request: bundle.agent_request, agent_validation: bundle.agent_validation })} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Review request details</button> : <p className="mt-2 text-sm text-slate-400">Sign in to save this record.</p>}
            </li>)}
        </ul>}
        {confirming && !listError && <Confirmation value={confirming} recording={recording} onConfirm={() => void record()} onCancel={() => setConfirming(null)} />}
        {recordError && <div role="alert" className="mt-4 rounded border border-amber-400/40 p-3 text-sm text-amber-100">
            <p className="font-semibold">The save result is unknown. Atlas will not send this request again.</p>
            <details className="mt-2"><summary className="cursor-pointer text-xs">Technical details</summary><p className="mt-2 break-all text-xs">{recordError.technicalDetail}</p></details>
            {recordCheckError && <div className="mt-2 text-sm">
                <p>Atlas could not check whether the request was saved. You can try the read again.</p>
                <details className="mt-2"><summary className="cursor-pointer text-xs">Technical details</summary><p className="mt-2 break-all text-xs">{recordCheckError}</p></details>
            </div>}
            <button type="button" disabled={checkingRecord} onClick={() => void checkSavedRecord()} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold disabled:opacity-50">{checkingRecord ? "Checking saved records…" : "Check saved records"}</button>
        </div>}
        {recordRecoveryMessage && <p role="status" className="mt-3 text-sm text-slate-300">{recordRecoveryMessage}</p>}
        {reviewError && <div role="alert" className="mt-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Request details are unavailable. Try again.</p>
            <details className="mt-2"><summary className="cursor-pointer text-xs">Technical details</summary><p className="mt-2 break-all text-xs">{reviewError.technicalDetail}</p></details>
            <button type="button" disabled={reviewingId === reviewError.requestId} onClick={() => void review(reviewError.requestId)} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold disabled:opacity-50">Retry request details</button>
        </div>}
        {reviewed && <RequestDetails request={reviewed} />}
        <InstallationDispatchHandoffs executionRequests={requests} csrfToken={csrfToken} />
    </section>;
}

function Confirmation({ value, recording, onConfirm, onCancel }: { value: InstallationExecutionRequestCreateV1; recording: boolean; onConfirm: () => void; onCancel: () => void }) {
    return <section aria-labelledby="execution-request-confirmation" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
        <h6 id="execution-request-confirmation" className="font-semibold text-amber-100">Confirm saving this request record</h6>
        <p className="mt-2 text-sm text-slate-200">This saves an inert record for this approved candidate and its validation. It does not contact Agent, send the request, install software, or run work.</p>
        <details className="mt-3">
            <summary className="cursor-pointer text-xs text-slate-400">Technical details</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Candidate record ID" value={value.candidate_record_id} /><Value name="Approval intent ID" value={value.approval_intent_id} /><Value name="Agent request ID" value={value.agent_request.request_id} /><Value name="Agent request fingerprint" value={value.agent_request.request_fingerprint.value} /><Value name="Agent validation fingerprint" value={value.agent_validation.validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={value.agent_validation.evidence.evidence_fingerprint.value} /></dl>
        </details>
        <div className="mt-3 flex gap-2"><button type="button" disabled={recording} onClick={onConfirm} className="mc-control mc-focusable px-3 py-2 text-sm font-semibold disabled:opacity-50">Save request record</button><button type="button" disabled={recording} onClick={onCancel} className="mc-control mc-focusable px-3 py-2 text-sm disabled:opacity-50">Cancel</button></div>
        {recording && <p role="status" className="mt-2 text-sm text-slate-400">Saving request record…</p>}
    </section>;
}

function RequestDetails({ request }: { request: InstallationExecutionRequestV1 }) {
    const link = request.linkage;
    return <section aria-labelledby="execution-request-detail" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="execution-request-detail" className="font-semibold text-slate-100">Request record details</h6>
        <p className="mt-1 text-sm text-slate-300">{request.lifecycle_state === "recorded" ? "Saved request record" : "Expired request record"}. This preserves the operator-submitted request and validation; it does not start work.</p>
        <p className="mt-1 text-sm text-slate-400">Saved {formatUtcTimestamp(request.recorded_at)} · valid until {formatUtcTimestamp(request.valid_until)}.</p>
        {request.lifecycle_state === "expired" && <p className="mt-2 text-sm text-amber-200">This record has expired. It cannot be renewed or used to start work.</p>}
        <details className="mt-3">
            <summary className="cursor-pointer text-xs text-slate-400">Technical details</summary>
            <p className="mt-3 text-sm text-slate-300">Reviewing this record returns its original saved details. It does not recheck evidence or start work.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Value name="Ownership" value="authenticated operator-scoped" /><Value name="Freshness when saved" value="evidence chain was fresh when accepted" /><Value name="Mode" value={request.mode} /><Value name="Statement" value={request.statement} /><Value name="Evidence provenance" value={request.evidence_provenance} /><Value name="Execution request ID" value={request.execution_request_id} /><Value name="Execution request fingerprint" value={request.execution_request_fingerprint.value} /><Value name="Candidate record ID" value={link.candidate_record_id} /><Value name="Candidate envelope fingerprint" value={link.candidate_envelope_fingerprint.value} /><Value name="Admission fingerprint" value={link.admission_fingerprint.value} /><Value name="Candidate record fingerprint" value={link.candidate_record_fingerprint.value} /><Value name="Approval intent ID" value={link.approval_intent_id} /><Value name="Approval intent fingerprint" value={link.approval_intent_fingerprint.value} /><Value name="Agent request ID" value={link.agent_request_id} /><Value name="Agent request fingerprint" value={link.agent_request_fingerprint.value} /><Value name="Agent validation fingerprint" value={link.agent_validation_fingerprint.value} /><Value name="Agent evidence fingerprint" value={link.agent_evidence_fingerprint.value} /><Value name="Destination fingerprint" value={link.destination_fingerprint} /><Value name="Source plan fingerprint" value={link.source_plan_fingerprint.value} /><Value name="Artifact policy fingerprint" value={link.artifact_policy_fingerprint.value} /></dl>
            <dl aria-label="Fixed-false authority fields" className="mt-4 grid gap-2 text-sm sm:grid-cols-2"><Value name="Execution authorized" value={String(request.execution_authorized)} /><Value name="Dispatch allowed" value={String(request.dispatch_allowed)} /><Value name="Agent invocation allowed" value={String(request.agent_invocation_allowed)} /><Value name="Mutation allowed" value={String(request.mutation_allowed)} /><Value name="Replay allowed" value={String(request.replay_allowed)} /></dl>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) { return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>; }

function formatUtcTimestamp(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date)} UTC`;
}
