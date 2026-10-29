import type { ReactNode } from "react";
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
import { formatResourceReference, formatResourceTargetLabel } from "../utils/resourceLabels";
import { evidenceTimestamp } from "../utils/healthPresentation";
import { workflowRailStages } from "../utils/workflowState";

type LoadMode = "initial" | "refresh";

type WorkflowActionFailure = {
    message: string;
    details: string | null;
};

const actionFailureFallback = "No additional technical details were provided.";

function workflowActionFailure(error: unknown, message: string): WorkflowActionFailure {
    const details = getAtlasAgentErrorMessage(error, actionFailureFallback);
    return {
        message,
        details: details === actionFailureFallback ? null : details,
    };
}

function WorkflowActionError({ failure }: { failure: WorkflowActionFailure }) {
    return (
        <div role="alert" className="mt-3 text-sm text-red-100">
            <p>{failure.message}</p>
            {failure.details && (
                <details className="mt-2">
                    <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                    <p className="mt-2 break-words text-sm text-slate-400">{failure.details}</p>
                </details>
            )}
        </div>
    );
}

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
    const [loadErrorDetails, setLoadErrorDetails] = useState<string | null>(null);
    const [approvalError, setApprovalError] = useState<WorkflowActionFailure | null>(null);
    const [approvalResult, setApprovalResult] = useState<WorkflowImplementationApprovalResponse | null>(null);
    const [isSubmittingVerification, setIsSubmittingVerification] = useState(false);
    const [verificationApprovalError, setVerificationApprovalError] = useState<WorkflowActionFailure | null>(null);
    const [verificationApprovalResult, setVerificationApprovalResult] = useState<WorkflowVerificationApprovalResponse | null>(null);
    const [isSubmittingCommit, setIsSubmittingCommit] = useState(false);
    const [commitApprovalError, setCommitApprovalError] = useState<WorkflowActionFailure | null>(null);
    const [commitApprovalResult, setCommitApprovalResult] = useState<WorkflowCommitApprovalResponse | null>(null);
    const [isResuming, setIsResuming] = useState(false);
    const [resumeError, setResumeError] = useState<WorkflowActionFailure | null>(null);
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
        setLoadErrorDetails(null);
        try {
            const detail = await getWorkflowDetail(workflowId);
            if (sequence !== readSequence.current) return;
            if (detail && detail.workflow_id !== workflowId) {
                setWorkflow(null);
                setLoadError("The returned workflow does not match this page.");
                setLoadErrorDetails("The workflow ID in the response differs from the requested workflow.");
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
                    nextDiagnosticError = "Mission Control could not check the latest recovery status.";
                } else if (diagnosticResult.value && diagnosticResult.value.correlation?.workflow_id !== workflowId) {
                    nextDiagnosticError = "The returned status does not match this workflow.";
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
            if (sequence === readSequence.current) {
                const malformed = error instanceof Error && error.message === "Malformed workflow detail payload.";
                setLoadError(malformed
                    ? "Atlas couldn’t read this workflow’s details. Try again to reload them."
                    : "Atlas couldn’t load this workflow, so its status is unknown.");
                setLoadErrorDetails(getAtlasAgentErrorMessage(error, "Atlas Agent unavailable."));
            }
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
                setSupportBundleError("Support information is not available for this maintenance request.");
                return;
            }
            setSupportBundle(bundle);
        } catch {
            setSupportBundleError("Mission Control could not prepare a support file.");
        } finally {
            setIsDownloadingSupport(false);
        }
    }

    function downloadSupportEvidence() {
        if (!supportBundle?.applicable) return;
        setSupportBundleError(null);
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
            setSupportBundleError("Mission Control could not download the support file. Try again.");
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
            setApprovalError(workflowActionFailure(
                error,
                workflow.effect_kind === "operational_action"
                    ? "Mission Control could not confirm the maintenance approval decision. The workflow status was refreshed; check its current status before taking another step."
                    : "Mission Control could not confirm the implementation approval decision. The workflow status was refreshed; check its current approval status before taking another step.",
            ));
            await loadWorkflow("refresh");
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
            setVerificationApprovalError(workflowActionFailure(
                error,
                "Mission Control could not confirm the verification approval decision. The workflow status was refreshed; check its current approval status before taking another step.",
            ));
            await loadWorkflow("refresh");
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
            setCommitApprovalError(workflowActionFailure(
                error,
                "Mission Control could not confirm the commit approval decision. The workflow status was refreshed; check its current approval status before taking another step.",
            ));
            await loadWorkflow("refresh");
        } finally {
            setIsSubmittingCommit(false);
        }
    }
    if (isLoading) {
        return (
            <main className="mx-auto max-w-6xl p-4 sm:p-8">
                <p role="status" className="text-slate-300">Loading workflow...</p>
            </main>
        );
    }

    if (loadError) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-8">
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-lg font-semibold text-red-100">Workflow unavailable</h1>
                    <p className="mt-2 text-sm text-red-100">{loadError}</p>
                    {loadErrorDetails && (
                        <details className="mt-3">
                            <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                            <p className="mt-2 break-words text-sm text-slate-400">{loadErrorDetails}</p>
                        </details>
                    )}
                    <button type="button" onClick={() => void loadWorkflow()} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>
                </section>
                <Link to="/workflows" className="text-sm text-blue-300">← All workflows</Link>
            </main>
        );
    }

    if (!workflow) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-8">
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
        (workflow.workflow_state === "awaiting_implementation_approval" || workflow.workflow_state === "awaiting_execution")
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
    const supportBundleIsIncomplete = Boolean(supportBundle && (
        supportBundle.lifecycle.availability !== "complete"
        || supportBundle.truncation.transitions_truncated
        || supportBundle.truncation.audit_references_truncated
        || supportBundle.truncation.text_fields_truncated.length > 0
    ));

    const resumeButtonLabel = canReconcileWorker
        ? "Check worker result"
        : canResumeImplementation
        ? isOperational ? "Run approved maintenance" : "Run approved change"
        : canResumeVerification
            ? "Run approved checks"
            : canResumeCommit
                ? "Record approved commit"
                : "Continue workflow";
    const resumingButtonLabel = canReconcileWorker
        ? "Checking worker result..."
        : canResumeImplementation
            ? isOperational ? "Submitting..." : "Running approved change..."
            : canResumeVerification
                ? "Running approved checks..."
                : canResumeCommit
                    ? "Recording approved commit..."
                    : "Working...";
    const resumingStatusLabel = canReconcileWorker
        ? "Checking the original worker result..."
        : canResumeImplementation
            ? isOperational ? "Submitting the approved maintenance request..." : "Running the approved change..."
            : canResumeVerification
                ? "Running the approved checks..."
                : canResumeCommit
                    ? "Recording the approved local commit..."
                    : "Continuing the workflow...";

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
            setResumeError(workflowActionFailure(
                error,
                "Mission Control could not confirm the workflow result. The workflow status was refreshed; review its current stage before taking another step.",
            ));
            await loadWorkflow("refresh");
        } finally {
            setIsResuming(false);
        }
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
            {isRefreshing && <p role="status" className="rounded-lg border border-blue-400/30 bg-blue-400/5 p-4 text-sm text-blue-100">Checking current workflow status. Approval and action buttons are unavailable until this check finishes.</p>}
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">{isOperational ? "Maintenance" : "Workflow"}</p>
                    <h1 className="mt-3 text-3xl font-bold text-white">{isOperational ? "Review maintenance request" : "Review workflow"}</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        {workflow.effect_kind === "operational_action"
                            ? "Review the exact maintenance request below. Approval and running it are separate steps."
                            : "Each change, check and commit needs its own approval. After approval, choose the matching action to continue."}
                    </p>
                </div>
                {isRepository && <WorkflowRail workflow={workflow} />}
            </header>

            <section aria-labelledby="workflow-summary-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="workflow-summary-heading" className="text-lg font-semibold text-white">Workflow summary</h2>
                <p className="mt-1 text-sm text-slate-300">{workflowStatusMessage(workflow)}</p>
                <details className="mt-4 rounded-lg border border-slate-800 px-4 py-3">
                    <summary className="mc-focusable cursor-pointer text-sm font-semibold text-blue-200">Workflow details</summary>
                    <dl className="mt-3 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Workflow ID" value={workflow.workflow_id} />
                        <Detail label="Workflow state" value={formatLabel(workflow.workflow_state)} />
                        <Detail label={isOperational ? "Maintenance request approval" : "Implementation approval"} value={formatLabel(workflow.implementation_approval_status)} />
                        <Detail label="Workflow source" value={workflow.workflow_source} />
                        <Detail label="Planning session" value={workflow.planning_session_id ?? "Not available"} />
                        <Detail label="Candidate ID" value={workflow.candidate_id ?? "Not available"} />
                        <Detail label="Candidate fingerprint" value={workflow.candidate_fingerprint ?? "Not available"} />
                        <Detail label="Plan fingerprint" value={workflow.plan_fingerprint ?? "Not available"} />
                        {isRepository && <>
                            <Detail label="Verification approval" value={formatLabel(workflow.verification_approval_status)} />
                            <Detail label="Commit approval" value={formatLabel(workflow.commit_approval_status)} />
                            <Detail label="Repository" value={workflow.repository ?? "Not available"} />
                            <Detail label="Working directory" value={workflow.working_directory ?? "Not available"} />
                            <Detail label="Translator version" value={workflow.translator_version ?? "Not available"} />
                            <Detail label="Affected files" value={workflow.affected_files.length > 0 ? workflow.affected_files.join(", ") : "None reported"} />
                        </>}
                    </dl>
                </details>
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
                    <details className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
                        <summary className="mc-focusable cursor-pointer text-lg font-semibold text-white">Optional support file</summary>
                        <div className="mt-3">
                            <p className="text-sm text-slate-300">Prepare a sanitized support file to review. Atlas does not upload it; you choose if and when to download or share it.</p>
                            <button type="button" onClick={() => void prepareSupportEvidence()} disabled={isDownloadingSupport} className="mt-4 rounded-lg border border-cyan-400/60 px-3 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50">
                                {isDownloadingSupport ? "Preparing support file..." : supportBundleError && !supportBundle ? "Retry support file" : "Prepare support file"}
                            </button>
                            {supportBundle && <>
                                <p role="status" className="mt-3 text-sm text-slate-200">{supportBundleIsIncomplete ? "Support file ready. Some information is missing or shortened." : "Support file ready to download."}</p>
                                <details className="mt-3">
                                    <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                                    <dl className="mt-3 grid gap-3 text-sm md:grid-cols-3">
                                        <div><dt className="text-slate-400">File format</dt><dd className="text-slate-100">{supportBundle.metadata.schema_version}</dd></div>
                                        <div><dt className="text-slate-400">Generated (local time)</dt><dd className="text-slate-100">{formatRequestTimestamp(supportBundle.metadata.generated_at, false)}</dd></div>
                                        <div><dt className="text-slate-400">Integrity digest</dt><dd className="break-all text-slate-100">{supportBundle.integrity.digest}</dd></div>
                                        <div><dt className="text-slate-400">Information shortened</dt><dd className="text-slate-100">{supportBundleIsIncomplete ? "Yes" : "No"}</dd></div>
                                    </dl>
                                    <p className="mt-3 text-sm text-slate-300">The digest helps identify the file; it is not a digital signature.</p>
                                </details>
                                <button type="button" onClick={downloadSupportEvidence} className="mt-3 rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950">Download support file</button>
                            </>}
                            {supportBundleError && <p role="alert" className="mt-3 text-sm text-red-100">{supportBundleError}</p>}
                        </div>
                    </details>
                </>
            )}

            <ExecutionTimeline workflow={workflow} isRefreshing={isRefreshing} refreshDisabled={controlsBusy} onRefresh={refreshWorkflow} />

            {isRepository && workflow.execution.output_capture?.some((item) => item.truncated) && (
                <section aria-labelledby="output-capture-heading" className="rounded-xl border border-amber-500/50 p-5">
                    <h2 id="output-capture-heading" className="font-semibold text-white">Worker output was shortened</h2>
                    <p className="mt-2 text-sm text-slate-300">Only part of the worker's output is shown. Verification and commit each need separate approval.</p>
                    <details className="mt-3 text-sm text-slate-300">
                        <summary className="mc-focusable cursor-pointer text-blue-200">Output details</summary>
                        {workflow.execution.output_capture.filter((item) => item.truncated).map((item) => (
                            <p key={item.stream} className="mt-2 text-slate-400">{item.stream}: {item.retained_bytes} bytes retained; {item.observed_bytes ?? "unknown"} bytes observed.</p>
                        ))}
                    </details>
                </section>
            )}

            {isRepository && workflow.worker_reconciliation?.outcome === "unknown" && (
                <section aria-labelledby="worker-outcome-heading" className="rounded-xl border border-amber-500/50 bg-slate-900/70 p-5">
                    <h2 id="worker-outcome-heading" className="text-lg font-semibold text-white">Worker result not confirmed</h2>
                    <p className="mt-2 text-sm text-slate-300">The change may have finished. Check its original result before starting it again.</p>
                </section>
            )}

            {isRepository && workflow.worker_reconciliation && (workflow.worker_reconciliation.request_digest || workflow.worker_reconciliation.outcome === "unknown") && (
                <details className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
                    <summary className="cursor-pointer text-sm text-slate-300">Request details</summary>
                    <p className="mt-2 break-all text-sm text-slate-400">Request ID: {workflow.worker_reconciliation.request_id}</p>
                    {workflow.worker_reconciliation.request_digest && <p className="mt-2 break-all text-sm text-slate-400">Request digest: {workflow.worker_reconciliation.request_digest}</p>}
                    <p className="mt-2 text-sm text-slate-400">This identifies the submitted request. It does not approve another action.</p>
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

                    {shouldShowCommitSection(workflow) && <CommitSection
                        workflow={workflow}
                        canDecideCommit={canDecideCommit}
                        isSubmittingCommit={isSubmittingCommit}
                        actionsDisabled={controlsBusy}
                        commitApprovalResult={commitApprovalResult}
                        commitApprovalError={commitApprovalError}
                        onCommitDecision={submitCommitDecision}
                    />}
                </>
            )}

            <section aria-labelledby="approval-controls-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="approval-controls-heading" className="text-lg font-semibold text-white">
                    {isOperational ? "Maintenance request approval" : "Implementation approval"}
                </h2>
                <p className="mt-2 text-sm text-slate-400">
                    {isOperational
                        ? "Approve or reject this exact maintenance request. Approval does not run it; choose Run approved maintenance separately when you are ready."
                        : "Approve or reject the exact implementation request shown above. Approval does not run the change; choose Run approved change when you are ready."}
                </p>
                {canDecide ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void submitDecision("approve")} disabled={controlsBusy} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">
                            {isOperational ? "Approve maintenance request" : "Approve Implementation"}
                        </button>
                        <button type="button" onClick={() => void submitDecision("reject")} disabled={controlsBusy} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">
                            {isOperational ? "Reject maintenance request" : "Reject implementation"}
                        </button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">{isOperational && workflow.implementation_approval_status === "approved"
                        ? "Maintenance request approval is recorded."
                        : workflow.implementation_approval_status === "approved"
                        ? "Implementation approval is recorded."
                        : workflow.implementation_approval_status === "rejected"
                        ? isOperational
                            ? "Maintenance request approval was rejected. No further decision is available."
                            : "Implementation approval was rejected. No further decision is available."
                        : isOperational && workflow.workflow_state === "awaiting_implementation_approval" && !operationalApprovalReady
                        ? "Maintenance request approval is unavailable. Refresh to check the request and its approval status."
                        : "Implementation approval is not available at this step."}</p>
                )}
                {isSubmitting && <p role="status" className="mt-3 text-sm text-blue-200">{isOperational ? "Submitting maintenance approval..." : "Submitting implementation approval..."}</p>}
                {approvalResult && approvalResult.implementation_approval_status === "approved" && canResumeImplementation && !controlsBusy && (
                    <p role="status" className="mt-3 text-sm text-emerald-200">{isOperational ? "Maintenance request approved. Run it when you are ready." : "Change approved. Run it when you are ready."}</p>
                )}
                {approvalResult && approvalResult.implementation_approval_status === "rejected" && (
                    <p role="status" className="mt-3 text-sm text-red-100">{isOperational ? "Maintenance request rejected." : "Implementation request rejected."}</p>
                )}
                {approvalError && <WorkflowActionError failure={approvalError} />}
            </section>

            {canResume && (
                <section aria-labelledby="resume-controls-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <h2 id="resume-controls-heading" className="text-lg font-semibold text-white">Next step</h2>
                    <p className="mt-2 text-sm text-slate-400">{canReconcileWorker
                        ? "This checks the original request once. It will not run the change again. A recovered change still requires separate verification and commit approvals."
                        : isOperational
                            ? "Submit the approved maintenance request. Atlas checks its execution permissions before acting."
                            : canResumeImplementation
                                ? "This runs the approved change."
                                : canResumeVerification
                                    ? "This runs the checks you approved."
                                    : "This records the local commit you approved. It does not push or publish."}</p>
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button
                            type="button"
                            onClick={() => void resumeWorkflowTransition()}
                            disabled={controlsBusy}
                            className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-blue-950 transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {isResuming ? resumingButtonLabel : resumeButtonLabel}
                        </button>
                    </div>
                    {isResuming && <p role="status" className="mt-3 text-sm text-blue-200">{resumingStatusLabel}</p>}
                    {resumeError && <WorkflowActionError failure={resumeError} />}
                </section>
            )}

            <Link
                to={workflow.workflow_source === "candidate" ? "/execution-candidates" : "/workflows"}
                className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
                {workflow.workflow_source === "candidate" ? "Back to execution candidates" : "← All workflows"}
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
        <h2 className="font-semibold text-amber-200">Maintenance request unavailable</h2>
        <p className="mt-2 text-sm text-slate-300">Refresh this workflow before reviewing or approving the maintenance request.</p>
    </section>;
    return <section aria-labelledby="maintenance-request-heading" className="space-y-4 rounded-xl border border-cyan-400/30 bg-slate-900/70 p-5">
        <h2 id="maintenance-request-heading" className="text-lg font-semibold text-white">Maintenance request</h2>
        <p className="text-sm text-slate-300">Review the selected service and target, expected interruption, and how Atlas will verify the result. Approval and running the maintenance are separate steps.</p>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <Detail label="Action" value={formatLabel(request.intended_action)} />
            <Detail label="Target" value={formatResourceTargetLabel(request.provider_id, request.resource_type, request.resource_id)} />
            <Detail label="Expected starting state" value={request.expected_pre_state} />
            <Detail label="Expected disruption" value={request.disruption_scope} />
            <Detail label="Request expires (local time)" value={formatRequestTimestamp(request.expires_at, true)} />
            <Detail label="Expected outcome" value={request.verification.expected_post_state} />
            <Detail label="Health check" value={request.verification.health_requirement} />
            <Detail label="Uncertain outcome" value={request.verification.unknown_outcome_policy} />
        </dl>
        <details>
            <summary className="mc-focusable cursor-pointer text-sm text-cyan-200">Request references</summary>
            <dl className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
                <Detail label="Request ID" value={request.request_id} />
                <Detail label="Request digest" value={request.request_digest} />
                <Detail label="Target reference" value={formatResourceReference(request.provider_id, request.resource_type, request.resource_id)} />
                <Detail label="Target fingerprint" value={request.target_fingerprint} />
                <Detail label="Target version" value={request.target_version ?? "Not supplied"} />
                <Detail label="Generated (local time)" value={formatRequestTimestamp(request.generated_at, false)} />
            </dl>
        </details>
    </section>;
}

