import type { ServiceHealth } from "../types/health";
import { StatusBadge } from "./StatusBadge";

type ServiceHealthCardProps = {
    name: string;
    health: ServiceHealth;
    onSelect: () => void;
};

function formatLatency(latency: number | null): string {
    if (latency === null) {
        return "Unavailable";
    }

    return `${Math.round(latency)} ms`;
}

function formatHttpStatus(status: number | null): string {
    if (status === null) {
        return "No response";
    }

    return String(status);
}

export function ServiceHealthCard({
    name,
    health,
    onSelect,
}: ServiceHealthCardProps) {
    return (
        <button
            type="button"
            onClick={onSelect}
            className="w-full rounded-lg border border-slate-800 bg-slate-900 p-5 text-left shadow-sm transition hover:border-slate-700 hover:bg-slate-800/70 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            aria-label={`View details for ${name}`}
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h3 className="font-semibold text-slate-100">
                        {name}
                    </h3>
                    <p className="mt-1 text-xs uppercase tracking-wider text-slate-500">
                        Service health
                    </p>
                </div>

                <StatusBadge status={health.status} />
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-800 pt-4">
                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        Latency
                    </dt>
                    <dd className="mt-1 text-sm font-medium text-slate-300">
                        {formatLatency(health.latency_ms)}
                    </dd>
                </div>

                <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                        HTTP
                    </dt>
                    <dd className="mt-1 text-sm font-medium text-slate-300">
                        {formatHttpStatus(health.http_status)}
                    </dd>
                </div>
            </dl>

            {health.message && (
                <p className="mt-4 rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-200">
                    {health.message}
                </p>
            )}
        </button>
    );
}
