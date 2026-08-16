import { useCallback, useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";

import { getAtlasErrorMessage } from "../api/atlas";
import { getAuthenticatedProviderManagement, getProviderManagement, putProviderMonitoringIntent } from "../api/providerManagement";
import { getProviderMonitoringIntentSuggestions } from "../api/providerIntentSuggestions";
import { getProviderResources, refreshProviderResources } from "../api/resources";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { Provider } from "../types/provider";
import type { ManagedProviderResourceV2, ManagedProviderResourceV3, ProviderManagementV2, ProviderManagementV3, ProviderMonitoringExpectation, ProviderMonitoringIntentSuggestionV1 } from "../types/providerManagement";
import type { ProviderResource, ProviderResourceCollection } from "../types/resources";
import { ProviderIntentEditor } from "./ProviderIntentEditor";
import { ProviderIntentSuggestionCard } from "./ProviderIntentSuggestionCard";
import {
    composeProviderResources,
    coordinate,
    formatLabel,
    monitoringPresentation,
    type ComposedResource,
    type Coordinate,
} from "./providerResourceComposition";
import { SectionHeader } from "./SectionHeader";

type ProviderResourcesProps = { provider: Provider };
type MetadataColumn = { key: string; label: string; render: (resource: ProviderResource) => string };

const metadataColumnsByProvider: Record<string, MetadataColumn[]> = {
    proxmox: [
        { key: "vmid", label: "VMID", render: (resource) => formatMetadata(resource.metadata.vmid) },
        { key: "node", label: "Node", render: (resource) => formatMetadata(resource.metadata.node) },
    ],
};

function managementCoordinate(resource: Pick<ManagedProviderResourceV2, "provider_id" | "resource_type" | "resource_id">): Coordinate {
    return coordinate(resource.provider_id, resource.resource_type, resource.resource_id);
}

export function ProviderResources({ provider }: ProviderResourcesProps) {
    const session = useOperatorSession();
    const supported = provider.capabilities.includes("resources");
    const [inventory, setInventory] = useState<ProviderResourceCollection | null>(null);
    const [management, setManagement] = useState<ProviderManagementV2 | null>(null);
    const [operator, setOperator] = useState<ProviderManagementV3 | null>(null);
    const [suggestions, setSuggestions] = useState<ProviderMonitoringIntentSuggestionV1[]>([]);
    const [inventoryLoading, setInventoryLoading] = useState(supported);
    const [managementLoading, setManagementLoading] = useState(supported);
    const [operatorLoading, setOperatorLoading] = useState(false);
    const [inventoryError, setInventoryError] = useState<string | null>(null);
    const [managementError, setManagementError] = useState<string | null>(null);
    const [operatorError, setOperatorError] = useState<string | null>(null);
    const [suggestionError, setSuggestionError] = useState<string | null>(null);
    const [updatingCoordinate, setUpdatingCoordinate] = useState<Coordinate | null>(null);
    const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
    const [rowStatuses, setRowStatuses] = useState<Record<string, string>>({});
    const [decisionRevisions, setDecisionRevisions] = useState<Record<string, number>>({});
    const [reviewedSuggestions, setReviewedSuggestions] = useState<Record<string, ProviderMonitoringIntentSuggestionV1>>({});
    const [invalidatedReviews, setInvalidatedReviews] = useState<Record<string, boolean>>({});
    const metadataColumns = useMemo(() => metadataColumnsByProvider[provider.id] ?? [], [provider.id]);

    const loadInventory = useCallback(async (refresh = false): Promise<boolean> => {
        setInventoryLoading(true); setInventoryError(null);
        try { setInventory(refresh ? await refreshProviderResources(provider.id) : await getProviderResources(provider.id)); return true; }
        catch (error) { setInventoryError(getAtlasErrorMessage(error, `Mission Control could not load observed resources for ${provider.name}.`)); return false; }
        finally { setInventoryLoading(false); }
    }, [provider.id, provider.name]);

    const loadManagement = useCallback(async (): Promise<boolean> => {
        setManagementLoading(true); setManagementError(null);
        try { setManagement(await getProviderManagement(provider.id)); return true; }
        catch (error) { setManagementError(getAtlasErrorMessage(error, "Provider Intent authority could not be read.")); return false; }
        finally { setManagementLoading(false); }
    }, [provider.id]);

    const loadOperator = useCallback(async (): Promise<boolean> => {
        if (!session.authenticated) { setOperator(null); setOperatorError(null); setOperatorLoading(false); return true; }
        setOperatorLoading(true); setOperatorError(null);
        try { setOperator(await getAuthenticatedProviderManagement(provider.id)); return true; }
        catch (error) {
            if (isAxiosError(error) && error.response?.status === 401) session.invalidate();
            setOperator(null); setOperatorError("Operator edit readiness could not be loaded. Public monitoring state remains available."); return false;
        } finally { setOperatorLoading(false); }
    }, [provider.id, session]);

    const loadSuggestions = useCallback(async (): Promise<boolean> => {
        if (!session.authenticated) { setSuggestions([]); setSuggestionError(null); return true; }
        setSuggestionError(null);
        try { setSuggestions(await getProviderMonitoringIntentSuggestions(provider.id)); return true; }
        catch (error) {
            if (isAxiosError(error) && error.response?.status === 401) session.invalidate();
            setSuggestions([]);
            setSuggestionError("Advisory monitoring suggestions could not be loaded. Current monitoring state remains authoritative.");
            return false;
        }
    }, [provider.id, session]);

    useEffect(() => { if (supported) void Promise.resolve().then(() => Promise.all([loadInventory(), loadManagement()])); }, [loadInventory, loadManagement, supported]);
    useEffect(() => { if (supported) void Promise.resolve().then(loadOperator); }, [loadOperator, supported]);
    useEffect(() => { if (supported) void Promise.resolve().then(loadSuggestions); }, [loadSuggestions, supported]);

    function revise(key: Coordinate) {
        setDecisionRevisions((current) => ({ ...current, [key]: (current[key] ?? 0) + 1 }));
    }

    function clearReviewed(key: Coordinate) {
        setReviewedSuggestions((current) => {
            const next = { ...current };
            delete next[key];
            return next;
        });
        setInvalidatedReviews((current) => {
            const next = { ...current };
            delete next[key];
            return next;
        });
        revise(key);
    }

    function invalidateReviewed(key: Coordinate) {
        setInvalidatedReviews((current) => ({ ...current, [key]: true }));
        revise(key);
    }

    async function saveProviderIntent(publicResource: ManagedProviderResourceV2, operatorResource: ManagedProviderResourceV3, reviewedSuggestion: ProviderMonitoringIntentSuggestionV1 | null, selected: ProviderMonitoringExpectation, acknowledgeSuppression: boolean): Promise<void> {
        const key = managementCoordinate(publicResource);
        if (!operatorResource.management_fingerprint || !session.csrfToken) return;
        if (reviewedSuggestion && (
            reviewedSuggestion.provider_id !== publicResource.provider_id
            || reviewedSuggestion.resource_type !== publicResource.resource_type
            || reviewedSuggestion.resource_id !== publicResource.resource_id
            || reviewedSuggestion.management_fingerprint !== publicResource.management_fingerprint
            || reviewedSuggestion.management_fingerprint !== operatorResource.management_fingerprint
            || publicResource.intent_status !== "needs_review"
            || publicResource.intent_reason !== "no_active_intent"
            || publicResource.record_version !== null
        )) {
            clearReviewed(key);
            setRowErrors((current) => ({ ...current, [key]: "The reviewed suggestion is stale. Review current monitoring state before saving." }));
            await Promise.all([loadManagement(), loadOperator(), loadSuggestions()]);
            return;
        }
        setUpdatingCoordinate(key);
        setRowErrors((current) => ({ ...current, [key]: "" }));
        setRowStatuses((current) => ({ ...current, [key]: "" }));
        let committed = false;
        try {
            await putProviderMonitoringIntent(provider.id, publicResource.resource_type, publicResource.resource_id, {
                request_id: `provider-intent-mutation-${crypto.randomUUID().replaceAll("-", "")}`,
                expected_management_fingerprint: operatorResource.management_fingerprint,
                expectation: selected,
                expected_record_version: publicResource.replacement_detected ? 0 : publicResource.record_version ?? 0,
                acknowledge_monitoring_suppression: acknowledgeSuppression,
            }, session.csrfToken);
            committed = true; invalidateReviewed(key);
            const [publicReloaded, operatorReloaded, suggestionsReloaded] = await Promise.all([loadManagement(), loadOperator(), loadSuggestions()]);
            if (suggestionsReloaded) clearReviewed(key);
            if (!publicReloaded || !operatorReloaded) setRowErrors((current) => ({ ...current, [key]: "Provider Intent was saved, but refreshed server state could not be loaded." }));
            else setRowStatuses((current) => ({ ...current, [key]: suggestionsReloaded ? "Monitoring expectation saved and confirmed by Atlas Core." : "Monitoring expectation saved and confirmed. Advisory suggestions could not be refreshed." }));
        } catch (error) {
            if (committed) return;
            const status = isAxiosError(error) ? error.response?.status : undefined;
            const detail = isAxiosError<{ detail?: string }>(error) ? error.response?.data?.detail : undefined;
            let message = "Atlas Core could not save the monitoring expectation.";
            if (status === 401) { session.invalidate(); message = "Operator session expired. Sign in again."; }
            else if (status === 403) message = "Your operator session does not permit Provider Intent updates.";
            else if (status === 409 && detail === "cas_conflict") message = "Provider Intent changed. Review the current state and make a fresh decision.";
            else if (status === 409 && detail === "fingerprint_mismatch") message = "The resource identity changed. Review the replacement before saving.";
            else if (status === 409 && detail === "request_conflict") message = "This save request is stale. Start a new Save action.";
            else if (status === 429) message = "Provider Intent saves are rate limited. Wait before trying again.";
            else if (status === 422) message = "The Provider Intent request is invalid. Review the current state and choose again.";
            else if (status === 503) message = "Provider Intent editing is temporarily unavailable or awaiting migration.";
            setRowErrors((current) => ({ ...current, [key]: message }));
            if (status === 409 && (detail === "cas_conflict" || detail === "fingerprint_mismatch")) { invalidateReviewed(key); await Promise.all([loadManagement(), loadOperator(), loadSuggestions()]); }
        } finally { setUpdatingCoordinate(null); }
    }

    const composition = useMemo(() => {
        try { return { resources: composeProviderResources(inventory, management, operator), error: false }; }
        catch { return { resources: [] as ComposedResource[], error: true }; }
    }, [inventory, management, operator]);
    const suggestionsByCoordinate = useMemo(() => new Map(
        suggestions.map((suggestion) => [coordinate(suggestion.provider_id, suggestion.resource_type, suggestion.resource_id), suggestion]),
    ), [suggestions]);
    if (!supported) return null;
    const refreshedAt = inventory ? new Date(inventory.refreshed_at).toLocaleString() : "Not refreshed yet";

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/70 p-6 shadow-lg shadow-slate-950/30">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div><SectionHeader title="Resources and monitoring" description="Observed provider facts, identity assurance, and monitoring policy are shown separately." /><p className="mt-2 text-xs text-slate-500">Observed inventory refreshed: {refreshedAt}</p></div>
                <button type="button" onClick={() => void Promise.all([loadInventory(true), loadManagement(), loadOperator(), loadSuggestions()])} disabled={inventoryLoading || managementLoading || operatorLoading} className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50">{inventoryLoading || managementLoading || operatorLoading ? "Refreshing..." : "Refresh resources"}</button>
            </div>
            <div className="mt-4 space-y-2">
                {inventoryError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{inventoryError}</p>}
                {managementError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">Monitoring unavailable — {managementError} Observed inventory remains visible.</p>}
                {operatorError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{operatorError}</p>}
                {suggestionError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{suggestionError}</p>}
                {composition.error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">Resource coordinates could not be composed safely. Monitoring and editing are unavailable.</p>}
            </div>
            {inventoryLoading && inventory === null && managementLoading && management === null ? <p role="status" className="mt-6 text-sm text-slate-400">Loading observed resources and monitoring state...</p> : composition.resources.length === 0 ? <p className="mt-6 text-sm text-slate-400">No provider resources are available.</p> : (
                <div className="mt-6 space-y-4" aria-label="Provider resources">{composition.resources.map((resource) => <ResourceCard key={resource.coordinate} resource={resource} suggestion={suggestionsByCoordinate.get(resource.coordinate) ?? null} reviewedSuggestion={reviewedSuggestions[resource.coordinate] ?? null} reviewInvalidated={invalidatedReviews[resource.coordinate] ?? false} onReview={(suggestion) => { setReviewedSuggestions((current) => ({ ...current, [resource.coordinate]: suggestion })); setInvalidatedReviews((current) => ({ ...current, [resource.coordinate]: false })); revise(resource.coordinate); }} metadataColumns={metadataColumns} managementUnavailable={management === null} operatorState={session.authenticated ? (operator ? "available" : "unavailable") : "anonymous"} saving={updatingCoordinate === resource.coordinate} decisionRevision={decisionRevisions[resource.coordinate] ?? 0} error={rowErrors[resource.coordinate] || null} status={rowStatuses[resource.coordinate] || null} onSave={saveProviderIntent} />)}</div>
            )}
        </section>
    );
}

function ResourceCard({ resource, suggestion, reviewedSuggestion, reviewInvalidated, onReview, metadataColumns, managementUnavailable, operatorState, saving, decisionRevision, error, status, onSave }: { resource: ComposedResource; suggestion: ProviderMonitoringIntentSuggestionV1 | null; reviewedSuggestion: ProviderMonitoringIntentSuggestionV1 | null; reviewInvalidated: boolean; onReview: (suggestion: ProviderMonitoringIntentSuggestionV1) => void; metadataColumns: MetadataColumn[]; managementUnavailable: boolean; operatorState: "anonymous" | "available" | "unavailable"; saving: boolean; decisionRevision: number; error: string | null; status: string | null; onSave: (publicResource: ManagedProviderResourceV2, operatorResource: ManagedProviderResourceV3, reviewedSuggestion: ProviderMonitoringIntentSuggestionV1 | null, expectation: ProviderMonitoringExpectation, acknowledge: boolean) => Promise<void> }) {
    const observed = resource.inventory;
    const managed = resource.inconsistent ? null : resource.management;
    const displayName = observed?.display_name ?? managed?.display_name ?? "Unknown resource";
    const resourceType = observed?.resource_type ?? managed?.resource_type ?? "unknown";
    const resourceId = observed?.resource_id ?? managed?.resource_id ?? "unknown";
    const observedState = observed?.missing || (!observed && managed?.missing)
        ? "Missing"
        : formatLabel(observed?.current_state ?? "Unavailable");
    const presentation = monitoringPresentation(managed, observed?.current_state ?? null, managementUnavailable || resource.inconsistent);
    const displayedSuggestion = suggestion ?? reviewedSuggestion;
    const suggestionStale = displayedSuggestion !== null && (
        (reviewInvalidated && displayedSuggestion.suggestion_id === reviewedSuggestion?.suggestion_id)
        ||
        managed === null
        || displayedSuggestion.provider_id !== managed.provider_id
        || displayedSuggestion.resource_type !== managed.resource_type
        || displayedSuggestion.resource_id !== managed.resource_id
        || displayedSuggestion.management_fingerprint !== managed.management_fingerprint
        || managed.intent_status !== "needs_review"
        || managed.intent_reason !== "no_active_intent"
        || managed.record_version !== null
    );
    const reviewedCurrentSuggestion = reviewedSuggestion !== null
        && displayedSuggestion?.suggestion_id === reviewedSuggestion.suggestion_id
        && !suggestionStale;
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5" data-testid={`resource-row-${resourceType}-${resourceId}`}>
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
                <section aria-label={`Resource ${displayName}`}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Resource</p><h3 className="mt-2 font-semibold text-slate-100">{displayName}</h3><p className="mt-1 text-sm uppercase text-slate-400">{resourceType} {resourceId}</p>{observed && metadataColumns.length > 0 && <dl className="mt-3 space-y-1 text-xs text-slate-400">{metadataColumns.map((column) => <div key={column.key} className="flex gap-2"><dt>{column.label}:</dt><dd>{column.render(observed)}</dd></div>)}</dl>}</section>
                <FactSection title="Observed state" value={observedState} detail="Live provider inventory; not monitoring policy." />
                <FactSection title="Identity" value={presentation.identity} detail={resource.inconsistent ? "Inventory and management coordinates disagree." : "Provider identity assurance; no native identity is displayed."} />
                <section aria-label={`Monitoring for ${displayName}`}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monitoring expectation</p><p className="mt-2 font-semibold text-slate-100">{presentation.expectation}</p><p className="mt-2 text-sm text-slate-300">{presentation.status}</p></section>
            </div>
            {displayedSuggestion && <ProviderIntentSuggestionCard suggestion={displayedSuggestion} stale={suggestionStale} reviewed={reviewedCurrentSuggestion} onReview={() => onReview(displayedSuggestion)} />}
            {managed?.provider_id === "proxmox" && managed.resource_type === "qemu" && <div className="mt-5 border-t border-slate-800 pt-4"><ProviderIntentEditor key={`${resource.coordinate}:${managed.management_fingerprint}:${managed.record_version}:${decisionRevision}`} resource={managed} mutationResource={resource.operator} operatorState={operatorState} saving={saving} initialSelection={reviewedCurrentSuggestion ? reviewedSuggestion.suggested_expectation : undefined} requireExplicitSelection={reviewedSuggestion !== null && !reviewedCurrentSuggestion} onSave={async (expectation, acknowledge) => { if (resource.operator) await onSave(managed, resource.operator, reviewedCurrentSuggestion ? reviewedSuggestion : null, expectation, acknowledge); }} /></div>}
            {error && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
            {status && <p role="status" className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">{status}</p>}
        </article>
    );
}

function FactSection({ title, value, detail }: { title: string; value: string; detail: string }) {
    return <section><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p><p className="mt-2 font-semibold text-slate-100">{value}</p><p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p></section>;
}

function formatMetadata(value: unknown): string { return typeof value === "string" || typeof value === "number" ? String(value) : "—"; }
