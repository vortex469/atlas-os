import { useState } from "react";

import { exportIntelligenceTelemetryHistory } from "../../api/atlas";
import { SectionHeader } from "../../components/SectionHeader";
import type {
    IntelligenceTelemetryExportFormat,
    IntelligenceTelemetrySnapshot,
} from "../../types/ace";

type IntelligenceTrendSectionProps = {
    snapshots: IntelligenceTelemetrySnapshot[];
};

export function IntelligenceTrendSection({
    snapshots,
}: IntelligenceTrendSectionProps) {
    const [providerFilter, setProviderFilter] = useState("all");
    const [statusFilter, setStatusFilter] = useState("all");
    const [isExporting, setIsExporting] = useState(false);
    const [exportError, setExportError] = useState<string | null>(
        null,
    );

    async function exportHistory(
        format: IntelligenceTelemetryExportFormat,
    ) {
        setIsExporting(true);
        setExportError(null);

        try {
            const blob = await exportIntelligenceTelemetryHistory(
                format,
                {
                    providerId:
                        providerFilter === "all"
                            ? undefined
                            : providerFilter,
                    status:
                        statusFilter === "all"
                            ? undefined
                            : (statusFilter as
                                  | "completed"
                                  | "timed_out"
                                  | "failed"),
                },
            );
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = `atlas-intelligence-history.${format}`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
        } catch {
            setExportError(
                "Mission Control could not export telemetry history.",
            );
        } finally {
            setIsExporting(false);
        }
    }

    if (snapshots.length === 0) {
        return null;
    }

    const providerOptions = Array.from(
        new Map(
            snapshots.flatMap(({ telemetry }) =>
                telemetry.providers.map((provider) => [
                    provider.provider_id,
                    provider.provider_name,
                ]),
            ),
        ),
    ).sort((first, second) =>
        first[1].localeCompare(second[1]),
    );
    const filteredSnapshots = snapshots.filter(({ telemetry }) => {
        let providers = telemetry.providers;
        if (providerFilter !== "all") {
            providers = providers.filter(
                ({ provider_id }) =>
                    provider_id === providerFilter,
            );
            if (providers.length === 0) {
                return false;
            }
        }
        if (
            statusFilter !== "all" &&
            !providers.some(
                ({ status }) => status === statusFilter,
            )
        ) {
            return false;
        }
        return true;
    });
    const chronological = [...filteredSnapshots].reverse();
    if (chronological.length === 0) {
        return (
            <section>
                <SectionHeader
                    title="Intelligence Trend"
                    description="Persistent provider finding-collection history across recent ACE reports."
                />
                <TrendFilters
                    providers={providerOptions}
                    providerFilter={providerFilter}
                    statusFilter={statusFilter}
                    onProviderChange={setProviderFilter}
                    onStatusChange={setStatusFilter}
                    isExporting={isExporting}
                    onExport={(format) =>
                        void exportHistory(format)
                    }
                />
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                    No telemetry snapshots match the selected filters.
                </div>
            </section>
        );
    }
    const durations = chronological.map(
        ({ telemetry }) =>
            telemetry.provider_collection_duration_ms,
    );
    const maximumDuration = Math.max(...durations, 1);
    const averageDuration =
        durations.reduce((total, duration) => total + duration, 0) /
        durations.length;
    const unhealthySnapshots = chronological.filter(({ telemetry }) =>
        telemetry.providers.some(
            ({ status }) => status !== "completed",
        ),
    ).length;

    return (
        <section>
            <SectionHeader
                title="Intelligence Trend"
                description="Persistent provider finding-collection history across recent ACE reports."
            />

            <TrendFilters
                providers={providerOptions}
                providerFilter={providerFilter}
                statusFilter={statusFilter}
                onProviderChange={setProviderFilter}
                onStatusChange={setStatusFilter}
                isExporting={isExporting}
                onExport={(format) =>
                    void exportHistory(format)
                }
            />

            {exportError && (
                <p
                    role="alert"
                    className="mb-4 text-sm text-red-300"
                >
                    {exportError}
                </p>
            )}

            <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                <div className="grid gap-4 sm:grid-cols-3">
                    <Metric
                        label="Snapshots"
                        value={String(chronological.length)}
                    />
                    <Metric
                        label="Average"
                        value={formatDuration(averageDuration)}
                    />
                    <Metric
                        label="With issues"
                        value={String(unhealthySnapshots)}
                        warning={unhealthySnapshots > 0}
                    />
                </div>

                <div
                    role="img"
                    aria-label="Provider intelligence collection duration trend"
                    className="mt-6 flex h-36 items-end gap-1 border-b border-l border-slate-700 px-2 pt-2"
                >
                    {chronological.map((snapshot) => {
                        const duration =
                            snapshot.telemetry
                                .provider_collection_duration_ms;
                        const unhealthy =
                            snapshot.telemetry.providers.some(
                                ({ status }) =>
                                    status !== "completed",
                            );
                        const height = Math.max(
                            (duration / maximumDuration) * 100,
                            3,
                        );

                        return (
                            <div
                                key={snapshot.id}
                                title={`${new Date(snapshot.collected_at).toLocaleString()} · ${formatDuration(duration)}${unhealthy ? " · provider issue" : ""}`}
                                aria-label={`${formatDuration(duration)}${unhealthy ? ", provider issue" : ""}`}
                                className={`min-w-1 flex-1 rounded-t ${
                                    unhealthy
                                        ? "bg-amber-400/80"
                                        : "bg-blue-400/70"
                                }`}
                                style={{ height: `${height}%` }}
                            />
                        );
                    })}
                </div>

                <div className="mt-2 flex justify-between text-xs text-slate-500">
                    <span>
                        {new Date(
                            chronological[0].collected_at,
                        ).toLocaleTimeString()}
                    </span>
                    <span>
                        {new Date(
                            chronological[
                                chronological.length - 1
                            ].collected_at,
                        ).toLocaleTimeString()}
                    </span>
                </div>
            </div>
        </section>
    );
}

