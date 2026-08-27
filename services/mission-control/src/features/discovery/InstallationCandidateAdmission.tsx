import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import { getInstallationCandidateAdmission } from "../../api/installationCandidateAdmission";
import type {
    InstallationCandidateAdmissionReason,
    InstallationCandidateAdmissionV1,
    InstallationCandidateRecordV1,
} from "../../types/installationCandidateAdmission";

const REASON_LABELS: Record<InstallationCandidateAdmissionReason, string> = {
    input_invalid: "A required admission input is invalid.",
    input_unavailable: "A required admission input is unavailable.",
    installation_plan_not_review_ready: "The installation plan is not ready for review.",
    destination_selection_not_active: "The destination selection is not active.",
    destination_selection_expired: "The destination selection has expired.",
    destination_identity_unavailable: "The current destination identity is unavailable.",
    destination_replaced_or_moved: "The destination was replaced or moved.",
    capability_assessment_stale: "The capability assessment is stale.",
    capability_assessment_mismatched: "The capability assessment does not match these exact inputs.",
    capability_assessment_not_admissible: "The capability assessment is not admissible.",
    authority_invariant_violated: "A fixed non-authority invariant was violated.",
};

export function InstallationCandidateAdmission({ itemId, selectionId }: { itemId: string; selectionId: string | null }) {
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
                if (current) setError(getAtlasErrorMessage(requestError, "Installation candidate admission is currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [itemId, selectionId]);

    return <section aria-labelledby="candidate-admission-heading" className="mt-5 rounded-lg border border-slate-700 p-4">
        <h4 id="candidate-admission-heading" className="font-semibold text-slate-100">Installation candidate admission</h4>
        <p className="mt-1 text-sm font-semibold text-amber-200">Admission is not approval, not execution, and not installation readiness.</p>
        <p className="mt-1 text-sm text-slate-300">This is an ephemeral, read-only description. It grants no authority and initiates no work.</p>
        {!selectionId && <p className="mt-3 text-sm text-slate-400">No destination selection is available for candidate admission.</p>}
        {selectionId && loading && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Loading installation candidate admission…</p>}
        {selectionId && !loading && error && <p role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {selectionId && !loading && !error && !admission && <p className="mt-3 text-sm text-slate-400">No installation candidate admission was returned.</p>}
        {selectionId && admission && !loading && !error && <Admission admission={admission} />}
    </section>;
}

function Admission({ admission }: { admission: InstallationCandidateAdmissionV1 }) {
    return <div className="mt-4">
        <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 font-semibold text-amber-200">Admission status: {admission.status}</p>
        <h5 className="mt-5 text-sm font-semibold text-slate-200">Exact source linkage</h5>
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
        <h5 className="mt-5 text-sm font-semibold text-slate-200">Ordered admission reasons</h5>
        {admission.reason_codes.length === 0
            ? <p className="mt-2 text-sm text-slate-400">No admission reasons.</p>
            : <ol aria-label="Installation candidate admission reasons" className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-300">
                {admission.reason_codes.map((reason) => <li key={reason}>{REASON_LABELS[reason]} <code className="text-xs text-slate-400">{reason}</code></li>)}
            </ol>}
        {admission.candidate_record
            ? <CandidateRecord record={admission.candidate_record} />
            : <p className="mt-5 rounded-md border border-slate-700 p-3 text-sm text-slate-300">Candidate record: not present.</p>}
    </div>;
}

function CandidateRecord({ record }: { record: InstallationCandidateRecordV1 }) {
    return <section aria-labelledby="candidate-record-heading" className="mt-5 rounded-md border border-slate-700 p-3">
        <h5 id="candidate-record-heading" className="text-sm font-semibold text-slate-200">Non-executable candidate record</h5>
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
