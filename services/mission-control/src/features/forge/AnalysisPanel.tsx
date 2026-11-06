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
                    Services
                </h2>

                <p className="mt-3 text-sm text-slate-500">
                    Deployment analysis will appear here.
                </p>
            </section>
        );
    }

    const plan = result.result.analysis.plan;

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold text-slate-100">
                Services
            </h2>

            <dl className="mt-5 grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
                <div>
                    <dt className="text-slate-500">
                        Stack name
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100">
                        {plan.name}
                    </dd>
                </div>

                <div>
                    <dt className="text-slate-500">
                        Services found
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100">
                        {plan.components.length}
                    </dd>
                </div>
            </dl>

            <p className="mt-6 text-sm text-slate-500">
                Host ports are on the computer where Docker runs; service ports are inside the container. This review does not check whether a firewall, router, or internet connection allows other computers to reach the service.
            </p>

            <div className="mt-6 space-y-3">
                {plan.components.map((component) => (
                    <div
                        key={component.id}
                        className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 space-y-4"
                    >
                        <div>
                            <h3 className="text-lg font-semibold text-slate-100">
                                {component.name}
                            </h3>

                            <p className="mt-1 text-sm capitalize text-slate-400">
                                {component.kind}
                            </p>
                        </div>

                        <div>
                            <h4 className="mb-2 text-sm font-medium text-slate-300">
                                Network ports
                            </h4>
                            {component.ports.length === 0 ? (
                                <p className="text-sm text-slate-500">
                                    No network ports are listed for this service.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {component.ports.map((port, index) => (
                                        <div
                                            key={index}
                                            className="rounded border border-slate-800 bg-slate-900 px-3 py-3 text-sm"
                                        >
                                            <p className="font-medium text-slate-200">
                                                {port.host_port === null
                                                    ? "No fixed host port was specified in this file"
                                                    : `Host port ${port.host_port}`} → service port {port.container_port}/{port.protocol.toUpperCase()}
                                            </p>
                                            <p className="mt-1 text-slate-400">
                                                {port.public
                                                    ? "The binding may accept connections from other computers."
                                                    : "Access from other computers was not reported."}
                                            </p>
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
