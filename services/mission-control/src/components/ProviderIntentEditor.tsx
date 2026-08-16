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
    not_activated: "Provider Intent authority is not activated.",
    authority_unavailable: "Provider Intent authority is temporarily unavailable.",
    store_migration_required: "Provider Intent editing is awaiting a store migration.",
    store_unavailable: "Provider Intent storage is temporarily unavailable.",
    resource_missing: "Missing resources cannot be edited.",
    identity_unavailable: "Authoritative QEMU identity is unavailable.",
    resource_type_unsupported: "Provider Intent editing is unsupported for this resource type.",
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
    onSave,
}: {
    resource: ManagedProviderResourceV2;
    mutationResource: ManagedProviderResourceV3 | null;
    operatorState: "anonymous" | "available" | "unavailable";
    saving: boolean;
    onSave: (
        expectation: ProviderMonitoringExpectation,
        acknowledgeSuppression: boolean,
    ) => Promise<void>;
}) {
    const configured = resource.intent_status === "configured";
    const [selected, setSelected] = useState<ProviderMonitoringExpectation | "">(
        configured ? resource.expectation ?? "" : "",
    );
    const [acknowledged, setAcknowledged] = useState(false);

    const canEdit = mutationResource !== null
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
        && selected !== ""
        && (selected !== "ignored" || acknowledged);

    return (
        <div className="min-w-64 space-y-2">
            {resource.replacement_detected && (
                <p role="alert" className="text-xs text-amber-300">
                    This resource incarnation changed. The previous expectation is historical only and does not apply to the current identity. Choose a new value explicitly.
                </p>
            )}
            {resource.legacy_review_available && resource.legacy_expectation && (
                <p className="text-xs text-slate-400">
                    Historical legacy expectation: {labels[resource.legacy_expectation]} — review context only; it will not be selected automatically.
                </p>
            )}
            {canEdit ? (
                <>
                    <label className="block text-xs text-slate-400">
                        Monitoring expectation
                        <select
                            aria-label={`Monitoring expectation for ${resource.display_name}`}
                            value={selected}
                            disabled={saving}
                            onChange={(event) => {
                                setSelected(
                                    parseExpectationSelection(event.target.value),
                                );
                                setAcknowledged(false);
                            }}
                            className="mt-1 block rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                        >
                            {!configured && <option value="">Choose explicitly</option>}
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
                                disabled={saving}
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
                <p className="text-xs text-slate-500">
                    {operatorState === "anonymous"
                        ? "Sign in with Provider Intent permission to edit this public monitoring state."
                        : operatorState === "unavailable"
                          ? "Editing is unavailable because operator capability could not be loaded."
                          : mutationResource?.mutation_readiness === "ready"
                            ? "Your operator session does not permit Provider Intent updates."
                            : readOnlyReasons[mutationResource?.mutation_readiness ?? "authority_unavailable"]}
                </p>
            )}
        </div>
    );
}
