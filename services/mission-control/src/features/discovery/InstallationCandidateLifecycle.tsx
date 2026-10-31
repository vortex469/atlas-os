import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import {
    candidateRecordIdempotencyKey,
    deleteInstallationCandidateRecord,
    getInstallationCandidateRecord,
    listInstallationCandidateRecords,
    preserveInstallationCandidateRecord,
} from "../../api/installationCandidateLifecycle";
import type { InstallationCandidateAdmissionV1 } from "../../types/installationCandidateAdmission";
import type { InstallationCandidateRecordEnvelopeV1 } from "../../types/installationCandidateLifecycle";
import { InstallationApprovalIntents } from "./InstallationApprovalIntents";

export function InstallationCandidateLifecycle({
    admission, itemId, selectionId, csrfToken,
}: {
    admission: InstallationCandidateAdmissionV1 | null;
    itemId: string;
    selectionId: string | null;
    csrfToken: string | null;
}) {
    const [records, setRecords] = useState<InstallationCandidateRecordEnvelopeV1[]>([]);
    const [reviewed, setReviewed] = useState<InstallationCandidateRecordEnvelopeV1 | null>(null);
    const [loading, setLoading] = useState(true);
    const [listError, setListError] = useState<string | null>(null);
    const [listAttempt, setListAttempt] = useState(0);
    const [reviewError, setReviewError] = useState<{ candidateRecordId: string; technicalDetail: string } | null>(null);
    const [reviewingId, setReviewingId] = useState<string | null>(null);
    const [mutation, setMutation] = useState<"preserve" | "delete" | null>(null);
    const [mutationError, setMutationError] = useState<{
        action: "preserve" | "delete";
        technicalDetail: string;
    } | null>(null);
    const [preserveRecovery, setPreserveRecovery] = useState<{
        request: { item_id: string; selection_id: string; admission_fingerprint: string };
        idempotencyKey: string;
    } | null>(null);
    const [deleteUncertainId, setDeleteUncertainId] = useState<string | null>(null);
    const [deletedId, setDeletedId] = useState<string | null>(null);
    const [recoveryMessage, setRecoveryMessage] = useState<string | null>(null);

    useEffect(() => {
        let current = true;
        queueMicrotask(() => {
            if (current) {
                setLoading(true);
                setListError(null);
                setReviewError(null);
            }
        });
        listInstallationCandidateRecords()
            .then((values) => { if (current) setRecords(values); })
            .catch((requestError: unknown) => {
                if (current) setListError(getAtlasErrorMessage(requestError, "Saved review records are currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [listAttempt]);

    const preserve = async () => {
        if (!csrfToken || !selectionId || admission?.status !== "admitted_but_non_executable" || !admission.candidate_record || mutation || reviewingId !== null || deleteUncertainId !== null) return;
        setMutation("preserve"); setMutationError(null); setDeletedId(null);
        setRecoveryMessage(null);
        const request = {
            item_id: itemId,
            selection_id: selectionId,
            admission_fingerprint: admission.admission_fingerprint,
        };
        const canReuseRequestKey = preserveRecovery !== null
            && preserveRecovery.request.item_id === request.item_id
            && preserveRecovery.request.selection_id === request.selection_id
            && preserveRecovery.request.admission_fingerprint === request.admission_fingerprint;
        const idempotencyKey = canReuseRequestKey ? preserveRecovery.idempotencyKey : candidateRecordIdempotencyKey();
        try {
            const value = await preserveInstallationCandidateRecord(
                { item_id: request.item_id, selection_id: request.selection_id }, csrfToken, idempotencyKey,
            );
            setRecords((current) => [value, ...current.filter((record) => record.candidate_record_id !== value.candidate_record_id)]);
            setReviewed(value);
            setListError(null);
            setReviewError(null);
            setPreserveRecovery(null);
        } catch (requestError: unknown) {
            setPreserveRecovery({ request, idempotencyKey });
            setMutationError({
                action: "preserve",
                technicalDetail: getAtlasErrorMessage(requestError, "The review record could not be saved."),
            });
        } finally { setMutation(null); }
    };

    const review = async (candidateRecordId: string) => {
        if (reviewingId !== null || mutation !== null) return;
        setReviewed(null);
        setReviewError(null);
        setReviewingId(candidateRecordId);
        try { setReviewed(await getInstallationCandidateRecord(candidateRecordId)); }
        catch (requestError: unknown) {
            setReviewError({
                candidateRecordId,
                technicalDetail: getAtlasErrorMessage(requestError, "The saved review record is currently unavailable."),
            });
        } finally {
            setReviewingId(null);
        }
    };

    const remove = async (candidateRecordId: string) => {
        if (!csrfToken || mutation || reviewingId !== null || preserveRecovery !== null || deleteUncertainId !== null) return;
        setMutation("delete"); setMutationError(null); setDeletedId(null);
        setRecoveryMessage(null);
        setReviewError(null);
        try {
            await deleteInstallationCandidateRecord(candidateRecordId, csrfToken);
            setRecords((current) => current.filter((record) => record.candidate_record_id !== candidateRecordId));
            setReviewed((current) => current?.candidate_record_id === candidateRecordId ? null : current);
            setDeletedId(candidateRecordId);
            setDeleteUncertainId(null);
        } catch (requestError: unknown) {
            setDeleteUncertainId(candidateRecordId);
            setMutationError({
                action: "delete",
                technicalDetail: getAtlasErrorMessage(requestError, "The saved review record could not be deleted."),
            });
        } finally { setMutation(null); }
    };

    const refreshAfterDelete = async (candidateRecordId: string) => {
        setLoading(true);
        setListError(null);
        try {
            const currentRecords = await listInstallationCandidateRecords();
            const stillPresent = currentRecords.some((record) => record.candidate_record_id === candidateRecordId);
            setRecords(currentRecords);
            setDeleteUncertainId(null);
            setMutationError(null);
            setReviewError(null);
            if (stillPresent) {
                setDeletedId(null);
                setRecoveryMessage("The review record is still saved. You can try deleting it again.");
            } else {
                setReviewed((current) => current?.candidate_record_id === candidateRecordId ? null : current);
                setDeletedId(candidateRecordId);
                setRecoveryMessage(null);
            }
        } catch (requestError: unknown) {
            setMutationError({
                action: "delete",
                technicalDetail: getAtlasErrorMessage(requestError, "Saved review records could not be refreshed."),
            });
        } finally { setLoading(false); }
    };

    const preservable = admission?.status === "admitted_but_non_executable" && admission.candidate_record !== null;
    const canRetryPreservation = preserveRecovery !== null
        && preserveRecovery.request.item_id === itemId
        && preserveRecovery.request.selection_id === selectionId
        && preserveRecovery.request.admission_fingerprint === admission?.admission_fingerprint;
    return <section aria-labelledby="candidate-lifecycle-heading" className="mt-5 border-t border-slate-700 pt-5">
        <h5 id="candidate-lifecycle-heading" className="font-semibold text-slate-100">Saved review records</h5>
        <p className="mt-1 text-sm text-slate-300">Saved records are for reference only. Saving one does not approve or start an installation.</p>
        <p className="mt-1 text-sm font-semibold text-amber-200">Saved records cannot install, deploy, dispatch, or run through an Agent.</p>
        {preservable && <div className="mt-3">
            {csrfToken && <button type="button" disabled={mutation !== null || reviewingId !== null || deleteUncertainId !== null || (preserveRecovery !== null && !canRetryPreservation)} onClick={() => void preserve()} className="rounded-lg border border-blue-400/50 px-3 py-2 text-sm font-semibold text-blue-200 disabled:opacity-50">{canRetryPreservation ? "Retry save" : "Save review record"}</button>}
            {!csrfToken && <p className="text-xs text-slate-400">Sign in as an operator to save this review record.</p>}
        </div>}
        {!preservable && admission && <p className="mt-3 text-sm text-slate-400">This check did not produce a review record that can be saved.</p>}
        {mutation === "preserve" && <p role="status" className="mt-3 text-sm text-slate-400">Saving review record…</p>}
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading saved review records…</p>}
        {!loading && listError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Atlas could not load the saved review records. Retry to check the list.</p>
            <details className="mt-3 text-red-100/80">
                <summary className="cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{listError}</p>
            </details>
            <button type="button" onClick={() => setListAttempt((attempt) => attempt + 1)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100">Retry list</button>
        </div>}
        {!loading && !listError && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No saved review records.</p>}
        {!loading && !listError && records.length > 0 && <ul aria-label="Saved review records" className="mt-4 space-y-3">
            {records.map((record) => <li key={record.candidate_record_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">{record.candidate_record.item_id} · {record.lifecycle_state === "active" ? "Inputs up to date" : "Inputs outdated"}</p>
                <details className="mt-1 text-xs text-slate-400"><summary className="mc-focusable cursor-pointer">Technical ID</summary><p className="mt-1 break-all">{record.candidate_record_id}</p></details>
                <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" disabled={reviewingId !== null || mutation !== null || reviewError?.candidateRecordId === record.candidate_record_id} onClick={() => void review(record.candidate_record_id)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-50">View saved record</button>
                    <a href={`/installation/candidate-records/${encodeURIComponent(record.candidate_record_id)}/readiness-review`} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-blue-200">Open readiness review</a>
                    <button type="button" disabled={!csrfToken || mutation !== null || reviewingId !== null || preserveRecovery !== null || deleteUncertainId !== null} onClick={() => void remove(record.candidate_record_id)} className="rounded border border-red-500/50 px-3 py-1.5 text-sm text-red-200 disabled:opacity-50">Delete review record</button>
                </div>
                {reviewingId === record.candidate_record_id && <p role="status" className="mt-3 text-sm text-slate-400">Opening saved review record…</p>}
                {reviewError?.candidateRecordId === record.candidate_record_id && <div role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                    <p>Atlas could not open this review record. Your saved review records are still available.</p>
                    <details className="mt-3 text-red-100/80">
                        <summary className="cursor-pointer">Technical details</summary>
                        <p className="mt-2 break-words">{reviewError.technicalDetail}</p>
                    </details>
                    <button type="button" disabled={reviewingId !== null} onClick={() => void review(record.candidate_record_id)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100 disabled:opacity-50">Retry opening record</button>
                </div>}
                <p className="mt-2 text-xs text-slate-400">Deleting this removes only the saved review record. It does not affect anything that has already started.</p>
            </li>)}
        </ul>}
        {mutationError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>{mutationError.action === "preserve"
                ? "Atlas could not confirm whether it saved the review record. Retry the same request to check."
                : "Atlas could not confirm whether the review record was removed. Refresh the list before trying again."}</p>
            <details className="mt-3 text-red-100/80">
                <summary className="cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{mutationError.technicalDetail}</p>
            </details>
            {mutationError.action === "delete" && deleteUncertainId && <button type="button" disabled={loading} onClick={() => void refreshAfterDelete(deleteUncertainId)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100 disabled:opacity-50">Refresh list</button>}
        </div>}
        {deletedId && <p role="status" className="mt-4 rounded-md border border-slate-700 p-3 text-sm text-slate-300">The saved review record was deleted.</p>}
        {recoveryMessage && <p role="status" className="mt-4 rounded-md border border-slate-700 p-3 text-sm text-slate-300">{recoveryMessage}</p>}
        {reviewed && <RecordDetails record={reviewed} />}
        <InstallationApprovalIntents records={records} csrfToken={csrfToken} />
    </section>;
}

function RecordDetails({ record }: { record: InstallationCandidateRecordEnvelopeV1 }) {
    const candidate = record.candidate_record;
    return <section aria-labelledby="saved-record-detail-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="saved-record-detail-heading" className="font-semibold text-slate-100">Saved review record</h6>
        <p className="mt-2 text-sm text-slate-300">Inputs {record.lifecycle_state === "active" ? "are up to date" : "are outdated"}. This record is not permission to install or run anything.</p>
        <details className="mt-3 text-sm text-slate-300">
            <summary className="mc-focusable cursor-pointer text-blue-200">Record details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Value name="Lifecycle state" value={record.lifecycle_state} />
                <Value name="Candidate record ID" value={record.candidate_record_id} />
                <Value name="Item ID" value={candidate.item_id} />
                <Value name="Catalog entry ID" value={candidate.catalog_entry_id} />
                <Value name="Created at" value={record.created_at} />
                <Value name="Evaluated at" value={candidate.evaluated_at} />
                <Value name="Valid until" value={candidate.valid_until} />
                <Value name="Admission fingerprint" value={record.admission_fingerprint} />
                <Value name="Candidate fingerprint" value={candidate.record_fingerprint} />
                <Value name="Envelope fingerprint" value={record.envelope_fingerprint} />
                <Value name="Plan fingerprint" value={candidate.plan_fingerprint} />
                <Value name="Selection ID" value={candidate.selection_id} />
            </dl>
            <dl aria-label="Saved candidate record authority flags" className="mt-4 grid gap-2 sm:grid-cols-2">
                <Value name="Approved" value="false" /><Value name="Executable" value="false" />
                <Value name="Deployable" value="false" /><Value name="Dispatchable" value="false" />
                <Value name="Agent execution supported" value="false" />
            </dl>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
