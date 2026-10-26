import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
    getAtlasAgentErrorMessage,
    getWorkflowDetail,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    getWorkflowSupportBundle,
    submitWorkflowCommitApproval,
    submitWorkflowImplementationApproval,
    submitWorkflowVerificationApproval,
    resumeWorkflow,
} from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import { OperationalLifecyclePanel } from "../components/OperationalLifecyclePanel";
import { OperationalRecoverySummary } from "../components/OperationalRecoverySummary";
import { ExecutionTimeline } from "./ExecutionTimeline";
import type {
    WorkflowDetailResponse,
    WorkflowCommitApprovalResponse,
    WorkflowImplementationApprovalResponse,
    WorkflowImplementationDecision,
    WorkflowVerificationApprovalResponse,
    WorkflowOperationalLifecycle,
    WorkflowRecoveryDiagnostic,
    OperationalSupportBundle,
    WorkflowOperationalActionRequestSummary,
} from "../types/atlasAgent";
import { operationalRequest } from "../utils/operationalRequest";
import { fallbackWorkflowRailStages, workflowRailStages } from "../utils/workflowState";

type LoadMode = "initial" | "refresh";

export function WorkflowPage() {
    const { workflowId = "" } = useParams<{ workflowId: string }>();
    return <WorkflowDetail key={workflowId} workflowId={workflowId} />;
}

