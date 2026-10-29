import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import {
    getAtlasAgentErrorMessage,
    getWorkflowAudit,
    getWorkflowOperationalLifecycle,
} from "../api/atlas-agent";
import type { WorkflowAuditResponse, WorkflowAuditStageName, WorkflowAuditStageStatus, WorkflowOperationalLifecycle } from "../types/atlasAgent";
import { OperationalLifecyclePanel } from "../components/OperationalLifecyclePanel";
import { useCallback, useEffect, useRef, useState } from "react";
import { evidenceTimestamp } from "../utils/healthPresentation";

interface AuditStageDefinition {
    stage: WorkflowAuditStageName;
    title: string;
    details: (audit: WorkflowAuditResponse) => { label: string; value: ReactNode }[];
}

const AUDIT_STAGE_ORDER: AuditStageDefinition[] = [
    {
        stage: "candidate",
        title: "Change proposal",
        details: (audit) => [
            { label: "Candidate ID", value: audit.candidate.candidate_id ?? "Not started" },
            { label: "Candidate fingerprint", value: audit.candidate.candidate_fingerprint ?? "Not exposed" },
            { label: "Source recommendation ID", value: audit.candidate.source_recommendation_id ?? "Not exposed" },
            { label: "Target ID", value: audit.candidate.target_id ?? "Not exposed" },
            { label: "Target type", value: audit.candidate.target_type ?? "Not exposed" },
        ],
    },
    {
        stage: "planning",
        title: "Planning",
        details: (audit) => [
            { label: "Planning session ID", value: audit.planning.planning_session_id ?? "Not started" },
            { label: "Planning state", value: audit.planning.planning_state ?? "Not exposed" },
            { label: "Planning status", value: audit.planning.planning_status ?? "Not exposed" },
            { label: "Created (local time)", value: formatAuditTimestamp(audit.planning.created_at) },
            { label: "Planning completed (local time)", value: formatAuditTimestamp(audit.planning.planning_completed_at) },
        ],
    },
    {
        stage: "plan",
        title: "Change plan",
        details: (audit) => [
            { label: "Plan ID", value: audit.plan.plan_id ?? "Not started" },
            { label: "Candidate plan fingerprint", value: audit.plan.candidate_plan_fingerprint ?? "Not exposed" },
            { label: "Likely affected files", value: audit.plan.likely_affected_files.length > 0 ? audit.plan.likely_affected_files.join(", ") : "None reported" },
        ],
    },
    {
        stage: "workflow",
        title: "Workflow setup",
        details: (audit) => [
            { label: "Workflow ID", value: audit.workflow.workflow_id },
            { label: "Workflow state", value: formatStatusLabel(audit.workflow.workflow_state) },
            { label: "Workflow source", value: audit.workflow.workflow_source },
        ],
    },
    {
        stage: "implementation",
        title: "Change request",
        details: (audit) => [
            { label: "Implementation request ID", value: audit.implementation.implementation_request_id ?? "Not started" },
            { label: "Execution intent", value: audit.implementation.execution_intent ?? "Not exposed" },
            { label: "Tool", value: audit.implementation.tool ?? "Not exposed" },
            { label: "Repository root", value: audit.implementation.repository_root ?? "Not exposed" },
            { label: "Repository HEAD", value: audit.implementation.repository_head ?? "Not exposed" },
            { label: "Repository branch", value: audit.implementation.repository_branch ?? "Not exposed" },
            { label: "Working directory", value: audit.implementation.working_directory ?? "Not exposed" },
            { label: "Affected files", value: audit.implementation.affected_files.length > 0 ? audit.implementation.affected_files.join(", ") : "None reported" },
            { label: "Translator version", value: audit.implementation.translator_version ?? "Not exposed" },
        ],
    },
    {
        stage: "approvals",
        title: "Change approval",
        details: (audit) => [
            { label: "Workflow approval status", value: formatStatusLabel(audit.approvals.implementation.status) },
            { label: "Implementation approval ID", value: audit.approvals.implementation.approval_id ?? "Not started" },
            { label: "Overall approval decision", value: formatStatusLabel(audit.approvals.status) },
        ],
    },
    {
        stage: "execution",
        title: "Apply change",
        details: (audit) => [
            { label: "Execution status", value: formatStatusLabel(audit.execution.execution_status ?? "not_reached") },
            { label: "Execution request ID", value: audit.execution.execution_request_id ?? "Not started" },
            { label: "Changed files count", value: String(audit.execution.changed_files_count) },
            { label: "Changed files", value: audit.execution.changed_files.length > 0 ? audit.execution.changed_files.join(", ") : "None reported" },
            { label: "Tool", value: audit.execution.tool ?? "Not exposed" },
            { label: "Repository", value: audit.execution.repository ?? "Not exposed" },
        ],
    },
    {
        stage: "verification",
        title: "Checks to run",
        details: (audit) => [
            { label: "Verification plan ID", value: audit.verification.verification_plan_id ?? "Not started" },
            { label: "Verification status", value: formatStatusLabel(audit.verification.verification_status ?? "not_reached") },
            { label: "Changed files digest", value: audit.verification.changed_files_digest ?? "Not exposed" },
            { label: "Verification check IDs", value: audit.verification.verification_check_ids.length > 0 ? audit.verification.verification_check_ids.join(", ") : "None reported" },
            { label: "Repository head", value: audit.verification.repository_head ?? "Not exposed" },
            { label: "Verification started (local time)", value: formatAuditTimestamp(audit.verification.verification_started_at) },
            { label: "Verification completed (local time)", value: formatAuditTimestamp(audit.verification.verification_completed_at) },
        ],
    },
    {
        stage: "verification",
        title: "Verification approval",
        details: (audit) => [
            { label: "Verification approval status", value: formatStatusLabel(audit.approvals.verification.status) },
            { label: "Verification approval ID", value: audit.approvals.verification.approval_id ?? "Not started" },
            { label: "Verification evidence ID", value: audit.verification.verification_evidence_id ?? "Not started" },
        ],
    },
    {
        stage: "verification",
        title: "Check results",
        details: (audit) => [
            { label: "Verification status", value: formatStatusLabel(audit.verification.verification_status ?? "not_reached") },
            { label: "Changed files digest", value: audit.verification.changed_files_digest ?? "Not available" },
            { label: "Repository head", value: audit.verification.repository_head ?? "Not available" },
            { label: "Verification started (local time)", value: formatAuditTimestamp(audit.verification.verification_started_at) },
            { label: "Verification completed (local time)", value: formatAuditTimestamp(audit.verification.verification_completed_at) },
        ],
    },
    {
        stage: "review",
        title: "Review results",
        details: (audit) => [
            { label: "Review status", value: formatStatusLabel(audit.review.review_status ?? "not_reached") },
            { label: "Review result ID", value: audit.review.review_result_id ?? "Not started" },
            { label: "Review report ID", value: audit.review.review_report_id ?? "Not started" },
            { label: "Reviewed content fingerprint", value: audit.review.reviewed_content_fingerprint ?? "Not exposed" },
            { label: "Changed files", value: audit.review.changed_files.length > 0 ? audit.review.changed_files.join(", ") : "None reported" },
        ],
    },
    {
        stage: "commit",
        title: "Commit details",
        details: (audit) => [
            { label: "Commit request ID", value: audit.commit.commit_request_id ?? "Not started" },
            { label: "Expected branch", value: audit.commit.expected_branch ?? "Not exposed" },
            { label: "Expected HEAD", value: audit.commit.expected_head ?? "Not exposed" },
            { label: "Commit message", value: audit.commit.commit_message ?? "Not exposed" },
            { label: "Reviewed files", value: audit.commit.reviewed_files.length > 0 ? audit.commit.reviewed_files.join(", ") : "None reported" },
            { label: "Reviewed content fingerprint", value: audit.commit.reviewed_content_fingerprint ?? "Not exposed" },
        ],
    },
    {
        stage: "commit",
        title: "Commit approval",
        details: (audit) => [
            { label: "Commit approval status", value: formatStatusLabel(audit.approvals.commit.status) },
            { label: "Commit approval ID", value: audit.approvals.commit.approval_id ?? "Not started" },
        ],
    },
    {
        stage: "commit",
        title: "Commit result",
        details: (audit) => [
            { label: "Commit SHA", value: audit.commit.commit_sha ?? "Not started" },
            { label: "Commit message", value: audit.commit.commit_message ?? "Not available" },
            { label: "Committed files", value: audit.commit.committed_files.length > 0 ? audit.commit.committed_files.join(", ") : "None reported" },
        ],
    },
];

