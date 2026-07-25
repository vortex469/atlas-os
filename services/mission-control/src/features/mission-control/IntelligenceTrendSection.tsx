import { SectionHeader } from "../../components/SectionHeader";
import type { IntelligenceTelemetrySnapshot } from "../../types/ace";

type IntelligenceTrendSectionProps = {
    snapshots: IntelligenceTelemetrySnapshot[];
};

export function IntelligenceTrendSection({
    snapshots,
}: IntelligenceTrendSectionProps) {
    if (snapshots.length === 0) {
        return null;
    }

    const chronological = [...snapshots].reverse();
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
