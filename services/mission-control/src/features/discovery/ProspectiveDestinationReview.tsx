import { useEffect, useState } from "react";

import { getAtlasErrorMessage } from "../../api/atlas";
import {
    assessInstallationAdmission,
    installationIdempotencyKey,
    listProspectiveInstallationDestinations,
    selectProspectiveInstallationDestination,
} from "../../api/installationDestination";
import type { InstallationPlan } from "../../types/installationPlan";
import type {
    InstallationAdmissionAssessmentV1,
    InstallationAdmissionReasonCode,
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
} from "../../types/installationDestination";
import { InstallationCapabilityAssessment } from "./InstallationCapabilityAssessment";
import { InstallationCandidateAdmission } from "./InstallationCandidateAdmission";

const REASON_LABELS: Record<InstallationAdmissionReasonCode, { title: string; detail: string }> = {
    installation_plan_conflicted: { title: "Plan contains conflicting information", detail: "Resolve the conflicting facts before continuing." },
    installation_plan_missing_deployment_artifact: { title: "Installation file is missing", detail: "The plan does not identify the file needed to install this application." },
    installation_plan_incompatible: { title: "Plan reports an incompatible environment", detail: "The application may not work in the environment described by the plan." },
    installation_plan_stale_evidence: { title: "Plan information is out of date", detail: "Refresh the plan evidence before checking this VM." },
    installation_plan_insufficient_information: { title: "Plan is missing required information", detail: "Atlas needs more information to check this VM." },
    destination_selection_missing: { title: "Select a VM first", detail: "Choose a current VM before requesting this check." },
    destination_selection_expired: { title: "VM selection expired", detail: "Select the VM again to request a new check." },
    destination_unavailable: { title: "VM cannot be checked right now", detail: "Atlas could not find the selected VM." },
    destination_identity_unavailable: { title: "VM identity could not be checked", detail: "Atlas could not confirm this is the same VM you selected." },
    destination_replaced_or_moved: { title: "VM has changed", detail: "Its location or identity no longer matches your saved selection." },
    destination_installation_capability_unknown: { title: "VM readiness is unknown", detail: "Atlas has not confirmed that this VM can run the app or accept an installation." },
    installation_interest_missing: { title: "Check is no longer current", detail: "Start a new check for this plan and VM." },
    installation_interest_expired: { title: "Check has expired", detail: "Start a new check for this plan and VM." },
    installation_interest_plan_stale: { title: "Plan changed", detail: "Review the latest plan and start a new check." },
    installation_interest_destination_stale: { title: "VM selection changed", detail: "Select the current VM and start a new check." },
    agent_install_container_unsupported: { title: "Installation planning is not available yet", detail: "Atlas Agent cannot prepare this type of installation yet." },
};

const ASSESSMENT_STATUS_LABELS = {
    blocked: "Blocked by the issues below",
    preconditions_satisfied_but_unsupported: "Atlas cannot plan this installation yet",
} as const;

type AssessmentRequest = {
    item_id: string;
    catalog_entry_id: string;
    plan_fingerprint: string;
    selection_id: string;
};

