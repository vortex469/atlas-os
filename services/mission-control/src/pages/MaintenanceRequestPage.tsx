import { isAxiosError } from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useLocation } from "react-router-dom";

import { getDiscoveryProposal } from "../api/discovery";
import {
    getCapabilityResources,
    getOperationalCapabilities,
    requestRestartServiceIntent,
} from "../api/operatorIntent";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import { OPERATIONAL_INTENT_CREATE } from "../types/operatorAuth";
import type { DiscoveryProposalNavigation } from "../types/discovery";
import { DiscoveryProposalCard } from "../features/discovery/DiscoveryProposalCard";
import { proposalIdFromState } from "../features/discovery/proposalNavigation";
import type {
    OperatorIntentCreationResponse,
    OperationalCapabilityDescriptor,
    OperatorIntentResource,
} from "../types/operatorIntent";

function errorMessage(status: number | undefined): string {
    if (status === 403) return "Your account does not have permission to request maintenance.";
    if (status === 409) return "This VM changed. Refresh the list and choose it again.";
    if (status === 429) return "Too many maintenance requests. Wait before trying again.";
    if (status === 503) return "The VM list is temporarily unavailable. Try again shortly.";
    return "The maintenance request could not be completed.";
}

function descriptorLabel(value: string | undefined): string {
    if (!value) return "Not available";
    if (value === "qemu") return "QEMU";
    return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("-", " ");
}

function resourceBlocker(reason: OperatorIntentResource["reason"]): string {
    switch (reason) {
        case "identity_unavailable": return "Atlas could not confirm this VM’s identity.";
        case "unsupported_resource_type": return "This resource type cannot be restarted here.";
        case "stopped": return "This VM is stopped. Select a running VM to request a restart.";
        case "template": return "Templates cannot be restarted.";
        case "locked": return "This VM is locked in Proxmox.";
        case "migrating": return "This VM is moving between hosts.";
        case "unavailable_state": return "Atlas could not confirm this VM’s current state.";
        default: return "This VM cannot be selected for a restart.";
    }
}

function formatExpiry(value: string | null | undefined): string | null {
    if (!value) return null;
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return null;
    return `${date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC`;
}

