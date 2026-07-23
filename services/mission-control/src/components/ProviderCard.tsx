import { Link } from "react-router-dom";

import type { Provider } from "../types/provider";
import { StatusBadge } from "./StatusBadge";

type ProviderCardProps = {
    provider: Provider;
};

export function ProviderCard({
    provider,
}: ProviderCardProps) {
    const isCritical = provider.priority === "critical";

    return (
        <Link
            to={`/providers/${provider.id}`}
            aria-label={`Open ${provider.name} provider details`}
            className="group block rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
        >
            <article className="h-full rounded-lg border border-slate-800 bg-slate-900 p-5 transition duration-200 group-hover:-translate-y-0.5 group-hover:border-slate-600 group-hover:shadow-lg group-hover:shadow-black/20">
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                        <h3 className="truncate font-semibold text-slate-100">
                            {provider.name}
                        </h3>

                        <p className="mt-1 text-xs uppercase tracking-wider text-slate-500">
                            {isCritical
                                ? "Critical provider"
                                : `${provider.workspace} provider`}
                        </p>
                    </div>

                    <StatusBadge status={provider.health.status} />
                </div>

                <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-800 pt-4">
                    <div>
                        <dt className="text-xs uppercase tracking-wider text-slate-500">
                            Latency
                        </dt>

                        <dd className="mt-1 text-sm font-medium text-slate-200">
                            {provider.health.latency_ms === null
                                ? "—"
                                : `${provider.health.latency_ms} ms`}
                        </dd>
                    </div>

                    <div>
                        <dt className="text-xs uppercase tracking-wider text-slate-500">
                            HTTP
                        </dt>

                        <dd className="mt-1 text-sm font-medium text-slate-200">
                            {provider.health.http_status ?? "—"}
                        </dd>
                    </div>
                </dl>

                <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-3">
                    <span className="text-xs text-slate-500">
                        {provider.capabilities.length}{" "}
                        {provider.capabilities.length === 1
                            ? "capability"
                            : "capabilities"}
                    </span>

                    <span className="text-xs font-medium text-slate-500 transition group-hover:text-blue-300">
                        View details →
                    </span>
                </div>
            </article>
        </Link>
    );
}
