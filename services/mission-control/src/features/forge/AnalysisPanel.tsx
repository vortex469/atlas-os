import type { DeploymentAnalysisResponse } from "./types";

type AnalysisPanelProps = {
    result: DeploymentAnalysisResponse | null;
};

export function AnalysisPanel({
    result,
}: AnalysisPanelProps) {
    if (!result) {
        return (
            <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                <h2 className="text-lg font-semibold text-slate-100">
                    Analysis
                </h2>

                <p className="mt-3 text-sm text-slate-500">
                    Deployment analysis will appear here.
                </p>
            </section>
        );
    }

    const analysis = result.result.analysis;
    const plan = analysis.plan;

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold text-slate-100">
                Analysis
            </h2>

            <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
                <div>
                    <dt className="text-slate-500">
                        Application
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100">
                        {plan.name}
                    </dd>
                </div>

                <div>
                    <dt className="text-slate-500">
                        Analyzer
                    </dt>
                    <dd className="mt-1 font-medium capitalize text-slate-100">
                        {analysis.analyzer}
                    </dd>
                </div>

                <div>
                    <dt className="text-slate-500">
                        Components
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100">
                        {plan.components.length}
                    </dd>
                </div>

                <div>
                    <dt className="text-slate-500">
                        Risk
                    </dt>
                    <dd className="mt-1 font-semibold uppercase text-emerald-300">
                        {plan.risk}
                    </dd>
                </div>
            </dl>

            <div className="mt-6 space-y-3">
                {plan.components.map((component) => (
                    <div
                        key={component.id}
                        className="rounded-lg border border-slate-800 bg-slate-950/60 p-4"
                    >
                        <p className="font-medium text-slate-100">
                            {component.name}
                        </p>

                        <p className="mt-1 text-sm text-slate-500">
                            {component.image ?? component.kind}
                        </p>
                    </div>
                ))}
            </div>
        </section>
    );
}