import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import { getInstallationCandidateAdmission } from "../../api/installationCandidateAdmission";
import type {
    InstallationCandidateAdmissionReason,
    InstallationCandidateAdmissionV1,
    InstallationCandidateRecordV1,
} from "../../types/installationCandidateAdmission";
import { InstallationCandidateLifecycle } from "./InstallationCandidateLifecycle";

const REASON_LABELS: Record<InstallationCandidateAdmissionReason, string> = {
    input_invalid: "Some required information is invalid.",
    input_unavailable: "Some required information is unavailable.",
    installation_plan_not_review_ready: "The installation plan is not ready for review.",
    destination_selection_not_active: "The saved guest choice is no longer active.",
    destination_selection_expired: "The saved guest choice has expired.",
    destination_identity_unavailable: "Atlas could not verify the guest identity.",
    destination_replaced_or_moved: "The guest moved or was replaced since it was selected.",
    capability_assessment_stale: "The installation capability check has expired.",
    capability_assessment_mismatched: "The installation capability check used different information.",
    capability_assessment_not_admissible: "The installation capability check does not support a review record.",
    authority_invariant_violated: "A required safety check failed.",
};

export function InstallationCandidateAdmission({ itemId, selectionId, csrfToken = null }: { itemId: string; selectionId: string | null; csrfToken?: string | null }) {
    const [admission, setAdmission] = useState<InstallationCandidateAdmissionV1 | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!selectionId) return;
        let current = true;
        queueMicrotask(() => {
            if (current) { setAdmission(null); setLoading(true); setError(null); }
        });
        getInstallationCandidateAdmission(itemId, selectionId)
            .then((value) => { if (current) setAdmission(value); })
            .catch((requestError: unknown) => {
                if (current) setError(getAtlasErrorMessage(requestError, "The candidate record check is currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [itemId, selectionId]);

    return <section aria-labelledby="candidate-admission-heading" className="mt-5 rounded-lg border border-slate-700 p-4">
        <h4 id="candidate-admission-heading" className="font-semibold text-slate-100">Candidate record check</h4>
        <p className="mt-1 text-sm font-semibold text-amber-200">This check only assesses whether a review-only candidate record is available. It does not approve or start an installation.</p>
        <p className="mt-1 text-sm text-slate-300">The check is read-only and grants no authority.</p>
        {!selectionId && <p className="mt-3 text-sm text-slate-400">Select a prospective destination above to check whether a candidate record is available.</p>}
        {selectionId && loading && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Checking candidate record availability…</p>}
        {selectionId && !loading && error && <p role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {selectionId && !loading && !error && !admission && <p className="mt-3 text-sm text-slate-400">No candidate review result was returned.</p>}
        {selectionId && admission && !loading && !error && <Admission admission={admission} />}
        {admission && <InstallationCandidateLifecycle admission={admission} itemId={itemId} selectionId={selectionId} csrfToken={csrfToken} />}
    </section>;
}

function Admission({ admission }: { admission: InstallationCandidateAdmissionV1 }) {
    const admitted = admission.status === "admitted_but_non_executable";
    const status = admitted
        ? "A review-only candidate record is available. It cannot be executed, deployed, or dispatched."
        : "No candidate record is available yet. Review the reasons below.";
    return <div className="mt-4">
        <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 font-semibold text-amber-200">{status}</p>
        {admission.reason_codes.length === 0
            ? <p className="mt-3 text-sm text-slate-400">No issues were reported by this check.</p>
            : <>
                <h5 className="mt-5 text-sm font-semibold text-slate-200">{admitted ? "Notes from the admission check" : "Reasons no candidate record is available"}</h5>
                <ol aria-label="Candidate record check reasons" className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-300">
                    {admission.reason_codes.map((reason) => <li key={reason}>{REASON_LABELS[reason]}</li>)}
                </ol>
                <details className="mt-4 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400">
                    <summary className="cursor-pointer font-medium text-slate-300">Technical reason codes</summary>
                    <ol className="mt-2 list-decimal space-y-1 pl-5">
                        {admission.reason_codes.map((reason) => <li key={reason}><code className="break-all text-xs">{reason}</code></li>)}
                    </ol>
                </details>
            </>}
        <details className="mt-4 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400">
            <summary className="cursor-pointer font-medium text-slate-300">Source linkage and technical identifiers</summary>
            <dl aria-label="Candidate admission source linkage" className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Plan fingerprint" value={admission.plan_fingerprint} />
                <Value name="Selection fingerprint" value={admission.selection_fingerprint} />
                <Value name="Selected destination fingerprint" value={admission.selected_destination_fingerprint} />
                <Value name="Current destination fingerprint" value={admission.current_destination_fingerprint} />
                <Value name="Capability assessment fingerprint" value={admission.capability_assessment_fingerprint} />
                <Value name="Provider fact set fingerprint" value={admission.provider_fact_set_fingerprint} />
                <Value name="Evaluated at" value={admission.evaluated_at} />
                <Value name="Admission fingerprint" value={admission.admission_fingerprint} />
            </dl>
        </details>
        {admission.candidate_record && <CandidateRecord record={admission.candidate_record} />}
    </div>;
}

function CandidateRecord({ record }: { record: InstallationCandidateRecordV1 }) {
    return <section aria-labelledby="candidate-record-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h5 id="candidate-record-heading" className="text-sm font-semibold text-slate-200">Review-only candidate record</h5>
        <p className="mt-1 text-sm text-slate-300">This advisory record cannot be approved, run, deployed, or dispatched.</p>
        <details className="mt-3 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400">
            <summary className="cursor-pointer font-medium text-slate-300">Record details</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Item ID" value={record.item_id} />
                <Value name="Catalog entry ID" value={record.catalog_entry_id} />
                <Value name="Plan fingerprint" value={record.plan_fingerprint} />
                <Value name="Selection ID" value={record.selection_id} />
                <Value name="Selected destination fingerprint" value={record.selected_destination_fingerprint} />
                <Value name="Current destination fingerprint" value={record.current_destination_fingerprint} />
                <Value name="Capability assessment fingerprint" value={record.capability_assessment_fingerprint} />
                <Value name="Provider fact set fingerprint" value={record.provider_fact_set_fingerprint} />
                <Value name="Evaluated at" value={record.evaluated_at} />
                <Value name="Valid until" value={record.valid_until} />
                <Value name="Record fingerprint" value={record.record_fingerprint} />
            </dl>
            <h6 className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Authority flags</h6>
            <dl aria-label="Candidate record authority flags" className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                <Value name="Approved" value="false" />
                <Value name="Executable" value="false" />
                <Value name="Deployable" value="false" />
                <Value name="Dispatchable" value="false" />
                <Value name="Agent execution supported" value="false" />
            </dl>
        </details>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
