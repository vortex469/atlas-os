import { useEffect, useState } from "react";

import { getInstallationCapabilityAssessment } from "../../api/installationCapability";
import { getAtlasErrorMessage } from "../../api/atlas";
import type {
    InstallationCapabilityAssessmentV1,
    InstallationCapabilityReasonCode,
    InstallationCapabilityResult,
    ProviderCapabilityFactV1,
} from "../../types/installationCapability";

const REASONS: Record<InstallationCapabilityReasonCode, string> = {
    installation_plan_blocked: "The installation plan is blocked.",
    destination_selection_not_current: "The prospective destination selection is not current.",
    destination_identity_not_current: "The selected and currently observed destination identities do not match.",
    provider_facts_not_current: "The provider configuration observation is no longer current.",
    provider_facts_unknown: "Required provider configuration facts are unavailable or unreliable.",
    requirement_not_assessable: "A requirement needs in-guest or runtime evidence that this assessment does not collect.",
    requirement_not_satisfied: "Observed provider configuration is below a stated requirement.",
    agent_install_container_unsupported: "Atlas does not support installation execution for this assessment.",
};

const FACT_LABELS: Record<ProviderCapabilityFactV1["code"], string> = {
    current_destination_identity: "Selected guest identity",
    current_lifecycle_state: "Power state reported by Proxmox",
    configured_cpu_cores: "Configured virtual CPU cores",
    configured_memory_bytes: "Configured memory",
    configured_disk_capacity_bytes: "Configured virtual disk size",
    guest_agent_configured: "Proxmox Guest Agent setting",
};

const FACT_STATE_LABELS: Record<ProviderCapabilityFactV1["state"], string> = {
    observed: "Reported",
    not_observed: "Not reported",
    malformed: "Could not be read",
    conflicted: "Conflicting reports",
    unavailable: "Not available",
};

const COMPARISON_LABELS: Record<InstallationCapabilityResult, string> = {
    satisfied: "Meets requirement",
    not_satisfied: "Below requirement",
    unknown: "Not enough information",
    not_assessable: "Not checked",
};

const ASSESSMENT_LABELS: Record<InstallationCapabilityAssessmentV1["assessment_status"], string> = {
    blocked: "Some stated requirements are not met.",
    insufficient_provider_facts: "There is not enough reliable information to assess this guest.",
    requirements_satisfied_but_non_authorizing: "The checked requirements appear satisfied. This does not approve installation.",
};

function formatBytes(value: number, includeExactBytes = false): string {
    const gib = value / 1024 ** 3;
    const readable = `${gib.toLocaleString(undefined, { maximumFractionDigits: 2 })} GiB`;
    return includeExactBytes ? `${readable} (${value.toLocaleString()} bytes)` : readable;
}

function formatFact(fact: ProviderCapabilityFactV1): string {
    if (fact.state !== "observed") return "No value reported";
    if (fact.value === null) return "No value reported";
    if (typeof fact.value === "boolean" && fact.code === "current_destination_identity") {
        return fact.value ? "Matches selected guest" : "Does not match selected guest";
    }
    if (typeof fact.value === "boolean") return fact.value ? "Configured" : "Not configured";
    if (typeof fact.value === "number" && fact.code.includes("bytes")) return formatBytes(fact.value, true);
    return String(fact.value).replaceAll("_", " ");
}

function formatObservedValue(value: number | null, kind: InstallationCapabilityAssessmentV1["comparisons"][number]["requirement_kind"]): string {
    if (value === null) return "No reliable value was reported.";
    if (kind === "cpu_cores") return `${value.toLocaleString()} virtual CPU cores`;
    if (kind === "memory" || kind === "storage") return formatBytes(value);
    return "No comparable value is available.";
}

