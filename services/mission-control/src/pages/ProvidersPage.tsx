import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { atlas } from "../api/atlas";
import { HealthEvidence } from "../components/HealthEvidence";
import { providerObservations } from "../features/mission-control/agentProviderEvidence";
import { safeText } from "../features/mission-control/overviewEvidence";

export function ProvidersPage() {
    const [providers, setProviders] = useState<ReturnType<typeof providerObservations>>(null);
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const requestGeneration = useRef(0);

    const load = useCallback(async () => {
        const generation = ++requestGeneration.current;
        setLoading(true);
        setError(false);
        try {
            const response = await atlas.get<unknown>("/providers");
            const observations = providerObservations(response.data);
            if (observations === null) throw new Error("Invalid provider catalog");
            if (generation === requestGeneration.current) setProviders(observations);
        } catch {
            if (generation === requestGeneration.current) {
                setError(true);
            }
        } finally {
            if (generation === requestGeneration.current) setLoading(false);
        }
    }, []);

    useEffect(() => {
        let active = true;
        void Promise.resolve().then(() => { if (active) return load(); });
        return () => { active = false; requestGeneration.current += 1; };
    }, [load]);

    const search = query.trim().toLowerCase();
    const visible = providers?.filter((provider) => provider.name.toLowerCase().includes(search)) ?? [];

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-4 sm:p-8">
            <header className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <Link to="/" className="mc-focusable text-sm text-blue-300">← Mission Control</Link>
                    <h1 className="mt-3 text-3xl font-semibold text-white">Providers</h1>
                    <p className="mt-2 text-sm text-slate-400">See the providers Atlas knows about. Open a provider for details.</p>
                </div>
                <button type="button" onClick={() => void load()} disabled={loading} className="mc-control mc-focusable px-4 py-2 text-sm font-semibold disabled:opacity-50">Refresh</button>
            </header>
            {loading && providers === null && <p role="status" className="text-slate-300">Loading providers…</p>}
            {loading && providers !== null && <p role="status" className="text-slate-300">Refreshing providers. Showing the last loaded information.</p>}
            {!loading && error && providers === null && (
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h2 className="font-semibold text-red-100">Providers could not load</h2>
                    <button type="button" onClick={() => void load()} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>
                </section>
            )}
            {!loading && error && providers !== null && (
                <section role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <h2 className="font-semibold text-amber-100">Provider refresh failed</h2>
                    <p className="mt-1 text-sm text-amber-100/80">Current provider information is unknown. The list shows the last loaded response.</p>
                    <button type="button" onClick={() => void load()} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>
                </section>
            )}
            {!loading && !error && providers?.length === 0 && <p className="rounded-xl border border-slate-800 p-5 text-slate-300">No providers are listed yet.</p>}
            {(loading || error) && providers?.length === 0 && <p role="status" className="text-slate-300">The last loaded response listed no providers.</p>}
            {providers !== null && (providers.length > 1 || query.length > 0) && (
                <label className="block max-w-md text-sm text-slate-300">
                    Search providers
                    <input type="search" value={query} maxLength={100} onChange={(event) => setQuery(event.target.value)} placeholder="Find a provider" className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                </label>
            )}
            {providers !== null && providers.length > 0 && visible.length === 0 && (
                <section className="rounded-xl border border-slate-800 p-5 text-slate-300">
                    <p>No providers match your search.</p>
                    <button type="button" onClick={() => setQuery("")} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm">Clear search</button>
                </section>
            )}
            {providers !== null && visible.length > 0 && (
                <section aria-label="Provider list" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {visible.map((provider, index) => (
                        <article key={provider.path ?? index} className="min-w-0 space-y-3 rounded-xl border border-slate-800 bg-slate-900/70 p-5 [overflow-wrap:anywhere]">
                            <h2 className="text-lg font-semibold text-white">{provider.name}</h2>
                            <HealthEvidence status={safeText(provider.status)} reason={safeText(provider.reason)} stale={loading || error} compact />
                            {provider.path && <Link to={provider.path} className="mc-focusable inline-block text-sm font-semibold text-blue-300">Open {provider.name} provider</Link>}
                        </article>
                    ))}
                </section>
            )}
        </main>
    );
}
