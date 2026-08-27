import { useEffect, useState } from "react";

import { getInstallationCapabilityAssessment } from "../../api/installationCapability";
import { getAtlasErrorMessage } from "../../api/atlas";
import type {
    InstallationCapabilityAssessmentV1,
    InstallationCapabilityReasonCode,
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
                if (current) setError(getAtlasErrorMessage(requestError, "Installation capability assessment is currently unavailable."));
            })
            .finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
    }, [itemId, selectionId]);

    return <section aria-labelledby="capability-assessment-heading" className="mt-5 rounded-lg border border-slate-700 p-4">
        <h4 id="capability-assessment-heading" className="font-semibold text-slate-100">Installation capability assessment</h4>
        <p className="mt-1 text-sm text-slate-300">Read-only comparison of sanitized provider configuration facts. It does not inspect actual in-guest or runtime capability and grants no installation or execution authority.</p>
        {!selectionId && <p className="mt-3 text-sm text-slate-400">No prospective destination selection is available for capability assessment.</p>}
        {selectionId && loading && <p role="status" aria-live="polite" className="mt-3 text-sm text-slate-400">Loading installation capability assessment…</p>}
        {selectionId && !loading && error && <p role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {selectionId && !loading && !error && !assessment && <p className="mt-3 text-sm text-slate-400">No installation capability assessment was returned.</p>}
        {selectionId && assessment && !loading && !error && <Assessment assessment={assessment} />}
    </section>;
}

function Assessment({ assessment }: { assessment: InstallationCapabilityAssessmentV1 }) {
    return <div className="mt-4">
        <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 font-semibold text-amber-200">Status: {label(assessment.assessment_status)} — non-authorizing</p>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <Value name="Plan item" value={assessment.plan.application.item_id} />
            <Value name="Plan fingerprint" value={assessment.plan.fingerprint.value} />
            <Value name="Selection ID" value={assessment.selection.selection_id} />
            <Value name="Destination resource" value={`Proxmox QEMU ${assessment.selection.resource_id} (existing guest)`} />
            <Value name="Selected destination fingerprint" value={assessment.selection.selected_destination_fingerprint} />
            <Value name="Current destination fingerprint" value={assessment.current_destination.destination_fingerprint} />
        </dl>

        <h5 className="mt-5 text-sm font-semibold text-slate-200">Sanitized provider configuration facts</h5>
        <p className="mt-1 text-xs text-slate-400">Source: Proxmox QEMU control-plane configuration. These observations do not prove process health, reachability, runtime support, free space, or in-guest readiness.</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            {assessment.provider_facts.facts.map((fact) => <Value key={fact.code} name={FACT_LABELS[fact.code]} value={`${formatFact(fact)} (${label(fact.state)})`} />)}
        </dl>

        <h5 className="mt-5 text-sm font-semibold text-slate-200">Requirement comparisons</h5>
        {assessment.comparisons.length === 0
            ? <p className="mt-2 text-sm text-slate-400">No requirement comparisons are present.</p>
            : <ul aria-label="Installation capability comparisons" className="mt-2 space-y-2">
                {assessment.comparisons.map((comparison) => <li key={comparison.prerequisite_id} className="rounded-md border border-slate-700 p-3 text-sm text-slate-300">
                    <span className="font-semibold text-slate-100">{label(comparison.result)}</span> — {comparison.requirement}
                    <span className="block text-xs text-slate-400">{comparison.observed_value === null ? "No reliable comparable value" : `Observed: ${comparison.requirement_kind === "cpu_cores" ? comparison.observed_value : formatBytes(comparison.observed_value)}`}</span>
                </li>)}
            </ul>}

        <h5 className="mt-5 text-sm font-semibold text-slate-200">Ordered blockers and reasons</h5>
        <ol aria-label="Installation capability reasons" className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-300">
            {assessment.reason_codes.map((reason) => <li key={reason}>{REASONS[reason]}</li>)}
        </ol>

        <h5 className="mt-5 text-sm font-semibold text-slate-200">Freshness and provenance</h5>
        <dl className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
            <Value name="Provider facts observed" value={assessment.provider_facts.observed_at} />
            <Value name="Provider facts fresh until" value={assessment.provider_facts.fresh_until} />
            <Value name="Assessment evaluated" value={assessment.evaluated_at} />
            <Value name="Assessment fingerprint" value={assessment.assessment_fingerprint} />
        </dl>
        <p className="mt-4 text-sm font-semibold text-amber-200">This read model does not authorize installation, execution, provider changes, or any in-guest operation.</p>
    </div>;
}

function Value({ name, value }: { name: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{value}</dd></div>;
}
