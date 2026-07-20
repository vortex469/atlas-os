import type { DeploymentAnalysisResponse } from "./types";

type PlanPanelProps = {
    result: DeploymentAnalysisResponse | null;
};

export function PlanPanel({
    result,
}: PlanPanelProps) {
    if (!result) {
        return (
            <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                <h2 className="text-lg font-semibold text-slate-100">
                    Proposed Plan
                </h2>

                <p className="mt-3 text-sm text-slate-500">
                    The proposed deployment steps will appear here.
                </p>
            </section>
        );
    }

    const proposal = result.result.planning.proposal;

    return (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold text-slate-100">
                        Proposed Plan
                    </h2>

                    <p className="mt-1 text-sm text-slate-500">
                        {proposal.summary}
                    </p>
                </div>

                <div className="text-right text-sm">
                    <p className="font-medium text-slate-200">
                        {proposal.estimated_duration_minutes ?? 0} minutes
                    </p>

                    <p className="mt-1 text-slate-500">
                        Approval{" "}
                        {proposal.approval_required
                            ? "required"
                            : "not required"}
                    </p>
                </div>
            </div>

            <ol className="mt-6 space-y-3">
                {proposal.steps.map((step) => (
                    <li
                        key={step.id}
                        className="flex gap-4 rounded-lg border border-slate-800 bg-slate-950/60 p-4"
                    >
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-500/10 text-sm font-semibold text-blue-300">
                            {step.order}
                        </span>

                        <div>
                            <p className="font-medium text-slate-100">
                                {step.title}
                            </p>

                            <p className="mt-1 text-sm text-slate-500">
                                {step.description}
                            </p>
                        </div>
                    </li>
                ))}
            </ol>
        </section>
    );
}