import { isAxiosError } from "axios";
import { evidenceTimestamp } from "../utils/healthPresentation";
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

type MaintenanceError = { message: string; reviewProposals?: boolean };

function errorMessage(status: number | undefined, stage: "resources" | "proposal"): MaintenanceError {
    if (status === 403) return { message: "Your operator session lacks maintenance permission." };
    if (status === 409) return { message: "The resource changed. Refresh and select it again." };
    if (status === 429) return { message: "Maintenance requests are rate limited. Wait before trying again." };
    if (stage === "proposal" && (status === undefined || status >= 500)) {
        return {
            message: status === 503
                ? "The maintenance proposal service is temporarily unavailable. The request outcome is unknown. Review change proposals before creating another request."
                : "The proposal request outcome is unknown. Review change proposals before creating another request.",
            reviewProposals: true,
        };
    }
    if (status === 503) return { message: "Maintenance resources are temporarily unavailable. Choose Refresh to check again." };
    return { message: stage === "resources"
        ? "Maintenance resources could not be loaded. Choose Refresh to check again."
        : "The proposal request could not be completed." };
}

function descriptorLabel(value: string | undefined): string {
    if (!value) return "Not available";
    if (value === "qemu") return "QEMU";
    return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("-", " ");
}

export function MaintenanceRequestPage() {
    const session = useOperatorSession();
    const location = useLocation();
    const [resources, setResources] = useState<OperatorIntentResource[]>([]);
    const [capability, setCapability] = useState<OperationalCapabilityDescriptor | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<MaintenanceError | null>(null);
    const [result, setResult] = useState<OperatorIntentCreationResponse | null>(null);
    const [resultExpired, setResultExpired] = useState(false);
    const [proposal, setProposal] = useState<DiscoveryProposalNavigation | null>(null);
    const [proposalLoading, setProposalLoading] = useState(false);
    const [proposalError, setProposalError] = useState<string | null>(null);
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
                setError({ message: "No consistent production maintenance capability is currently available." });
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
            setError(errorMessage(status, "resources"));
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
            setProposalLoading(true);
            void getDiscoveryProposal(proposalId)
                .then((value) => { if (!cancelled) setProposal(value); })
                .catch((requestError: unknown) => {
                    if (cancelled) return;
                    const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
                    setProposalError(status === 404
                        ? "The advisory proposal was not found. Select only from the current authoritative resource list."
                        : "Advisory proposal context is temporarily unavailable. The authoritative selector remains independent.");
                })
                .finally(() => { if (!cancelled) setProposalLoading(false); });
        });
        return () => { cancelled = true; };
    }, [proposalId, session.authenticated]);

    const expiresAt = result?.candidate.expires_at;
    const expiryTime = evidenceTimestamp(expiresAt);
    const expiryUnreadable = expiresAt !== null && expiresAt !== undefined && expiryTime === null;
    const proposalExpired = resultExpired || result?.candidate.status === "expired";
    const proposalReady = result?.candidate.status === "eligible" && !proposalExpired && !expiryUnreadable;
    useEffect(() => {
        if (expiryTime === null) return;
        let timer: number;
        const checkExpiry = () => {
            const remaining = expiryTime - Date.now();
            if (remaining <= 0) setResultExpired(true);
            else timer = window.setTimeout(checkExpiry, Math.min(remaining, 2_147_483_647));
        };
        // Cap long waits to the browser timer limit; expiry does not trigger a request.
        timer = window.setTimeout(checkExpiry, Math.max(0, Math.min(expiryTime - Date.now(), 2_147_483_647)));
        return () => window.clearTimeout(timer);
    }, [expiryTime, result]);

    if (session.loading) return <main className="p-8 text-slate-400">Restoring operator session…</main>;
    if (!session.authenticated) {
        return <Navigate to="/operator/login" state={proposalId ? { proposalId } : undefined} replace />;
    }

    const permitted = session.principal?.permissions.includes(OPERATIONAL_INTENT_CREATE) ?? false;
    const selected = resources.find((resource) => resource.resource_id === selectedId) ?? null;
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
                setError({ message: "The returned proposal does not match this maintenance request. Refresh the resource list before continuing.", reviewProposals: true });
                return;
            }
            setResult(response);
            setResultExpired(
                response.candidate.expires_at !== null
                && response.candidate.expires_at !== undefined
                && (evidenceTimestamp(response.candidate.expires_at) ?? Infinity) <= Date.now()
            );
        } catch (requestError) {
            if (generation !== submissionGeneration.current) return;
            const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
            if (status === 401) session.invalidate();
            if (status === 409) {
                setSelectedId(null);
                await loadResources();
            }
            setError(errorMessage(status, "proposal"));
        } finally {
            if (generation === submissionGeneration.current) setSubmitting(false);
        }
    }

    return (
        <main className="mx-auto max-w-6xl space-y-6 p-8">
            <header>
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Maintenance</p>
                <h1 className="mt-2 text-3xl font-bold text-white">Request service restart</h1>
                <div className="mt-3 flex flex-wrap items-center gap-3"><p className="text-sm text-slate-400">Signed in as {session.principal?.operator_id}. Creating a proposal does not restart anything.</p><button type="button" onClick={() => void session.logout()} className="text-sm font-semibold text-blue-300">Sign out</button></div>
            </header>
            {(proposalId !== null || proposalLoading || proposalError || proposal) && (
                <section aria-label="Advisory proposal context" className="space-y-3">
                    <h2 className="text-xl font-semibold text-white">Advisory proposal context</h2>
                    <p className="text-sm text-slate-400">This context cannot select a resource or alter the authoritative maintenance request.</p>
                    {proposalLoading && <p className="text-sm text-slate-400">Refreshing proposal status…</p>}
                    {proposalError && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">{proposalError}</p>}
                    {proposal && <DiscoveryProposalCard proposal={proposal} showNavigation={false} />}
                </section>
            )}
            <section className="grid gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-5 sm:grid-cols-3">
                <FixedField label="Action" value={capability?.label ?? (loading ? "Loading capability" : "Maintenance unavailable")} />
                <FixedField label="Provider" value={descriptorLabel(capability?.provider_id)} />
                <FixedField label="Resource type" value={descriptorLabel(capability?.resource_type)} />
            </section>
            {!permitted && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">Your operator session lacks maintenance permission.</p>}
            {error && <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-200">
                <p>{error.message}</p>
                {error.reviewProposals && <Link to="/execution-candidates" className="mt-3 inline-flex font-semibold text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Review change proposals</Link>}
            </div>}
            <section className="space-y-3" aria-label="Authoritative Proxmox resources">
                <div className="flex items-center justify-between"><h2 className="text-xl font-semibold text-white">Choose a resource</h2><button type="button" onClick={() => void loadResources()} disabled={loading || submitting} className="text-sm font-semibold text-blue-300">Refresh</button></div>
                {loading && <p className="text-sm text-slate-400">Refreshing authoritative resources…</p>}
                {!loading && capability && resources.length === 0 && <p role="status" className="text-sm text-slate-400">No resources were returned. Choose Refresh to check again.</p>}
                {resources.map((resource) => (
                    <label key={resource.resource_id} className={`block rounded-xl border p-4 ${resource.requestable ? "border-slate-700 bg-slate-900/70" : "border-slate-800 bg-slate-900/30 text-slate-500"}`}>
                        <span className="flex gap-3">
                            <input type="radio" name="resource" checked={selectedId === resource.resource_id} disabled={!resource.requestable || !permitted || loading || submitting} onChange={() => { setSelectedId(resource.resource_id); setResult(null); setResultExpired(false); setError(null); }} />
                            <span><strong className="text-slate-100">{resource.display_name}</strong><span className="ml-2 text-sm">VMID {resource.resource_id}</span><span className="ml-2 text-sm">{resource.node}</span><span className="ml-2 text-sm">{resource.current_state}</span>{!resource.requestable && <span className="mt-1 block text-sm">Unavailable: {resource.reason?.replaceAll("_", " ") ?? "unknown"}</span>}</span>
                        </span>
                    </label>
                ))}
            </section>
            <button type="button" onClick={() => void submit()} disabled={!selected?.requestable || loading || submitting || !permitted} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-700">
                {submitting ? "Creating proposal…" : "Create restart proposal"}
            </button>
            {result && (
                <section className={`rounded-xl border p-5 ${!proposalReady ? "border-amber-500/30 bg-amber-500/10" : "border-emerald-500/30 bg-emerald-500/10"}`}>
                    <h2 className={`text-lg font-semibold ${!proposalReady ? "text-amber-200" : "text-emerald-200"}`}>
                        {expiryUnreadable ? "Proposal expiration unknown" : proposalExpired ? "Maintenance proposal expired" : !proposalReady ? "Maintenance proposal unavailable" : "Maintenance proposal ready"}
                    </h2>
                    <p className="mt-2 text-sm text-slate-300">Target: {selected?.display_name ?? result.candidate.target_id} ({result.candidate.target_id})</p>
                    <p className="mt-1 text-sm text-slate-300">Expires: {expiryUnreadable ? "Not readable" : result.candidate.expires_at ?? "Not reported"}</p>
                    <p className="mt-1 text-sm text-amber-200">Expected disruption: brief service interruption</p>
                    <details className="mt-3 text-sm text-slate-300">
                        <summary className="cursor-pointer font-semibold text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Proposal details</summary>
                        <p className="mt-2 break-all">Candidate ID: {result.candidate_id}</p>
                        <p className="mt-1">Status: {result.candidate.status}</p>
                    </details>
                    {expiryUnreadable ? (
                        <p role="alert" className="mt-3 text-sm text-amber-200">The proposal expiration could not be confirmed. Refresh the resource list before requesting a new proposal.</p>
                    ) : proposalExpired ? (
                        <p role="alert" className="mt-3 text-sm text-amber-200">This proposal has expired. Refresh the resource list before requesting a new proposal.</p>
                    ) : !proposalReady ? (
                        <p role="alert" className="mt-3 text-sm text-amber-200">
                            {result.candidate.status === "not_eligible" || result.candidate.status === "rejected"
                                ? "This proposal is not eligible for planning."
                                : "The proposal status could not be confirmed."} Refresh the resource list before requesting a new proposal.
                        </p>
                    ) : (
                        <>
                            <p className="mt-3 text-sm text-slate-300">Review the proposal and its plan, then approve the exact restart action.</p>
                            <Link className="mt-4 inline-flex rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950" to={`/execution-candidates/${encodeURIComponent(result.candidate_id)}`}>Review restart proposal</Link>
                        </>
                    )}
                </section>
            )}
        </main>
    );
}

function FixedField({ label, value }: { label: string; value: string }) {
    return <div><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-1 font-semibold text-slate-100">{value}</p></div>;
}
