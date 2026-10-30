import { useEffect, useState } from "react";

import { getInstallationCapabilityAssessment } from "../../api/installationCapability";
import { getAtlasErrorMessage } from "../../api/atlas";
import type {
    InstallationCapabilityAssessmentV1,
    InstallationCapabilityReasonCode,
    ProviderCapabilityFactV1,
} from "../../types/installationCapability";

const REASONS: Record<InstallationCapabilityReasonCode, string> = {
    installation_plan_blocked: "The installation plan has issues that need review.",
    destination_selection_not_current: "The saved VM selection is no longer current.",
    destination_identity_not_current: "Atlas could not confirm that the selected VM is still the same VM.",
    provider_facts_not_current: "The provider settings are out of date.",
    provider_facts_unknown: "Some required provider settings are missing or unclear.",
    requirement_not_assessable: "Atlas needs information from inside the VM that this check does not collect.",
    requirement_not_satisfied: "The provider settings do not meet a stated requirement.",
    agent_install_container_unsupported: "Atlas cannot prepare this type of installation yet.",
};

const ASSESSMENT_STATUS_LABELS = {
    blocked: "Blocked by issues listed below",
    insufficient_provider_facts: "Some requirements could not be checked",
    requirements_satisfied_but_non_authorizing: "Checked provider settings meet the requirements Atlas can compare",
} as const;

const COMPARISON_LABELS = {
    satisfied: "Meets requirement",
    not_satisfied: "Does not meet requirement",
    unknown: "Could not confirm",
    not_assessable: "Not assessed here",
} as const;

const FACT_LABELS: Record<ProviderCapabilityFactV1["code"], string> = {
    current_destination_identity: "Current destination identity",
    current_lifecycle_state: "Provider lifecycle state",
    configured_cpu_cores: "Configured virtual CPU cores",
    configured_memory_bytes: "Configured memory",
    configured_disk_capacity_bytes: "Provider-visible virtual disk capacity",
    guest_agent_configured: "Guest integration configuration bit",
};

function formatBytes(value: number): string {
    const gib = value / 1024 ** 3;
    return `${gib.toLocaleString(undefined, { maximumFractionDigits: 2 })} GiB (${value.toLocaleString()} bytes)`;
}

function formatFact(fact: ProviderCapabilityFactV1): string {
    if (fact.state !== "observed") return fact.state.replaceAll("_", " ");
    if (typeof fact.value === "boolean") return fact.value ? "configured" : "not configured";
    if (typeof fact.value === "number" && fact.code.includes("bytes")) return formatBytes(fact.value);
    return String(fact.value);
}

function label(value: string): string {
    return value.replaceAll("_", " ");
}

export function InstallationCapabilityAssessment({ itemId, selectionId }: { itemId: string; selectionId: string | null }) {
    const [assessment, setAssessment] = useState<InstallationCapabilityAssessmentV1 | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loadAttempt, setLoadAttempt] = useState(0);

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
                if (current) setError(getAtlasErrorMessage(requestError, "Provider settings could not be checked."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [itemId, selectionId, loadAttempt]);

    return <section aria-labelledby="capability-assessment-heading" className="mt-5 rounded-lg border border-slate-700 p-4">
        <h4 id="capability-assessment-heading" className="font-semibold text-slate-100">Provider settings check</h4>
        <p className="mt-1 text-sm text-slate-300">This compares settings reported by Proxmox with requirements in the plan. It does not check software inside the VM or approve an installation.</p>
        {!selectionId && <p className="mt-3 text-sm text-slate-400">Select a VM to check its provider settings.</p>}
        {selectionId && loading && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Checking provider settings…</p>}
        {selectionId && !loading && error && <div role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <p>Atlas couldn’t check the provider settings. Retry to check again.</p>
            <details className="mt-3 text-red-100/80">
                <summary className="cursor-pointer">Technical details</summary>
                <p className="mt-2 break-words">{error}</p>
            </details>
            <button type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)} className="mt-3 rounded-lg border border-red-300/40 px-3 py-2 font-semibold text-red-100">Retry provider check</button>
        </div>}
        {selectionId && !loading && !error && !assessment && <p className="mt-3 text-sm text-slate-400">No provider check result was returned.</p>}
        {selectionId && assessment && !loading && !error && <Assessment assessment={assessment} />}
    </section>;
}

