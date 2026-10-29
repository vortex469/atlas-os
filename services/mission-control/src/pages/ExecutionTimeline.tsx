import type { ReactNode } from "react";

import type { WorkflowDetailResponse, WorkflowExecutionSummary, WorkflowTimelineStage } from "../types/atlasAgent";
import { evidenceTimestamp } from "../utils/healthPresentation";
import { workflowStageStatusLabel } from "../utils/workflowState";

interface ExecutionTimelineProps {
    workflow: WorkflowDetailResponse;
    isRefreshing: boolean;
    refreshDisabled?: boolean;
    onRefresh: () => void;
}

export function ExecutionTimeline({ workflow, isRefreshing, refreshDisabled = false, onRefresh }: ExecutionTimelineProps) {
    const isOperational = workflow.effect_kind === "operational_action";
    const executionState = executionStateText(workflow);
    const timeline = isOperational
        ? workflow.timeline.filter((stage) => stage.name !== "Review" && stage.name !== "Commit")
        : workflow.timeline;

    return (
        <section aria-labelledby="execution-timeline-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 id="execution-timeline-heading" className="text-lg font-semibold text-white">{isOperational ? "Maintenance progress" : "Change progress"}</h2>
                    <p aria-live="polite" role="status" className="mt-1 text-sm text-slate-300">{executionState}</p>
                </div>
                <button type="button" onClick={onRefresh} disabled={isRefreshing || refreshDisabled} className="rounded-lg border border-blue-400 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60">
                    {isRefreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <ol className={`mt-5 grid gap-2 text-sm md:grid-cols-3 ${isOperational ? "xl:grid-cols-7" : "xl:grid-cols-9"}`} aria-label={isOperational ? "Maintenance workflow stages" : "Change stages"}>
                {timeline.map((stage) => (
                    <TimelineStage key={stage.name} stage={stage} isOperational={isOperational} />
                ))}
            </ol>

            {isOperational
                ? <p className="mt-5 text-sm text-slate-300">Check Maintenance status above for the outcome and verification.</p>
                : <ExecutionSection execution={workflow.execution} />}
        </section>
    );
}

function TimelineStage({ stage, isOperational }: { stage: WorkflowTimelineStage; isOperational: boolean }) {
    return (
        <li className={["rounded-lg border px-3 py-2", stageClass(stage.status)].join(" ")}>
            <span className="block font-medium">{isOperational ? operationalStageLabel(stage.name) : repositoryStageLabel(stage.name)}</span>
            <span className="text-xs">{workflowStageStatusLabel(stage.status)}</span>
        </li>
    );
}

function repositoryStageLabel(name: string): string {
    switch (name) {
        case "Execution Candidate": return "Change proposal";
        case "Planning Session": return "Planning";
        case "Candidate Plan": return "Change plan";
        case "Workflow": return "Workflow created";
        case "Implementation Approval": return "Change approval";
        case "Execution": return "Apply change";
        case "Verification": return "Verify change";
        case "Review": return "Review results";
        default: return name;
    }
}

function operationalStageLabel(name: string): string {
    switch (name) {
        case "Execution Candidate": return "Proposal";
        case "Planning Session": return "Planning";
        case "Candidate Plan": return "Maintenance plan";
        case "Implementation Approval": return "Maintenance request approval";
        case "Execution": return "Run maintenance";
        case "Verification": return "Verify result";
        default: return name;
    }
}

function ExecutionSection({ execution }: { execution: WorkflowExecutionSummary }) {
    const hasResult = execution.execution_status !== null;

    return (
        <section aria-labelledby="execution-section-heading" className="mt-5 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h3 id="execution-section-heading" className="text-base font-semibold text-white">Execution</h3>
            {hasResult && (
                <>
                    <p className="mt-3 text-sm text-slate-300">Files changed: {execution.changed_files_count}</p>
                    <details className="mt-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <dl className="mt-3 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                            <Detail label="Execution status" value={formatLabel(execution.execution_status ?? "not_available")} />
                            <Detail label="Started (local time)" value={formatExecutionTime(execution.started_at)} />
                            <Detail label="Completed (local time)" value={formatExecutionTime(execution.completed_at)} />
                            <Detail label="Execution result" value={formatLabel(execution.result ?? "not_available")} />
                            <Detail label="Tool" value={execution.tool ?? "Not exposed"} />
                            <Detail label="Working directory" value={execution.working_directory ?? "Not exposed"} />
                            <Detail label="Repository" value={execution.repository ?? "Not exposed"} />
                            <Detail label="Changed files" value={execution.changed_files.length > 0 ? execution.changed_files.join(", ") : "None reported"} />
                            <Detail label="Execution request ID" value={execution.execution_request_id ?? "Not exposed"} />
                        </dl>
                    </details>
                </>
            )}
        </section>
    );
}

function executionStateText(workflow: WorkflowDetailResponse): string {
    if (workflow.effect_kind === "operational_action") {
        if (workflow.workflow_state === "completed") return "Maintenance workflow completed. Review the recorded operational outcome.";
        if (workflow.workflow_state === "blocked") return "Maintenance workflow is blocked. Review Maintenance status for details.";
        if (workflow.workflow_state === "executing") return "Maintenance is running.";
        if (workflow.workflow_state === "implementation_rejected" || workflow.implementation_approval_status === "rejected") return "The maintenance request was rejected; it was not run.";
        if (workflow.workflow_state === "planned") return "Maintenance request is ready for review.";
        if (workflow.workflow_state === "awaiting_execution" && workflow.implementation_approval_status !== "approved") {
            return "Maintenance approval is not confirmed. Refresh before running it.";
        }
        if (workflow.workflow_state === "awaiting_execution"
            || (workflow.workflow_state === "awaiting_implementation_approval" && workflow.implementation_approval_status === "approved")) {
            return "Maintenance is approved. Run it when you are ready.";
        }
        if (workflow.workflow_state === "awaiting_implementation_approval" && workflow.implementation_approval_status !== "approved") return "Waiting for maintenance request approval.";
        return "Review Maintenance status for the latest result.";
    }
    const execution = workflow.execution;
    if (workflow.worker_reconciliation?.outcome === "unknown" || execution.execution_status === "unknown") {
        return "The change may have finished. Check its result before starting it again.";
    }
    if (workflow.workflow_state === "executing") return "Execution running...";
    if (execution.execution_status === "succeeded") return "Execution complete.";
    if (execution.execution_status === "failed" || execution.execution_status === "timed_out" || execution.execution_status === "launch_failed") return "Execution failed.";
    if (execution.execution_status !== null) return "Atlas Agent reported an execution status Mission Control does not recognize. Refresh before continuing.";
    if (workflow.workflow_state === "implementation_rejected" || workflow.implementation_approval_status === "rejected") return "The change was not applied because implementation approval was rejected.";
    if (workflow.workflow_state === "planned") return "Review the proposed change before continuing.";
    if (workflow.workflow_state === "awaiting_execution" && workflow.implementation_approval_status !== "approved") {
        return "Implementation approval is not confirmed. Refresh before running the change.";
    }
    if (workflow.workflow_state === "awaiting_execution"
        || (workflow.workflow_state === "awaiting_implementation_approval" && workflow.implementation_approval_status === "approved")) {
        return "Approval is recorded. Run the change when you are ready.";
    }
    if (workflow.implementation_approval_status !== "approved") return "Waiting for implementation approval.";
    return "Atlas Agent has not reported whether the change ran. Refresh to check again.";
}

function stageClass(status: string): string {
    if (status === "completed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
    if (status === "current") return "border-blue-400 bg-blue-500/10 text-blue-200";
    if (status === "blocked") return "border-amber-400 bg-amber-500/10 text-amber-100";
    if (status === "failed") return "border-red-400 bg-red-500/10 text-red-100";
    return "border-slate-800 bg-slate-950/50 text-slate-500";
}

function formatExecutionTime(value: string | null): ReactNode {
    if (value === null) return "Not exposed by Atlas Agent";
    const timestamp = evidenceTimestamp(value);
    return timestamp === null
        ? "Time unavailable"
        : <time dateTime={value}>{new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>;
}

function Detail({ label, value }: { label: string; value: ReactNode }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