export function MaintenanceRequestPage() {
    const session = useOperatorSession();
    const location = useLocation();
    const [resources, setResources] = useState<OperatorIntentResource[]>([]);
    const [capability, setCapability] = useState<OperationalCapabilityDescriptor | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<OperatorIntentCreationResponse | null>(null);
    const [resultExpired, setResultExpired] = useState(false);
    const [proposal, setProposal] = useState<DiscoveryProposalNavigation | null>(null);
    const [proposalLoading, setProposalLoading] = useState(false);
    const [proposalError, setProposalError] = useState<string | null>(null);
    const [proposalNotFound, setProposalNotFound] = useState(false);
    const [proposalLoadAttempt, setProposalLoadAttempt] = useState(0);
    const proposalId = proposalIdFromState(location.state);

    const selectorGeneration = useRef(0);
    const submissionGeneration = useRef(0);

    const loadResources = useCallback(async () => {
        const generation = ++selectorGeneration.current;
        setSelectedId(null);
        setResources([]);
        setCapability(null);
        setResult(null);
        setResultExpired(false);
        setLoading(true);
        setError(null);
        try {
            const capabilities = await getOperationalCapabilities();
            if (generation !== selectorGeneration.current) return;
            const selectedCapability = capabilities.capabilities.find(
                (item) => item.production_enabled && item.selector_available,
            ) ?? null;
            if (!selectedCapability) {
                setCapability(null);
                setResources([]);
                setError("Restart requests are not available right now.");
                return;
            }
            const response = await getCapabilityResources(selectedCapability.selector_id);
            if (generation !== selectorGeneration.current) return;
            setCapability(selectedCapability);
            setResources(response.resources);
        } catch (requestError) {
            if (generation !== selectorGeneration.current) return;
            const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
            if (status === 401) session.invalidate();
            setError(errorMessage(status));
        } finally {
            if (generation === selectorGeneration.current) setLoading(false);
        }
    }, [session]);

    useEffect(() => {
        let cancelled = false;
        if (session.authenticated) {
            queueMicrotask(() => { if (!cancelled) void loadResources(); });
        }
        return () => { cancelled = true; selectorGeneration.current += 1; submissionGeneration.current += 1; };
    }, [session.authenticated, loadResources]);

    useEffect(() => {
        let cancelled = false;
        if (!session.authenticated || proposalId === null) return () => { cancelled = true; };
        queueMicrotask(() => {
            if (cancelled) return;
            setProposal(null);
            setProposalError(null);
            setProposalNotFound(false);
            setProposalLoading(true);
            void getDiscoveryProposal(proposalId)
                .then((value) => { if (!cancelled) setProposal(value); })
                .catch((requestError: unknown) => {
                    if (cancelled) return;
                    const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
                    setProposalNotFound(status === 404);
                    setProposalError(status === 404
                        ? "This suggestion is no longer available. Choose a VM from the list below."
                        : "Suggestion details could not be loaded. You can still choose a VM from the list below.");
                })
                .finally(() => { if (!cancelled) setProposalLoading(false); });
        });
        return () => { cancelled = true; };
    }, [proposalId, proposalLoadAttempt, session.authenticated]);

    if (session.loading) return <main className="p-8 text-slate-400">Restoring operator session…</main>;
    if (!session.authenticated) {
        return <Navigate to="/operator/login" state={proposalId ? { proposalId } : undefined} replace />;
    }

    const permitted = session.principal?.permissions.includes(OPERATIONAL_INTENT_CREATE) ?? false;
    const selected = resources.find((resource) => resource.resource_id === selectedId) ?? null;
    const expiry = result ? formatExpiry(result.candidate.expires_at) : null;
    async function submit() {
        if (!selected?.requestable || !selected.operational_target_fingerprint || !session.csrfToken || !permitted || loading || submitting) return;
        const generation = ++submissionGeneration.current;
        setSubmitting(true);
        setError(null);
        setResult(null);
        setResultExpired(false);
        try {
            const response = await requestRestartServiceIntent(
                selected.resource_id,
                selected.operational_target_fingerprint,
                session.csrfToken,
            );
            if (generation !== submissionGeneration.current) return;
            if (!response.candidate_id || response.candidate_id !== response.candidate?.id
                || response.candidate.target_id !== selected.resource_id
                || response.candidate.target_type !== selected.resource_type
                || response.candidate.execution_intent !== "restart-service"
                || response.candidate.source_subsystem !== "operator-intent") {
                setError("The returned proposal does not match this maintenance request. Refresh the resource list before continuing.");
                return;
            }
            setResult(response);
            setResultExpired(
                response.candidate.expires_at !== null
                && response.candidate.expires_at !== undefined
                && new Date(response.candidate.expires_at).getTime() <= Date.now()
            );
        } catch (requestError) {
            if (generation !== submissionGeneration.current) return;
            const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
            if (status === 401) session.invalidate();
            if (status === 409) {
                setSelectedId(null);
                await loadResources();
            }
            setError(errorMessage(status));
        } finally {
            if (generation === submissionGeneration.current) setSubmitting(false);
        }
    }

    return (
        <main className="mx-auto max-w-6xl space-y-6 p-8">
            <header>
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Maintenance request</p>
                <h1 className="mt-2 text-3xl font-bold text-white">Request service restart</h1>
                <div className="mt-3 flex flex-wrap items-center gap-3"><p className="text-sm text-slate-400">Signed in as {session.principal?.operator_id}. This creates a proposal for separate review and approval; it does not restart the VM.</p><button type="button" onClick={() => void session.logout()} className="text-sm font-semibold text-blue-300">Sign out</button></div>
            </header>
            {(proposalId !== null || proposalLoading || proposalError || proposal) && (
                <section aria-label="Suggestion details" className="space-y-3">
                    <h2 className="text-xl font-semibold text-white">Suggestion details</h2>
                    <p className="text-sm text-slate-400">This suggestion cannot select a VM for you. Choose one from the VM list below.</p>
                    {proposalLoading && <p className="text-sm text-slate-400">Loading suggestion details…</p>}
                    {proposalError && <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200"><p>{proposalError}</p>{!proposalNotFound && <button type="button" onClick={() => setProposalLoadAttempt((attempt) => attempt + 1)} className="mt-3 rounded-lg border border-amber-300/40 px-3 py-2 font-semibold text-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-200">Retry loading suggestion</button>}</div>}
                    {proposal && <DiscoveryProposalCard proposal={proposal} showNavigation={false} />}
                </section>
            )}
            {capability && <section className="grid gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-5 sm:grid-cols-3">
                <FixedField label="Action" value={capability.label} />
                <FixedField label="Provider" value={descriptorLabel(capability.provider_id)} />
                <FixedField label="Resource type" value={descriptorLabel(capability.resource_type)} />
            </section>}
            {!permitted && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">Your account does not have permission to request maintenance.</p>}
            {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</p>}
            <section className="space-y-3" aria-label="Available virtual machines">
                <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold text-white">Choose a virtual machine</h2><p className="mt-1 text-sm text-slate-400">Only running VMs can be selected. Atlas checks the VM again before creating your proposal.</p></div><button type="button" onClick={() => void loadResources()} disabled={loading || submitting} className="text-sm font-semibold text-blue-300">Refresh</button></div>
                {loading && <p className="text-sm text-slate-400">Loading available VMs…</p>}
                {resources.map((resource) => (
                    <label key={resource.resource_id} className={`block rounded-xl border p-4 ${resource.requestable ? "border-slate-700 bg-slate-900/70" : "border-slate-800 bg-slate-900/30 text-slate-500"}`}>
                        <span className="flex gap-3">
                            <input type="radio" name="resource" checked={selectedId === resource.resource_id} disabled={!resource.requestable || !permitted || loading || submitting} onChange={() => { setSelectedId(resource.resource_id); setResult(null); setResultExpired(false); setError(null); }} />
                            <span className="min-w-0 flex-1">
                                <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                    <strong className="text-slate-100">{resource.display_name}</strong>
                                    <span className="rounded-full border border-slate-600 px-2 py-0.5 text-xs">{descriptorLabel(resource.current_state)}</span>
                                </span>
                                <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-400"><span>VMID {resource.resource_id}</span><span>Node {resource.node}</span></span>
                                {!resource.requestable && <span className="mt-2 block text-sm text-amber-200">{resourceBlocker(resource.reason)}</span>}
                            </span>
                        </span>
                    </label>
                ))}
            </section>
            <button type="button" onClick={() => void submit()} disabled={!selected?.requestable || loading || submitting || !permitted} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-700">
                {submitting ? "Requesting restart proposal…" : "Request restart proposal"}
            </button>
            {result && <section aria-label="Restart proposal ready" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-5">
                <h2 className="text-lg font-semibold text-emerald-200">Restart proposal ready for review</h2>
                <p className="mt-2 text-sm text-slate-200">Target: {selected?.display_name ?? "selected VM"}. Nothing has restarted.</p>
                <p className="mt-1 text-sm text-slate-300">Expected impact: brief service interruption.</p>
                {expiry ? <p className="mt-1 text-sm text-slate-300">Expires {expiry}</p> : <p className="mt-1 text-sm text-slate-300">Expiry time unavailable.</p>}
                {resultExpired ? <p role="alert" className="mt-3 text-sm text-amber-200">This proposal has expired. Request a new restart proposal before continuing.</p> : <Link className="mt-4 inline-flex rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950" to={`/execution-candidates/${encodeURIComponent(result.candidate_id)}`}>Review restart proposal</Link>}
                <details className="mt-4 text-sm text-slate-300"><summary>Technical details</summary><dl className="mt-3 grid gap-2 sm:grid-cols-2"><TechnicalField label="Proposal ID" value={result.candidate_id} /><TechnicalField label="Target ID" value={result.candidate.target_id} /><TechnicalField label="Reported status" value={result.candidate.status} /><TechnicalField label="Expiry time (UTC)" value={result.candidate.expires_at ?? "Not reported"} /></dl></details>
            </section>}
        </main>
    );
}

function FixedField({ label, value }: { label: string; value: string }) {
    return <div><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-1 font-semibold text-slate-100">{value}</p></div>;
}

function TechnicalField({ label, value }: { label: string; value: string }) {
    return <div className="min-w-0"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-all font-mono text-xs">{value}</dd></div>;
}
