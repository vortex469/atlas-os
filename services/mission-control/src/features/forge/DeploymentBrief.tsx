import type { DeploymentAnalysisResponse } from "./types";

type DeploymentBriefProps = {
    analysis: DeploymentAnalysisResponse;
};

export function DeploymentBrief({
    analysis,
}: DeploymentBriefProps) {
    const plan = analysis.result.analysis.plan;
    const proposal = analysis.result.planning.proposal;

    const risks = ["low", "medium", "high", "critical"];
    const knownRisks = risks.includes(plan.risk) && risks.includes(proposal.risk);
    const highestRisk = knownRisks ? risks[Math.max(risks.indexOf(plan.risk), risks.indexOf(proposal.risk))] : null;
    const status = highestRisk ? `Highest reported risk: ${highestRisk}` : "Risk unavailable";
    const statusColor = highestRisk === "critical" ? "text-red-400" : highestRisk === "high" ? "text-orange-400" : "text-slate-200";
    const recommendation = highestRisk === "critical" || highestRisk === "high"
        ? "Review the diagnostics and address the reported risks before using this plan."
        : "Review the analysis and proposed steps. Workflow permissions and exact approvals are checked separately.";

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
                    • Analysis risk:{" "}
                    <span className="font-semibold uppercase">
                        {plan.risk}
                    </span>
                </li>

                <li>• Proposed plan risk: <span className="font-semibold uppercase">{proposal.risk}</span></li>

                <li>
                    • Estimated deployment:{" "}
                    {proposal.estimated_duration_minutes === null ? "Not estimated" : `${proposal.estimated_duration_minutes} minutes`}
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