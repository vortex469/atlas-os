import { useState } from "react";

import { AnalysisPanel } from "./AnalysisPanel";
import { ComposeEditor } from "./ComposeEditor";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { PlanPanel } from "./PlanPanel";

export function Forge() {
    const [result, setResult] = useState<unknown>(null);

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
                <AnalysisPanel />
                <DiagnosticsPanel />
            </div>

            <PlanPanel />

            {result !== null && (
                <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                    <h2 className="text-lg font-semibold text-slate-100">
                        Raw Result
                    </h2>

                    <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs text-slate-300">
                        {JSON.stringify(result, null, 2)}
                    </pre>
                </section>
            )}
        </main>
    );
}