export function InstallationCapabilityAssessment({ itemId, selectionId }: { itemId: string; selectionId: string | null }) {
    const [assessment, setAssessment] = useState<InstallationCapabilityAssessmentV1 | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!selectionId) {
            return;
        }
        let current = true;
        queueMicrotask(() => {
            if (current) {
                setAssessment(null);
                setLoading(true);
                setError(null);
            }
        });
        getInstallationCapabilityAssessment(itemId, selectionId)
            .then((value) => { if (current) setAssessment(value); })
            .catch((requestError: unknown) => {
                if (current) setError(getAtlasErrorMessage(requestError, "The guest configuration check is currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [itemId, selectionId]);

    return <section aria-labelledby="capability-assessment-heading" className="mt-5 rounded-lg border border-slate-700 p-4">
        <h4 id="capability-assessment-heading" className="font-semibold text-slate-100">Check stated installation requirements</h4>
        <p className="mt-1 text-sm text-slate-300">Compares Proxmox VM settings with the plan. It cannot check software or services inside the guest, change VM settings, or approve or run an installation.</p>
        {!selectionId && <p className="mt-3 text-sm text-slate-400">Select a prospective destination above to check its settings against the plan requirements.</p>}
        {selectionId && loading && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Checking the selected guest configuration…</p>}
        {selectionId && !loading && error && <p role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {selectionId && !loading && !error && !assessment && <p className="mt-3 text-sm text-slate-400">No guest configuration check result was returned.</p>}
        {selectionId && assessment && !loading && !error && <Assessment assessment={assessment} />}
    </section>;
}

function Assessment({ assessment }: { assessment: InstallationCapabilityAssessmentV1 }) {
    return <div className="mt-4">
        <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 font-semibold text-amber-200">{ASSESSMENT_LABELS[assessment.assessment_status]}</p>
        <h5 className="mt-5 text-sm font-semibold text-slate-200">How the guest compares</h5>
        {assessment.comparisons.length === 0
            ? <p className="mt-2 text-sm text-slate-400">No plan requirements could be checked.</p>
            : <ul aria-label="Installation capability comparisons" className="mt-2 space-y-2">
                {assessment.comparisons.map((comparison) => <li key={comparison.prerequisite_id} className="rounded-md border border-slate-700 p-3 text-sm text-slate-300">
                    <span className="font-semibold text-slate-100">{COMPARISON_LABELS[comparison.result]}</span> — {comparison.requirement}
                    <span className="block text-xs text-slate-400">Observed: {formatObservedValue(comparison.observed_value, comparison.requirement_kind)}</span>
                </li>)}
            </ul>}

        <h5 className="mt-5 text-sm font-semibold text-slate-200">Assessment notes</h5>
        {assessment.reason_codes.length === 0
            ? <p className="mt-2 text-sm text-slate-400">No additional issues were reported.</p>
            : <ol aria-label="Installation capability reasons" className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-300">
                {assessment.reason_codes.map((reason) => <li key={reason}>{REASONS[reason]}</li>)}
            </ol>}

        <details className="mt-5 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400">
            <summary className="cursor-pointer font-medium text-slate-300">Technical facts and verification details</summary>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Assessment status code" value={assessment.assessment_status} />
                <Value name="Plan item" value={assessment.plan.application.item_id} />
                <Value name="Plan fingerprint" value={assessment.plan.fingerprint.value} />
                <Value name="Selection ID" value={assessment.selection.selection_id} />
                <Value name="Destination resource" value={`Proxmox QEMU ${assessment.selection.resource_id} (existing guest)`} />
                <Value name="Selected destination fingerprint" value={assessment.selection.selected_destination_fingerprint} />
                <Value name="Current destination fingerprint" value={assessment.current_destination.destination_fingerprint} />
            </dl>
            <h6 className="mt-4 text-sm font-semibold text-slate-300">Proxmox configuration reported for this guest</h6>
            <p className="mt-1 text-xs text-slate-400">These settings do not prove the guest is reachable, has free disk space, or can run the application.</p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                {assessment.provider_facts.facts.map((fact) => <Value key={fact.code} name={FACT_LABELS[fact.code]} value={`${formatFact(fact)} (${FACT_STATE_LABELS[fact.state]})`} />)}
            </dl>
            <h6 className="mt-4 text-sm font-semibold text-slate-300">When and where these facts were read</h6>
            <dl className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
                <Value name="Provider facts observed" value={assessment.provider_facts.observed_at} />
                <Value name="Provider facts fresh until" value={assessment.provider_facts.fresh_until} />
                <Value name="Assessment evaluated" value={assessment.evaluated_at} />
                <Value name="Assessment fingerprint" value={assessment.assessment_fingerprint} />
            </dl>
        </details>
    </div>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
