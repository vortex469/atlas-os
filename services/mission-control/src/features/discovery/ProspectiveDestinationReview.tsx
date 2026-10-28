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
    installation_plan_conflicted: { title: "Installation plan conflicted", detail: "The reviewed plan contains conflicting evidence or facts." },
    installation_plan_missing_deployment_artifact: { title: "Installation plan missing deployment artifact", detail: "The reviewed plan has no required deployment artifact." },
    installation_plan_incompatible: { title: "Installation plan incompatible", detail: "The reviewed plan reports an incompatible application environment." },
    installation_plan_stale_evidence: { title: "Installation plan evidence is stale", detail: "Required plan evidence is outside its accepted freshness window." },
    installation_plan_insufficient_information: { title: "Installation plan has insufficient information", detail: "The reviewed plan is missing facts required for consistent assessment." },
    destination_selection_missing: { title: "Destination selection missing", detail: "No exact prospective destination selection is bound to this assessment." },
    destination_selection_expired: { title: "Destination selection expired", detail: "The recorded prospective destination selection is no longer current." },
    destination_unavailable: { title: "Destination unavailable", detail: "Atlas could not currently resolve the selected destination." },
    destination_identity_unavailable: { title: "Destination identity unavailable", detail: "Atlas could not establish the current opaque identity of the selected destination." },
    destination_replaced_or_moved: { title: "Destination replaced or moved", detail: "The current guest incarnation or placement no longer matches the immutable selection." },
    destination_installation_capability_unknown: { title: "Destination installation capability unknown", detail: "Atlas has not established in-guest installability, runtime, transport, or readiness for this destination." },
    installation_interest_missing: { title: "Installation interest missing", detail: "No current ephemeral assessment interest was available." },
    installation_interest_expired: { title: "Installation interest expired", detail: "The ephemeral assessment interest expired before evaluation." },
    installation_interest_plan_stale: { title: "Installation interest plan stale", detail: "The interest does not match the exact current InstallationPlan fingerprint." },
    installation_interest_destination_stale: { title: "Installation interest destination stale", detail: "The interest does not match the exact current destination selection." },
    agent_install_container_unsupported: { title: "Agent install-container unsupported", detail: "Atlas Agent cannot plan this install intent yet." },
};

