import { useState } from "react";

import { analyzeCompose } from "../../api/atlas";
import type { DeploymentAnalysisResponse } from "./types";

const defaultCompose = `services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
`;

type ComposeEditorProps = {
    onAnalysis: (
        result: DeploymentAnalysisResponse,
    ) => void;
};

export function ComposeEditor({
    onAnalysis,
}: ComposeEditorProps) {
    const [compose, setCompose] = useState(defaultCompose);
    const [reference, setReference] = useState("nginx-demo");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleAnalyze() {
        setError(null);

        const normalizedReference = reference.trim();

        if (!normalizedReference) {
            setError("Deployment name is required.");
            return;
        }

        setLoading(true);

        try {
            const result = await analyzeCompose(
                compose,
                normalizedReference,
            );

            onAnalysis(result);
        } catch (caughtError) {
            const message =
                caughtError instanceof Error
                    ? caughtError.message
                    : "Deployment analysis failed.";

            setError(message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <div className="mb-4">
                <h2 className="text-lg font-semibold text-slate-100">
                    Compose Deployment
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                    Paste or edit a Docker Compose document for Atlas to
                    analyze.
                </p>
            </div>

            <label className="mb-4 block">
                <span className="text-sm font-medium text-slate-300">
                    Deployment name
                </span>

                <input
                    type="text"
                    value={reference}
                    onChange={(event) =>
                        setReference(event.target.value)
                    }
                    placeholder="nginx-demo"
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none transition focus:border-blue-500"
                />
            </label>

            <textarea
                value={compose}
                onChange={(event) =>
                    setCompose(event.target.value)
                }
                spellCheck={false}
                className="min-h-80 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-200 outline-none transition focus:border-blue-500"
            />

            {error && (
                <p className="mt-3 text-sm text-red-300">
                    {error}
                </p>
            )}

            <div className="mt-4 flex justify-end">
                <button
                    type="button"
                    onClick={() => void handleAnalyze()}
                    disabled={loading}
                    className="rounded-lg bg-blue-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading
                        ? "Analyzing..."
                        : "Analyze Deployment"}
                </button>
            </div>
        </section>
    );
}