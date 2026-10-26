import { useEffect, useState } from "react";

import {
    getAtlasDoctorReport,
    getAtlasErrorMessage,
} from "../api/atlas";
import type { DoctorReport } from "../types/doctor";
import { evidenceTimestamp } from "../utils/healthPresentation";

const FRESH_REPORT_MS = 60_000;
interface DoctorSnapshot {
    report: DoctorReport;
    checkedAt: number | null;
    ageAtReceipt: number | null;
}

const statusClasses = {
    healthy:
        "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    degraded:
        "border-amber-500/30 bg-amber-500/10 text-amber-300",
    critical:
        "border-red-500/30 bg-red-500/10 text-red-300",
};

export function AtlasDoctorPanel() {
    const [snapshot, setSnapshot] = useState<DoctorSnapshot | null>(null);
    const [expiredSnapshot, setExpiredSnapshot] = useState<DoctorSnapshot | null>(null);
    const report = snapshot?.report ?? null;
    const unverifiedTime = snapshot?.ageAtReceipt === null;
    const stale = snapshot !== null && snapshot.ageAtReceipt !== null
        && (snapshot.ageAtReceipt > FRESH_REPORT_MS || expiredSnapshot === snapshot);

    useEffect(() => {
        if (!snapshot || snapshot.ageAtReceipt === null || snapshot.ageAtReceipt > FRESH_REPORT_MS) return;
        // One relative timer ages this snapshot without another diagnostic read.
        // Binding expiry to the snapshot keeps an old callback from aging a new report.
        const timer = window.setTimeout(() => setExpiredSnapshot(snapshot), FRESH_REPORT_MS + 1 - snapshot.ageAtReceipt);
        return () => window.clearTimeout(timer);
    }, [snapshot]);
    const [isRunning, setIsRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function runDoctor() {
        setIsRunning(true);
        setError(null);
        setSnapshot(null);
        setExpiredSnapshot(null);

        try {
            const next = await getAtlasDoctorReport();
            const checkedAt = evidenceTimestamp(next.checked_at);
            const receivedAt = Date.now();
            setSnapshot({ report: next, checkedAt,
                ageAtReceipt: checkedAt !== null && checkedAt <= receivedAt ? receivedAt - checkedAt : null });
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
        <section aria-label="Atlas Doctor" className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                    <h2 className="font-semibold text-slate-100">
                        Atlas Doctor
                    </h2>
                    <p className="mt-1 text-sm text-slate-400">
                        Check configuration, connections, and service health.
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

            {isRunning && <p role="status" className="mt-4 text-sm text-slate-300">Checking the latest health...</p>}

            {error && (
                <div className="mt-4 space-y-2">
                    <p role="alert" className="text-sm text-red-300">{error}</p>
                    <p className="text-sm text-slate-400">Current health is unknown until a report loads.</p>
                </div>
            )}

            {report && (
                <div className="mt-5 space-y-4 border-t border-slate-800 pt-5">
                    <div className="flex flex-wrap items-center gap-3">
                        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium uppercase ${
                            stale || unverifiedTime ? "border-slate-600 bg-slate-800 text-slate-200" : statusClasses[report.status]
                        }`}>
                            {unverifiedTime ? "Report time unverified" : stale ? "Needs refresh" : report.status}
                        </span>
                        <div>
                            <p className="text-xs text-slate-400">Reported score</p>
                            <strong className="text-lg text-slate-100">{report.score}/100</strong>
                        </div>
                        <p className="text-xs text-slate-400">
                            {report.checks.length > 0
                                ? `Results collected: ${report.checks.filter((check) => check.passed).length} of ${report.checks.length} checks`
                                : "No individual checks were reported."}
                        </p>
                    </div>
                    {(stale || unverifiedTime) && <p role="status" className="text-sm text-slate-300">
                        Last reported status: {report.status}. Current health is unknown.
                    </p>}
                    <p className="text-xs text-slate-400">
                        {snapshot?.checkedAt !== null && snapshot?.checkedAt !== undefined
                            ? <>Checked <time dateTime={report.checked_at}>{new Date(snapshot.checkedAt).toLocaleString()}</time></>
                            : "Report time is unavailable."}
                    </p>
                    {unverifiedTime && <p className="text-sm text-slate-400">Check this device's clock and run Doctor again.</p>}

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
                        <p className="text-sm text-slate-400">No findings were included in this report.</p>
                    )}
                    <details className="border-t border-slate-800 pt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300">Check details</summary>
                        <p className="mt-3 text-sm text-slate-300">Configuration: {report.configuration_ok ? "Validated" : "Needs attention"}</p>
                        <dl className="mt-3 space-y-3 text-sm">
                            {report.checks.map((check, index) => <div key={`${check.name}-${index}`}>
                                <dt className="font-medium text-slate-200">{check.name}</dt>
                                <dd className="mt-1 text-slate-400">{check.passed ? "Result received" : "Result unavailable"}</dd>
                                {check.error && <dd className="mt-1 text-slate-300">{check.error}</dd>}
                            </div>)}
                        </dl>
                        {report.information.length > 0 && <div className="mt-4 text-sm text-slate-400">
                            <p className="font-medium text-slate-200">Notes</p>
                            <ul className="mt-2 space-y-2">{report.information.map((message, index) => <li key={index}>{message}</li>)}</ul>
                        </div>}
                    </details>
                </div>
            )}
        </section>
    );
}