function ImplementationRequestSection({ workflow }: { workflow: WorkflowDetailResponse }) {
    const request = workflow.implementation_request;

    return (
        <section aria-labelledby="implementation-request-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 id="implementation-request-heading" className="text-lg font-semibold text-white">Change details</h2>
            <p className="mt-2 text-sm text-slate-400">Review the tool and files involved in this proposed change.</p>
            {request ? (
                <>
                    <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Tool" value={request.tool} />
                        <Detail label="Affected files" value={request.affected_files.length > 0 ? request.affected_files.join(", ") : "None reported"} />
                    </dl>
                    <details className="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                            <Detail label="Working directory" value={request.working_directory} />
                            <Detail label="Repository" value={request.repository} />
                            <Detail label="Translator version" value={request.translator_version ?? "Not available"} />
                            <Detail label="Request ID" value={request.immutable_request_id} />
                        </dl>
                    </details>
                </>
            ) : (
                <p role="alert" className="mt-4 text-sm text-amber-100">Change details are unavailable. Refresh this workflow before continuing.</p>
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
    verificationApprovalError: WorkflowActionFailure | null;
    onVerificationDecision: (decision: WorkflowImplementationDecision) => Promise<void>;
}) {
    const plan = workflow.verification_plan;
    const evidence = workflow.verification_evidence;
    const review = workflow.review;
    const reviewDecision = review.approved === null
        ? review.review_result ?? review.review_status
        : review.approved ? "approved" : "failed";
    const hasVerificationResults = evidence.verification_status !== null
        || evidence.completed_time !== null
        || evidence.executed_checks.length > 0
        || evidence.check_results.length > 0
        || evidence.repository_head !== null
        || evidence.changed_files_digest !== null;
    const hasReviewResults = review.review_result !== null
        || review.review_status !== null
        || review.approved !== null
        || review.evidence_summary !== null
        || review.changed_files.length > 0
        || review.review_fingerprint !== null;
    const awaitingVerificationApproval = workflow.workflow_state === "awaiting_verification_approval";

    return (
        <section aria-labelledby="verification-review-heading" className="space-y-5 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div>
                <h2 id="verification-review-heading" className="text-lg font-semibold text-white">Verification and review</h2>
                <p className="mt-2 text-sm text-slate-400">Review the planned checks and their results. Approve the checks before Atlas runs them.</p>
            </div>

            <details className="rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3">
                <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Verification Plan ID" value={plan.verification_plan_id ?? "Not available"} />
                    <Detail label="Verifier Version" value={plan.verifier_version ?? "Not available"} />
                    <Detail label="Changed-files digest" value={plan.changed_files_digest ?? "Not available"} />
                    <Detail label="Verification check IDs" value={plan.verification_check_ids.length > 0 ? plan.verification_check_ids.join(", ") : "None reported"} />
                    <Detail label="Working directory" value={plan.working_directory ?? "Not available"} />
                    <Detail label="Repository" value={plan.repository ?? "Not available"} />
                    <Detail label="Repository HEAD" value={evidence.repository_head ?? "Not available"} />
                    <Detail label="Evidence changed-files digest" value={evidence.changed_files_digest ?? "Not available"} />
                    <Detail label="Review result" value={review.review_result ? formatLabel(review.review_result) : "Not available"} />
                    <Detail label="Review status" value={review.review_status ? formatLabel(review.review_status) : "Not available"} />
                    <Detail label="Review fingerprint" value={review.review_fingerprint ?? "Not available"} />
                    <Detail label="Model-assisted review" value={review.model_assisted_review} />
                </dl>
            </details>

            <section aria-labelledby="verification-plan-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="verification-plan-heading" className="text-base font-semibold text-white">Checks to run</h3>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Planned checks" value={plan.command_backed_checks.length > 0 ? plan.command_backed_checks.join(", ") : "None reported"} />
                </dl>
            </section>

            {(hasVerificationResults || awaitingVerificationApproval) && <section aria-labelledby="verification-evidence-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="verification-evidence-heading" className="text-base font-semibold text-white">Check results</h3>
                {hasVerificationResults ? (
                    <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Result" value={evidence.verification_status ? formatLabel(evidence.verification_status) : "Not available"} />
                        <Detail label="Completed" value={evidence.completed_time ?? "Not available"} />
                        <Detail label="Checks run" value={evidence.executed_checks.length > 0 ? evidence.executed_checks.join(", ") : "None reported"} />
                        <Detail label="Results" value={evidence.check_results.length > 0 ? evidence.check_results.map((check) => `${String(check.identifier)}: ${String(check.status)}`).join(", ") : "None reported"} />
                    </dl>
                ) : (
                    <p className="mt-3 text-sm text-slate-300">
                        {awaitingVerificationApproval && workflow.verification_approval_status === "pending"
                            ? "Review these checks. Approve them before Atlas runs them."
                            : awaitingVerificationApproval && workflow.verification_approval_status === "approved"
                                ? "Checks are approved. Run them when you are ready."
                                : "Check results will appear after implementation and verification finish."}
                    </p>
                )}
            </section>}

            {(hasReviewResults || awaitingVerificationApproval) && <section aria-labelledby="review-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="review-heading" className="text-base font-semibold text-white">Review</h3>
                {hasReviewResults ? (
                    <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Decision" value={reviewDecision ? formatLabel(reviewDecision) : "Not available"} />
                        <Detail label="Summary" value={formatReviewEvidenceSummary(review.evidence_summary)} />
                        <Detail label="Changed files" value={review.changed_files.length > 0 ? review.changed_files.join(", ") : "None reported"} />
                    </dl>
                ) : (
                    <p className="mt-3 text-sm text-slate-300">Review results will appear after verification runs.</p>
                )}
            </section>}

            {shouldShowVerificationApprovalSection(workflow, verificationApprovalResult, verificationApprovalError) && <section aria-labelledby="verification-approval-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="verification-approval-heading" className="text-base font-semibold text-white">Verification approval</h3>
                <p className="mt-2 text-sm text-slate-400">These controls submit only the workflow ID and verification approval decision. Approved checks run only after you choose Run approved checks.</p>
                {canDecideVerification ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                        <button type="button" onClick={() => void onVerificationDecision("approve")} disabled={actionsDisabled} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">Approve Verification</button>
                        <button type="button" onClick={() => void onVerificationDecision("reject")} disabled={actionsDisabled} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60">Reject Verification</button>
                    </div>
                ) : (
                    <p className="mt-4 text-sm text-slate-300">{workflow.verification_approval_status === "approved"
                        ? "Verification approval is recorded."
                        : workflow.verification_approval_status === "rejected"
                            ? "Verification approval was rejected. No further decision is available."
                            : "Verification approval is not available at this step."}</p>
                )}
                {isSubmittingVerification && <p role="status" aria-live="polite" className="mt-3 text-sm text-blue-200">Submitting verification approval...</p>}
                {verificationApprovalResult?.verification_approval_status === "approved" && !actionsDisabled && workflow.workflow_state === "awaiting_verification_approval" && workflow.verification_approval_status === "approved" && <p role="status" className="mt-3 text-sm text-emerald-200">Checks approved. Run them when you are ready.</p>}
                {verificationApprovalResult?.verification_approval_status === "rejected" && <p role="status" className="mt-3 text-sm text-red-100">Verification approval rejected.</p>}
                {verificationApprovalError && <WorkflowActionError failure={verificationApprovalError} />}
            </section>}

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
    commitApprovalError: WorkflowActionFailure | null;
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
                    Review and approve or reject this exact local commit request. Approval does not record it; choose Record approved commit when you are ready. This does not push or publish a release.
                </p>
            </div>

            <section aria-labelledby="commit-request-heading" className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 id="commit-request-heading" className="text-base font-semibold text-white">Commit details</h3>
                {request ? (
                    <>
                        <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                            <Detail label="Branch" value={request.branch ?? "Not available"} />
                            <Detail label="Commit message" value={request.commit_message} />
                            <Detail label="Reviewed files" value={request.reviewed_files.length > 0 ? request.reviewed_files.join(", ") : "None reported"} />
                            <Detail label="Commit approval status" value={formatLabel(request.commit_approval_status)} />
                        </dl>
                        <details className="mt-4 rounded-lg border border-slate-800 px-4 py-3">
                            <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                            <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                                <Detail label="Commit request ID" value={request.commit_request_id} />
                                <Detail label="Repository" value={request.repository ?? "Not available"} />
                                <Detail label="Expected HEAD" value={request.expected_head ?? "Not available"} />
                                <Detail label="Reviewed-content fingerprint" value={request.reviewed_content_fingerprint} />
                            </dl>
                        </details>
                    </>
                ) : (
                    <p className="mt-3 text-sm text-slate-300">Commit details are unavailable for this workflow.</p>
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
                    <p className="mt-4 text-sm text-slate-300">{workflow.commit_approval_status === "approved"
                        ? "Commit approval is recorded."
                        : workflow.commit_approval_status === "rejected"
                            ? "Commit approval was rejected. No further decision is available."
                            : "Commit approval is not available at this step."}</p>
                )}
                {isSubmittingCommit && <p role="status" aria-live="polite" className="mt-3 text-sm text-blue-200">Submitting commit approval...</p>}
                {commitApprovalResult?.commit_approval_status === "approved" && !actionsDisabled && workflow.workflow_state === "awaiting_commit_approval" && workflow.commit_approval_status === "approved" && <p role="status" className="mt-3 text-sm text-emerald-200">Commit approved. Record it when you are ready.</p>}
                {commitApprovalResult?.commit_approval_status === "rejected" && <p role="status" className="mt-3 text-sm text-red-100">Commit approval rejected.</p>}
                {commitApprovalError && <WorkflowActionError failure={commitApprovalError} />}
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

function WorkflowRail({ workflow }: { workflow: WorkflowDetailResponse }) {
    const stages = workflowRailStages(workflow);
    return (
        <section aria-label="Read-only workflow rail" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <WorkflowMiniRail stages={stages} />
        </section>
    );
}

function formatRequestTimestamp(value: string, isExpiry: boolean): ReactNode {
    const timestamp = evidenceTimestamp(value);
    if (timestamp === null) return isExpiry ? "Unverified expiry" : "Time unavailable";
    return <time dateTime={value}>{new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>;
}

function Detail({ label, value }: { label: string; value: ReactNode }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}

function workflowStatusMessage(workflow: WorkflowDetailResponse): string {
    const action = workflow.effect_kind === "operational_action" ? "Maintenance request" : "Implementation";
    switch (workflow.workflow_state) {
        case "planned":
            return "Workflow is ready for review.";
        case "awaiting_approval":
            return "Prepare the change for review.";
        case "awaiting_implementation_approval":
            if (workflow.implementation_approval_status === "approved") return `${action} is approved. Run it when ready.`;
            if (workflow.implementation_approval_status === "rejected") return `${action} approval was rejected.`;
            return `${action} needs approval.`;
        case "awaiting_execution":
            if (workflow.implementation_approval_status === "approved") return `${action} is approved and ready to run.`;
            if (workflow.implementation_approval_status === "rejected") return `${action} approval was rejected.`;
            return `${action} approval is not confirmed. Refresh before running it.`;
        case "executing":
            return `${action} is running.`;
        case "patch_applied_pending_verification":
            return "Implementation is complete. Verification is next.";
        case "awaiting_verification_approval":
            if (workflow.verification_approval_status === "approved") return "Checks are approved. Run them when you are ready.";
            if (workflow.verification_approval_status === "rejected") return "Verification approval was rejected.";
            return "Verification needs approval.";
        case "verifying":
            return "Verification checks are running.";
        case "awaiting_commit_approval":
            if (workflow.commit_approval_status === "approved") return "Commit is approved. Record it when you are ready.";
            if (workflow.commit_approval_status === "rejected") return "Commit approval was rejected.";
            return "Commit needs approval.";
        case "committing":
            return "The commit is being recorded.";
        case "blocked":
            return workflow.worker_reconciliation?.outcome === "unknown"
                ? "Atlas couldn't confirm whether the change finished. Check its result before starting the change again."
                : "Workflow is blocked. Review the request and latest result below.";
        case "implementation_rejected":
            return "Implementation approval was rejected.";
        case "completed":
            return "Workflow completed.";
        default:
            return "Current workflow status is unavailable. Review Workflow details.";
    }
}

function shouldShowCommitSection(workflow: WorkflowDetailResponse): boolean {
    const result = workflow.commit_result;
    const commitHasStarted = workflow.workflow_state === "awaiting_commit_approval"
        || workflow.workflow_state === "committing"
        || workflow.workflow_state === "completed";
    const commitResultExists = result.commit_sha !== null
        || result.commit_message !== null
        || result.committed_files.length > 0
        || result.completion_time !== null;
    return workflow.commit_request !== null || commitHasStarted || commitResultExists;
}

function shouldShowVerificationApprovalSection(
    workflow: WorkflowDetailResponse,
    approvalResult: WorkflowVerificationApprovalResponse | null,
    approvalError: WorkflowActionFailure | null,
): boolean {
    return workflow.workflow_state === "awaiting_verification_approval"
        || workflow.verification_approval_status === "approved"
        || workflow.verification_approval_status === "rejected"
        || approvalResult !== null
        || approvalError !== null;
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatReviewEvidenceSummary(value: string | null): string {
    if (!value) return "Not available";

    const match = value.match(/^(\d+) findings?, (\d+) recommendations?$/);
    if (!match) return value;

    const findingCount = Number(match[1]);
    const recommendationCount = Number(match[2]);
    if (findingCount === 0 && recommendationCount === 0) return "No findings or recommendations.";

    const findings = findingCount === 0
        ? "no findings"
        : `${findingCount} finding${findingCount === 1 ? "" : "s"}`;
    const recommendations = recommendationCount === 0
        ? "no recommendations"
        : `${recommendationCount} recommendation${recommendationCount === 1 ? "" : "s"}`;
    return `${findings[0].toUpperCase()}${findings.slice(1)} and ${recommendations}.`;
}
