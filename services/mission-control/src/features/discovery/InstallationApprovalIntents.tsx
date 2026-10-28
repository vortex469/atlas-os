import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import {
    approvalIntentIdempotencyKey,
    getInstallationApprovalIntent,
    listInstallationApprovalIntents,
    recordInstallationApprovalIntent,
} from "../../api/installationApprovalIntent";
import type { InstallationApprovalIntentV1 } from "../../types/installationApprovalIntent";
import type { InstallationCandidateRecordEnvelopeV1 } from "../../types/installationCandidateLifecycle";
import { InstallationExecutionRequests } from "./InstallationExecutionRequests";

export function InstallationApprovalIntents({ records, csrfToken }: {
    records: InstallationCandidateRecordEnvelopeV1[];
    csrfToken: string | null;
}) {
    const [intents, setIntents] = useState<InstallationApprovalIntentV1[]>([]);
    const [reviewed, setReviewed] = useState<InstallationApprovalIntentV1 | null>(null);
    const [confirming, setConfirming] = useState<InstallationCandidateRecordEnvelopeV1 | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [listError, setListError] = useState<string | null>(null);
    const [listAttempt, setListAttempt] = useState(0);
    const [reviewError, setReviewError] = useState<{ approvalIntentId: string; technicalDetail: string } | null>(null);
    const [reviewingId, setReviewingId] = useState<string | null>(null);
    const [recording, setRecording] = useState(false);
    const [attemptedCandidates, setAttemptedCandidates] = useState<Set<string>>(() => new Set());

    useEffect(() => {
        let current = true;
        listInstallationApprovalIntents()
            .then((values) => { if (current) setIntents(values); })
            .catch((requestError: unknown) => {
                if (current) setListError(getAtlasErrorMessage(requestError, "Approval evidence is currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [listAttempt]);

    const review = async (approvalIntentId: string) => {
        if (reviewingId !== null || recording) return;
        setReviewed(null);
        setReviewError(null);
        setReviewingId(approvalIntentId);
        try { setReviewed(await getInstallationApprovalIntent(approvalIntentId)); }
        catch (requestError: unknown) {
            setReviewError({
                approvalIntentId,
                technicalDetail: getAtlasErrorMessage(requestError, "Approval evidence is currently unavailable."),
            });
        } finally {
            setReviewingId(null);
        }
    };

    const retryList = () => {
        setLoading(true);
        setListError(null);
        setReviewError(null);
        setListAttempt((attempt) => attempt + 1);
    };

    const record = async () => {
        if (!confirming || !csrfToken || recording) return;
        const candidateId = confirming.candidate_record_id;
        setAttemptedCandidates((current) => new Set(current).add(candidateId));
        setRecording(true); setError(null);
        try {
            const value = await recordInstallationApprovalIntent(
                confirming.candidate_record_id, csrfToken, approvalIntentIdempotencyKey(),
            );
            setIntents((current) => [value, ...current.filter((intent) => intent.approval_intent_id !== value.approval_intent_id)]);
            setReviewed(value); setConfirming(null);
        } catch (requestError: unknown) {
            setError(getAtlasErrorMessage(requestError, "Approval evidence could not be recorded."));
            setConfirming(null);
        } finally { setRecording(false); }
    };

    const evidenced = new Set(intents.map((intent) => intent.approved_subject.candidate_record_id));
    const active = records.filter((recordValue) => recordValue.lifecycle_state === "active" && !evidenced.has(recordValue.candidate_record_id) && !attemptedCandidates.has(recordValue.candidate_record_id));
    return <section aria-labelledby="approval-intents-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="approval-intents-heading" className="font-semibold text-slate-100">Installation approval evidence</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">Evidence only — an approval intent is not execution authorization, dispatch, or installation.</p>
        <p className="mt-1 text-sm text-slate-300">Recording this fixed statement neither starts nor permits installation. Source expiry or deletion does not make the historical intent executable.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading installation approval evidence…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Atlas could not load installation approval evidence. Retry to check the current records.</p>
            <details className="mt-3 text-red-100/80">
                <summary className="mc-focusable cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{listError}</p>
            </details>
            <button type="button" onClick={retryList} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100">Retry approval evidence</button>
        </div>}
        {!loading && error && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !listError && !error && intents.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No installation approval evidence has been recorded.</p>}
        {!loading && !listError && !error && active.length > 0 && <ul aria-label="Active records eligible for approval evidence" className="mt-4 space-y-2">
            {active.map((recordValue) => <li key={recordValue.candidate_record_id} className="rounded-md border border-slate-700 p-3">
                <p className="break-all text-xs text-slate-300">Active candidate record: {recordValue.candidate_record_id}</p>
                {csrfToken
                    ? <button type="button" disabled={reviewingId !== null || recording} onClick={() => setConfirming(recordValue)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Record approval intent</button>
                    : <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required to record approval evidence.</p>}
            </li>)}
        </ul>}
        {!loading && !listError && intents.length > 0 && <ul aria-label="Installation approval evidence records" className="mt-4 space-y-3">
            {intents.map((intent) => <li key={intent.approval_intent_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">Immutable approval evidence</p>
                <p className="mt-1 break-all text-xs text-slate-400">Candidate record ID: {intent.approved_subject.candidate_record_id}</p>
                <button type="button" disabled={reviewingId !== null || recording} onClick={() => void review(intent.approval_intent_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-50">Review approval evidence</button>
                {reviewingId === intent.approval_intent_id && <p role="status" className="mt-3 text-sm text-slate-400">Loading approval evidence details…</p>}
                {reviewError?.approvalIntentId === intent.approval_intent_id && <div role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                    <p>Atlas could not load this approval evidence. The evidence list is still available.</p>
                    <details className="mt-3 text-red-100/80">
                        <summary className="mc-focusable cursor-pointer">Technical details</summary>
                        <p className="mt-2 break-words">{reviewError.technicalDetail}</p>
                    </details>
                    <button type="button" disabled={reviewingId !== null} onClick={() => void review(intent.approval_intent_id)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100 disabled:opacity-50">Retry evidence review</button>
                </div>}
            </li>)}
        </ul>}
        {confirming && !error && <section aria-labelledby="approval-confirmation-heading" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="approval-confirmation-heading" className="font-semibold text-amber-100">Confirm exact non-executable candidate identity</h6>
            <p className="mt-2 text-sm text-slate-200">You are recording approval evidence only for this complete identity:</p>
            <SubjectValues record={confirming} />
            <p className="mt-3 break-all text-sm text-slate-200">Fixed statement: operator_approved_exact_non_executable_candidate</p>
            <p className="mt-2 text-sm font-semibold text-amber-200">This confirmation does not authorize or initiate any work.</p>
            <div className="mt-3 flex gap-2">
                <button type="button" disabled={recording} onClick={() => void record()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm and record approval evidence only</button>
                <button type="button" disabled={recording} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-50">Cancel</button>
            </div>
            {recording && <p role="status" className="mt-2 text-sm text-slate-400">Recording immutable approval evidence…</p>}
        </section>}
        {reviewed && <IntentDetails intent={reviewed} sourcePresent={records.some((recordValue) => recordValue.candidate_record_id === reviewed.approved_subject.candidate_record_id)} />}
        <InstallationExecutionRequests intents={intents} csrfToken={csrfToken} />
    </section>;
}

function SubjectValues({ record }: { record: InstallationCandidateRecordEnvelopeV1 }) {
    return <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
        <Value name="Candidate record ID" value={record.candidate_record_id} />
        <Value name="Candidate envelope fingerprint" value={record.envelope_fingerprint} />
        <Value name="Admission fingerprint" value={record.admission_fingerprint} />
        <Value name="Embedded candidate-record fingerprint" value={record.candidate_record.record_fingerprint} />
    </dl>;
}

function IntentDetails({ intent, sourcePresent }: { intent: InstallationApprovalIntentV1; sourcePresent: boolean }) {
    const subject = intent.approved_subject;
    return <section aria-labelledby="approval-evidence-detail-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="approval-evidence-detail-heading" className="font-semibold text-slate-100">Historical approval evidence</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">This record grants no authority and cannot be executed.</p>
        <p className="mt-1 text-sm text-slate-300">Source record: {sourcePresent ? "available in this operator-scoped review" : "unavailable or deleted; the historical identity is not reconstructed"}.</p>
        <details className="mt-3 text-sm text-slate-300">
            <summary className="mc-focusable cursor-pointer text-blue-200">Evidence details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Value name="Schema" value={intent.schema} /><Value name="Approval intent ID" value={intent.approval_intent_id} />
                <Value name="Authenticated operator ID" value={intent.operator_id} /><Value name="Server-recorded time" value={intent.recorded_at} />
                <Value name="Candidate record ID" value={subject.candidate_record_id} />
                <Value name="Candidate envelope fingerprint" value={subject.candidate_envelope_fingerprint} />
                <Value name="Admission fingerprint" value={subject.admission_fingerprint} />
                <Value name="Embedded candidate-record fingerprint" value={subject.candidate_record_fingerprint} />
                <Value name="Exact fixed approval statement" value={intent.statement} /><Value name="Approval intent fingerprint" value={intent.intent_fingerprint} />
            </dl>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