function TrendFilters({
    providers,
    providerFilter,
    statusFilter,
    onProviderChange,
    onStatusChange,
    isExporting,
    onExport,
}: {
    providers: [string, string][];
    providerFilter: string;
    statusFilter: string;
    onProviderChange: (value: string) => void;
    onStatusChange: (value: string) => void;
    isExporting: boolean;
    onExport: (
        format: IntelligenceTelemetryExportFormat,
    ) => void;
}) {
    return (
        <div className="mb-4 flex flex-wrap gap-3">
            <label className="text-xs font-medium text-slate-400">
                Provider
                <select
                    value={providerFilter}
                    onChange={(event) =>
                        onProviderChange(event.target.value)
                    }
                    className="ml-2 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200"
                >
                    <option value="all">All providers</option>
                    {providers.map(([id, name]) => (
                        <option key={id} value={id}>
                            {name}
                        </option>
                    ))}
                </select>
            </label>

            <label className="text-xs font-medium text-slate-400">
                Outcome
                <select
                    value={statusFilter}
                    onChange={(event) =>
                        onStatusChange(event.target.value)
                    }
                    className="ml-2 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200"
                >
                    <option value="all">All outcomes</option>
                    <option value="completed">Completed</option>
                    <option value="timed_out">Timed out</option>
                    <option value="failed">Failed</option>
                </select>
            </label>

            <div className="flex gap-2">
                <button
                    type="button"
                    disabled={isExporting}
                    onClick={() => onExport("json")}
                    className="rounded border border-slate-700 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:text-white disabled:opacity-50"
                >
                    Export JSON
                </button>
                <button
                    type="button"
                    disabled={isExporting}
                    onClick={() => onExport("csv")}
                    className="rounded border border-slate-700 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:text-white disabled:opacity-50"
                >
                    Export CSV
                </button>
            </div>
        </div>
    );
}

function Metric({
    label,
    value,
    warning = false,
}: {
    label: string;
    value: string;
    warning?: boolean;
}) {
    return (
        <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                {label}
            </p>
            <p
                className={`mt-1 text-lg font-semibold ${
                    warning ? "text-amber-300" : "text-slate-100"
                }`}
            >
                {value}
            </p>
        </div>
    );
}

function formatDuration(durationMs: number): string {
    if (durationMs < 1) {
        return "<1 ms";
    }
    if (durationMs >= 1000) {
        return `${(durationMs / 1000).toFixed(2)} s`;
    }
    return `${Math.round(durationMs)} ms`;
}