function WorkflowDetail({ workflowId }: { workflowId: string }) {
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
    const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
    const [supportBundle, setSupportBundle] = useState<OperationalSupportBundle | null>(null);
    const [isDownloadingSupport, setIsDownloadingSupport] = useState(false);
    const [supportBundleError, setSupportBundleError] = useState<string | null>(null);
    const readSequence = useRef(0);
    const readPending = useRef(false);
    const controlsBusy = isLoading || isRefreshing || isSubmitting || isSubmittingVerification || isSubmittingCommit || isResuming;

    const loadWorkflow = useCallback(async (mode: LoadMode = "initial") => {
        const sequence = ++readSequence.current;
        readPending.current = true;
        if (mode === "initial") setIsLoading(true);
        if (mode === "refresh") setIsRefreshing(true);
        setLoadError(null);
        try {
            const detail = await getWorkflowDetail(workflowId);
            if (sequence !== readSequence.current) return;
            if (detail && detail.workflow_id !== workflowId) {
                setWorkflow(null);
                setLoadError("The returned workflow does not match this page. Try loading it again.");
                return;
            }
            let nextLifecycle: WorkflowOperationalLifecycle | null = null;
            let nextDiagnostic: WorkflowRecoveryDiagnostic | null = null;
            let nextLifecycleError: string | null = null;
            let nextDiagnosticError: string | null = null;
            if (detail?.effect_kind === "operational_action") {
                const [lifecycleResult, diagnosticResult] = await Promise.allSettled([
                    getWorkflowOperationalLifecycle(workflowId), getWorkflowRecoveryDiagnostic(workflowId),
                ]);
                if (sequence !== readSequence.current) return;
                if (lifecycleResult.status === "rejected") {
                    nextLifecycleError = "Mission Control could not read the operational lifecycle.";
                } else if (lifecycleResult.value && lifecycleResult.value.workflow_id !== workflowId) {
                    nextLifecycleError = "The operational lifecycle response does not match this workflow.";
                } else {
                    nextLifecycle = lifecycleResult.value;
                    if (nextLifecycle === null) nextLifecycleError = "The operational lifecycle is no longer available for this workflow.";
                }
                if (diagnosticResult.status === "rejected") {
                    nextDiagnosticError = "Mission Control could not read the recovery diagnostic.";
                } else if (diagnosticResult.value && diagnosticResult.value.correlation?.workflow_id !== workflowId) {
                    nextDiagnosticError = "The recovery diagnostic response does not match this workflow.";
                } else {
                    nextDiagnostic = diagnosticResult.value;
                }
            }
            setWorkflow(detail);
            setOperationalLifecycle(nextLifecycle);
            setRecoveryDiagnostic(nextDiagnostic);
            setLifecycleError(nextLifecycleError);
            setDiagnosticError(nextDiagnosticError);
        } catch (error) {
            if (sequence === readSequence.current) setLoadError(getAtlasAgentErrorMessage(error, "Atlas Agent unavailable."));
        } finally {
            if (sequence === readSequence.current) {
                readPending.current = false;
                setIsLoading(false);
                setIsRefreshing(false);
            }
        }
    }, [workflowId]);

    useEffect(() => {
        let cancelled = false;
        void Promise.resolve().then(() => {
            if (!cancelled) void loadWorkflow();
        });
        return () => { cancelled = true; readSequence.current += 1; readPending.current = false; };
    }, [loadWorkflow]);

    useEffect(() => {
        if (controlsBusy) return undefined;
        if (workflow?.workflow_state !== "executing" && operationalLifecycle?.terminal !== false) return undefined;
        const interval = window.setInterval(() => {
            void loadWorkflow("refresh");
        }, 5_000);
        return () => window.clearInterval(interval);
    }, [controlsBusy, loadWorkflow, operationalLifecycle?.terminal, workflow?.workflow_state]);

    function refreshWorkflow() {
        if (controlsBusy || readPending.current) return;
        void loadWorkflow("refresh");
    }

    async function prepareSupportEvidence() {
        if (!workflow || workflow.effect_kind !== "operational_action" || isDownloadingSupport) return;
        setIsDownloadingSupport(true);
        setSupportBundleError(null);
        try {
            const bundle = await getWorkflowSupportBundle(workflow.workflow_id);
            if (!bundle?.applicable) {
                setSupportBundleError("Support evidence is not available for this workflow.");
                return;
            }
            setSupportBundle(bundle);
        } catch {
            setSupportBundleError("Mission Control could not prepare sanitized support evidence.");
        } finally {
            setIsDownloadingSupport(false);
        }
    }

    function downloadSupportEvidence() {
        if (!supportBundle?.applicable) return;
        try {
            const bundle = supportBundle;
            const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
            const downloadUrl = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = downloadUrl;
            anchor.download = "atlas-operational-support-evidence.json";
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(downloadUrl);
        } catch {
            setSupportBundleError("Mission Control could not create the local evidence download.");
        }
    }

    async function submitDecision(decision: WorkflowImplementationDecision) {
        if (!workflow || !canDecide || controlsBusy || readPending.current) return;
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
        if (!workflow || workflow.workflow_state !== "awaiting_verification_approval" || controlsBusy || readPending.current) return;
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
        if (!workflow || workflow.workflow_state !== "awaiting_commit_approval" || controlsBusy || readPending.current) return;
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
                    <button type="button" onClick={() => void loadWorkflow()} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>
                </section>
                <Link to="/workflows" className="text-sm text-blue-300">← All workflows</Link>
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
                <Link to="/workflows" className="text-sm text-blue-300">← All workflows</Link>
            </main>
        );
    }

    const isOperational = workflow.effect_kind === "operational_action";
    const isRepository = !isOperational;
    const actionRequest = isOperational ? operationalRequest(workflow.operational_action_request) : null;
    const operationalApprovalReady = !isOperational || (actionRequest !== null
        && Array.isArray(workflow.approval_presentations) && workflow.approval_presentations.some((approval) =>
            approval?.purpose === "operational_action" && approval.decision_status === "pending"
            && approval.presentation_state === "actionable" && approval.actionable === true));
    const canDecide =
        workflow.workflow_state === "awaiting_implementation_approval"
        && workflow.implementation_approval_status === "pending"
        && operationalApprovalReady;
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
        && workflow.implementation_approval_status === "approved"
        && (!isOperational || actionRequest !== null);
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
    const canReconcileWorker =
        isRepository
        && workflow.workflow_state === "blocked"
        && workflow.worker_reconciliation?.outcome === "unknown"
        && workflow.worker_reconciliation.can_check_result === true;
    const canResume = canResumeImplementation || canResumeVerification || canResumeCommit || canReconcileWorker;

    const resumeButtonLabel = canReconcileWorker
        ? "Check worker result"
        : canResumeImplementation
        ? isOperational ? "Run approved action" : "Resume Approved Implementation"
        : canResumeVerification
            ? "Resume Approved Verification"
            : canResumeCommit
                ? "Resume Approved Commit"
                : "Resume";

    async function resumeWorkflowTransition() {
        if (!workflow || !canResume || controlsBusy || readPending.current) {
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
            {isRefreshing && <p role="status" className="rounded-lg border border-blue-400/30 bg-blue-400/5 p-4 text-sm text-blue-100">Checking current workflow status. Approval and resume controls are unavailable until this check finishes.</p>}
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow</p>
                    <h1 className="mt-3 break-all text-3xl font-bold text-white">Workflow {workflow.workflow_id}</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        {workflow.effect_kind === "operational_action"
                            ? "Review the maintenance request, its approval and current result. Use Resume to advance an approved stage."
                            : "Review this workflow and its exact approval requests. Use Resume to advance an approved stage. Implementation, verification and commit each need their own approval."}
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
                <>
                    <OperationalActionRequestSection request={actionRequest} />
                    <OperationalLifecyclePanel
                        lifecycle={operationalLifecycle}
                        isLoading={isRefreshing && operationalLifecycle === null && lifecycleError === null}
                        isRefreshing={isRefreshing}
                        refreshDisabled={controlsBusy}
                        error={lifecycleError}
                        onRefresh={refreshWorkflow}
                    />
                    <OperationalRecoverySummary
                        diagnostic={recoveryDiagnostic}
                        isLoading={isRefreshing && recoveryDiagnostic === null && diagnosticError === null}
                        error={diagnosticError}
                        supportEvidenceAvailable={operationalLifecycle !== null}
                    />
                    <section aria-labelledby="support-evidence-heading" className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
                        <h2 id="support-evidence-heading" className="text-lg font-semibold text-white">Support evidence</h2>
                        <p className="mt-2 text-sm text-slate-300">Download one bounded, sanitized JSON projection. Nothing is uploaded or persisted by Mission Control.</p>
                        <button type="button" onClick={() => void prepareSupportEvidence()} disabled={isDownloadingSupport} className="mt-4 rounded-lg border border-cyan-400/60 px-3 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50">
                            {isDownloadingSupport ? "Preparing support evidence..." : "Prepare support evidence"}
                        </button>
                        {supportBundle && <><dl className="mt-4 grid gap-3 text-sm md:grid-cols-3"><div><dt className="text-slate-400">Schema</dt><dd className="text-slate-100">{supportBundle.metadata.schema_version}</dd></div><div><dt className="text-slate-400">Generated</dt><dd className="text-slate-100">{supportBundle.metadata.generated_at}</dd></div><div><dt className="text-slate-400">Integrity digest</dt><dd className="break-all text-slate-100">{supportBundle.integrity.digest}</dd></div><div><dt className="text-slate-400">Partial or truncated</dt><dd className="text-slate-100">{supportBundle.lifecycle.availability !== "complete" || supportBundle.truncation.transitions_truncated || supportBundle.truncation.audit_references_truncated || supportBundle.truncation.text_fields_truncated.length > 0 ? "Yes" : "No"}</dd></div></dl><p className="mt-3 text-sm text-slate-300">The digest supports integrity and correlation only; it is not a signature. The bundle is sanitized and no upload occurs automatically.</p><button type="button" onClick={downloadSupportEvidence} className="mt-3 rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950">Download support evidence</button></>}
                        {supportBundleError && <p role="alert" className="mt-3 text-sm text-red-100">{supportBundleError}</p>}
                    </section>
                </>
            )}

            <ExecutionTimeline workflow={workflow} isRefreshing={isRefreshing} refreshDisabled={controlsBusy} onRefresh={refreshWorkflow} />

            {isRepository && workflow.execution.output_capture?.some((item) => item.truncated) && (
                <section aria-labelledby="output-capture-heading" className="rounded-xl border border-amber-500/50 p-5">
                    <h2 id="output-capture-heading" className="font-semibold text-white">Worker output was shortened</h2>
                    <p className="mt-2 text-sm text-slate-300">The worker retained a bounded portion of its output. Verification and commit still require their own approvals.</p>
                    {workflow.execution.output_capture.filter((item) => item.truncated).map((item) => (
                        <p key={item.stream} className="mt-2 text-sm text-slate-400">{item.stream}: {item.retained_bytes} bytes retained; {item.observed_bytes ?? "unknown"} bytes observed.</p>
                    ))}
                </section>
            )}

            {isRepository && workflow.worker_reconciliation?.outcome === "unknown" && (
                <section aria-labelledby="worker-outcome-heading" className="rounded-xl border border-amber-500/50 bg-slate-900/70 p-5">
                    <h2 id="worker-outcome-heading" className="text-lg font-semibold text-white">Worker outcome unknown</h2>
                    <p className="mt-2 text-sm text-slate-300">The worker may have completed the change. Check its original result before taking further action. Do not submit another execution request.</p>
                    <p className="mt-2 break-all text-sm text-slate-400">Original request: {workflow.worker_reconciliation.request_id}</p>
                </section>
            )}

            {isRepository && workflow.worker_reconciliation?.request_digest && (
                <details className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
                    <summary className="cursor-pointer text-sm text-slate-300">Worker request record</summary>
                    <p className="mt-2 break-all text-sm text-slate-400">Request: {workflow.worker_reconciliation.request_id}</p>
                    <p className="mt-2 break-all text-sm text-slate-400">Digest: {workflow.worker_reconciliation.request_digest}</p>
                    <p className="mt-2 text-sm text-slate-400">This identifies the submitted request. It does not grant approval for another action.</p>
                </details>
            )}

            {isRepository && (
                <>
                    <VerificationReviewSection
                        workflow={workflow}
                        canDecideVerification={canDecideVerification}
                        isSubmittingVerification={isSubmittingVerification}
                        actionsDisabled={controlsBusy}
                        verificationApprovalResult={verificationApprovalResult}
                        verificationApprovalError={verificationApprovalError}
                        onVerificationDecision={submitVerificationDecision}
                    />

                    <CommitSection
                        workflow={workflow}
                        canDecideCommit={canDecideCommit}
                        isSubmittingCommit={isSubmittingCommit}
                        actionsDisabled={controlsBusy}
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
                    Approve or reject the exact request shown above. Approval does not run the change; use Resume afterward to advance an approved stage.
                </p>
                {canDecide ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void submitDecision("approve")} disabled={controlsBusy} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">
                            {workflow.effect_kind === "operational_action" ? "Approve Exact Action" : "Approve Implementation"}
                        </button>
                        <button type="button" onClick={() => void submitDecision("reject")} disabled={controlsBusy} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">
                            Reject
                        </button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">{isOperational && workflow.implementation_approval_status === "approved"
                        ? "Exact action approval is recorded."
                        : isOperational && workflow.workflow_state === "awaiting_implementation_approval" && !operationalApprovalReady
                        ? "Exact action approval is unavailable. Refresh to check the request and its approval status."
                        : `Approval controls are unavailable because this workflow is ${formatLabel(workflow.workflow_state)}.`}</p>
                )}
                {isSubmitting && <p role="status" className="mt-3 text-sm text-blue-200">Submitting approval...</p>}
                {approvalResult && approvalResult.implementation_approval_status === "approved" && canResumeImplementation && !controlsBusy && (
                    <p role="status" className="mt-3 text-sm text-emerald-200">{isOperational ? "Action approved. Run it when you are ready." : "Implementation approved. Resume to run this change."}</p>
                )}
                {approvalResult && approvalResult.implementation_approval_status === "rejected" && (
                    <p role="status" className="mt-3 text-sm text-red-100">Approval rejected.</p>
                )}
                {approvalError && <p role="alert" className="mt-3 text-sm text-red-100">{approvalMessage(approvalError)}</p>}
            </section>

            {canResume && (
                <section aria-labelledby="resume-controls-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <h2 id="resume-controls-heading" className="text-lg font-semibold text-white">{canReconcileWorker ? "Check original worker result" : isOperational ? "Run approved maintenance" : "Resume approved stage"}</h2>
                    <p className="mt-2 text-sm text-slate-400">{canReconcileWorker ? "This checks the original request once. It will not run the change again. A recovered change still requires separate verification and commit approvals." : isOperational ? "Submit the approved maintenance request. Atlas checks its execution permissions before acting." : "Use this to advance execution after an approval decision."}</p>
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button
                            type="button"
                            onClick={() => void resumeWorkflowTransition()}
                            disabled={controlsBusy}
                            className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-blue-950 transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {isResuming ? isOperational ? "Submitting..." : "Resuming..." : resumeButtonLabel}
                        </button>
                    </div>
                    {isResuming && <p role="status" className="mt-3 text-sm text-blue-200">{isOperational ? "Submitting the approved action..." : "Resuming workflow..."}</p>}
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

function OperationalActionRequestSection({ request }: { request: WorkflowOperationalActionRequestSummary | null }) {
    if (!request) return <section role="alert" className="rounded-xl border border-amber-400/30 p-5">
        <h2 className="font-semibold text-amber-200">Exact action request unavailable</h2>
        <p className="mt-2 text-sm text-slate-300">Refresh this workflow before reviewing or approving the action.</p>
    </section>;
    return <section aria-labelledby="exact-action-heading" className="space-y-4 rounded-xl border border-cyan-400/30 bg-slate-900/70 p-5">
        <h2 id="exact-action-heading" className="text-lg font-semibold text-white">Exact action request</h2>
        <p className="text-sm text-slate-300">Review this exact target and its verification rules. Approval and running the action are separate steps.</p>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <Detail label="Action" value={formatLabel(request.intended_action)} />
            <Detail label="Target" value={`${request.provider_id}/${request.resource_type}/${request.resource_id}`} />
            <Detail label="Expected starting state" value={request.expected_pre_state} />
            <Detail label="Expected disruption" value={request.disruption_scope} />
            <Detail label="Request expires" value={request.expires_at} />
            <Detail label="Expected outcome" value={request.verification.expected_post_state} />
            <Detail label="Health check" value={request.verification.health_requirement} />
            <Detail label="Uncertain outcome" value={request.verification.unknown_outcome_policy} />
        </dl>
        <details>
            <summary className="mc-focusable cursor-pointer text-sm text-cyan-200">Request references</summary>
            <dl className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
                <Detail label="Request ID" value={request.request_id} />
                <Detail label="Request digest" value={request.request_digest} />
                <Detail label="Target fingerprint" value={request.target_fingerprint} />
                <Detail label="Target version" value={request.target_version ?? "Not supplied"} />
                <Detail label="Generated time" value={request.generated_at} />
            </dl>
        </details>
    </section>;
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
    actionsDisabled,
    verificationApprovalResult,
    verificationApprovalError,
    onVerificationDecision,
}: {
    workflow: WorkflowDetailResponse;
    canDecideVerification: boolean;
    isSubmittingVerification: boolean;
    actionsDisabled: boolean;
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
                <p className="mt-2 text-sm text-slate-400">Review the proposed checks and their recorded results. Verification needs its own approval and a separate Resume step.</p>
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
                        <button type="button" onClick={() => void onVerificationDecision("approve")} disabled={actionsDisabled} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">Approve Verification</button>
                        <button type="button" onClick={() => void onVerificationDecision("reject")} disabled={actionsDisabled} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">Reject Verification</button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">Verification approval controls are unavailable because this workflow is {formatLabel(workflow.workflow_state)}.</p>
                )}
                {isSubmittingVerification && <p role="status" aria-live="polite" className="mt-3 text-sm text-blue-200">Submitting verification approval...</p>}
                {verificationApprovalResult?.verification_approval_status === "approved" && !actionsDisabled && workflow.workflow_state === "awaiting_verification_approval" && workflow.verification_approval_status === "approved" && <p role="status" className="mt-3 text-sm text-emerald-200">Verification approved. Resume to run the checks.</p>}
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
    actionsDisabled,
    commitApprovalResult,
    commitApprovalError,
    onCommitDecision,
}: {
    workflow: WorkflowDetailResponse;
    canDecideCommit: boolean;
    isSubmittingCommit: boolean;
    actionsDisabled: boolean;
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
                    Review and approve or reject this exact local commit request. Approval and resuming the commit are separate steps. This does not push or publish a release.
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
                        <button type="button" onClick={() => void onCommitDecision("approve")} disabled={actionsDisabled} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">Approve Commit</button>
                        <button type="button" onClick={() => void onCommitDecision("reject")} disabled={actionsDisabled} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">Reject Commit</button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">Commit approval controls are unavailable because this workflow is {formatLabel(workflow.workflow_state)}.</p>
                )}
                {isSubmittingCommit && <p role="status" aria-live="polite" className="mt-3 text-sm text-blue-200">Submitting commit approval...</p>}
                {commitApprovalResult?.commit_approval_status === "approved" && !actionsDisabled && workflow.workflow_state === "awaiting_commit_approval" && workflow.commit_approval_status === "approved" && <p role="status" className="mt-3 text-sm text-emerald-200">Commit approved. Resume to finish the local commit.</p>}
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
