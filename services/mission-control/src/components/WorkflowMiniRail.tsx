import type { WorkflowRailStage } from "../utils/workflowState";

interface WorkflowMiniRailProps {
    stages: WorkflowRailStage[];
    labelledBy?: string;
}

const STATUS_CLASSES: Record<WorkflowRailStage["status"], string> = {
    completed: "border-emerald-400/60 bg-emerald-500/10 text-emerald-100",
    current: "border-blue-400/70 bg-blue-500/15 text-blue-100",
    waiting: "border-slate-700 bg-slate-900 text-slate-400",
    blocked: "border-amber-400/60 bg-amber-500/10 text-amber-100",
    failed: "border-red-400/60 bg-red-500/10 text-red-100",
};

const STATUS_MARK: Record<WorkflowRailStage["status"], string> = {
    completed: "✔",
    current: "●",
    waiting: "○",
    blocked: "!",
    failed: "×",
};

export function WorkflowMiniRail({ stages, labelledBy }: WorkflowMiniRailProps) {
    return (
        <ol aria-labelledby={labelledBy} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {stages.map((stage) => (
                <li
                    key={stage.label}
                    className={`rounded-lg border px-3 py-2 text-sm ${STATUS_CLASSES[stage.status]}`}
                >
                    <span aria-hidden="true" className="mr-2 font-semibold">
                        {STATUS_MARK[stage.status]}
                    </span>
                    <span className="font-medium">{stage.label}</span>
                    <span className="sr-only">:</span>
                    <span className="ml-2 text-xs uppercase tracking-wide">
                        {stage.status}
                    </span>
                </li>
            ))}
        </ol>
    );
}
