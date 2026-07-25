import { SectionHeader } from "./SectionHeader";
import type {
    IntelligenceTelemetrySnapshot,
    ProviderCollectionTiming,
} from "../types/ace";

type Props = {
    providerId: string;
    snapshots: IntelligenceTelemetrySnapshot[];
};

export function ProviderTelemetryTrend({
    providerId,
    snapshots,
}: Props) {
    const points = snapshots
        .flatMap((snapshot) => {
            const timing = snapshot.telemetry.providers.find(
                ({ provider_id }) => provider_id === providerId,
            );
            return timing
                ? [{
                      id: snapshot.id,
                      collectedAt: snapshot.collected_at,
                      timing,
                  }]
                : [];
        })
        .reverse();

    return (
        <section>
            <SectionHeader
                title="Intelligence History"
                description="Provider-specific ACE finding-collection duration and outcomes."
            />
            {points.length === 0 ? (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                    No intelligence collection history is available for
                    this provider yet.
                </div>
            ) : (
                <TrendChart points={points} />
            )}
        </section>
    );
}

type Point = {
    id: string;
    collectedAt: string;
    timing: ProviderCollectionTiming;
};

function TrendChart({ points }: { points: Point[] }) {
    const maximum = Math.max(
        ...points.map(({ timing }) => timing.duration_ms),
        1,
    );
    const average =
        points.reduce(
            (total, { timing }) => total + timing.duration_ms,
            0,
        ) / points.length;
    const issues = points.filter(
        ({ timing }) => timing.status !== "completed",
    ).length;
    const latest = points[points.length - 1];

    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div className="grid gap-4 sm:grid-cols-4">
                <Metric label="Snapshots" value={String(points.length)} />
                <Metric label="Average" value={duration(average)} />
                <Metric
                    label="Issues"
                    value={String(issues)}
                    warning={issues > 0}
                />
                <Metric
                    label="Latest"
                    value={status(latest.timing.status)}
                    warning={latest.timing.status !== "completed"}
                />
            </div>
            <div
                role="img"
                aria-label={`${latest.timing.provider_name} intelligence duration trend`}
                className="mt-6 flex h-32 items-end gap-1 border-b border-l border-slate-700 px-2 pt-2"
            >
                {points.map((point) => {
                    const unhealthy =
                        point.timing.status !== "completed";
                    return (
                        <div
                            key={point.id}
                            title={`${new Date(point.collectedAt).toLocaleString()} · ${duration(point.timing.duration_ms)} · ${status(point.timing.status)}`}
                            aria-label={`${duration(point.timing.duration_ms)}, ${status(point.timing.status)}`}
                            className={`min-w-1 flex-1 rounded-t ${
                                unhealthy
                                    ? "bg-amber-400/80"
                                    : "bg-emerald-400/70"
                            }`}
                            style={{
                                height: `${Math.max(
                                    (point.timing.duration_ms /
                                        maximum) *
                                        100,
                                    3,
                                )}%`,
                            }}
                        />
                    );
                })}
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
                className={`mt-1 text-base font-semibold ${
                    warning ? "text-amber-300" : "text-slate-100"
                }`}
            >
                {value}
            </p>
        </div>
    );
}

function duration(value: number): string {
    if (value < 1) return "<1 ms";
    if (value >= 1000) return `${(value / 1000).toFixed(2)} s`;
    return `${Math.round(value)} ms`;
}

function status(
    value: ProviderCollectionTiming["status"],
): string {
    if (value === "timed_out") return "Timed out";
    return value === "completed" ? "Completed" : "Failed";
}