export function WorkflowAuditPage() {
    const { workflowId = "" } = useParams<{ workflowId: string }>();
    return <WorkflowAudit key={workflowId} workflowId={workflowId} />;
}

function WorkflowAudit({ workflowId }: { workflowId: string }) {
    const [audit, setAudit] = useState<WorkflowAuditResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<{ message: string; details?: string } | null>(null);

    const loadAudit = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        try {
            const detail = await getWorkflowAudit(workflowId);
            if (detail && (detail.workflow_id !== workflowId || detail.workflow.workflow_id !== workflowId)) {
                setAudit(null);
                setLoadError({ message: "The returned record does not match this workflow link." });
                return;
            }
            setAudit(detail);
        } catch (error) {
            setLoadError({
                message: "Mission Control could not load the workflow record.",
                details: getAtlasAgentErrorMessage(error, "Atlas Agent unavailable."),
            });
        } finally {
            setIsLoading(false);
        }
    }, [workflowId]);

    useEffect(() => {
        let cancelled = false;
        void Promise.resolve().then(() => { if (!cancelled) void loadAudit(); });
        return () => { cancelled = true; };
    }, [loadAudit]);

    if (isLoading) {
        return (
            <main className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
                <p role="status" className="text-blue-200">Loading workflow audit...</p>
            </main>
        );
    }

    if (loadError) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-8">
                <Link to={`/workflows/${workflowId}`} className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">← Back to Workflow</Link>
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-lg font-semibold text-red-100">Workflow audit unavailable</h1>
                    <p className="mt-2 text-sm text-red-100">{loadError.message}</p>
                    <button type="button" onClick={() => void loadAudit()} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>
                    {loadError.details && <details className="mt-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{loadError.details}</p>
                    </details>}
                </section>
            </main>
        );
    }

    if (!audit) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-8">
                <Link to="/workflows" className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">← Back to Workflow Dashboard</Link>
                <section role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <h1 className="text-lg font-semibold text-amber-100">Workflow not found</h1>
                    <p className="mt-2 text-sm text-slate-300">This workflow could not be found. Check the link or return to the workflow list.</p>
                </section>
            </main>
        );
    }

    const timeline = audit.timeline;

    if (audit.effect_kind === "operational_action") return <MaintenanceAudit audit={audit} />;

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
            <header className="space-y-4">
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Read-only record</p>
                <h1 className="text-3xl font-bold text-white">Workflow audit</h1>
                <p className="max-w-3xl text-sm leading-6 text-slate-400">
                    Review the recorded stages and results. Open a stage to inspect its details; this page does not change the workflow.
                </p>
            </header>

            <section aria-labelledby="audit-overview-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="audit-overview-heading" className="text-lg font-semibold text-white">Overview</h2>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-3">
                    <Detail label="Workflow status" value={formatWorkflowAuditStatus(audit)} />
                    {audit.blocked_reason ? <Detail label="Blocked reason" value={audit.blocked_reason} /> : null}
                    <Detail label="Audit validation" value={audit.validation.valid ? "Valid" : "Invalid"} />
                </dl>
                {audit.validation.failure_code !== null && (
                    <p role="alert" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                        This audit record is inconsistent. Review the flagged stage below and its recorded details.
                    </p>
                )}
                <details className="mt-4 border-t border-slate-800 pt-4">
                    <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                    <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Workflow ID" value={audit.workflow_id} />
                        <Detail label="Recorded workflow state" value={formatStatusLabel(audit.workflow_state)} />
                        <Detail label="Workflow source" value={audit.workflow_source} />
                        <Detail label="Audit failure code" value={audit.validation.failure_code ?? "None"} />
                        <Detail label="Audit failure stage" value={audit.validation.failure_stage ?? "None"} />
                    </dl>
                </details>
            </section>

            {AUDIT_STAGE_ORDER.map(({ stage, title, details }) => {
                const status = normalizeStageStatus(findStageStatus(timeline, stage));
                const isIssue = status === "missing" || status === "inconsistent";
                const headingId = `audit-stage-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
                return (
                    <details key={title} role="region" aria-labelledby={headingId} className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                        <summary id={headingId} aria-label={`${title}, ${formatStatusLabel(status)}`} className="mc-focusable flex cursor-pointer list-none items-center justify-between gap-3 rounded text-lg font-semibold text-white">
                            <span>{title}</span>
                            <span className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-medium ${timelineClass(status)}`}>
                                {formatStatusLabel(status)}
                            </span>
                        </summary>
                        {isIssue && (
                            <p role="alert" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">
                                {status === "missing" ? "Required artifact is missing." : "This stage is inconsistent with audit-chain validation."}
                            </p>
                        )}
                        <dl className="mt-4 grid gap-4 border-t border-slate-800 pt-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                            {details(audit).map((detail) => (
                                <Detail key={detail.label} label={detail.label} value={detail.value} />
                            ))}
                        </dl>
                    </details>
                );
            })}

            <Link
                to={`/workflows/${audit.workflow_id}`}
                className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
                ← Back to Workflow
            </Link>
        </main>
    );
}

