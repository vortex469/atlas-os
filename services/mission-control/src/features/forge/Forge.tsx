import { useState } from "react";

import { AnalysisPanel } from "./AnalysisPanel";
import { ComposeEditor } from "./ComposeEditor";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { PlanPanel } from "./PlanPanel";
import type { DeploymentAnalysisResponse } from "./types";
import { DeploymentBrief } from "./DeploymentBrief";
import { safeText } from "../../utils/safeText";

function redactResponseText(value: unknown): unknown {
    if (typeof value === "string") return safeText(value);
    if (Array.isArray(value)) return value.map(redactResponseText);
    if (value !== null && typeof value === "object") {
        return Object.fromEntries(Object.entries(value).map(([key, nested]) => [key, redactResponseText(nested)]));
    }
    return value;
}

export function Forge() {
    const [result, setResult] =
        useState<DeploymentAnalysisResponse | null>(null);

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <header>
                <h1 className="text-3xl font-bold text-slate-100">
                    Deployment analysis
                </h1>

                <p className="mt-2 text-slate-400">
                    Review a Docker Compose file, findings, and suggested
                    steps. This page does not deploy anything.
                </p>
            </header>

            <ComposeEditor onAnalysis={setResult} />

            {result && (
                <div className="space-y-6">
                    <DeploymentBrief analysis={result} />

                    <div className="grid gap-6 lg:grid-cols-2">
                        <AnalysisPanel result={result} />
                        <DiagnosticsPanel result={result} />
                    </div>

                    <PlanPanel result={result} />
                </div>
            )}

            {result && (
                <details className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                    <summary className="cursor-pointer text-sm font-semibold text-slate-300">
                        Technical details
                    </summary>

                    <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs text-slate-400">
                        {JSON.stringify(redactResponseText(result), null, 2)}
                    </pre>
                </details>
            )}
        </main>
    );
}
