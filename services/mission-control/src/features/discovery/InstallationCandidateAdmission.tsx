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
    input_unavailable: "Atlas cannot check the result because required information is unavailable.",
    installation_plan_not_review_ready: "The installation plan is not ready for review.",
    destination_selection_not_active: "The selected destination is no longer active.",
    destination_selection_expired: "The selected destination has expired. Select it again.",
    destination_identity_unavailable: "Atlas cannot verify the current destination.",
    destination_replaced_or_moved: "The destination changed after selection. Select the current destination again.",
    capability_assessment_stale: "The capability check has expired. Run a fresh check.",
    capability_assessment_mismatched: "The capability check does not match the current plan or destination. Run a fresh check.",
    capability_assessment_not_admissible: "The capability check did not confirm that requirements are met.",
    authority_invariant_violated: "Atlas blocked this record because a safety rule was violated.",
};

export function InstallationCandidateAdmission({ itemId, selectionId, csrfToken = null }: { itemId: string; selectionId: string | null; csrfToken?: string | null }) {
    const [admission, setAdmission] = useState<InstallationCandidateAdmissionV1 | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loadAttempt, setLoadAttempt] = useState(0);

    useEffect(() => {
        if (!selectionId) return;
        let current = true;
        queueMicrotask(() => {
            if (current) { setAdmission(null); setLoading(true); setError(null); }
        });
        getInstallationCandidateAdmission(itemId, selectionId)
            .then((value) => { if (current) setAdmission(value); })
            .catch((requestError: unknown) => {
                if (current) setError(getAtlasErrorMessage(requestError, "Review record check is currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [itemId, selectionId, loadAttempt]);

    return <section aria-labelledby="candidate-admission-heading" className="mt-5 rounded-lg border border-slate-700 p-4">
        <h4 id="candidate-admission-heading" className="font-semibold text-slate-100">Review record check</h4>
        <p className="mt-1 text-sm text-slate-300">Checks whether Atlas can save a review record for this plan and VM. It does not approve or start an installation.</p>
        {!selectionId && <p className="mt-3 text-sm text-slate-400">Select a VM above before checking whether a review record can be saved.</p>}
        {selectionId && loading && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Checking whether a review record can be saved…</p>}
        {selectionId && !loading && error && <div role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Atlas could not check whether a review record can be saved for this VM. Retry the check.</p>
            <details className="mt-3 text-red-100/80">
                <summary className="cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{error}</p>
            </details>
            <button type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100">Retry check</button>
        </div>}
        {selectionId && !loading && !error && !admission && <p className="mt-3 text-sm text-slate-400">No result was returned for the review record check.</p>}
        {selectionId && admission && !loading && !error && <Admission admission={admission} />}
        {admission && <InstallationCandidateLifecycle admission={admission} itemId={itemId} selectionId={selectionId} csrfToken={csrfToken} />}
    </section>;
}

function Admission({ admission }: { admission: InstallationCandidateAdmissionV1 }) {
    const statusSummary = admission.status === "admitted_but_non_executable"
        ? "A review record is available to save"
        : "This plan is not ready to save for review";

    return <div className="mt-4">
        <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 font-semibold text-amber-200">{statusSummary}</p>
        <h5 className="mt-5 text-sm font-semibold text-slate-200">What needs attention</h5>
        {admission.reason_codes.length === 0
            ? <p className="mt-2 text-sm text-slate-400">No issues were reported.</p>
            : <ol aria-label="Review record check reasons" className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-300">
                {admission.reason_codes.map((reason) => <li key={reason}>{REASON_LABELS[reason]}</li>)}
            </ol>}
        <details className="mt-4 rounded-lg border border-slate-700 px-4 py-3">
            <summary className="mc-focusable cursor-pointer text-sm font-semibold text-slate-200">Technical details</summary>
            <h5 className="mt-4 text-sm font-semibold text-slate-200">Exact source linkage</h5>
            <dl className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Plan fingerprint" value={admission.plan_fingerprint} />
                <Value name="Selection fingerprint" value={admission.selection_fingerprint} />
                <Value name="Selected destination fingerprint" value={admission.selected_destination_fingerprint} />
                <Value name="Current destination fingerprint" value={admission.current_destination_fingerprint} />
                <Value name="Capability assessment fingerprint" value={admission.capability_assessment_fingerprint} />
                <Value name="Provider fact set fingerprint" value={admission.provider_fact_set_fingerprint} />
                <Value name="Evaluated at" value={admission.evaluated_at} />
                <Value name="Admission fingerprint" value={admission.admission_fingerprint} />
            </dl>
            {admission.reason_codes.length > 0 && <>
                <h5 className="mt-5 text-sm font-semibold text-slate-200">Reason codes</h5>
                <ol aria-label="Installation candidate admission reason codes" className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-300">
                    {admission.reason_codes.map((reason) => <li key={reason}><code>{reason}</code></li>)}
                </ol>
            </>}
            {admission.candidate_record
                ? <CandidateRecord record={admission.candidate_record} />
                : <p className="mt-5 rounded-md border border-slate-700 p-3 text-sm text-slate-300">Candidate record: not present.</p>}
        </details>
    </div>;
}

function CandidateRecord({ record }: { record: InstallationCandidateRecordV1 }) {
    return <section aria-labelledby="candidate-record-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h5 id="candidate-record-heading" className="text-sm font-semibold text-slate-200">Review record details</h5>
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
        <h6 className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Fixed authority flags</h6>
        <dl aria-label="Candidate record authority flags" className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
            <Value name="Approved" value="false" />
            <Value name="Executable" value="false" />
            <Value name="Deployable" value="false" />
            <Value name="Dispatchable" value="false" />
            <Value name="Agent execution supported" value="false" />
        </dl>
    </section>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