function MaintenanceAudit({ audit }: { audit: WorkflowAuditResponse }) {
    const [lifecycle, setLifecycle] = useState<WorkflowOperationalLifecycle | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const generation = useRef(0);
    const load = useCallback(async () => {
        const attempt = ++generation.current;
        setLoading(true);
        setError(null);
        try {
            const result = await getWorkflowOperationalLifecycle(audit.workflow_id);
            if (attempt !== generation.current) return;
            if (!result || result.workflow_id !== audit.workflow_id || !result.applicable) {
                setLifecycle(null);
                setError("Matching maintenance evidence is unavailable. Refresh to check again.");
            } else setLifecycle(result);
        } catch {
            if (attempt === generation.current) setError("Could not load maintenance evidence. Refresh to check again.");
        } finally { if (attempt === generation.current) setLoading(false); }
    }, [audit.workflow_id]);
    useEffect(() => {
        let active = true;
        void Promise.resolve().then(() => { if (active) void load(); });
        return () => { active = false; generation.current += 1; };
    }, [load]);
    return <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-8">
        <header>
            <h1 className="break-all text-3xl font-bold text-white">Maintenance audit</h1>
            <p className="mt-3 text-sm text-slate-300">Review recorded approvals, dispatch and verification. This page only reads information.</p>
            <Link to={`/workflows/${encodeURIComponent(audit.workflow_id)}`} className="mt-4 inline-flex text-sm text-blue-300">Back to workflow</Link>
        </header>
        <section aria-label="Audit validation" className="rounded-xl border border-slate-800 p-5 text-slate-300">
            <p>Maintenance status: {formatWorkflowAuditStatus(audit)}</p>
            <p>Audit validation: {audit.validation.valid ? "Valid" : "Invalid"}</p>
            {audit.blocked_reason && <p>Blocked reason: {audit.blocked_reason}</p>}
            {audit.validation.failure_code && <p role="alert">This audit record is inconsistent. Review its technical details.</p>}
            <details className="mt-4 border-t border-slate-800 pt-4">
                <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Workflow ID" value={audit.workflow_id} />
                    <Detail label="Recorded workflow state" value={formatStatusLabel(audit.workflow_state)} />
                    <Detail label="Workflow source" value={audit.workflow_source} />
                    <Detail label="Audit failure code" value={audit.validation.failure_code ?? "None"} />
                    <Detail label="Audit failure stage" value={audit.validation.failure_stage ?? "None"} />
                </dl>
            </details>
        </section>
        <OperationalLifecyclePanel lifecycle={lifecycle} isLoading={loading && !lifecycle} isRefreshing={loading} error={error} onRefresh={() => void load()} />
    </main>;
}

