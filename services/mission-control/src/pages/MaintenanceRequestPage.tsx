import { isAxiosError } from "axios";
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import {
    getCapabilityResources,
    getOperationalCapabilities,
    requestRestartServiceIntent,
} from "../api/operatorIntent";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import { OPERATIONAL_INTENT_CREATE } from "../types/operatorAuth";
import type {
    OperatorIntentCreationResponse,
    OperationalCapabilityDescriptor,
    OperatorIntentResource,
} from "../types/operatorIntent";

function errorMessage(status: number | undefined): string {
    if (status === 403) return "Your operator session lacks maintenance permission.";
    if (status === 409) return "The resource changed. Refresh and select it again.";
    if (status === 429) return "Maintenance requests are rate limited. Wait before trying again.";
    if (status === 503) return "The Proxmox resource selector is temporarily unavailable.";
    return "The maintenance request could not be completed.";
}

function descriptorLabel(value: string | undefined): string {
    if (!value) return "Not available";
    if (value === "qemu") return "QEMU";
    return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("-", " ");
}

export function MaintenanceRequestPage() {
    const session = useOperatorSession();
    const [resources, setResources] = useState<OperatorIntentResource[]>([]);
    const [capability, setCapability] = useState<OperationalCapabilityDescriptor | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<OperatorIntentCreationResponse | null>(null);
    const [resultExpired, setResultExpired] = useState(false);

    const loadResources = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const capabilities = await getOperationalCapabilities();
            const selectedCapability = capabilities.capabilities.find(
                (item) => item.production_enabled && item.selector_available,
            ) ?? null;
            if (!selectedCapability) {
                setCapability(null);
                setResources([]);
                setError("No consistent production maintenance capability is currently available.");
                return;
            }
            const response = await getCapabilityResources(selectedCapability.selector_id);
            setCapability(selectedCapability);
            setResources(response.resources);
        } catch (requestError) {
            const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
            if (status === 401) session.invalidate();
            setError(errorMessage(status));
        } finally {
            setLoading(false);
        }
    }, [session]);

    useEffect(() => {
        if (session.authenticated) {
            queueMicrotask(() => void loadResources());
        }
    }, [session.authenticated, loadResources]);

    if (session.loading) return <main className="p-8 text-slate-400">Restoring operator session…</main>;
    if (!session.authenticated) {
        return <Navigate to="/operator/login" state={{ returnTo: "/operations/request" }} replace />;
    }

    const permitted = session.principal?.permissions.includes(OPERATIONAL_INTENT_CREATE) ?? false;
    const selected = resources.find((resource) => resource.resource_id === selectedId) ?? null;
    async function submit() {
        if (!selected?.requestable || !selected.operational_target_fingerprint || !session.csrfToken || submitting) return;
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
            setResult(response);
            setResultExpired(
                response.candidate.expires_at !== null
                && response.candidate.expires_at !== undefined
                && new Date(response.candidate.expires_at).getTime() <= Date.now()
            );
        } catch (requestError) {
            const status = isAxiosError(requestError) ? requestError.response?.status : undefined;
            if (status === 401) session.invalidate();
            if (status === 409) {
                setSelectedId(null);
                await loadResources();
            }
            setError(errorMessage(status));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="mx-auto max-w-6xl space-y-6 p-8">
            <header>
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Bounded maintenance</p>
                <h1 className="mt-2 text-3xl font-bold text-white">Request service restart</h1>
                <div className="mt-3 flex flex-wrap items-center gap-3"><p className="text-sm text-slate-400">Signed in as {session.principal?.operator_id}. This creates a candidate only; it does not restart anything.</p><button type="button" onClick={() => void session.logout()} className="text-sm font-semibold text-blue-300">Sign out</button></div>
            </header>
            <section className="grid gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-5 sm:grid-cols-3">
                <FixedField label="Action" value={capability?.label ?? "Loading capability"} />
                <FixedField label="Provider" value={descriptorLabel(capability?.provider_id)} />
                <FixedField label="Resource type" value={descriptorLabel(capability?.resource_type)} />
            </section>
            {!permitted && <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">Your operator session lacks maintenance permission.</p>}
            {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</p>}
            <section className="space-y-3" aria-label="Authoritative Proxmox resources">
                <div className="flex items-center justify-between"><h2 className="text-xl font-semibold text-white">Select one exact resource</h2><button type="button" onClick={() => void loadResources()} disabled={loading} className="text-sm font-semibold text-blue-300">Refresh</button></div>
                {loading && <p className="text-sm text-slate-400">Refreshing authoritative resources…</p>}
                {resources.map((resource) => (
                    <label key={resource.resource_id} className={`block rounded-xl border p-4 ${resource.requestable ? "border-slate-700 bg-slate-900/70" : "border-slate-800 bg-slate-900/30 text-slate-500"}`}>
                        <span className="flex gap-3">
                            <input type="radio" name="resource" checked={selectedId === resource.resource_id} disabled={!resource.requestable || !permitted} onChange={() => setSelectedId(resource.resource_id)} />
                            <span><strong className="text-slate-100">{resource.display_name}</strong><span className="ml-2 text-sm">VMID {resource.resource_id}</span><span className="ml-2 text-sm">{resource.node}</span><span className="ml-2 text-sm">{resource.current_state}</span>{!resource.requestable && <span className="mt-1 block text-sm">Unavailable: {resource.reason?.replaceAll("_", " ") ?? "unknown"}</span>}</span>
                        </span>
                    </label>
                ))}
            </section>
            <button type="button" onClick={() => void submit()} disabled={!selected?.requestable || submitting || !permitted} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-700">
                {submitting ? "Requesting candidate…" : "Request restart candidate"}
            </button>
            {result && <section className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-5"><h2 className="text-lg font-semibold text-emerald-200">Maintenance candidate ready</h2><p className="mt-2 break-all text-sm text-slate-200">Candidate ID: {result.candidate_id}</p><p className="mt-1 text-sm text-slate-300">Target: {selected?.display_name ?? result.candidate.target_id} ({result.candidate.target_id})</p><p className="mt-1 text-sm text-slate-300">Status: {result.candidate.status}</p><p className="mt-1 text-sm text-slate-300">Expires: {result.candidate.expires_at ?? "Not reported"}</p><p className="mt-1 text-sm text-amber-200">Expected disruption: brief service interruption</p>{resultExpired ? <p role="alert" className="mt-3 text-sm text-amber-200">This candidate has expired. Request a new maintenance candidate.</p> : <Link className="mt-4 inline-flex rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950" to={`/execution-candidates/${encodeURIComponent(result.candidate_id)}`}>Continue to candidate planning</Link>}</section>}
        </main>
    );
}

function FixedField({ label, value }: { label: string; value: string }) {
    return <div><p className="text-xs uppercase tracking-wider text-slate-500">{label}</p><p className="mt-1 font-semibold text-slate-100">{value}</p></div>;
}
