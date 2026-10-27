import { type RefObject, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
    return <ProviderResourcePanel key={provider.id} provider={provider} />;
}

function ProviderResourcePanel({ provider }: ProviderResourcesProps) {
    const session = useOperatorSession();
    const supported = provider.capabilities.includes("resources");
    const [inventory, setInventory] = useState<ProviderResourceCollection | null>(null);
    const [management, setManagement] = useState<ProviderManagementV2 | null>(null);
    const managementReadRef = useRef<ProviderManagementV2 | null>(null);
    const managementReadId = useRef(0);
    const [inventoryLoading, setInventoryLoading] = useState(supported);
    const [managementLoading, setManagementLoading] = useState(supported);
    const [inventoryError, setInventoryError] = useState<string | null>(null);
    const [managementError, setManagementError] = useState<string | null>(null);
    const loadInventory = useCallback(async (refresh = false): Promise<boolean> => {
        setInventoryLoading(true); setInventoryError(null);
        try { setInventory(refresh ? await refreshProviderResources(provider.id) : await getProviderResources(provider.id)); return true; }
        catch (error) { setInventoryError(getAtlasErrorMessage(error, `Mission Control could not load observed resources for ${provider.name}.`)); return false; }
        finally { setInventoryLoading(false); }
    }, [provider.id, provider.name]);

    const loadManagement = useCallback(async (): Promise<boolean> => {
        const readId = ++managementReadId.current;
        managementReadRef.current = null;
        setManagementLoading(true); setManagementError(null);
        try {
            const value = await getProviderManagement(provider.id);
            if (readId !== managementReadId.current) return false;
            managementReadRef.current = value;
            setManagement(value); return true;
        } catch (error) {
            if (readId !== managementReadId.current) return false;
            setManagementError(getAtlasErrorMessage(error, "Monitoring settings could not be loaded.")); return false;
        } finally { if (readId === managementReadId.current) setManagementLoading(false); }
    }, [provider.id]);

    useEffect(() => { if (supported) void Promise.resolve().then(() => Promise.all([loadInventory(), loadManagement()])); }, [loadInventory, loadManagement, supported]);
    if (!supported) return null;
    // Public principal metadata identifies the session; CSRF secrets never enter a key.
    const operatorEpoch = session.authenticated ? JSON.stringify(session.principal) : "anonymous";
    return <SessionResourcePanel key={operatorEpoch} provider={provider} session={session} operatorEpoch={operatorEpoch}
        inventory={inventory} management={management} managementReadRef={managementReadRef} inventoryLoading={inventoryLoading} managementLoading={managementLoading}
        inventoryError={inventoryError} managementError={managementError} loadInventory={loadInventory} loadManagement={loadManagement} />;
}

type SessionResourceProps = ProviderResourcesProps & {
    session: ReturnType<typeof useOperatorSession>;
    operatorEpoch: string;
    inventory: ProviderResourceCollection | null;
    management: ProviderManagementV2 | null;
    managementReadRef: RefObject<ProviderManagementV2 | null>;
    inventoryLoading: boolean;
    managementLoading: boolean;
    inventoryError: string | null;
    managementError: string | null;
    loadInventory: (refresh?: boolean) => Promise<boolean>;
    loadManagement: () => Promise<boolean>;
};

