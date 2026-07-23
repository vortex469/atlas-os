import type { Provider } from "../types/provider";
import { StatusBadge } from "./StatusBadge";

type ProviderOverviewProps = {
    provider: Provider;
};

function formatLabel(value: string): string {
    return value
        .split(/[-_]/)
        .filter(Boolean)
        .map(
            (word) =>
                word.charAt(0).toUpperCase() +
                word.slice(1),
        )
        .join(" ");
}

export function ProviderOverview({
    provider,
}: ProviderOverviewProps) {
    const endpoint =
        typeof provider.health.details.url === "string"
            ? provider.health.details.url
            : null;

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-8">
            <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Provider
                    </p>

                    <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-100">
                        {provider.name}
                    </h1>

                    <p className="mt-2 text-sm text-slate-400">
                        {provider.description ||
                            `${formatLabel(provider.workspace)} provider`}
                    </p>
                </div>

                <StatusBadge status={provider.health.status} />
            </div>

            <dl className="mt-8 grid gap-4 border-t border-slate-800 pt-6 sm:grid-cols-2 lg:grid-cols-5">
                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Status
                    </dt>

                    <dd className="mt-2 text-base font-semibold capitalize text-slate-100">
                        {provider.health.status}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Latency
                    </dt>

                    <dd className="mt-2 text-base font-semibold text-slate-100">
                        {provider.health.latency_ms === null
                            ? "—"
                            : `${provider.health.latency_ms} ms`}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        HTTP Status
                    </dt>

                    <dd className="mt-2 text-base font-semibold text-slate-100">
                        {provider.health.http_status ?? "—"}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Priority
                    </dt>

                    <dd className="mt-2 text-base font-semibold text-slate-100">
                        {formatLabel(provider.priority)}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Version
                    </dt>

                    <dd className="mt-2 text-base font-semibold text-slate-100">
                        {provider.version}
                    </dd>
                </div>
            </dl>

            <div className="mt-6 grid gap-6 border-t border-slate-800 pt-6 lg:grid-cols-2">
                <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                        Workspace
                    </p>

                    <p className="mt-2 text-sm font-medium text-slate-300">
                        {formatLabel(provider.workspace)}
                    </p>
                </div>

                <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                        Capabilities
                    </p>

                    {provider.capabilities.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                            {provider.capabilities.map((capability) => (
                                <span
                                    key={capability}
                                    className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs font-medium text-slate-300"
                                >
                                    {formatLabel(capability)}
                                </span>
                            ))}
                        </div>
                    ) : (
                        <p className="mt-2 text-sm text-slate-500">
                            No capabilities advertised.
                        </p>
                    )}
                </div>
            </div>

            {endpoint && (
                <div className="mt-6 border-t border-slate-800 pt-6">
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                        Health Endpoint
                    </p>

                    <p className="mt-2 break-all font-mono text-sm text-slate-300">
                        {endpoint}
                    </p>
                </div>
            )}

            {provider.health.message && (
                <div className="mt-6 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4">
                    <p className="text-sm text-amber-200">
                        {provider.health.message}
                    </p>
                </div>
            )}
        </section>
    );
}