function normalizeStageStatus(status: string | undefined): "completed" | "current" | "not_reached" | "missing" | "inconsistent" {
    if (status === undefined || status === "not_reached") {
        return "not_reached";
    }
    if (status === "invalid" || status === "inconsistent") {
        return "inconsistent";
    }
    if (status === "missing") {
        return "missing";
    }
    if (status === "current" || status === "completed") {
        return status;
    }
    return "not_reached";
}

function findStageStatus(
    timeline: WorkflowAuditResponse["timeline"],
    stage: WorkflowAuditStageName,
): WorkflowAuditStageStatus {
    const entry = timeline.find((item) => item.name === stage);
    return entry ? normalizeStageNameStatus(entry.status) : "missing";
}

function normalizeStageNameStatus(status: WorkflowAuditStageStatus): WorkflowAuditStageStatus {
    if (status === "invalid") return "inconsistent";
    return status;
}

function formatAuditTimestamp(value: string | null): ReactNode {
    if (value === null) return "Not available";
    const timestamp = evidenceTimestamp(value);
    return timestamp === null
        ? "Time unavailable"
        : <time dateTime={value}>{new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>;
}

function Detail({ label, value }: { label: string; value: ReactNode }) {
    return (
        <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
            <dd className="mt-1 break-all text-sm text-slate-200">{value}</dd>
        </div>
    );
}

function timelineClass(status: "completed" | "current" | "not_reached" | "missing" | "inconsistent") {
    if (status === "completed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
    if (status === "current") return "border-blue-400 bg-blue-500/10 text-blue-200";
    if (status === "inconsistent") return "border-amber-500/30 bg-amber-500/10 text-amber-100";
    if (status === "missing") return "border-red-500/30 bg-red-500/10 text-red-100";
    return "border-slate-800 bg-slate-950/50 text-slate-500";
}

function formatStatusLabel(value: string): string {
    const normalized = value.replaceAll("_", " ").replaceAll("-", " ");
    if (normalized === "not reached") return "Not started";
    if (normalized === "invalid" || normalized === "inconsistent") return "Inconsistent";
    return normalized.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatWorkflowAuditStatus(audit: WorkflowAuditResponse): string {
    const isMaintenance = audit.effect_kind === "operational_action";
    const action = isMaintenance ? "Maintenance request" : "Implementation";
    switch (audit.workflow_state) {
        case "planned":
            return isMaintenance ? "Maintenance request is ready for review." : "Workflow is ready for review.";
        case "awaiting_approval":
            return isMaintenance ? "Maintenance workflow is waiting for review." : "Workflow is waiting for review.";
        case "awaiting_implementation_approval":
            return approvalStatusMessage(action, audit.approvals.implementation.status, isMaintenance
                ? "Run approved maintenance when you are ready."
                : "Run the approved change when you are ready.");
        case "awaiting_execution":
            return action + " is approved and ready to run.";
        case "executing":
            return isMaintenance ? "Maintenance is running." : action + " is running.";
        case "patch_applied_pending_verification":
            return "Implementation is complete. Verification is next.";
        case "awaiting_verification_approval":
            return approvalStatusMessage("Verification", audit.approvals.verification.status, "Run the approved checks when you are ready.");
        case "verifying":
            return "Verification checks are running.";
        case "awaiting_commit_approval":
            return approvalStatusMessage("Commit", audit.approvals.commit.status, "Record the approved commit when you are ready.");
        case "committing":
            return "The commit is being recorded.";
        case "blocked":
            return isMaintenance
                ? "Maintenance workflow is blocked. Review the recorded stages and results below."
                : "Workflow is blocked. Review the recorded stages and results below.";
        case "implementation_rejected":
            return action + " approval was rejected.";
        case "completed":
            return isMaintenance ? "Maintenance workflow completed." : "Workflow completed.";
        default:
            return "Workflow status is unavailable.";
    }
}

function approvalStatusMessage(action: string, status: string, approvedNextStep: string): string {
    if (status === "approved") return action + " is approved. " + approvedNextStep;
    if (status === "rejected") return action + " approval was rejected.";
    if (status === "pending") return action + " needs approval.";
    return action + " approval status is unavailable.";
}