function Assessment({ assessment }: { assessment: InstallationCapabilityAssessmentV1 }) {
    return <div className="mt-4">
        <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 font-semibold text-amber-200">{ASSESSMENT_STATUS_LABELS[assessment.assessment_status]}</p>
        <p className="mt-2 text-sm text-slate-300">This result does not confirm that the VM is ready or approve an installation.</p>

        <h5 className="mt-5 text-sm font-semibold text-slate-200">Requirements checked</h5>
        {assessment.comparisons.length === 0
            ? <p className="mt-2 text-sm text-slate-400">The plan does not list requirements Atlas can compare.</p>
            : <ul aria-label="Requirements checked" className="mt-2 space-y-2">
                {assessment.comparisons.map((comparison) => <li key={comparison.prerequisite_id} className="rounded-md border border-slate-700 p-3 text-sm text-slate-300">
                    <span className="font-semibold text-slate-100">{COMPARISON_LABELS[comparison.result]}</span>
                    <p className="mt-1">{comparison.requirement}</p>
                    <p className="mt-1 text-xs text-slate-400">{comparison.observed_value === null ? "Atlas could not confirm a comparable value." : `Proxmox reports: ${comparison.requirement_kind === "cpu_cores" ? comparison.observed_value : formatBytes(comparison.observed_value)}`}</p>
                </li>)}
            </ul>}

        {assessment.reason_codes.length > 0 && <>
            <h5 className="mt-5 text-sm font-semibold text-slate-200">What needs attention</h5>
            <ul aria-label="What needs attention" className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-300">
                {assessment.reason_codes.map((reason) => <li key={reason}>{REASONS[reason]}</li>)}
            </ul>
        </>}

        <details className="mt-5 text-sm text-slate-300">
            <summary className="cursor-pointer">Technical details</summary>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Value name="Plan item" value={assessment.plan.application.item_id} />
                <Value name="Plan fingerprint" value={assessment.plan.fingerprint.value} />
                <Value name="Selection ID" value={assessment.selection.selection_id} />
                <Value name="Destination resource" value={`Proxmox QEMU ${assessment.selection.resource_id} (existing guest)`} />
                <Value name="Selected destination fingerprint" value={assessment.selection.selected_destination_fingerprint} />
                <Value name="Current destination fingerprint" value={assessment.current_destination.destination_fingerprint} />
                <Value name="Assessment status code" value={assessment.assessment_status} />
            </dl>
            <h5 className="mt-5 text-sm font-semibold text-slate-200">Provider settings from Proxmox</h5>
            <p className="mt-1 text-xs text-slate-400">These are control-plane settings. They do not show whether software inside the VM is running or ready.</p>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                {assessment.provider_facts.facts.map((fact) => <Value key={fact.code} name={FACT_LABELS[fact.code]} value={`${formatFact(fact)} (${label(fact.state)})`} />)}
            </dl>
            <h5 className="mt-5 text-sm font-semibold text-slate-200">Check times and fingerprints</h5>
            <dl className="mt-2 grid gap-3 sm:grid-cols-2">
                <Value name="Provider settings observed" value={assessment.provider_facts.observed_at} />
                <Value name="Provider settings fresh until" value={assessment.provider_facts.fresh_until} />
                <Value name="Assessment checked" value={assessment.evaluated_at} />
                <Value name="Assessment fingerprint" value={assessment.assessment_fingerprint} />
            </dl>
        </details>
    </div>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
