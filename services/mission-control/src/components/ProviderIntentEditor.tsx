import { useState } from "react";

import type {
    ManagedProviderResourceV2,
    ManagedProviderResourceV3,
    ProviderMonitoringExpectation,
} from "../types/providerManagement";

const labels: Record<ProviderMonitoringExpectation, string> = {
    running: "Running",
    stopped: "Stopped",
    ignored: "Ignored",
};

const readOnlyReasons: Record<string, string> = {
    not_activated: "Monitoring edits are not enabled for this provider.",
    authority_unavailable: "Atlas cannot check monitoring settings right now. Editing is unavailable.",
    store_migration_required: "Atlas needs a storage update before this setting can be edited.",
    store_unavailable: "Monitoring settings cannot be read right now.",
    resource_missing: "This resource is missing, so its monitoring setting cannot be changed.",
    identity_unavailable: "Atlas cannot confirm this VM is the same instance, so its monitoring setting cannot be changed safely.",
    resource_type_unsupported: "Atlas cannot edit monitoring for this resource type.",
};

function parseExpectationSelection(
    value: string,
): ProviderMonitoringExpectation | "" {
    switch (value) {
        case "running":
        case "stopped":
        case "ignored":
            return value;
        default:
            return "";
    }
}

export function ProviderIntentEditor({
    resource,
    mutationResource,
    operatorState,
    saving,
    initialSelection,
    requireExplicitSelection = false,
    onSave,
}: {
    resource: ManagedProviderResourceV2;
    mutationResource: ManagedProviderResourceV3 | null;
    operatorState: "anonymous" | "loading" | "available" | "unavailable";
    saving: boolean;
    initialSelection?: ProviderMonitoringExpectation;
    requireExplicitSelection?: boolean;
    onSave: (
        expectation: ProviderMonitoringExpectation,
        acknowledgeSuppression: boolean,
    ) => Promise<void>;
}) {
    const configured = resource.intent_status === "configured";
    const [selected, setSelected] = useState<ProviderMonitoringExpectation | "">(
        requireExplicitSelection
            ? ""
            : configured ? resource.expectation ?? "" : initialSelection ?? "",
    );
    const [acknowledged, setAcknowledged] = useState(false);

    const canEdit = operatorState !== "anonymous"
        && operatorState !== "unavailable"
        && mutationResource !== null
        && mutationResource.caller_can_mutate
        && mutationResource.provider_intent_mutation_supported
        && mutationResource.editable_in_principle
        && mutationResource.resource_live
        && !resource.missing
        && resource.provider_id === "proxmox"
        && resource.resource_type === "qemu"
        && resource.identity_assurance === "authoritative"
        && mutationResource.management_fingerprint !== null;
    const canSave = canEdit
        && operatorState === "available"
        && selected !== ""
        && (selected !== "ignored" || acknowledged);
    const readOnlyMessage = operatorState === "anonymous"
        ? "Sign in with permission to edit monitoring expectations."
        : operatorState !== "available"
          ? null
          : mutationResource?.mutation_readiness === "ready"
            ? "Your account does not have permission to edit monitoring expectations."
            : readOnlyReasons[mutationResource?.mutation_readiness ?? "authority_unavailable"];

    return (
        <div className="min-w-0 space-y-2">
            {resource.replacement_detected && (
                <p role="alert" className="text-xs text-amber-300">
                    This VM was replaced. Its previous monitoring expectation does not apply to this instance. Choose a new value.
                </p>
            )}
            {resource.legacy_review_available && resource.legacy_expectation && (
                <p className="text-xs text-slate-400">
                    An older monitoring setting says {labels[resource.legacy_expectation]}. Review it if useful; Atlas will not select it automatically.
                </p>
            )}
            {canEdit ? (
                <>
                    <label className="block text-xs text-slate-400">
                        Monitoring expectation
                        <select
                            aria-label={`Monitoring expectation for ${resource.display_name}`}
                            value={selected}
                            disabled={saving || operatorState !== "available"}
                            onChange={(event) => {
                                setSelected(
                                    parseExpectationSelection(event.target.value),
                                );
                                setAcknowledged(false);
                            }}
                            className="mt-1 block rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                        >
                            {(!configured || requireExplicitSelection) && <option value="">Choose explicitly</option>}
                            {Object.entries(labels).map(([value, label]) => (
                                <option key={value} value={value}>{label}</option>
                            ))}
                        </select>
                    </label>
                    {selected === "ignored" && (
                        <label className="flex gap-2 text-xs text-amber-200">
                            <input
                                type="checkbox"
                                checked={acknowledged}
                                disabled={saving || operatorState !== "available"}
                                onChange={(event) => setAcknowledged(event.target.checked)}
                            />
                            I understand monitoring findings for this expectation will be suppressed.
                        </label>
                    )}
                    <button
                        type="button"
                        disabled={!canSave || saving}
                        onClick={() => selected && void onSave(selected, acknowledged)}
                        className="rounded-lg border border-blue-500/50 bg-blue-500/10 px-3 py-2 text-xs font-medium text-blue-200 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                        {saving ? "Saving..." : "Save"}
                    </button>
                </>
            ) : (
                readOnlyMessage && <p className="text-xs text-slate-500">{readOnlyMessage}</p>
            )}
        </div>
    );
}
