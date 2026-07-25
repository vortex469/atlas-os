import { useEffect } from "react";
import type { ServiceHealth } from "../types/health";
import { StatusBadge } from "./StatusBadge";

type ServiceDetailsDrawerProps = {
    name: string;
    health: ServiceHealth;
    isRefreshing: boolean;
    onRefresh: () => void;
    onClose: () => void;
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

export function ServiceDetailsDrawer({
    name,
    health,
    isRefreshing,
    onRefresh,
    onClose,
}: ServiceDetailsDrawerProps) {
    useEffect(() => {
        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", handleKeyDown);

        return () => {
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [onClose]);

    const hasDetails = Object.keys(health.details).length > 0;

    return (
        <div
            className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm"
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) {
                    onClose();
                }
            }}
        >
            <aside
                role="dialog"
                aria-modal="true"
                aria-labelledby="service-details-title"
                className="h-full w-full max-w-lg overflow-y-auto border-l border-slate-800 bg-slate-950 shadow-2xl"
            >
                <div className="flex items-start justify-between gap-4 border-b border-slate-800 p-6">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                            Service details
                        </p>
                        <h2
                            id="service-details-title"
                            className="mt-2 text-2xl font-semibold text-slate-100"
                        >
                            {name}
                        </h2>
                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white"
                    >
                        Close
                    </button>
                </div>

                <div className="space-y-6 p-6">
                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                        <div className="flex items-center justify-between gap-4">
                            <span className="text-sm font-medium text-slate-400">
                                Current status
                            </span>
                            <StatusBadge status={health.status} />
                        </div>
                    </div>

                    <dl className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                            <dt className="text-xs uppercase tracking-wider text-slate-500">
                                Latency
                            </dt>
                            <dd className="mt-2 text-lg font-semibold text-slate-100">
                                {formatLatency(health.latency_ms)}
                            </dd>
                        </div>

                        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                            <dt className="text-xs uppercase tracking-wider text-slate-500">
                                HTTP status
                            </dt>
                            <dd className="mt-2 text-lg font-semibold text-slate-100">
                                {formatHttpStatus(health.http_status)}
                            </dd>
                        </div>
                    </dl>

                    <section>
                        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                            Operations
                        </h3>

                        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900 p-4">
                            <button
                                type="button"
                                onClick={onRefresh}
                                disabled={isRefreshing}
                                className="w-full rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm font-semibold text-cyan-200 transition hover:border-cyan-400/50 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {isRefreshing
                                    ? "Refreshing health..."
                                    : "Refresh health"}
                            </button>

                            <p className="mt-3 text-xs text-slate-500">
                                Request the latest health state from Atlas Core.
                            </p>
                        </div>
                    </section>

                    <section>
                        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                            Message
                        </h3>
                        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900 p-4">
                            <p className="text-sm text-slate-300">
                                {health.message ?? "No service message."}
                            </p>
                        </div>
                    </section>

                    <section>
                        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                            Details
                        </h3>
                        <pre className="mt-3 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs leading-6 text-slate-300">
                            {hasDetails
                                ? JSON.stringify(health.details, null, 2)
                                : "No additional details returned."}
                        </pre>
                    </section>

                    <p className="text-xs text-slate-500">
                        Press Escape or click outside the drawer to close.
                    </p>
                </div>
            </aside>
        </div>
    );
}
