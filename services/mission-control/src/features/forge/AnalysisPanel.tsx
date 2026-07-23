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

            <dl className="mt-5 grid grid-cols-2 gap-6 text-sm">
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
                        className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 space-y-4"
                    >
                        <div>
                            <h3 className="text-lg font-semibold text-slate-100">
                                🧩 {component.name}
                            </h3>

                            <p className="mt-1 text-sm capitalize text-slate-500">
                                Compose {component.kind}
                            </p>
                        </div>

                        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                            <div>
                                <dt className="text-slate-500">
                                    Risk
                                </dt>

                                <dd className="mt-2">
                                    <span
                                        className={[
                                            "inline-flex items-center rounded-full px-3 py-1",
                                            "text-xs font-semibold uppercase",
                                            plan.risk === "low"
                                                ? "bg-emerald-950/60 text-emerald-300"
                                                : plan.risk === "medium"
                                                ? "bg-yellow-950/60 text-yellow-300"
                                                : plan.risk === "high"
                                                    ? "bg-orange-950/60 text-orange-300"
                                                    : "bg-red-950/60 text-red-300",
                                        ].join(" ")}
                                    >
                                        {plan.risk}
                                    </span>
                                </dd>
                            </div>

                            <div>
                                <dt className="text-slate-500">Type</dt>
                                <dd className="mt-1 font-medium capitalize text-slate-200">
                                    {component.kind}
                                </dd>
                            </div>
                        </dl>

                        <div>
                            <p className="mb-2 text-sm font-medium text-slate-300">
                                Published Ports
                            </p>

                            {component.ports.length === 0 ? (
                                <p className="text-sm text-slate-500">
                                    No published ports
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {component.ports.map((port, index) => (
                                        <div
                                            key={index}
                                            className="flex items-center justify-between rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm"
                                        >
                                            <span className="font-mono text-slate-200">
                                                {port.host_port ?? "-"} → {port.container_port}
                                            </span>

                                            <span className="text-slate-400">
                                                {port.protocol.toUpperCase()}
                                            </span>

                                            <span
                                                className={
                                                    port.public
                                                        ? "text-emerald-400"
                                                        : "text-slate-500"
                                                }
                                            >
                                                {port.public ? "Public" : "Internal"}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}