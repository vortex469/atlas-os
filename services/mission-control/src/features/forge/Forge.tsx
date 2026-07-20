import { useState } from "react";

import { AnalysisPanel } from "./AnalysisPanel";
import { ComposeEditor } from "./ComposeEditor";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { PlanPanel } from "./PlanPanel";
import type { DeploymentAnalysisResponse } from "./types";

export function Forge() {
    const [result, setResult] =
        useState<DeploymentAnalysisResponse | null>(null);

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <header>
                <h1 className="text-3xl font-bold text-slate-100">
                    Atlas Forge
                </h1>

                <p className="mt-2 text-slate-400">
                    Analyze, understand, and prepare deployments before
                    execution.
                </p>
            </header>

            <ComposeEditor onAnalysis={setResult} />

            <div className="grid gap-6 lg:grid-cols-2">
                <AnalysisPanel result={result} />
                <DiagnosticsPanel result={result} />
            </div>

            <PlanPanel result={result} />

            {result && (
                <details className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                    <summary className="cursor-pointer text-sm font-semibold text-slate-300">
                        Developer Output
                    </summary>

                    <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs text-slate-400">
                        {JSON.stringify(result, null, 2)}
                    </pre>
                </details>
            )}
        </main>
    );
}