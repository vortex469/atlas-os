import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
    getAtlasAgentErrorMessage,
    getWorkflowDetail,
    submitWorkflowImplementationApproval,
} from "../api/atlas-agent";
import { ExecutionTimeline } from "./ExecutionTimeline";
import type {
    WorkflowDetailResponse,
    WorkflowImplementationApprovalResponse,
    WorkflowImplementationDecision,
} from "../types/atlasAgent";

type LoadMode = "initial" | "refresh";

export function WorkflowPage() {
    const { workflowId = "" } = useParams<{ workflowId: string }>();
    const [workflow, setWorkflow] = useState<WorkflowDetailResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [approvalError, setApprovalError] = useState<string | null>(null);
    const [approvalResult, setApprovalResult] = useState<WorkflowImplementationApprovalResponse | null>(null);

    const loadWorkflow = useCallback(async (mode: LoadMode = "initial") => {
        if (mode === "initial") setIsLoading(true);
        if (mode === "refresh") setIsRefreshing(true);
        setLoadError(null);
        try {
            const detail = await getWorkflowDetail(workflowId);
            setWorkflow(detail);
        } catch (error) {
            setLoadError(getAtlasAgentErrorMessage(error, "Atlas Agent unavailable."));
        } finally {
            if (mode === "initial") setIsLoading(false);
            if (mode === "refresh") setIsRefreshing(false);
        }
    }, [workflowId]);

    useEffect(() => {
        void Promise.resolve().then(() => loadWorkflow());
    }, [loadWorkflow]);

    useEffect(() => {
        if (workflow?.workflow_state !== "executing") return undefined;
        const interval = window.setInterval(() => {
            void loadWorkflow("refresh");
        }, 5_000);
        return () => window.clearInterval(interval);
    }, [loadWorkflow, workflow?.workflow_state]);

    function refreshWorkflow() {
        if (isRefreshing) return;
        void loadWorkflow("refresh");
    }

    async function submitDecision(decision: WorkflowImplementationDecision) {
        if (!workflow || workflow.workflow_state !== "awaiting_implementation_approval" || isSubmitting) return;
        setIsSubmitting(true);
        setApprovalError(null);
        try {
            const result = await submitWorkflowImplementationApproval(workflow.workflow_id, decision);
            setApprovalResult(result);
            setWorkflow({
                ...workflow,
                workflow_state: result.workflow_state,
                implementation_approval_status: result.implementation_approval_status,
            });
        } catch (error) {
            setApprovalError(getAtlasAgentErrorMessage(error, decision === "approve" ? "Approval failed." : "Rejection failed."));
        } finally {
            setIsSubmitting(false);
        }
    }

    if (isLoading) {
        return (
            <main className="mx-auto max-w-6xl p-8">
                <p role="status" className="text-slate-300">Loading workflow...</p>
            </main>
        );
    }

    if (loadError) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-8">
                <WorkflowRail />
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-lg font-semibold text-red-100">Workflow unavailable</h1>
                    <p className="mt-2 text-sm text-red-100">{loadError}</p>
                </section>
            </main>
        );
    }

    if (!workflow) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-8">
                <WorkflowRail />
                <section role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <h1 className="text-lg font-semibold text-amber-100">Workflow not found</h1>
                    <p className="mt-2 text-sm text-slate-300">Atlas Agent did not find workflow {workflowId}.</p>
                </section>
            </main>
        );
    }

    const canDecide = workflow.workflow_state === "awaiting_implementation_approval";

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow</p>
                    <h1 className="mt-3 break-all text-3xl font-bold text-white">Workflow {workflow.workflow_id}</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Review the immutable implementation request and approve or reject that exact request only. Mission Control does not execute, edit commands, modify repositories, verify, review, or commit from this page.
                    </p>
                </div>
                <WorkflowRail />
            </header>

            <section aria-labelledby="workflow-summary-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <h2 id="workflow-summary-heading" className="text-lg font-semibold text-white">Workflow summary</h2>
                        <p className="mt-1 text-sm text-slate-400">Implementation approval status: {formatLabel(workflow.implementation_approval_status)}</p>
                    </div>
                    <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">{formatLabel(workflow.workflow_state)}</span>
                </div>
                <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Workflow ID" value={workflow.workflow_id} />
                    <Detail label="Workflow Source" value={workflow.workflow_source} />
                    <Detail label="Workflow State" value={formatLabel(workflow.workflow_state)} />
                    <Detail label="Planning Session ID" value={workflow.planning_session_id ?? "Not exposed"} />
                    <Detail label="Candidate ID" value={workflow.candidate_id ?? "Not exposed"} />
                    <Detail label="Candidate Fingerprint" value={workflow.candidate_fingerprint ?? "Not exposed"} />
                    <Detail label="Plan Fingerprint" value={workflow.plan_fingerprint ?? "Not exposed"} />
                    <Detail label="Implementation Approval Status" value={formatLabel(workflow.implementation_approval_status)} />
                    <Detail label="Repository" value={workflow.repository ?? "Not exposed"} />
                    <Detail label="Working Directory" value={workflow.working_directory ?? "Not exposed"} />
                    <Detail label="Translator Version" value={workflow.translator_version ?? "Not exposed"} />
                    <Detail label="Affected Files" value={workflow.affected_files.length > 0 ? workflow.affected_files.join(", ") : "None reported"} />
                </dl>
            </section>

            <ImplementationRequestSection workflow={workflow} />

            <ExecutionTimeline workflow={workflow} isRefreshing={isRefreshing} onRefresh={refreshWorkflow} />

            <section aria-labelledby="approval-controls-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="approval-controls-heading" className="text-lg font-semibold text-white">Implementation approval</h2>
                <p className="mt-2 text-sm text-slate-400">
                    These controls submit only the workflow ID and approval decision to Atlas Agent. They do not execute or mutate the implementation request.
                </p>
                {canDecide ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void submitDecision("approve")} disabled={isSubmitting} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">
                            Approve Implementation
                        </button>
                        <button type="button" onClick={() => void submitDecision("reject")} disabled={isSubmitting} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">
                            Reject
                        </button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">Approval controls are unavailable because this workflow is {formatLabel(workflow.workflow_state)}.</p>
                )}
                {isSubmitting && <p role="status" className="mt-3 text-sm text-blue-200">Submitting approval...</p>}
                {approvalResult && approvalResult.implementation_approval_status === "approved" && (
                    <p role="status" className="mt-3 text-sm text-emerald-200">Implementation approved. Execution is now available.</p>
                )}
                {approvalResult && approvalResult.implementation_approval_status === "rejected" && (
                    <p role="status" className="mt-3 text-sm text-red-100">Approval rejected.</p>
                )}
                {approvalError && <p role="alert" className="mt-3 text-sm text-red-100">{approvalMessage(approvalError)}</p>}
            </section>

            <Link to="/execution-candidates" className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                Back to execution candidates
            </Link>
        </main>
    );
}

