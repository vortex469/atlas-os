import { SectionHeader } from "./SectionHeader";
import type {
    IntelligenceTelemetrySnapshot,
    ProviderCollectionTiming,
} from "../types/ace";
import type { PolicySeverity } from "../types/policies";

type PerformancePolicy = {
    maximum_collection_duration_ms: number;
    severity: PolicySeverity;
};

type Props = {
    providerId: string;
    snapshots: IntelligenceTelemetrySnapshot[];
    performancePolicy?: PerformancePolicy | null;
};

export function ProviderTelemetryTrend({
    providerId,
    snapshots,
    performancePolicy = null,
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
                <TrendChart
                    points={points}
                    performancePolicy={performancePolicy}
                />
            )}
        </section>
    );
}

type Point = {
    id: string;
    collectedAt: string;
    timing: ProviderCollectionTiming;
};

function TrendChart({
    points,
    performancePolicy,
}: {
    points: Point[];
    performancePolicy: PerformancePolicy | null;
}) {
    const maximumDuration = Math.max(
        ...points.map(({ timing }) => timing.duration_ms),
        1,
    );
    const scaleMaximum = Math.max(
        maximumDuration,
        performancePolicy?.maximum_collection_duration_ms ?? 0,
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
    const overThreshold =
        performancePolicy === null
            ? 0
            : points.filter(
                  ({ timing }) =>
                      timing.status === "completed" &&
                      timing.duration_ms >
                          performancePolicy.maximum_collection_duration_ms,
              ).length;

    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div className="grid gap-4 sm:grid-cols-4">
                <Metric label="Snapshots" value={String(points.length)} />
                <Metric label="Average" value={duration(average)} />
                <Metric
                    label={
                        performancePolicy
                            ? "Over threshold"
                            : "Issues"
                    }
                    value={String(
                        performancePolicy
                            ? overThreshold
                            : issues,
                    )}
                    warning={
                        performancePolicy
                            ? overThreshold > 0
                            : issues > 0
                    }
                />
                <Metric
                    label="Latest"
                    value={status(latest.timing.status)}
                    warning={latest.timing.status !== "completed"}
                />
            </div>
            <div className="relative mt-6">
                {performancePolicy && (
                    <div
                        aria-label={`Policy threshold ${duration(performancePolicy.maximum_collection_duration_ms)}`}
                        className={`absolute right-0 left-0 z-10 border-t border-dashed ${
                            performancePolicy.severity === "critical"
                                ? "border-red-400"
                                : performancePolicy.severity ===
                                    "warning"
                                  ? "border-amber-400"
                                  : "border-blue-400"
                        }`}
                        style={{
                            bottom: `${(performancePolicy.maximum_collection_duration_ms / scaleMaximum) * 100}%`,
                        }}
                    >
                        <span className="absolute right-0 -top-5 text-[10px] text-slate-400">
                            {duration(
                                performancePolicy.maximum_collection_duration_ms,
                            )}{" "}
                            policy
                        </span>
                    </div>
                )}
                <div
                    role="img"
                    aria-label={`${latest.timing.provider_name} intelligence duration trend`}
                    className="flex h-32 items-end gap-1 border-b border-l border-slate-700 px-2 pt-2"
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
                                            scaleMaximum) *
                                            100,
                                        3,
                                    )}%`,
                                }}
                            />
                        );
                    })}
                </div>
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
