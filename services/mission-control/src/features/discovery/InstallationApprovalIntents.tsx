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
    const [recordError, setRecordError] = useState<{ candidateRecordId: string; technicalDetail: string } | null>(null);
    const [recordCheckError, setRecordCheckError] = useState<string | null>(null);
    const [checkingRecord, setCheckingRecord] = useState(false);
    const [recordRecoveryMessage, setRecordRecoveryMessage] = useState<string | null>(null);
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
        if (!confirming || !csrfToken || recording || recordError !== null) return;
        const candidateId = confirming.candidate_record_id;
        setAttemptedCandidates((current) => new Set(current).add(candidateId));
        setRecording(true);
        setRecordCheckError(null);
        setRecordRecoveryMessage(null);
        try {
            const value = await recordInstallationApprovalIntent(
                confirming.candidate_record_id, csrfToken, approvalIntentIdempotencyKey(),
            );
            setIntents((current) => [value, ...current.filter((intent) => intent.approval_intent_id !== value.approval_intent_id)]);
            setReviewed(value);
            setConfirming(null);
            setRecordError(null);
        } catch (requestError: unknown) {
            setRecordError({
                candidateRecordId: candidateId,
                technicalDetail: getAtlasErrorMessage(requestError, "Approval evidence could not be recorded."),
            });
            setConfirming(null);
        } finally { setRecording(false); }
    };

    const checkUncertainRecord = async () => {
        if (!recordError || checkingRecord) return;
        setCheckingRecord(true);
        setRecordCheckError(null);
        setRecordRecoveryMessage(null);
        try {
            const current = await listInstallationApprovalIntents();
            setIntents(current);
            const matching = current.find((intent) => intent.approved_subject.candidate_record_id === recordError.candidateRecordId);
            if (matching) {
                setReviewed(matching);
                setRecordError(null);
                setRecordRecoveryMessage("Atlas found the saved approval record. Review its details below.");
            } else {
                setRecordRecoveryMessage("No matching approval record was found. The original result is still uncertain. This screen will not send the request again.");
            }
        } catch (requestError: unknown) {
            setRecordCheckError(getAtlasErrorMessage(requestError, "Approval evidence is currently unavailable."));
        } finally {
            setCheckingRecord(false);
        }
    };

    const evidenced = new Set(intents.map((intent) => intent.approved_subject.candidate_record_id));
    const active = records.filter((recordValue) => recordValue.lifecycle_state === "active" && !evidenced.has(recordValue.candidate_record_id) && !attemptedCandidates.has(recordValue.candidate_record_id));
    return <section aria-labelledby="approval-intents-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h5 id="approval-intents-heading" className="font-semibold text-slate-100">Installation approval records</h5>
        <p className="mt-1 text-sm font-semibold text-amber-200">A saved approval record does not authorize or start an installation.</p>
        <p className="mt-1 text-sm text-slate-300">A record stays non-executable even if its source candidate expires or is deleted.</p>
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Checking saved approval records…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Atlas could not load the approval records. Retry to check them again.</p>
            <details className="mt-3 text-red-100/80">
                <summary className="mc-focusable cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{listError}</p>
            </details>
            <button type="button" onClick={retryList} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100">Retry approval records</button>
        </div>}
        {!loading && recordError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Atlas could not confirm whether it saved this record. This screen will not send the request again.</p>
            <details className="mt-3 text-red-100/80">
                <summary className="mc-focusable cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{recordError.technicalDetail}</p>
            </details>
            {recordCheckError && <details className="mt-3 text-red-100/80">
                <summary className="mc-focusable cursor-pointer">Record check details</summary>
                <p className="mt-2 break-words">{recordCheckError}</p>
            </details>}
            <button type="button" disabled={checkingRecord} onClick={() => void checkUncertainRecord()} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100 disabled:opacity-50">{recordCheckError ? "Retry record check" : "Check saved record"}</button>
            {checkingRecord && <p role="status" className="mt-3 text-sm text-red-100/80">Checking the saved approval record…</p>}
        </div>}
        {recordRecoveryMessage && <p role="status" className="mt-4 rounded-md border border-slate-700 p-3 text-sm text-slate-300">{recordRecoveryMessage}</p>}
        {!loading && !listError && !recordError && intents.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No approval records have been saved.</p>}
        {!loading && !listError && active.length > 0 && <ul aria-label="Active candidate records" className="mt-4 space-y-2">
            {active.map((recordValue) => <li key={recordValue.candidate_record_id} className="rounded-md border border-slate-700 p-3">
                <p className="text-sm text-slate-200">Candidate item: {recordValue.candidate_record.item_id}</p>
                <SubjectValues record={recordValue} />
                {csrfToken
                    ? <button type="button" disabled={reviewingId !== null || recording} onClick={() => setConfirming(recordValue)} className="mt-2 rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Review approval statement</button>
                    : <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required to record approval evidence.</p>}
            </li>)}
        </ul>}
        {!loading && !listError && !recordError && intents.length > 0 && <ul aria-label="Installation approval records" className="mt-4 space-y-3">
            {intents.map((intent) => <li key={intent.approval_intent_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">Approval record saved</p>
                <p className="mt-1 break-all text-xs text-slate-400">Candidate record ID: {intent.approved_subject.candidate_record_id}</p>
                <button type="button" disabled={reviewingId !== null || recording} onClick={() => void review(intent.approval_intent_id)} className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-50">View approval record</button>
                {reviewingId === intent.approval_intent_id && <p role="status" className="mt-3 text-sm text-slate-400">Loading record details…</p>}
                {reviewError?.approvalIntentId === intent.approval_intent_id && <div role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                    <p>Atlas could not load this approval record. The list is still available.</p>
                    <details className="mt-3 text-red-100/80">
                        <summary className="mc-focusable cursor-pointer">Technical details</summary>
                        <p className="mt-2 break-words">{reviewError.technicalDetail}</p>
                    </details>
                    <button type="button" disabled={reviewingId !== null} onClick={() => void review(intent.approval_intent_id)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100 disabled:opacity-50">Retry record review</button>
                </div>}
            </li>)}
        </ul>}
        {confirming && !recordError && <section aria-labelledby="approval-confirmation-heading" className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/5 p-4">
            <h6 id="approval-confirmation-heading" className="font-semibold text-amber-100">Confirm approval statement</h6>
            <p className="mt-2 text-sm text-slate-200">You are recording the statement below about this candidate. It does not make the candidate executable.</p>
            <SubjectValues record={confirming} />
            <p className="mt-3 text-sm text-slate-200">Statement: I approve this exact candidate as a non-executable record.</p>
            <p className="mt-2 text-sm font-semibold text-amber-200">This record does not authorize or start work.</p>
            <div className="mt-3 flex gap-2">
                <button type="button" disabled={recording} onClick={() => void record()} className="rounded border border-amber-400/50 px-3 py-1.5 text-sm font-semibold text-amber-100 disabled:opacity-50">Confirm and save record</button>
                <button type="button" disabled={recording} onClick={() => setConfirming(null)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-50">Cancel</button>
            </div>
            {recording && <p role="status" className="mt-2 text-sm text-slate-400">Saving approval record…</p>}
        </section>}
        {reviewed && <IntentDetails intent={reviewed} sourcePresent={records.some((recordValue) => recordValue.candidate_record_id === reviewed.approved_subject.candidate_record_id)} />}
        <InstallationExecutionRequests intents={intents} csrfToken={csrfToken} />
    </section>;
}

function SubjectValues({ record }: { record: InstallationCandidateRecordEnvelopeV1 }) {
    return <div className="mt-3 space-y-2 text-sm">
        <p>Candidate item: {record.candidate_record.item_id}</p>
        <p className="break-all">Candidate record ID: {record.candidate_record_id}</p>
        <details className="mt-2 text-slate-300"><summary className="mc-focusable cursor-pointer text-xs text-slate-400">Technical identity details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Value name="Candidate envelope fingerprint" value={record.envelope_fingerprint} />
                <Value name="Admission fingerprint" value={record.admission_fingerprint} />
                <Value name="Embedded candidate-record fingerprint" value={record.candidate_record.record_fingerprint} />
            </dl>
        </details>
    </div>;
}

function IntentDetails({ intent, sourcePresent }: { intent: InstallationApprovalIntentV1; sourcePresent: boolean }) {
    const subject = intent.approved_subject;
    return <section aria-labelledby="approval-evidence-detail-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="approval-evidence-detail-heading" className="font-semibold text-slate-100">Approval record history</h6>
        <p className="mt-1 text-sm font-semibold text-amber-200">This record grants no permission and cannot be used to run the candidate.</p>
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
