import type { Provider } from "../types/provider";
import { healthReason, healthState } from "../utils/healthPresentation";
import { HealthEvidence } from "./HealthEvidence";

type ProviderOverviewProps = {
    provider: Provider;
    stale?: boolean;
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

function providerAddress(value: unknown): string | null {
    if (typeof value !== "string") return null;
    try {
        const url = new URL(value);
        return url.protocol === "http:" || url.protocol === "https:"
            ? url.origin
            : null;
    } catch {
        return null;
    }
}

export function ProviderOverview({
    provider,
    stale = false,
}: ProviderOverviewProps) {
    const capabilities = Array.isArray(provider.capabilities)
        ? provider.capabilities
        : null;
    const address = providerAddress(provider.health.details.url);
    const isUnavailable = healthState(provider.health.status) === "Unavailable";
    const connectionMessage = healthReason(provider.health.message);

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-5 sm:p-8">
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

                <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                    <HealthEvidence
                        status={provider.health.status}
                        stale={stale}
                        compact
                    />
                    {provider.health.latency_ms !== null && (
                        <p className="text-sm text-slate-400">
                            {stale ? "Last known response time " : "Response time "}
                            <span className="font-semibold text-slate-200">
                                {provider.health.latency_ms} ms
                            </span>
                        </p>
                    )}
                </div>
            </div>

            {stale && (
                <p role="status" className="mt-4 text-sm text-amber-200">
                    Could not update provider details. This information may be out of date.
                </p>
            )}

            {isUnavailable && !stale && (
                <p className="mt-4 text-sm text-slate-400">
                    Atlas Core could not reach this provider. It may still be running on its own computer.
                </p>
            )}

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
                        Supported features
                    </p>

                    {capabilities === null ? (
                        <p role="status" className="mt-2 text-sm text-slate-500">
                            Atlas couldn't load this provider's supported features. Some sections are hidden.
                        </p>
                    ) : capabilities.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                            {capabilities.map((capability) => (
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
                            No supported features are listed.
                        </p>
                    )}
                </div>
            </div>

            <details className="mt-6 border-t border-slate-800 pt-5">
                <summary className="cursor-pointer text-sm font-medium text-slate-400 hover:text-slate-200">
                    Technical details
                </summary>

                <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <div>
                        <dt className="text-xs uppercase tracking-wider text-slate-500">
                            {stale ? "Last known HTTP response code" : "HTTP response code"}
                        </dt>
                        <dd className="mt-2 text-sm font-semibold text-slate-200">
                            {provider.health.http_status ?? "Not reported"}
                        </dd>
                    </div>

                    <div>
                        <dt className="text-xs uppercase tracking-wider text-slate-500">
                            Provider priority
                        </dt>
                        <dd className="mt-2 text-sm font-semibold text-slate-200">
                            {formatLabel(provider.priority)}
                        </dd>
                    </div>

                    <div>
                        <dt className="text-xs uppercase tracking-wider text-slate-500">
                            Version
                        </dt>
                        <dd className="mt-2 text-sm font-semibold text-slate-200">
                            {provider.version}
                        </dd>
                    </div>

                    {address && (
                        <div className="sm:col-span-2 lg:col-span-3">
                            <dt className="text-xs uppercase tracking-wider text-slate-500">
                                Provider address
                            </dt>
                            <dd className="mt-2 break-all font-mono text-sm text-slate-300">
                                {address}
                            </dd>
                        </div>
                    )}
                </dl>
            </details>

            {connectionMessage && (
                <div className="mt-6 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4">
                    <p className="text-sm text-amber-200">
                        {stale ? `Last known connection result: ${connectionMessage}` : connectionMessage}
                    </p>
                </div>
            )}
        </section>
    );
}