function SessionResourcePanel({ provider, session, operatorEpoch, inventory, management, managementReadRef, inventoryLoading,
    managementLoading, inventoryError, managementError, loadInventory, loadManagement }: SessionResourceProps) {
    const active = useRef(true);
    const operatorReadId = useRef(0);
    const suggestionReadId = useRef(0);
    useLayoutEffect(() => {
        active.current = true;
        return () => { active.current = false; };
    }, []);
    const supported = provider.capabilities.includes("resources");
    const [operator, setOperator] = useState<ProviderManagementV3 | null>(null);
    const [suggestions, setSuggestions] = useState<ProviderMonitoringIntentSuggestionV1[]>([]);
    const [operatorLoading, setOperatorLoading] = useState(session.authenticated);
    const [operatorError, setOperatorError] = useState<string | null>(null);
    const [suggestionError, setSuggestionError] = useState<string | null>(null);
    const [updatingCoordinate, setUpdatingCoordinate] = useState<Coordinate | null>(null);
    const saveInFlight = useRef(false);
    const uncertainSave = useRef<Coordinate | null>(null);
    const [uncertainCoordinate, setUncertainCoordinate] = useState<Coordinate | null>(null);
    const [checkingMonitoring, setCheckingMonitoring] = useState(false);
    const [recoveryNotice, setRecoveryNotice] = useState<string | null>(null);
    const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
    const [rowStatuses, setRowStatuses] = useState<Record<string, string>>({});
    const [decisionRevisions, setDecisionRevisions] = useState<Record<string, number>>({});
    const [reviewedSuggestions, setReviewedSuggestions] = useState<Record<string, ProviderMonitoringIntentSuggestionV1>>({});
    const [invalidatedReviews, setInvalidatedReviews] = useState<Record<string, boolean>>({});
    const metadataColumns = useMemo(() => metadataColumnsByProvider[provider.id] ?? [], [provider.id]);

    const loadOperator = useCallback(async (): Promise<boolean> => {
        if (!active.current) return false;
        const readId = ++operatorReadId.current;
        if (!session.authenticated) { setOperator(null); setOperatorError(null); setOperatorLoading(false); return true; }
        setOperatorLoading(true); setOperatorError(null);
        try {
            const value = await getAuthenticatedProviderManagement(provider.id);
            if (!active.current || readId !== operatorReadId.current) return false;
            setOperator(value); return true;
        } catch (error) {
            if (!active.current || readId !== operatorReadId.current) return false;
            if (isAxiosError(error) && error.response?.status === 401) session.invalidate();
            setOperator(null); setOperatorError("Could not check editing permissions. Resource details remain available."); return false;
        } finally { if (active.current && readId === operatorReadId.current) setOperatorLoading(false); }
    }, [provider.id, session]);

    const loadSuggestions = useCallback(async (): Promise<boolean> => {
        if (!active.current) return false;
        const readId = ++suggestionReadId.current;
        if (!session.authenticated) { setSuggestions([]); setSuggestionError(null); return true; }
        setSuggestionError(null);
        try {
            const value = await getProviderMonitoringIntentSuggestions(provider.id);
            if (!active.current || readId !== suggestionReadId.current) return false;
            setSuggestions(value); return true;
        } catch (error) {
            if (!active.current || readId !== suggestionReadId.current) return false;
            if (isAxiosError(error) && error.response?.status === 401) session.invalidate();
            setSuggestions([]);
            setSuggestionError("Advisory monitoring suggestions could not be loaded. Current monitoring state remains authoritative.");
            return false;
        }
    }, [provider.id, session]);

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

    async function checkMonitoringState(): Promise<void> {
        const key = uncertainSave.current;
        if (!active.current || key === null || saveInFlight.current) return;
        saveInFlight.current = true;
        setCheckingMonitoring(true);
        try {
            const [publicReloaded, operatorReloaded] = await Promise.all([loadManagement(), loadOperator()]);
            if (!active.current || !publicReloaded || !operatorReloaded) return;
            clearReviewed(key);
            uncertainSave.current = null;
            setUncertainCoordinate(null);
            setRecoveryNotice("Current monitoring state reloaded. Review it before saving again.");
        } finally {
            saveInFlight.current = false;
            if (active.current) setCheckingMonitoring(false);
        }
    }

    async function saveProviderIntent(publicResource: ManagedProviderResourceV2, operatorResource: ManagedProviderResourceV3, reviewedSuggestion: ProviderMonitoringIntentSuggestionV1 | null, selected: ProviderMonitoringExpectation, acknowledgeSuppression: boolean): Promise<void> {
        const key = managementCoordinate(publicResource);
        if (!active.current || managementReadRef.current === null || managementReadRef.current !== management
            || !managementReadRef.current.resources.includes(publicResource)
            || !operatorResource.management_fingerprint || !session.csrfToken || saveInFlight.current || uncertainSave.current !== null) return;
        saveInFlight.current = true;
        setUpdatingCoordinate(key);
        setRecoveryNotice(null);
        try {
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
                if (!active.current) return;
                committed = true; invalidateReviewed(key);
                const [publicReloaded, operatorReloaded, suggestionsReloaded] = await Promise.all([loadManagement(), loadOperator(), loadSuggestions()]);
                if (suggestionsReloaded) clearReviewed(key);
                if (!publicReloaded || !operatorReloaded) setRowErrors((current) => ({ ...current, [key]: "The monitoring expectation was saved, but the latest settings could not be loaded." }));
                else setRowStatuses((current) => ({ ...current, [key]: suggestionsReloaded ? "Monitoring expectation saved and confirmed by Atlas Core." : "Monitoring expectation saved and confirmed. Advisory suggestions could not be refreshed." }));
            } catch (error) {
                if (!active.current) return;
                if (committed) return;
                const status = isAxiosError(error) ? error.response?.status : undefined;
                const detail = isAxiosError<{ detail?: string }>(error) ? error.response?.data?.detail : undefined;
                const knownRejection = [401, 403, 404, 409, 413, 415, 422, 429].includes(status ?? 0)
                    || (status === 503 && ["mutation_not_activated", "store_migration_required", "store_unavailable", "provider_read_unavailable"].includes(detail ?? ""));
                if (!knownRejection) {
                    uncertainSave.current = key;
                    setUncertainCoordinate(key);
                    return;
                }
                let message = "Atlas Core could not save the monitoring expectation.";
                if (status === 401) { session.invalidate(); message = "Operator session expired. Sign in again."; }
                else if (status === 403) message = "You do not have permission to edit monitoring expectations.";
                else if (status === 409 && detail === "cas_conflict") message = "The monitoring setting changed. Review the latest value and choose again.";
                else if (status === 409 && detail === "fingerprint_mismatch") message = "The resource identity changed. Review the replacement before saving.";
                else if (status === 409 && detail === "request_conflict") message = "This save request is stale. Start a new Save action.";
                else if (status === 429) message = "Too many monitoring saves. Wait before trying again.";
                else if (status === 422) message = "This monitoring save request is invalid. Review the current state and choose again.";
                else if (status === 503) message = "Monitoring editing is temporarily unavailable or waiting for a data update.";
                setRowErrors((current) => ({ ...current, [key]: message }));
                if (status === 409 && (detail === "cas_conflict" || detail === "fingerprint_mismatch")) { invalidateReviewed(key); await Promise.all([loadManagement(), loadOperator(), loadSuggestions()]); }
            }
        } finally {
            saveInFlight.current = false;
            if (active.current) setUpdatingCoordinate(null);
        }
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
                <div><SectionHeader title="Resources and monitoring" description="Observed provider facts, identity assurance, and monitoring policy are shown separately." /><p className="mt-2 text-xs text-slate-500">Last successful inventory refresh: {refreshedAt}</p></div>
                <button type="button" onClick={() => { if (active.current && !saveInFlight.current && uncertainSave.current === null) void Promise.all([loadInventory(true), loadManagement(), loadOperator(), loadSuggestions()]); }} disabled={uncertainCoordinate !== null || checkingMonitoring || updatingCoordinate !== null || inventoryLoading || managementLoading || operatorLoading} className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50">{inventoryLoading || managementLoading || operatorLoading ? "Refreshing..." : "Refresh resources"}</button>
            </div>
            <div className="mt-4 space-y-2">
                {inventoryError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{inventoryError}</p>}
                {managementError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">Monitoring unavailable — {managementError} Observed inventory remains visible.</p>}
                {operatorError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{operatorError}</p>}
                {suggestionError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{suggestionError}</p>}
                {uncertainCoordinate !== null && <div role="alert" className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                    <p>Save outcome not confirmed. Check monitoring state before saving again.</p>
                    <button type="button" disabled={checkingMonitoring} onClick={() => void checkMonitoringState()} className="rounded-lg border border-amber-500/40 px-3 py-2 disabled:cursor-not-allowed disabled:opacity-50">{checkingMonitoring ? "Checking monitoring state..." : "Check monitoring state"}</button>
                </div>}
                {recoveryNotice && <p role="status" className="text-sm text-blue-200">{recoveryNotice}</p>}
                {updatingCoordinate !== null && <p role="status" className="text-sm text-blue-200">Monitoring update in progress. Other saves are temporarily paused.</p>}
                {composition.error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">Resource coordinates could not be composed safely. Monitoring and editing are unavailable.</p>}
            </div>
            {composition.resources.length === 0 ? (
                <p role="status" className="mt-6 text-sm text-slate-400">
                    {inventoryLoading || managementLoading
                        ? "Loading observed resources and monitoring state..."
                        : composition.error || inventoryError || managementError || inventory === null || management === null
                            ? "Resource list unavailable. Refresh resources to try again."
                            : "No provider resources are available."}
                </p>
            ) : (
                <div className="mt-6 space-y-4" aria-label="Provider resources">{composition.resources.map((resource) => <ResourceCard key={resource.coordinate} resource={resource} suggestion={suggestionsByCoordinate.get(resource.coordinate) ?? null} reviewedSuggestion={reviewedSuggestions[resource.coordinate] ?? null} reviewInvalidated={invalidatedReviews[resource.coordinate] ?? false} onReview={(suggestion) => { setReviewedSuggestions((current) => ({ ...current, [resource.coordinate]: suggestion })); setInvalidatedReviews((current) => ({ ...current, [resource.coordinate]: false })); revise(resource.coordinate); }} onDraftChange={() => setRowStatuses((current) => ({ ...current, [resource.coordinate]: "" }))} metadataColumns={metadataColumns} observationUnavailable={inventoryLoading || Boolean(inventoryError) || inventory === null} operatorEpoch={operatorEpoch} managementUnavailable={management === null} managementReadUnavailable={managementLoading || Boolean(managementError)} managementReadFailed={Boolean(managementError)} operatorState={session.authenticated ? (operator ? "available" : operatorLoading ? "loading" : "unavailable") : "anonymous"} saving={updatingCoordinate === resource.coordinate} blocked={uncertainCoordinate !== null || (updatingCoordinate !== null && updatingCoordinate !== resource.coordinate)} decisionRevision={decisionRevisions[resource.coordinate] ?? 0} error={rowErrors[resource.coordinate] || null} status={rowStatuses[resource.coordinate] || null} onSave={saveProviderIntent} />)}</div>
            )}
        </section>
    );
}

function ResourceCard({ resource, suggestion, reviewedSuggestion, reviewInvalidated, onReview, onDraftChange, metadataColumns, observationUnavailable, operatorEpoch, managementUnavailable, managementReadUnavailable, managementReadFailed, operatorState, saving, blocked, decisionRevision, error, status, onSave }: { resource: ComposedResource; suggestion: ProviderMonitoringIntentSuggestionV1 | null; reviewedSuggestion: ProviderMonitoringIntentSuggestionV1 | null; reviewInvalidated: boolean; onReview: (suggestion: ProviderMonitoringIntentSuggestionV1) => void; onDraftChange: () => void; metadataColumns: MetadataColumn[]; observationUnavailable: boolean; operatorEpoch: string; managementUnavailable: boolean; managementReadUnavailable: boolean; managementReadFailed: boolean; operatorState: "anonymous" | "loading" | "available" | "unavailable"; saving: boolean; blocked: boolean; decisionRevision: number; error: string | null; status: string | null; onSave: (publicResource: ManagedProviderResourceV2, operatorResource: ManagedProviderResourceV3, reviewedSuggestion: ProviderMonitoringIntentSuggestionV1 | null, expectation: ProviderMonitoringExpectation, acknowledge: boolean) => Promise<void> }) {
    const observed = resource.inventory;
    const managed = resource.inconsistent ? null : resource.management;
    const displayName = observed?.display_name ?? managed?.display_name ?? "Unknown resource";
    const resourceType = observed?.resource_type ?? managed?.resource_type ?? "unknown";
    const resourceId = observed?.resource_id ?? managed?.resource_id ?? "unknown";
    const reportedState = observed?.missing || (!observed && managed?.missing)
        ? "Missing"
        : formatLabel(observed?.current_state ?? "Unavailable");
    const observedState = observationUnavailable ? observed ? `Last reported: ${reportedState}` : "Unavailable" : reportedState;
    const presentation = monitoringPresentation(managed, observationUnavailable || managementReadUnavailable ? null : observed?.current_state ?? null, managementUnavailable || resource.inconsistent);
    const retainedManagement = managed !== null && managementReadUnavailable;
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
        <article className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/70 p-5 [overflow-wrap:anywhere]" data-testid={`resource-row-${resourceType}-${resourceId}`}>
            <div className="grid min-w-0 gap-5 md:grid-cols-2 xl:grid-cols-4">
                <section aria-label={`Resource ${displayName}`}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Resource</p><h3 className="mt-2 font-semibold text-slate-100">{displayName}</h3><p className="mt-1 text-sm uppercase text-slate-400">{resourceType} {resourceId}</p>{observed && metadataColumns.length > 0 && <dl className="mt-3 space-y-1 text-xs text-slate-400">{metadataColumns.map((column) => <div key={column.key} className="flex min-w-0 gap-2"><dt className="shrink-0">{column.label}:</dt><dd className="min-w-0">{column.render(observed)}</dd></div>)}</dl>}</section>
                <FactSection title="Observed state" value={observedState} detail={observationUnavailable ? observed ? "Current observation unavailable; the value above is last reported." : "No current provider observation is available." : "Reported by the provider; your monitoring setting is separate."} />
                <FactSection title="Identity" value={retainedManagement ? `Last reported: ${presentation.identity}` : presentation.identity} detail={retainedManagement ? "Current identity information could not be refreshed." : resource.inconsistent ? "Resource details do not match the monitoring record." : "Whether Atlas can verify this resource’s identity."} />
                <section aria-label={`Monitoring for ${displayName}`}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monitoring expectation</p><p className="mt-2 font-semibold text-slate-100">{retainedManagement ? `Last reported: ${presentation.expectation}` : presentation.expectation}</p><p className="mt-2 text-sm text-slate-300">{retainedManagement ? "Current monitoring settings could not be checked." : presentation.status}</p></section>
            </div>
            {displayedSuggestion && <ProviderIntentSuggestionCard suggestion={displayedSuggestion} unavailable={managementReadUnavailable || managementUnavailable} stale={suggestionStale} reviewed={reviewedCurrentSuggestion} onReview={() => onReview(displayedSuggestion)} />}
            {managed?.provider_id === "proxmox" && managed.resource_type === "qemu" && <div className="mt-5 border-t border-slate-800 pt-4"><ProviderIntentEditor key={`${resource.coordinate}:${managed.management_fingerprint}:${managed.record_version}:${decisionRevision}:${managementReadFailed}`} resource={managed} mutationResource={resource.operator} operatorState={operatorState} operatorEpoch={operatorEpoch} onDraftChange={onDraftChange} saving={saving} blocked={blocked || managementReadUnavailable} initialSelection={reviewedCurrentSuggestion ? reviewedSuggestion.suggested_expectation : undefined} requireExplicitSelection={reviewedSuggestion !== null && !reviewedCurrentSuggestion} onSave={async (expectation, acknowledge) => { if (resource.operator) await onSave(managed, resource.operator, reviewedCurrentSuggestion ? reviewedSuggestion : null, expectation, acknowledge); }} /></div>}
            {error && <p role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
            {status && <p role="status" className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">{status}</p>}
        </article>
    );
}

function FactSection({ title, value, detail }: { title: string; value: string; detail: string }) {
    return <section><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p><p className="mt-2 font-semibold text-slate-100">{value}</p><p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p></section>;
}

function formatMetadata(value: unknown): string { return typeof value === "string" || typeof value === "number" ? String(value) : "—"; }
