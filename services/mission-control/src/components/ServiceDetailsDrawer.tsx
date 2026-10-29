import { useEffect, useRef } from "react";
import type { ServiceHealth } from "../types/health";
import type { Provider } from "../types/provider";
import { healthNextCheck, healthState } from "../utils/healthPresentation";
import { ProviderActions } from "./ProviderActions";
import { HealthEvidence } from "./HealthEvidence";

type ServiceDetailsDrawerProps = {
    name: string;
    health: ServiceHealth;
    provider: Pick<Provider, "id" | "name"> | null;
    isRefreshing: boolean;
    onRefresh: () => void;
    onClose: () => void;
};

function formatLatency(latency: number | null): string {
    if (latency === null) {
        return "Not recorded";
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
    provider,
    isRefreshing,
    onRefresh,
    onClose,
}: ServiceDetailsDrawerProps) {
    const dialogRef = useRef<HTMLElement>(null);
    const closeButtonRef = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        closeButtonRef.current?.focus();

        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Tab") {
                const controls = dialogRef.current?.querySelectorAll<HTMLElement>(
                    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
                );
                const focusableControls = Array.from(controls ?? []).filter(
                    (control) => control.tabIndex >= 0 && !control.matches(":disabled"),
                );
                const first = focusableControls[0];
                const last = focusableControls[focusableControls.length - 1];
                const focusIsOutsideDialog = !dialogRef.current?.contains(document.activeElement);

                if (event.shiftKey && (document.activeElement === first || focusIsOutsideDialog)) {
                    event.preventDefault();
                    last?.focus();
                } else if (!event.shiftKey && (document.activeElement === last || focusIsOutsideDialog)) {
                    event.preventDefault();
                    first?.focus();
                }
            }
            if (event.key === "Escape") {
                event.preventDefault();
                onClose();
            }
        }

        window.addEventListener("keydown", handleKeyDown);

        return () => {
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [onClose]);

    useEffect(() => {
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = previousOverflow;
        };
    }, []);

    const healthCheckAddress = formatHealthCheckAddress(health.details.url);
    const technicalDetails = Object.fromEntries(
        Object.entries(health.details).filter(([key]) => key !== "url"),
    );
    const hasTechnicalDetails = Object.keys(technicalDetails).length > 0;
    const nextCheck = healthNextCheck(health.message);
    const currentHealthState = healthState(health.status);
    const healthReason = ["Unavailable", "Degraded", "Blocked"].includes(currentHealthState)
        ? health.message
        : undefined;

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
                ref={dialogRef}
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
                        ref={closeButtonRef}
                        type="button"
                        onClick={onClose}
                        className="mc-focusable rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white"
                    >
                        Close
                    </button>
                </div>

                <div className="space-y-6 p-6">
                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                        <div className="flex items-center justify-between gap-4">
                            <span className="text-sm font-medium text-slate-400">
                                Reachability from Atlas Core
                            </span>
                            <HealthEvidence
                                status={health.status}
                                reason={healthReason}
                                unavailableLabel="Unreachable from Atlas Core"
                                compact
                            />
                        </div>
                    </div>

                    <dl className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                            <dt className="text-xs uppercase tracking-wider text-slate-500">
                                Response time
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
                            Health check
                        </h3>
                        <dl className="mt-3 rounded-lg border border-slate-800 bg-slate-900 p-4">
                            <dt className="text-xs uppercase tracking-wider text-slate-500">
                                Address Atlas checked
                            </dt>
                            <dd className="mt-2 break-all font-mono text-sm text-slate-200">
                                {healthCheckAddress ?? "Not reported"}
                            </dd>
                        </dl>
                        <p className="mt-2 text-sm text-slate-400">
                            Run the test on the computer where Atlas Core runs. If Core runs in Docker Compose, run it inside the <code>atlas-core</code> container. Your browser or the service computer may use a different network path.
                        </p>
                        <details className="mt-2">
                            <summary className="mc-focusable cursor-pointer text-sm text-cyan-300">If Compose says the file is missing</summary>
                            <p className="mt-2 text-sm text-slate-400">Run the command from the directory that contains Atlas&apos;s Compose file, or pass its full path with <code>--file</code>.</p>
                        </details>
                        {nextCheck && (
                            <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                                <h4 className="text-sm font-semibold text-amber-200">
                                    What to check next
                                </h4>
                                <p className="mt-1 text-sm text-amber-100/80">
                                    {nextCheck}
                                </p>
                            </div>
                        )}
                    </section>

                    {provider ? (
                        <ProviderActions
                            provider={provider}
                            compact
                            onActionCompleted={onRefresh}
                        />
                    ) : (
                        <section>
                            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                                Operations
                            </h3>
                            <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
                                No provider operations are available for this service.
                            </div>
                        </section>
                    )}

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
                        <details>
                            <summary className="cursor-pointer text-sm font-semibold text-slate-400">
                                Technical details
                            </summary>
                            <pre className="mt-3 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs leading-6 text-slate-300">
                                {hasTechnicalDetails
                                    ? JSON.stringify(technicalDetails, null, 2)
                                    : "No additional details returned."}
                            </pre>
                        </details>
                    </section>

                    <p className="text-xs text-slate-500">
                        Press Escape or click outside the drawer to close.
                    </p>
                </div>
            </aside>
        </div>
    );
}

function formatHealthCheckAddress(value: unknown): string | null {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
        const url = new URL(value);
        return `${url.protocol}//${url.host}${url.pathname}${url.search ? "?…" : ""}`;
    } catch {
        return null;
    }
}
