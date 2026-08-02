import type { WorkflowDetailResponse, WorkflowExecutionSummary, WorkflowTimelineStage } from "../types/atlasAgent";

interface ExecutionTimelineProps {
    workflow: WorkflowDetailResponse;
    isRefreshing: boolean;
    onRefresh: () => void;
}

export function ExecutionTimeline({ workflow, isRefreshing, onRefresh }: ExecutionTimelineProps) {
    const executionState = executionStateText(workflow);

    return (
        <section aria-labelledby="execution-timeline-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 id="execution-timeline-heading" className="text-lg font-semibold text-white">Execution timeline</h2>
                    <p aria-live="polite" role="status" className="mt-1 text-sm text-slate-300">{executionState}</p>
                </div>
                <button type="button" onClick={onRefresh} disabled={isRefreshing} className="rounded-lg border border-blue-400 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60">
                    {isRefreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <ol className="mt-5 grid gap-2 text-sm md:grid-cols-3 xl:grid-cols-9" aria-label="Authoritative execution stages">
                {workflow.timeline.map((stage) => (
                    <TimelineStage key={stage.name} stage={stage} />
                ))}
            </ol>

            <ExecutionSection execution={workflow.execution} workflowState={workflow.workflow_state} approvalStatus={workflow.implementation_approval_status} />
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

function ExecutionSection({ execution, workflowState, approvalStatus }: { execution: WorkflowExecutionSummary; workflowState: string; approvalStatus: string }) {
    const hasResult = execution.execution_status !== null;
    const running = workflowState === "executing";

    return (
        <section aria-labelledby="execution-section-heading" className="mt-5 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h3 id="execution-section-heading" className="text-base font-semibold text-white">Execution</h3>
            {!hasResult && !running && approvalStatus !== "approved" && <p className="mt-2 text-sm text-slate-300">Waiting for implementation approval.</p>}
            {!hasResult && !running && approvalStatus === "approved" && <p className="mt-2 text-sm text-slate-300">Execution unavailable.</p>}
            {running && <p role="status" className="mt-2 text-sm text-blue-200">Execution running...</p>}
            {hasResult && <p role="status" className="mt-2 text-sm text-emerald-200">Execution complete.</p>}
            {hasResult && (
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
            )}
        </section>
    );
}

function executionStateText(workflow: WorkflowDetailResponse): string {
    const execution = workflow.execution;
    if (workflow.workflow_state === "executing") return "Execution running...";
    if (execution.execution_status === "succeeded") return "Execution complete.";
    if (execution.execution_status === "failed" || execution.execution_status === "timed_out" || execution.execution_status === "launch_failed") return "Execution failed.";
    if (workflow.implementation_approval_status !== "approved") return "Waiting for implementation approval.";
    return "Execution unavailable.";
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
