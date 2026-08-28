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
    const [error, setError] = useState<string | null>(null);
    const [mutation, setMutation] = useState<"preserve" | "delete" | null>(null);
    const [mutationError, setMutationError] = useState<string | null>(null);
    const [deletedId, setDeletedId] = useState<string | null>(null);

    useEffect(() => {
        let current = true;
        listInstallationCandidateRecords()
            .then((values) => { if (current) setRecords(values); })
            .catch((requestError: unknown) => {
                if (current) setError(getAtlasErrorMessage(requestError, "Saved candidate records are currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const preserve = async () => {
        if (!csrfToken || !selectionId || admission?.status !== "admitted_but_non_executable" || !admission.candidate_record || mutation) return;
        setMutation("preserve"); setMutationError(null); setDeletedId(null);
        try {
            const value = await preserveInstallationCandidateRecord(
                { item_id: itemId, selection_id: selectionId }, csrfToken, candidateRecordIdempotencyKey(),
            );
            setRecords((current) => [value, ...current.filter((record) => record.candidate_record_id !== value.candidate_record_id)]);
            setReviewed(value);
        } catch (requestError: unknown) {
            setMutationError(getAtlasErrorMessage(requestError, "The candidate record could not be preserved."));
        } finally { setMutation(null); }
    };

    const review = async (candidateRecordId: string) => {
        setError(null);
        try { setReviewed(await getInstallationCandidateRecord(candidateRecordId)); }
        catch (requestError: unknown) {
            setError(getAtlasErrorMessage(requestError, "The saved candidate record is currently unavailable."));
        }
    };

    const remove = async (candidateRecordId: string) => {
        if (!csrfToken || mutation) return;
        setMutation("delete"); setMutationError(null);
        try {
            await deleteInstallationCandidateRecord(candidateRecordId, csrfToken);
            setRecords((current) => current.filter((record) => record.candidate_record_id !== candidateRecordId));
            setReviewed((current) => current?.candidate_record_id === candidateRecordId ? null : current);
            setDeletedId(candidateRecordId);
        } catch (requestError: unknown) {
            setMutationError(getAtlasErrorMessage(requestError, "The saved candidate record could not be deleted."));
        } finally { setMutation(null); }
    };

    const preservable = admission?.status === "admitted_but_non_executable" && admission.candidate_record !== null;
    return <section aria-labelledby="candidate-lifecycle-heading" className="mt-5 border-t border-slate-700 pt-5">
        <h5 id="candidate-lifecycle-heading" className="font-semibold text-slate-100">Saved candidate record lifecycle</h5>
        <p className="mt-1 text-sm text-slate-300">Durable advisory records only. Preservation is not approval. Active means only that the exact source facts have not expired.</p>
        <p className="mt-1 text-sm font-semibold text-amber-200">Every record is non-executable, non-approved, non-deployable, non-dispatchable, and has no Agent execution support.</p>
        {preservable && <div className="mt-3">
            {csrfToken && <button type="button" disabled={mutation !== null} onClick={() => void preserve()} className="rounded-lg border border-blue-400/50 px-3 py-2 text-sm font-semibold text-blue-200 disabled:opacity-50">Preserve candidate record</button>}
            {!csrfToken && <p className="text-xs text-slate-400">An authenticated operator session with mutation protection is required to preserve this record.</p>}
        </div>}
        {!preservable && admission && <p className="mt-3 text-sm text-slate-400">This admission cannot be preserved because it has no positive non-executable candidate record.</p>}
        {mutation === "preserve" && <p role="status" className="mt-3 text-sm text-slate-400">Preserving candidate record…</p>}
        {loading && <p role="status" className="mt-4 text-sm text-slate-400">Loading saved candidate records…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {!loading && !error && records.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No saved candidate records.</p>}
        {!loading && !error && records.length > 0 && <ul aria-label="Saved candidate records" className="mt-4 space-y-3">
            {records.map((record) => <li key={record.candidate_record_id} className="rounded-md border border-slate-700 p-3">
                <p className="font-semibold text-slate-200">{record.candidate_record.item_id} · {record.lifecycle_state}</p>
                <p className="mt-1 break-all text-xs text-slate-400">Record ID: {record.candidate_record_id}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" onClick={() => void review(record.candidate_record_id)} className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200">Review saved record</button>
                    <button type="button" disabled={!csrfToken || mutation !== null} onClick={() => void remove(record.candidate_record_id)} className="rounded border border-red-500/50 px-3 py-1.5 text-sm text-red-200 disabled:opacity-50">Delete saved record</button>
                </div>
                <p className="mt-2 text-xs text-slate-400">Deletion removes only this advisory record. It cannot be replayed and does not cancel any external activity.</p>
            </li>)}
        </ul>}
        {mutationError && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{mutationError}</p>}
        {deletedId && <p role="status" className="mt-4 rounded-md border border-slate-700 p-3 text-sm text-slate-300">Deleted saved record {deletedId}. The advisory record is gone and cannot be replayed.</p>}
        {reviewed && <RecordDetails record={reviewed} />}
        <InstallationApprovalIntents records={records} csrfToken={csrfToken} />
    </section>;
}

function RecordDetails({ record }: { record: InstallationCandidateRecordEnvelopeV1 }) {
    const candidate = record.candidate_record;
    return <section aria-labelledby="saved-record-detail-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h6 id="saved-record-detail-heading" className="font-semibold text-slate-100">Saved non-executable candidate record</h6>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
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
        <dl aria-label="Saved candidate record authority flags" className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <Value name="Approved" value="false" /><Value name="Executable" value="false" />
            <Value name="Deployable" value="false" /><Value name="Dispatchable" value="false" />
            <Value name="Agent execution supported" value="false" />
        </dl>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
