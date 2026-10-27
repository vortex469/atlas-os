import type { WorkflowDetailResponse, WorkflowTimelineStage } from "../types/atlasAgent";

interface ExecutionTimelineProps {
    workflow: WorkflowDetailResponse;
    isRefreshing: boolean;
    refreshDisabled?: boolean;
    onRefresh: () => void;
    compact?: boolean;
}

export function ExecutionTimeline({ workflow, isRefreshing, refreshDisabled = false, onRefresh, compact = false }: ExecutionTimelineProps) {
    const executionState = executionStateText(workflow);
    const stages = (
            <ol className="mt-5 grid gap-2 text-sm md:grid-cols-3 xl:grid-cols-9" aria-label="Authoritative execution stages">
                {workflow.timeline.map((stage) => (
                    <TimelineStage key={stage.name} stage={stage} />
                ))}
            </ol>
    );

    return (
        <section aria-labelledby="execution-timeline-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 id="execution-timeline-heading" className="text-lg font-semibold text-white">Execution timeline</h2>
                    <p aria-live="polite" role="status" className="mt-1 text-sm text-slate-300">{executionState}</p>
                </div>
                <button type="button" onClick={onRefresh} disabled={isRefreshing || refreshDisabled} className="rounded-lg border border-blue-400 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60">
                    {isRefreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            {compact ? <details className="mt-4 rounded-lg border border-slate-800 p-3">
                <summary className="cursor-pointer text-sm text-slate-300">Execution stages</summary>
                {stages}
            </details> : stages}

            {workflow.effect_kind === "operational_action"
                ? <p className="mt-5 text-sm text-slate-300">Dispatch and verification results are shown in the operational lifecycle.</p>
                : <ExecutionSection workflow={workflow} compact={compact} />}
        </section>
    );
}

function TimelineStage({ stage }: { stage: WorkflowTimelineStage }) {
    return (
        <li className={["rounded-lg border px-3 py-2", stageClass(stage.status)].join(" ")}>
            <span className="block font-medium">{stage.name}</span>
            <span className="text-xs">{formatLabel(stage.status)}</span>
        </li>
    );
}

function ExecutionSection({ workflow, compact }: { workflow: WorkflowDetailResponse; compact: boolean }) {
    const execution = workflow.execution;
    const hasResult = execution.execution_status !== null;
    const outcome = repositoryExecutionState(workflow);
    const facts = hasResult ? (
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Execution status" value={formatLabel(execution.execution_status ?? "not_available")} />
                    <Detail label="Started time" value={execution.started_at ?? "Not exposed by Atlas Agent"} />
                    <Detail label="Completed time" value={execution.completed_at ?? "Not exposed by Atlas Agent"} />
                    <Detail label="Execution result" value={formatLabel(execution.result ?? "not_available")} />
                    <Detail label="Changed files count" value={String(execution.changed_files_count)} />
                    <Detail label="Tool" value={execution.tool ?? "Not exposed"} />
                    <Detail label="Working directory" value={execution.working_directory ?? "Not exposed"} />
                    <Detail label="Repository" value={execution.repository ?? "Not exposed"} />
                    <Detail label="Changed files" value={execution.changed_files.length > 0 ? execution.changed_files.join(", ") : "None reported"} />
                    <Detail label="Execution request ID" value={execution.execution_request_id ?? "Not exposed"} />
                </dl>
    ) : null;

    return (
        <section aria-labelledby="execution-section-heading" className="mt-5 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h3 id="execution-section-heading" className="text-base font-semibold text-white">Execution</h3>
            <p role="status" className={`mt-2 text-sm ${outcome.className}`}>{outcome.text}</p>
            {facts && (compact ? <details className="mt-4 rounded-lg border border-slate-800 p-3">
                <summary className="cursor-pointer text-sm text-slate-300">Execution details</summary>
                {facts}
            </details> : facts)}
        </section>
    );
}

function executionStateText(workflow: WorkflowDetailResponse): string {
    if (workflow.effect_kind === "operational_action") {
        if (workflow.workflow_state === "completed") return "Maintenance workflow completed. Review the recorded operational outcome.";
        if (workflow.workflow_state === "blocked") return "Maintenance workflow is blocked. Review the operational lifecycle.";
        if (workflow.implementation_approval_status === "rejected") return "Exact action approval was rejected.";
        if (workflow.workflow_state === "awaiting_implementation_approval" && workflow.implementation_approval_status !== "approved") return "Waiting for exact action approval.";
        return "Check the operational lifecycle for dispatch and verification results.";
    }
    return repositoryExecutionState(workflow).text;
}

function repositoryExecutionState(workflow: WorkflowDetailResponse): { text: string; className: string } {
    switch (workflow.execution.execution_status) {
        case "succeeded": return { text: "Execution complete.", className: "text-emerald-200" };
        case "failed": return { text: "Execution failed.", className: "text-red-200" };
        case "timed_out": return { text: "Execution timed out.", className: "text-red-200" };
        case "launch_failed": return { text: "Execution could not start.", className: "text-red-200" };
        case "unknown": return { text: "Worker outcome unknown. Check the original result; do not resubmit.", className: "text-amber-200" };
        case null: break;
        default: return { text: "Execution status is not recognized. Refresh to check its status.", className: "text-amber-200" };
    }
    if (workflow.workflow_state === "executing") return { text: "Execution running...", className: "text-blue-200" };
    if (workflow.implementation_approval_status === "rejected") return { text: "Implementation approval was rejected.", className: "text-amber-200" };
    if (workflow.workflow_state === "blocked") return { text: "Workflow is blocked. No execution result is reported.", className: "text-amber-200" };
    if (workflow.workflow_state === "awaiting_approval") return { text: "Prepare the exact request before implementation approval.", className: "text-slate-300" };
    if (workflow.workflow_state === "awaiting_implementation_approval") {
        if (workflow.implementation_approval_status === "approved") return { text: "Implementation approved. Waiting for a separate resume.", className: "text-slate-300" };
        if (workflow.implementation_approval_status === "pending") return { text: "Waiting for implementation approval.", className: "text-slate-300" };
    }
    return { text: "No execution result is reported.", className: "text-amber-200" };
}

function stageClass(status: string): string {
    if (status === "completed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
    if (status === "current") return "border-blue-400 bg-blue-500/10 text-blue-200";
    if (status === "blocked") return "border-amber-400 bg-amber-500/10 text-amber-100";
    if (status === "failed") return "border-red-400 bg-red-500/10 text-red-100";
    return "border-slate-800 bg-slate-950/50 text-slate-500";
}

function Detail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
