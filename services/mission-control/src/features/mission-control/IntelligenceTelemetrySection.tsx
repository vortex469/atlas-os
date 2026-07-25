import { SectionHeader } from "../../components/SectionHeader";
import type {
    IntelligenceTelemetry,
    ProviderCollectionTiming,
} from "../../types/ace";

type IntelligenceTelemetrySectionProps = {
    telemetry: IntelligenceTelemetry;
};

const statusOrder: Record<ProviderCollectionTiming["status"], number> = {
    failed: 0,
    timed_out: 1,
    completed: 2,
};

const statusStyles: Record<
    ProviderCollectionTiming["status"],
    string
> = {
    completed:
        "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    timed_out:
        "border-amber-500/30 bg-amber-500/10 text-amber-300",
    failed: "border-red-500/30 bg-red-500/10 text-red-300",
};

function formatDuration(durationMs: number): string {
    if (durationMs < 1) {
        return "<1 ms";
    }

    if (durationMs >= 1000) {
        return `${(durationMs / 1000).toFixed(2)} s`;
    }

    return `${Math.round(durationMs)} ms`;
}

function formatStatus(
    status: ProviderCollectionTiming["status"],
): string {
    if (status === "timed_out") {
        return "Timed out";
    }

    return status === "completed" ? "Completed" : "Failed";
}

export function IntelligenceTelemetrySection({
    telemetry,
}: IntelligenceTelemetrySectionProps) {
    if (telemetry.providers.length === 0) {
        return null;
    }

    const providers = [...telemetry.providers].sort(
        (first, second) => {
            const statusDifference =
                statusOrder[first.status] -
                statusOrder[second.status];

            if (statusDifference !== 0) {
                return statusDifference;
            }

            const durationDifference =
                second.duration_ms - first.duration_ms;

            if (durationDifference !== 0) {
                return durationDifference;
            }

            return first.provider_name.localeCompare(
                second.provider_name,
            );
        },
    );
    const timeoutMs = telemetry.provider_timeout_seconds * 1000;
    const withinBudget =
        telemetry.provider_collection_duration_ms <= timeoutMs;

    return (
        <section>
            <SectionHeader
                title="Provider Intelligence"
                description="ACE finding-collection timing and outcome telemetry from the latest situation report."
            />

            <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
                <div className="grid gap-4 border-b border-slate-800 px-5 py-4 sm:grid-cols-3">
                    <div>
                        <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                            Collection time
                        </p>
                        <p className="mt-1 text-lg font-semibold text-slate-100">
                            {formatDuration(
                                telemetry.provider_collection_duration_ms,
                            )}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                            Provider budget
                        </p>
                        <p className="mt-1 text-lg font-semibold text-slate-100">
                            {formatDuration(timeoutMs)}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs uppercase tracking-[0.12em] text-slate-500">
                            Budget status
                        </p>
                        <p
                            className={`mt-1 text-sm font-semibold ${
                                withinBudget
                                    ? "text-emerald-300"
                                    : "text-amber-300"
                            }`}
                        >
                            {withinBudget
                                ? "Within budget"
                                : "Budget exceeded"}
                        </p>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left text-sm">
                        <thead className="border-b border-slate-800 bg-slate-950/40 text-xs uppercase tracking-[0.12em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-medium">
                                    Provider
                                </th>
                                <th className="px-5 py-3 font-medium">
                                    Outcome
                                </th>
                                <th className="px-5 py-3 text-right font-medium">
                                    Duration
                                </th>
                                <th className="px-5 py-3 text-right font-medium">
                                    Findings
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {providers.map((provider) => (
                                <tr key={provider.provider_id}>
                                    <td className="px-5 py-4">
                                        <p className="font-medium text-slate-200">
                                            {provider.provider_name}
                                        </p>
                                        <p className="mt-0.5 text-xs text-slate-500">
                                            {provider.provider_id}
                                        </p>
                                    </td>
                                    <td className="px-5 py-4">
                                        <span
                                            className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusStyles[provider.status]}`}
                                        >
                                            {formatStatus(
                                                provider.status,
                                            )}
                                        </span>
                                    </td>
                                    <td className="px-5 py-4 text-right font-mono text-slate-300">
                                        {formatDuration(
                                            provider.duration_ms,
                                        )}
                                    </td>
                                    <td className="px-5 py-4 text-right font-mono text-slate-300">
                                        {provider.finding_count}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    );
}
