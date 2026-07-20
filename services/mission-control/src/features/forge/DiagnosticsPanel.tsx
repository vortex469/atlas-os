import type { DeploymentAnalysisResponse } from "./types";

type DiagnosticsPanelProps = {
    result: DeploymentAnalysisResponse | null;
};

export function DiagnosticsPanel({
    result,
}: DiagnosticsPanelProps) {
    const diagnostics =
        result?.result.analysis.diagnostics ?? [];

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold text-slate-100">
                Diagnostics
            </h2>

            {diagnostics.length === 0 ? (
                <p className="mt-3 text-sm text-emerald-300">
                    No issues detected.
                </p>
            ) : (
                <div className="mt-4 space-y-3">
                    {diagnostics.map((diagnostic) => (
                        <div
                            key={`${diagnostic.code}-${diagnostic.component_id ?? "global"}`}
                            className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4"
                        >
                            <p className="font-medium text-amber-200">
                                {diagnostic.code}
                            </p>

                            <p className="mt-1 text-sm text-amber-100/80">
                                {diagnostic.message}
                            </p>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}