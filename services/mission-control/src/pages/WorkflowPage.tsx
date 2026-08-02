import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
    getAtlasAgentErrorMessage,
    getWorkflowDetail,
    submitWorkflowImplementationApproval,
    submitWorkflowVerificationApproval,
} from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import { ExecutionTimeline } from "./ExecutionTimeline";
import type {
    WorkflowDetailResponse,
    WorkflowImplementationApprovalResponse,
    WorkflowImplementationDecision,
    WorkflowVerificationApprovalResponse,
} from "../types/atlasAgent";
import { fallbackWorkflowRailStages, workflowRailStages } from "../utils/workflowState";

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
    const [isSubmittingVerification, setIsSubmittingVerification] = useState(false);
    const [verificationApprovalError, setVerificationApprovalError] = useState<string | null>(null);
    const [verificationApprovalResult, setVerificationApprovalResult] = useState<WorkflowVerificationApprovalResponse | null>(null);

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

    async function submitVerificationDecision(decision: WorkflowImplementationDecision) {
        if (!workflow || workflow.workflow_state !== "awaiting_verification_approval" || isSubmittingVerification) return;
        setIsSubmittingVerification(true);
        setVerificationApprovalError(null);
        try {
            const result = await submitWorkflowVerificationApproval(workflow.workflow_id, decision);
            setVerificationApprovalResult(result);
            setWorkflow({
                ...workflow,
                workflow_state: result.workflow_state,
                verification_approval_status: result.verification_approval_status,
            });
        } catch (error) {
            setVerificationApprovalError(getAtlasAgentErrorMessage(error, decision === "approve" ? "Verification approval failed." : "Verification rejection failed."));
        } finally {
            setIsSubmittingVerification(false);
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
    const canDecideVerification = workflow.workflow_state === "awaiting_verification_approval";

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
                <WorkflowRail workflow={workflow} />
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

            <VerificationReviewSection
                workflow={workflow}
                canDecideVerification={canDecideVerification}
                isSubmittingVerification={isSubmittingVerification}
                verificationApprovalResult={verificationApprovalResult}
                verificationApprovalError={verificationApprovalError}
                onVerificationDecision={submitVerificationDecision}
            />

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

function VerificationReviewSection({
    workflow,
    canDecideVerification,
    isSubmittingVerification,
    verificationApprovalResult,
    verificationApprovalError,
    onVerificationDecision,
}: {
    workflow: WorkflowDetailResponse;
    canDecideVerification: boolean;
    isSubmittingVerification: boolean;
    verificationApprovalResult: WorkflowVerificationApprovalResponse | null;
    verificationApprovalError: string | null;
    onVerificationDecision: (decision: WorkflowImplementationDecision) => Promise<void>;
}) {
    const plan = workflow.verification_plan;
    const evidence = workflow.verification_evidence;
    const review = workflow.review;

    return (
        <section aria-labelledby="verification-review-heading" className="space-y-5 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div>
                <h2 id="verification-review-heading" className="text-lg font-semibold text-white">Verification and review</h2>
                <p className="mt-2 text-sm text-slate-400">Read-only verification and deterministic review state from Atlas Agent. Mission Control does not edit checks, regenerate plans, run verification manually, create commit approval, or commit.</p>
            </div>

            <section aria-labelledby="verification-plan-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="verification-plan-heading" className="text-base font-semibold text-white">Verification Plan</h3>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Verification Plan ID" value={plan.verification_plan_id ?? "Not available"} />
                    <Detail label="Verifier Version" value={plan.verifier_version ?? "Not available"} />
                    <Detail label="Changed-files digest" value={plan.changed_files_digest ?? "Not available"} />
                    <Detail label="Verification check IDs" value={plan.verification_check_ids.length > 0 ? plan.verification_check_ids.join(", ") : "None reported"} />
                    <Detail label="Command-backed checks" value={plan.command_backed_checks.length > 0 ? plan.command_backed_checks.join(", ") : "None reported"} />
                    <Detail label="Working directory" value={plan.working_directory ?? "Not available"} />
                    <Detail label="Repository" value={plan.repository ?? "Not available"} />
                    <Detail label="Verification status" value={formatLabel(plan.verification_status)} />
                </dl>
            </section>

            <section aria-labelledby="verification-evidence-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="verification-evidence-heading" className="text-base font-semibold text-white">Verification Evidence</h3>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Verification status" value={evidence.verification_status ? formatLabel(evidence.verification_status) : "Not available"} />
                    <Detail label="Completed time" value={evidence.completed_time ?? "Not available"} />
                    <Detail label="Executed checks" value={evidence.executed_checks.length > 0 ? evidence.executed_checks.join(", ") : "None reported"} />
                    <Detail label="Check results" value={evidence.check_results.length > 0 ? evidence.check_results.map((check) => `${String(check.identifier)}: ${String(check.status)}`).join(", ") : "None reported"} />
                    <Detail label="Repository HEAD" value={evidence.repository_head ?? "Not available"} />
                    <Detail label="Changed-files digest" value={evidence.changed_files_digest ?? "Not available"} />
                </dl>
            </section>

            <section aria-labelledby="review-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="review-heading" className="text-base font-semibold text-white">Review</h3>
                <p className="mt-2 text-sm text-slate-300">Deterministic review</p>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Review result" value={review.review_result ? formatLabel(review.review_result) : "Not available"} />
                    <Detail label="Review status" value={review.review_status ? formatLabel(review.review_status) : "Not available"} />
                    <Detail label="Approved / Failed" value={review.approved === null ? "Not available" : review.approved ? "Approved" : "Failed"} />
                    <Detail label="Evidence summary" value={review.evidence_summary ?? "Not available"} />
                    <Detail label="Changed files" value={review.changed_files.length > 0 ? review.changed_files.join(", ") : "None reported"} />
                    <Detail label="Review fingerprint" value={review.review_fingerprint ?? "Not available"} />
                    <Detail label="Model-assisted review" value={review.model_assisted_review} />
                </dl>
            </section>

            <section aria-labelledby="verification-approval-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="verification-approval-heading" className="text-base font-semibold text-white">Verification approval</h3>
                <p className="mt-2 text-sm text-slate-400">These controls submit only the workflow ID and verification approval decision.</p>
                {canDecideVerification ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void onVerificationDecision("approve")} disabled={isSubmittingVerification} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">Approve Verification</button>
                        <button type="button" onClick={() => void onVerificationDecision("reject")} disabled={isSubmittingVerification} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">Reject Verification</button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">Verification approval controls are unavailable because this workflow is {formatLabel(workflow.workflow_state)}.</p>
                )}
                {isSubmittingVerification && <p role="status" aria-live="polite" className="mt-3 text-sm text-blue-200">Submitting verification approval...</p>}
                {verificationApprovalResult?.verification_approval_status === "approved" && <p role="status" className="mt-3 text-sm text-emerald-200">Verification approved. Verification is now available.</p>}
                {verificationApprovalResult?.verification_approval_status === "rejected" && <p role="status" className="mt-3 text-sm text-red-100">Verification approval rejected.</p>}
                {verificationApprovalError && <p role="alert" className="mt-3 text-sm text-red-100">{approvalMessage(verificationApprovalError)}</p>}
            </section>

            <section aria-labelledby="commit-disabled-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="commit-disabled-heading" className="text-base font-semibold text-white">Commit</h3>
                <p className="mt-2 text-sm text-slate-400">Commit remains disabled in P4.6. Mission Control does not create commit approval or commit from this page.</p>
            </section>
        </section>
    );
}

function WorkflowRail({ workflow }: { workflow?: WorkflowDetailResponse }) {
    const stages = workflow ? workflowRailStages(workflow) : fallbackWorkflowRailStages();
    return (
        <section aria-label="Read-only workflow rail" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <WorkflowMiniRail stages={stages} />
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
