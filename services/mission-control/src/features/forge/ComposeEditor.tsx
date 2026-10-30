import { useEffect, useRef, useState } from "react";

import { analyzeCompose, getAtlasErrorMessage } from "../../api/atlas";
import type { DeploymentAnalysisResponse } from "./types";

const defaultCompose = `services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
`;

type ComposeEditorProps = {
    onAnalysis: (
        result: DeploymentAnalysisResponse | null,
    ) => void;
};

export function ComposeEditor({
    onAnalysis,
}: ComposeEditorProps) {
    const [compose, setCompose] = useState(defaultCompose);
    const [reference, setReference] = useState("nginx-demo");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [errorDetails, setErrorDetails] = useState<string | null>(null);

    const requestGeneration = useRef(0);
    useEffect(() => () => { requestGeneration.current += 1; }, []);

    function inputChanged() {
        requestGeneration.current += 1;
        setLoading(false);
        setError(null);
        setErrorDetails(null);
        onAnalysis(null);
    }

    async function handleAnalyze() {
        if (loading) return;
        const generation = ++requestGeneration.current;
        setError(null);
        setErrorDetails(null);
        onAnalysis(null);

        const normalizedReference = reference.trim();

        if (!normalizedReference) {
            setError("Deployment name is required.");
            return;
        }

        if (!compose.trim()) {
            setError("Add a Docker Compose file to analyze.");
            return;
        }

        setLoading(true);

        try {
            const result = await analyzeCompose(
                compose,
                normalizedReference,
            );

            if (generation === requestGeneration.current) onAnalysis(result);
        } catch (caughtError) {
            if (generation !== requestGeneration.current) return;
            const message = getAtlasErrorMessage(
                caughtError,
                "Mission Control couldn't complete the analysis. Check the Compose file and Atlas connection, then try again.",
            );
            const details = caughtError instanceof Error ? caughtError.message : null;
            setError(message);
            setErrorDetails(details && details !== message ? details : null);
        } finally {
            if (generation === requestGeneration.current) setLoading(false);
        }
    }

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <div className="mb-4">
                <h2 className="text-lg font-semibold text-slate-100">
                    Docker Compose file
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                    Paste or edit a Docker Compose file for review.
                </p>
            </div>

            <label className="mb-4 block">
                <span className="text-sm font-medium text-slate-300">
                    Deployment name
                </span>

                <input
                    type="text"
                    value={reference}
                    onChange={(event) => {
                        inputChanged();
                        setReference(event.target.value);
                    }}
                    placeholder="nginx-demo"
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none transition focus:border-blue-500"
                />
            </label>

            <label htmlFor="forge-compose" className="mb-2 block text-sm font-medium text-slate-300">Docker Compose file</label>
            <textarea id="forge-compose"
                value={compose}
                onChange={(event) => {
                    inputChanged();
                    setCompose(event.target.value);
                }}
                spellCheck={false}
                className="min-h-80 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-200 outline-none transition focus:border-blue-500"
            />

            {error && (
                <div role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                    <p>{error}</p>
                    {errorDetails && <details className="mt-2">
                        <summary className="mc-focusable cursor-pointer text-xs font-medium text-red-100">Technical details</summary>
                        <p className="mt-1 break-words text-xs text-red-100/80">{errorDetails}</p>
                    </details>}
                </div>
            )}

            {loading && <p role="status" className="mt-3 text-sm text-blue-200">Analyzing the current document…</p>}

            <div className="mt-4 flex justify-end">
                <button
                    type="button"
                    onClick={() => void handleAnalyze()}
                    disabled={loading}
                    className="rounded-lg bg-blue-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading
                        ? "Analyzing..."
                        : "Analyze Compose file"}
                </button>
            </div>
        </section>
    );
}