const ASSESSMENT_STATUS_LABELS = {
    blocked: "Blocked by the issues below",
    preconditions_satisfied_but_unsupported: "Plan and destination checks passed; installation support is unavailable",
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
                if (current) setError(getAtlasErrorMessage(requestError, "Prospective installation destinations are currently unavailable."));
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
        ? "An authenticated operator session with mutation protection is required."
        : selectionRecovery !== null
            ? "Resolve the pending destination selection before assessing."
            : selection?.status !== "active"
                ? "Assessment requires a current active prospective destination selection."
                : null;
    const canRetryAssessment = assessmentRecovery !== null
        && assessmentRecovery.request.item_id === plan.application.item_id
        && assessmentRecovery.request.catalog_entry_id === plan.application.catalog_entry_id
        && assessmentRecovery.request.plan_fingerprint === plan.fingerprint.value
        && assessmentRecovery.request.selection_id === selection?.selection_id;

    return <section aria-labelledby="prospective-destination-heading" className="mt-6 border-t border-slate-700 pt-5">
        <h3 id="prospective-destination-heading" className="text-lg font-semibold text-white">Prospective installation destination</h3>
        <p className="mt-1 text-sm text-slate-400">Review a server-enumerated existing guest as a possible destination for assessment only.</p>
        {loading && <p role="status" aria-live="polite" className="mt-4 text-sm text-slate-400">Loading prospective installation destinations…</p>}
        {!loading && error && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</p>}
        {!loading && !error && destinations.length === 0 && <p role="status" className="mt-4 text-sm text-slate-400">No prospective installation destinations are currently available.</p>}
        {!loading && !error && destinations.length > 0 && <ul aria-label="Prospective installation destinations" className="mt-4 space-y-3">
            {destinations.map((destination) => {
                const recoveryAttempt = selectionRecovery?.destination.resource_id === destination.resource_id
                    && selectionRecovery.destination.enumeration_token === destination.enumeration_token
                    ? selectionRecovery
                    : null;
                return (
                    <li key={`${destination.resource_id}-${destination.destination_fingerprint}`} className="rounded-lg border border-slate-700 p-4">
                        <dl className="grid gap-2 text-sm sm:grid-cols-2">
                            <Value name="QEMU resource ID" value={destination.resource_id} />
                            <Value name="Provider" value="Proxmox" />
                            <Value name="Resource type" value="QEMU" />
                            <Value name="Placement" value="existing guest" />
                        </dl>
                        <button
                            type="button"
                            aria-label={recoveryAttempt
                                ? `Retry selection — QEMU resource ${destination.resource_id}`
                                : `Select as prospective installation destination — QEMU resource ${destination.resource_id}`}
                            disabled={!csrfToken || mutation !== null || (selectionRecovery !== null && !recoveryAttempt)}
                            onClick={() => void select(
                                recoveryAttempt ? recoveryAttempt.destination : destination,
                                recoveryAttempt ? recoveryAttempt.idempotencyKey : installationIdempotencyKey(),
                            )}
                            className="mt-3 rounded-lg border border-blue-400/50 px-3 py-2 text-sm font-semibold text-blue-200 disabled:cursor-not-allowed disabled:opacity-50"
                        >{recoveryAttempt ? "Retry selection" : "Select as prospective installation destination"}</button>
                        {!csrfToken && <p className="mt-2 text-xs text-slate-400">An authenticated operator session with mutation protection is required to record a selection.</p>}
                    </li>
                );
            })}
        </ul>}
        {mutation === "selection" && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Recording prospective destination selection…</p>}
        {mutationError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
            <p>{mutationError.action === "selection"
                ? "Atlas could not confirm whether it saved this destination selection. Retry the same request to recover its result."
                : "Atlas could not confirm the assessment result. Retry the assessment to request the result again."}</p>
            <details className="mt-3 text-red-100/80">
                <summary className="cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{mutationError.technicalDetail}</p>
            </details>
        </div>}
        {selection && <SelectionSummary selection={selection} />}
        {selection && <div className="mt-4">
            <button type="button" disabled={assessmentDisabledReason !== null || mutation !== null} onClick={() => void assess()} className="rounded-lg border border-blue-400/50 px-3 py-2 text-sm font-semibold text-blue-200 disabled:cursor-not-allowed disabled:opacity-50">{canRetryAssessment ? "Retry assessment" : "Assess installation admission"}</button>
            {assessmentDisabledReason && <p className="mt-2 text-xs text-slate-400">{assessmentDisabledReason}</p>}
        </div>}
        {mutation === "assessment" && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Assessing installation admission…</p>}
        {assessment && <AssessmentSummary assessment={assessment} />}
        <InstallationCapabilityAssessment itemId={plan.application.item_id} selectionId={selection?.selection_id ?? null} />
        <InstallationCandidateAdmission itemId={plan.application.item_id} selectionId={selection?.selection_id ?? null} csrfToken={csrfToken} />
    </section>;
}

function SelectionSummary({ selection }: { selection: InstallationDestinationSelectionV1 }) {
    const terminal = selection.status !== "active";
    return <section aria-labelledby="selection-summary-heading" className={`mt-5 rounded-lg border p-4 ${terminal ? "border-amber-500/40" : "border-slate-700"}`}>
        <h4 id="selection-summary-heading" className="font-semibold text-slate-100">Immutable selection summary</h4>
        <p className="mt-1 text-sm text-slate-300">This selection records only where you want Atlas to assess a possible installation. It cannot install or plan the application, does not approve installation, does not prove the guest is installable, and does not authorize execution.</p>
        {terminal && <p role="status" className="mt-2 font-semibold text-amber-200">Terminal selection — {selection.status}</p>}
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <Value name="Selection ID" value={selection.selection_id} />
            <Value name="QEMU resource ID" value={selection.resource_id} />
            <Value name="Selected at" value={selection.selected_at} />
            <Value name="Expires at" value={selection.expires_at} />
            <Value name="Status" value={terminal ? `${selection.status} (terminal)` : "active (current)"} />
        </dl>
    </section>;
}

function AssessmentSummary({ assessment }: { assessment: InstallationAdmissionAssessmentV1 }) {
    const unsupported = assessment.assessment_status === "preconditions_satisfied_but_unsupported";
    return <section aria-labelledby="admission-assessment-heading" className="mt-5 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
        <h4 id="admission-assessment-heading" className="font-semibold text-slate-100">Assessment result</h4>
        <p role="status" className="mt-2 font-semibold text-amber-200">{ASSESSMENT_STATUS_LABELS[assessment.assessment_status]}</p>
        {unsupported && <p className="mt-2 text-sm text-slate-300">Atlas can evaluate the reviewed plan and destination consistently, but installation capability and Agent support remain unavailable.</p>}
        <p className="mt-2 text-sm text-slate-300">Candidate eligibility has not been evaluated. This assessment does not authorize installation.</p>
        <h5 className="mt-4 text-sm font-semibold text-slate-200">Issues found</h5>
        <ul aria-label="Installation admission blockers" className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-300">
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

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}

export { REASON_LABELS };
