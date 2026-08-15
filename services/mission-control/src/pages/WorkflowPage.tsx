import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
    getAtlasAgentErrorMessage,
    getWorkflowDetail,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    submitWorkflowCommitApproval,
    submitWorkflowImplementationApproval,
    submitWorkflowVerificationApproval,
    resumeWorkflow,
} from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import { OperationalLifecyclePanel } from "../components/OperationalLifecyclePanel";
import { ExecutionTimeline } from "./ExecutionTimeline";
import type {
    WorkflowDetailResponse,
    WorkflowCommitApprovalResponse,
    WorkflowImplementationApprovalResponse,
    WorkflowImplementationDecision,
    WorkflowVerificationApprovalResponse,
    WorkflowOperationalLifecycle,
    WorkflowRecoveryDiagnostic,
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
    const [isSubmittingCommit, setIsSubmittingCommit] = useState(false);
    const [commitApprovalError, setCommitApprovalError] = useState<string | null>(null);
    const [commitApprovalResult, setCommitApprovalResult] = useState<WorkflowCommitApprovalResponse | null>(null);
    const [isResuming, setIsResuming] = useState(false);
    const [resumeError, setResumeError] = useState<string | null>(null);
    const [operationalLifecycle, setOperationalLifecycle] = useState<WorkflowOperationalLifecycle | null>(null);
    const [recoveryDiagnostic, setRecoveryDiagnostic] = useState<WorkflowRecoveryDiagnostic | null>(null);
    const [lifecycleError, setLifecycleError] = useState<string | null>(null);

    const loadWorkflow = useCallback(async (mode: LoadMode = "initial") => {
        if (mode === "initial") setIsLoading(true);
        if (mode === "refresh") setIsRefreshing(true);
        setLoadError(null);
        try {
            const detail = await getWorkflowDetail(workflowId);
            setWorkflow(detail);
            setLifecycleError(null);
            if (detail?.effect_kind === "operational_action") {
                try {
                    const lifecycle = await getWorkflowOperationalLifecycle(workflowId);
                    setOperationalLifecycle(lifecycle);
                    setRecoveryDiagnostic(await getWorkflowRecoveryDiagnostic(workflowId));
                    if (lifecycle === null) {
                        setLifecycleError("The operational lifecycle is no longer available for this workflow.");
                    }
                } catch {
                    setOperationalLifecycle(null);
                    setRecoveryDiagnostic(null);
                    setLifecycleError("Mission Control could not read the operational lifecycle.");
                }
            } else {
                setOperationalLifecycle(null);
                setRecoveryDiagnostic(null);
            }
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
        if (workflow?.workflow_state !== "executing" && operationalLifecycle?.terminal !== false) return undefined;
        const interval = window.setInterval(() => {
            void loadWorkflow("refresh");
        }, 5_000);
        return () => window.clearInterval(interval);
    }, [loadWorkflow, operationalLifecycle?.terminal, workflow?.workflow_state]);

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
            await loadWorkflow("refresh");
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
            await loadWorkflow("refresh");
        } catch (error) {
            setVerificationApprovalError(getAtlasAgentErrorMessage(error, decision === "approve" ? "Verification approval failed." : "Verification rejection failed."));
        } finally {
            setIsSubmittingVerification(false);
        }
    }

    async function submitCommitDecision(decision: WorkflowImplementationDecision) {
        if (!workflow || workflow.workflow_state !== "awaiting_commit_approval" || isSubmittingCommit) return;
        setIsSubmittingCommit(true);
        setCommitApprovalError(null);
        try {
            const result = await submitWorkflowCommitApproval(workflow.workflow_id, decision);
            setCommitApprovalResult(result);
            await loadWorkflow("refresh");
        } catch (error) {
            setCommitApprovalError(getAtlasAgentErrorMessage(error, decision === "approve" ? "Commit approval failed." : "Commit rejection failed."));
        } finally {
            setIsSubmittingCommit(false);
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

    const isOperational = workflow.effect_kind === "operational_action";
    const isRepository = !isOperational;
    const canDecide =
        workflow.workflow_state === "awaiting_implementation_approval"
        && workflow.implementation_approval_status === "pending";
    const canDecideVerification =
        isRepository
        &&
        workflow.workflow_state === "awaiting_verification_approval"
        && workflow.verification_approval_status === "pending";
    const canDecideCommit =
        isRepository
        &&
        workflow.workflow_state === "awaiting_commit_approval"
        && workflow.commit_approval_status === "pending";

    const canResumeImplementation =
        workflow.workflow_state === "awaiting_implementation_approval"
        && workflow.implementation_approval_status === "approved";
    const canResumeVerification =
        isRepository
        &&
        workflow.workflow_state === "awaiting_verification_approval"
        && workflow.verification_approval_status === "approved";
    const canResumeCommit =
        isRepository
        &&
        workflow.workflow_state === "awaiting_commit_approval"
        && workflow.commit_approval_status === "approved";
    const canResume =
        !isResuming
        && (canResumeImplementation || canResumeVerification || canResumeCommit);

    const resumeButtonLabel = canResumeImplementation
        ? "Resume Approved Implementation"
        : canResumeVerification
            ? "Resume Approved Verification"
            : canResumeCommit
                ? "Resume Approved Commit"
                : "Resume";

    async function resumeWorkflowTransition() {
        if (!workflow || !canResume) {
            return;
        }

        setIsResuming(true);
        setResumeError(null);

        try {
            await resumeWorkflow(workflow.workflow_id);
            await loadWorkflow("refresh");
        } catch (error) {
            setResumeError(getAtlasAgentErrorMessage(error, "Workflow resume failed."));
            await loadWorkflow("refresh");
        } finally {
            setIsResuming(false);
        }
    }

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

            {isRepository && <ImplementationRequestSection workflow={workflow} />}

            {isOperational && (
                <OperationalLifecyclePanel
                    lifecycle={operationalLifecycle}
                    diagnostic={recoveryDiagnostic}
                    isLoading={operationalLifecycle === null && lifecycleError === null}
                    isRefreshing={isRefreshing}
                    error={lifecycleError}
                    onRefresh={refreshWorkflow}
                />
            )}

            <ExecutionTimeline workflow={workflow} isRefreshing={isRefreshing} onRefresh={refreshWorkflow} />

            {isRepository && (
                <>
                    <VerificationReviewSection
                        workflow={workflow}
                        canDecideVerification={canDecideVerification}
                        isSubmittingVerification={isSubmittingVerification}
                        verificationApprovalResult={verificationApprovalResult}
                        verificationApprovalError={verificationApprovalError}
                        onVerificationDecision={submitVerificationDecision}
                    />

                    <CommitSection
                        workflow={workflow}
                        canDecideCommit={canDecideCommit}
                        isSubmittingCommit={isSubmittingCommit}
                        commitApprovalResult={commitApprovalResult}
                        commitApprovalError={commitApprovalError}
                        onCommitDecision={submitCommitDecision}
                    />
                </>
            )}

            <section aria-labelledby="approval-controls-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="approval-controls-heading" className="text-lg font-semibold text-white">
                    {workflow.effect_kind === "operational_action" ? "Operational action approval" : "Implementation approval"}
                </h2>
                <p className="mt-2 text-sm text-slate-400">
                    These controls submit only the workflow ID and approval decision to Atlas Agent. They do not execute or mutate the implementation request.
                </p>
                {canDecide ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void submitDecision("approve")} disabled={isSubmitting} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">
                            {workflow.effect_kind === "operational_action" ? "Approve Exact Action" : "Approve Implementation"}
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

            {canResume && (
                <section aria-labelledby="resume-controls-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <h2 id="resume-controls-heading" className="text-lg font-semibold text-white">Resume approved stage</h2>
                    <p className="mt-2 text-sm text-slate-400">Use this to advance execution after an approval decision.</p>
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button
                            type="button"
                            onClick={() => void resumeWorkflowTransition()}
                            disabled={isResuming}
                            className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-blue-950 transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {isResuming ? "Resuming..." : resumeButtonLabel}
                        </button>
                    </div>
                    {isResuming && <p role="status" className="mt-3 text-sm text-blue-200">Resuming workflow...</p>}
                    {resumeError && <p role="alert" className="mt-3 text-sm text-red-100">{approvalMessage(resumeError)}</p>}
                </section>
            )}

            <Link to="/execution-candidates" className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                Back to execution candidates
            </Link>
            <Link
                to={`/workflows/${workflow.workflow_id}/audit`}
                className="ml-4 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
                Open Audit
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

        </section>
    );
}

