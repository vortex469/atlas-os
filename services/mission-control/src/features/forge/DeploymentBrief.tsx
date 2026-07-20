import type { DeploymentAnalysisResponse } from "./types";

type DeploymentBriefProps = {
    analysis: DeploymentAnalysisResponse;
};

export function DeploymentBrief({
    analysis,
}: DeploymentBriefProps) {
    const plan = analysis.result.analysis.plan;
    const proposal = analysis.result.planning.proposal;

    let status = "";
    let recommendation = "";
    let statusColor = "";

    switch (plan.risk) {
        case "low":
            status = "Ready for Review";
            recommendation =
                "Atlas recommends proceeding to review and approval.";
            statusColor = "text-emerald-400";
            break;

        case "medium":
            status = "Review Required";
            recommendation =
                "Atlas recommends reviewing diagnostics before approval.";
            statusColor = "text-yellow-400";
            break;

        case "high":
            status = "High Risk";
            recommendation =
                "Atlas recommends resolving identified risks before deployment.";
            statusColor = "text-orange-400";
            break;

        case "critical":
            status = "Deployment Blocked";
            recommendation =
                "Atlas recommends resolving critical issues before continuing.";
            statusColor = "text-red-400";
            break;
    }

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold text-slate-100">
                Deployment Brief
            </h2>

            <p className={`mt-4 text-xl font-bold ${statusColor}`}>
                {status}
            </p>

            <p className="mt-4 text-slate-300">
                Atlas analyzed{" "}
                <span className="font-semibold">
                    {plan.name}
                </span>.
            </p>

            <ul className="mt-4 space-y-2 text-sm text-slate-400">
                <li>
                    • {plan.components.length} application
                    component{plan.components.length === 1 ? "" : "s"} detected
                </li>

                <li>
                    • Overall risk:{" "}
                    <span className="font-semibold uppercase">
                        {plan.risk}
                    </span>
                </li>

                <li>
                    • Estimated deployment:{" "}
                    {proposal.estimated_duration_minutes ?? "Unknown"} minutes
                </li>
            </ul>

            <div className="mt-6 rounded-lg border border-slate-700 bg-slate-950 p-4">
                <p className="text-sm font-semibold text-slate-300">
                    Recommendation
                </p>

                <p className="mt-2 text-slate-400">
                    {recommendation}
                </p>
            </div>
        </section>
    );
}