function ImplementationRequestSection({ workflow }: { workflow: WorkflowDetailResponse }) {
    const request = workflow.implementation_request;

    return (
        <section aria-labelledby="implementation-request-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 id="implementation-request-heading" className="text-lg font-semibold text-white">Immutable implementation request</h2>
            <p className="mt-2 text-sm text-slate-400">Read-only summary. Commands, argv, shell editors, environment editing, repository editing, and path editing are intentionally not rendered.</p>
            {request ? (
                <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Tool" value={request.tool} />
                    <Detail label="Working directory" value={request.working_directory} />
                    <Detail label="Affected files" value={request.affected_files.length > 0 ? request.affected_files.join(", ") : "None reported"} />
                    <Detail label="Repository" value={request.repository} />
                    <Detail label="Translator version" value={request.translator_version ?? "Not exposed"} />
                    <Detail label="Immutable request ID" value={request.immutable_request_id} />
                </dl>
            ) : (
                <p role="alert" className="mt-4 text-sm text-amber-100">Immutable implementation request is not available for this workflow.</p>
            )}
        </section>
    );
}

function WorkflowRail() {
    const steps = ["Execution Candidate", "Planning Session", "Candidate Plan", "Workflow", "Implementation", "Execution", "Verification", "Review", "Commit"];
    const complete = new Set(["Execution Candidate", "Planning Session", "Candidate Plan", "Workflow", "Implementation", "Execution"]);

    return (
        <section aria-label="Read-only workflow rail" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <ol className="grid gap-2 text-sm md:grid-cols-3 xl:grid-cols-9">
                {steps.map((step) => {
                    const isExecution = step === "Execution";
                    const isComplete = complete.has(step);
                    return (
                        <li key={step} className={[
                            "rounded-lg border px-3 py-2",
                            isExecution ? "border-blue-400 bg-blue-500/10 text-blue-200" : isComplete ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-slate-800 bg-slate-950/50 text-slate-500",
                        ].join(" ")}
                        >
                            <span className="block font-medium">{step}{isComplete ? " ✔" : " ○"}</span>
                            <span className="text-xs">{isComplete ? "Read-only" : "Disabled"}</span>
                        </li>
                    );
                })}
            </ol>
        </section>
    );
}

function Detail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function approvalMessage(message: string): string {
    const lower = message.toLowerCase();
    if (lower.includes("already approved")) return "Approval already approved.";
    if (lower.includes("already") || lower.includes("conflict")) return "Approval already decided.";
    if (lower.includes("stale")) return "Stale workflow.";
    if (lower.includes("persistence")) return "Persistence failure.";
    if (lower.includes("unavailable")) return "Atlas Agent unavailable.";
    return message;
}