function CommitSection({
    workflow,
    canDecideCommit,
    isSubmittingCommit,
    commitApprovalResult,
    commitApprovalError,
    onCommitDecision,
}: {
    workflow: WorkflowDetailResponse;
    canDecideCommit: boolean;
    isSubmittingCommit: boolean;
    commitApprovalResult: WorkflowCommitApprovalResponse | null;
    commitApprovalError: string | null;
    onCommitDecision: (decision: WorkflowImplementationDecision) => Promise<void>;
}) {
    const request = workflow.commit_request;
    const result = workflow.commit_result;
    const isCompleted = workflow.workflow_state === "completed";

    return (
        <section aria-labelledby="commit-heading" className="space-y-5 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div>
                <h2 id="commit-heading" className="text-lg font-semibold text-white">Commit</h2>
                <p className="mt-2 text-sm text-slate-400">
                    Read-only commit approval boundary. Mission Control may approve or reject the exact commit request only. It never edits messages, edits paths, pushes, tags, amends, releases, or rolls back.
                </p>
            </div>

            <section aria-labelledby="commit-request-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="commit-request-heading" className="text-base font-semibold text-white">Commit Request</h3>
                {request ? (
                    <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Commit Request ID" value={request.commit_request_id} />
                        <Detail label="Repository" value={request.repository ?? "Not available"} />
                        <Detail label="Branch" value={request.branch ?? "Not available"} />
                        <Detail label="Expected HEAD" value={request.expected_head ?? "Not available"} />
                        <Detail label="Commit message" value={request.commit_message} />
                        <Detail label="Reviewed files" value={request.reviewed_files.length > 0 ? request.reviewed_files.join(", ") : "None reported"} />
                        <Detail label="Reviewed-content fingerprint" value={request.reviewed_content_fingerprint} />
                        <Detail label="Commit approval status" value={formatLabel(request.commit_approval_status)} />
                    </dl>
                ) : (
                    <p className="mt-3 text-sm text-slate-300">Commit request is not available for this workflow.</p>
                )}
            </section>

            <section aria-labelledby="commit-approval-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="commit-approval-heading" className="text-base font-semibold text-white">Commit approval</h3>
                <p className="mt-2 text-sm text-slate-400">These controls submit only the workflow ID and commit approval decision.</p>
                {canDecideCommit ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void onCommitDecision("approve")} disabled={isSubmittingCommit} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">Approve Commit</button>
                        <button type="button" onClick={() => void onCommitDecision("reject")} disabled={isSubmittingCommit} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">Reject Commit</button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">Commit approval controls are unavailable because this workflow is {formatLabel(workflow.workflow_state)}.</p>
                )}
                {isSubmittingCommit && <p role="status" aria-live="polite" className="mt-3 text-sm text-blue-200">Submitting commit approval...</p>}
                {commitApprovalResult?.commit_approval_status === "approved" && <p role="status" className="mt-3 text-sm text-emerald-200">Commit approved. Workflow may now complete through the existing backend resume path.</p>}
                {commitApprovalResult?.commit_approval_status === "rejected" && <p role="status" className="mt-3 text-sm text-red-100">Commit approval rejected.</p>}
                {commitApprovalError && <p role="alert" className="mt-3 text-sm text-red-100">{approvalMessage(commitApprovalError)}</p>}
            </section>

            {isCompleted && (
                <section aria-labelledby="completed-workflow-heading" className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
                    <h3 id="completed-workflow-heading" className="text-base font-semibold text-emerald-100">Completed workflow</h3>
                    <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Commit SHA" value={result.commit_sha ?? "Not available"} />
                        <Detail label="Commit message" value={result.commit_message ?? "Not available"} />
                        <Detail label="Committed files" value={result.committed_files.length > 0 ? result.committed_files.join(", ") : "None reported"} />
                        <Detail label="Completion time" value={result.completion_time ?? "Not available"} />
                    </dl>
                </section>
            )}
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
    if (lower.includes("completed")) return "Workflow completed.";
    if (lower.includes("blocked")) return "Workflow blocked.";
    if (lower.includes("already rejected")) return "Commit already rejected.";
    if (lower.includes("already approved")) return "Approval already approved.";
    if (lower.includes("already") || lower.includes("conflict")) return "Approval already decided.";
    if (lower.includes("stale")) return "Stale workflow.";
    if (lower.includes("persistence")) return "Persistence failure.";
    if (lower.includes("unavailable")) return "Atlas Agent unavailable.";
    return message;
}
