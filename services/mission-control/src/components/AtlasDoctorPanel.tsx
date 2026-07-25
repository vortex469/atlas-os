import { useState } from "react";

import {
    getAtlasDoctorReport,
    getAtlasErrorMessage,
} from "../api/atlas";
import type { DoctorReport } from "../types/doctor";

const statusClasses = {
    healthy:
        "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    degraded:
        "border-amber-500/30 bg-amber-500/10 text-amber-300",
    critical:
        "border-red-500/30 bg-red-500/10 text-red-300",
};

export function AtlasDoctorPanel() {
    const [report, setReport] = useState<DoctorReport | null>(
        null,
    );
    const [isRunning, setIsRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function runDoctor() {
        setIsRunning(true);
        setError(null);

        try {
            setReport(await getAtlasDoctorReport());
        } catch (requestError) {
            setError(
                getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not run Atlas Doctor.",
                ),
            );
        } finally {
            setIsRunning(false);
        }
    }

    const issues = report
        ? [
              ...report.critical.map((message) => ({
                  level: "Critical",
                  message,
              })),
              ...report.warnings.map((message) => ({
                  level: "Warning",
                  message,
              })),
          ]
        : [];

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                    <h2 className="font-semibold text-slate-100">
                        Atlas Doctor
                    </h2>
                    <p className="mt-1 text-sm text-slate-400">
                        Validate configuration, infrastructure
                        connectivity, and service health.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={() => void runDoctor()}
                    disabled={isRunning}
                    className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {isRunning ? "Running Doctor..." : "Run Doctor"}
                </button>
            </div>

            {error && (
                <p role="alert" className="mt-4 text-sm text-red-300">
                    {error}
                </p>
            )}

            {report && (
                <div className="mt-5 space-y-4 border-t border-slate-800 pt-5">
                    <div className="flex flex-wrap items-center gap-3">
                        <span
                            className={`rounded-full border px-2.5 py-1 text-xs font-medium uppercase ${statusClasses[report.status]}`}
                        >
                            {report.status}
                        </span>
                        <strong className="text-lg text-slate-100">
                            {report.score}/100
                        </strong>
                        <span className="text-xs text-slate-500">
                            {report.checks.filter(
                                (check) => check.passed,
                            ).length}
                            /{report.checks.length} checks passed
                        </span>
                    </div>

                    {issues.length > 0 ? (
                        <ul className="space-y-2">
                            {issues.map((issue, index) => (
                                <li
                                    key={`${issue.level}-${index}`}
                                    className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm text-slate-300"
                                >
                                    <span className="mr-2 font-semibold text-slate-400">
                                        {issue.level}:
                                    </span>
                                    {issue.message}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-sm text-emerald-300">
                            No critical issues or warnings detected.
                        </p>
                    )}
                </div>
            )}
        </section>
    );
}