export function ProspectiveDestinationReview({ plan, csrfToken }: { plan: InstallationPlan; csrfToken: string | null }) {
    const [destinations, setDestinations] = useState<ProspectiveInstallationDestinationV1[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selection, setSelection] = useState<InstallationDestinationSelectionV1 | null>(null);
    const [assessment, setAssessment] = useState<InstallationAdmissionAssessmentV1 | null>(null);
    const [mutation, setMutation] = useState<"selection" | "assessment" | null>(null);
    const [mutationError, setMutationError] = useState<{
        action: "selection" | "assessment";
        technicalDetail: string;
    } | null>(null);
    const [selectionRecovery, setSelectionRecovery] = useState<{
        destination: ProspectiveInstallationDestinationV1;
        idempotencyKey: string;
    } | null>(null);
    const [assessmentRecovery, setAssessmentRecovery] = useState<{
        request: AssessmentRequest;
        idempotencyKey: string;
    } | null>(null);

    useEffect(() => {
        let current = true;
        listProspectiveInstallationDestinations()
            .then((values) => { if (current) setDestinations(values); })
            .catch((requestError: unknown) => {
                if (current) setError(getAtlasErrorMessage(requestError, "Atlas cannot list available VMs right now."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, []);

    const select = async (destination: ProspectiveInstallationDestinationV1, idempotencyKey: string) => {
        if (!csrfToken || mutation) return;
        setMutation("selection");
        setMutationError(null);
        setAssessment(null);
        setAssessmentRecovery(null);
        try {
            const next = await selectProspectiveInstallationDestination(
                { resource_id: destination.resource_id, enumeration_token: destination.enumeration_token },
                csrfToken,
                idempotencyKey,
            );
            setSelection(next);
            setAssessment(null);
            setSelectionRecovery(null);
            setAssessmentRecovery(null);
        } catch (requestError: unknown) {
            setSelectionRecovery({ destination, idempotencyKey });
            setMutationError({
                action: "selection",
                technicalDetail: getAtlasErrorMessage(requestError, "The prospective destination selection could not be recorded."),
            });
        } finally { setMutation(null); }
    };

    const assess = async () => {
        if (!csrfToken || !selection || selection.status !== "active" || mutation) return;
        setMutation("assessment");
        setMutationError(null);
        setAssessment(null);
        const request: AssessmentRequest = {
            item_id: plan.application.item_id,
            catalog_entry_id: plan.application.catalog_entry_id,
            plan_fingerprint: plan.fingerprint.value,
            selection_id: selection.selection_id,
        };
        const canReuseRetryKey = assessmentRecovery !== null
            && assessmentRecovery.request.item_id === request.item_id
            && assessmentRecovery.request.catalog_entry_id === request.catalog_entry_id
            && assessmentRecovery.request.plan_fingerprint === request.plan_fingerprint
            && assessmentRecovery.request.selection_id === request.selection_id;
        const idempotencyKey = canReuseRetryKey ? assessmentRecovery.idempotencyKey : installationIdempotencyKey();
        try {
            setAssessment(await assessInstallationAdmission(request, csrfToken, idempotencyKey));
            setAssessmentRecovery(null);
        } catch (requestError: unknown) {
            setAssessmentRecovery({ request, idempotencyKey });
            setMutationError({
                action: "assessment",
                technicalDetail: getAtlasErrorMessage(requestError, "Installation admission could not be assessed."),
            });
        } finally { setMutation(null); }
    };

    const assessmentDisabledReason = !csrfToken
        ? "Mission Control needs an active sign-in before it can save a VM selection."
        : selectionRecovery !== null
            ? "Retry the saved VM selection before requesting a check."
            : selection?.status !== "active"
                ? "Select a current VM before requesting a check."
                : null;
    const canRetryAssessment = assessmentRecovery !== null
        && assessmentRecovery.request.item_id === plan.application.item_id
        && assessmentRecovery.request.catalog_entry_id === plan.application.catalog_entry_id
        && assessmentRecovery.request.plan_fingerprint === plan.fingerprint.value
        && assessmentRecovery.request.selection_id === selection?.selection_id;

    return <section aria-labelledby="prospective-destination-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h3 id="prospective-destination-heading" className="text-lg font-semibold text-white">Choose a VM for assessment</h3>
        <p className="mt-1 text-sm text-slate-400">Choose an existing Proxmox VM for a check. This saves a temporary selection; it does not install software or approve an installation.</p>
        {loading && <p role="status" aria-live="polite" className="mt-4 text-sm text-slate-400">Loading available VMs…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</p>}
        {!loading && !error && destinations.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No existing Proxmox VMs are available to assess.</p>}
        {!loading && !error && destinations.length > 0 && <ul aria-label="VMs available for assessment" className="mt-4 space-y-3">
            {destinations.map((destination) => {
                const recoveryAttempt = selectionRecovery?.destination.resource_id === destination.resource_id
                    && selectionRecovery.destination.enumeration_token === destination.enumeration_token
                    ? selectionRecovery
                    : null;
                return (
                    <li key={`${destination.resource_id}-${destination.destination_fingerprint}`} className="rounded-lg border border-slate-700 p-4">
                        <dl className="grid gap-2 text-sm sm:grid-cols-2">
                            <Value name="VM ID" value={destination.resource_id} />
                            <Value name="Provider" value="Proxmox" />
                        </dl>
                        <button
                            type="button"
                            aria-label={recoveryAttempt
                                ? `Retry selection — VM ${destination.resource_id}`
                                : `Select VM ${destination.resource_id} for assessment`}
                            disabled={!csrfToken || mutation !== null || (selectionRecovery !== null && !recoveryAttempt)}
                            onClick={() => void select(
                                recoveryAttempt ? recoveryAttempt.destination : destination,
                                recoveryAttempt ? recoveryAttempt.idempotencyKey : installationIdempotencyKey(),
                            )}
                            className="mt-3 rounded-lg border border-blue-400/50 px-3 py-2 text-sm font-semibold text-blue-200 disabled:cursor-not-allowed disabled:opacity-50"
                        >{recoveryAttempt ? "Retry selection" : "Select this VM for assessment"}</button>
                        {!csrfToken && <p className="mt-2 text-xs text-slate-400">An authenticated session is required to save a VM selection.</p>}
                    </li>
                );
            })}
        </ul>}
        {mutation === "selection" && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Saving VM selection…</p>}
        {mutationError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
            <p>{mutationError.action === "selection"
                ? "Atlas could not confirm whether it saved this VM selection. Retry the same selection to check its status."
                : "Atlas could not confirm the check result. Retry the same check to retrieve it."}</p>
            <details className="mt-3 text-red-100/80">
                <summary className="cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{mutationError.technicalDetail}</p>
            </details>
        </div>}
        {selection && <SelectionSummary selection={selection} />}
        {selection && <div className="mt-4">
            <p className="mb-2 text-sm text-slate-400">This checks the plan and selected VM only. It does not install or authorize anything.</p>
            <button type="button" disabled={assessmentDisabledReason !== null || mutation !== null} onClick={() => void assess()} className="rounded-lg border border-blue-400/50 px-3 py-2 text-sm font-semibold text-blue-200 disabled:cursor-not-allowed disabled:opacity-50">{canRetryAssessment ? "Retry check" : "Check this plan and VM"}</button>
            {assessmentDisabledReason && <p className="mt-2 text-xs text-slate-400">{assessmentDisabledReason}</p>}
        </div>}
        {mutation === "assessment" && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Checking the plan and VM…</p>}
        {assessment && <AssessmentSummary assessment={assessment} />}
        <InstallationCapabilityAssessment itemId={plan.application.item_id} selectionId={selection?.selection_id ?? null} />
        <InstallationCandidateAdmission itemId={plan.application.item_id} selectionId={selection?.selection_id ?? null} csrfToken={csrfToken} />
    </section>;
}

function SelectionSummary({ selection }: { selection: InstallationDestinationSelectionV1 }) {
    const terminal = selection.status !== "active";
    return <section aria-labelledby="selection-summary-heading" className={`mt-5 rounded-lg border p-4 ${terminal ? "border-amber-500/40" : "border-slate-700"}`}>
        <h4 id="selection-summary-heading" className="font-semibold text-slate-100">VM selected for assessment</h4>
        <p className="mt-1 text-sm text-slate-300">This is a temporary choice for a check. Atlas has not confirmed that this VM can run the app. It does not install or approve anything. It does not authorize execution.</p>
        {selection.status !== "active" && <p role="status" className="mt-2 font-semibold text-amber-200">{terminalSelectionMessage(selection.status)}</p>}
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <Value name="VM ID" value={selection.resource_id} />
            <Value name="Selection" value={selectionStatusLabel(selection.status)} />
            <Value name="Expires at" value={selection.expires_at} />
        </dl>
        <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-300">Selection details</summary>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <Value name="Selection ID" value={selection.selection_id} />
                <Value name="Selected at" value={selection.selected_at} />
                <Value name="Selected by" value={selection.selected_by} />
            </dl>
        </details>
    </section>;
}

function AssessmentSummary({ assessment }: { assessment: InstallationAdmissionAssessmentV1 }) {
    const unsupported = assessment.assessment_status === "preconditions_satisfied_but_unsupported";
    return <section aria-labelledby="admission-assessment-heading" className="mt-5 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
        <h4 id="admission-assessment-heading" className="font-semibold text-slate-100">Check result</h4>
        <p role="status" className="mt-2 font-semibold text-amber-200">{ASSESSMENT_STATUS_LABELS[assessment.assessment_status]}</p>
        {unsupported && <p className="mt-2 text-sm text-slate-300">Atlas has not confirmed that this VM can run the app. This check does not authorize an installation.</p>}
        <p className="mt-2 text-sm text-slate-300">This check did not determine whether the app qualifies for installation or approve an install.</p>
        <h5 className="mt-4 text-sm font-semibold text-slate-200">What needs attention</h5>
        <ul aria-label="Issues to review" className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-300">
            {assessment.reason_codes.map((code) => <li key={code}><span className="font-semibold">{REASON_LABELS[code].title}</span><span> — {REASON_LABELS[code].detail}</span></li>)}
        </ul>
        <details className="mt-4 text-sm text-slate-400">
            <summary className="cursor-pointer">Technical details</summary>
            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                <Value name="Assessment status code" value={assessment.assessment_status} />
                <Value name="Candidate eligibility evaluated" value={String(assessment.candidate_eligibility_evaluated)} />
            </dl>
            <h5 className="mt-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Issue codes</h5>
            <ul className="mt-1 list-disc space-y-1 pl-5">
                {assessment.reason_codes.map((code) => <li key={code}><code className="break-all">{code}</code></li>)}
            </ul>
        </details>
    </section>;
}

function selectionStatusLabel(status: InstallationDestinationSelectionV1["status"]): string {
    switch (status) {
        case "active": return "Current";
        case "cancelled": return "Cancelled";
        case "expired": return "Expired";
        case "stale": return "Out of date";
    }
}

function terminalSelectionMessage(status: Exclude<InstallationDestinationSelectionV1["status"], "active">): string {
    switch (status) {
        case "cancelled": return "Selection was cancelled. Select this VM again to start a new check.";
        case "expired": return "Selection expired. Select this VM again to start a new check.";
        case "stale": return "The destination changed. Select the current VM to start a new check.";
    }
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}

export { REASON_LABELS };
