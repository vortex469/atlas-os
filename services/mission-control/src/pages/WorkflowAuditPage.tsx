import { Link, useParams } from "react-router-dom";

import {
    getAtlasAgentErrorMessage,
    getWorkflowAudit,
} from "../api/atlas-agent";
import type { WorkflowAuditResponse, WorkflowAuditStageName, WorkflowAuditStageStatus } from "../types/atlasAgent";
import { useCallback, useEffect, useState } from "react";

interface AuditStageDefinition {
    stage: WorkflowAuditStageName;
    title: string;
    details: (audit: WorkflowAuditResponse) => { label: string; value: string }[];
}

const AUDIT_STAGE_ORDER: AuditStageDefinition[] = [
    {
        stage: "candidate",
        title: "Candidate",
        details: (audit) => [
            { label: "Candidate ID", value: audit.candidate.candidate_id ?? "Not reached" },
            { label: "Candidate fingerprint", value: audit.candidate.candidate_fingerprint ?? "Not exposed" },
            { label: "Source recommendation ID", value: audit.candidate.source_recommendation_id ?? "Not exposed" },
            { label: "Target ID", value: audit.candidate.target_id ?? "Not exposed" },
            { label: "Target type", value: audit.candidate.target_type ?? "Not exposed" },
        ],
    },
    {
        stage: "planning",
        title: "Planning Session",
        details: (audit) => [
            { label: "Planning session ID", value: audit.planning.planning_session_id ?? "Not reached" },
            { label: "Planning state", value: audit.planning.planning_state ?? "Not exposed" },
            { label: "Planning status", value: audit.planning.planning_status ?? "Not exposed" },
            { label: "Created at", value: audit.planning.created_at ?? "Not available" },
            { label: "Planning completed at", value: audit.planning.planning_completed_at ?? "Not available" },
        ],
    },
    {
        stage: "plan",
        title: "Candidate Plan",
        details: (audit) => [
            { label: "Plan ID", value: audit.plan.plan_id ?? "Not reached" },
            { label: "Candidate plan fingerprint", value: audit.plan.candidate_plan_fingerprint ?? "Not exposed" },
            { label: "Likely affected files", value: audit.plan.likely_affected_files.length > 0 ? audit.plan.likely_affected_files.join(", ") : "None reported" },
        ],
    },
    {
        stage: "workflow",
        title: "Workflow",
        details: (audit) => [
            { label: "Workflow ID", value: audit.workflow.workflow_id },
            { label: "Workflow state", value: formatStatusLabel(audit.workflow.workflow_state) },
            { label: "Workflow source", value: audit.workflow.workflow_source },
        ],
    },
    {
        stage: "implementation",
        title: "Implementation Request",
        details: (audit) => [
            { label: "Implementation request ID", value: audit.implementation.implementation_request_id ?? "Not reached" },
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
        title: "Implementation Approval",
        details: (audit) => [
            { label: "Workflow approval status", value: formatStatusLabel(audit.approvals.implementation.status) },
            { label: "Implementation approval ID", value: audit.approvals.implementation.approval_id ?? "Not reached" },
            { label: "Overall approval decision", value: formatStatusLabel(audit.approvals.status) },
        ],
    },
    {
        stage: "execution",
        title: "Execution Result",
        details: (audit) => [
            { label: "Execution status", value: formatStatusLabel(audit.execution.execution_status ?? "not_reached") },
            { label: "Execution request ID", value: audit.execution.execution_request_id ?? "Not reached" },
            { label: "Changed files count", value: String(audit.execution.changed_files_count) },
            { label: "Changed files", value: audit.execution.changed_files.length > 0 ? audit.execution.changed_files.join(", ") : "None reported" },
            { label: "Tool", value: audit.execution.tool ?? "Not exposed" },
            { label: "Repository", value: audit.execution.repository ?? "Not exposed" },
        ],
    },
    {
        stage: "verification",
        title: "Verification Plan",
        details: (audit) => [
            { label: "Verification plan ID", value: audit.verification.verification_plan_id ?? "Not reached" },
            { label: "Verification status", value: formatStatusLabel(audit.verification.verification_status ?? "not_reached") },
            { label: "Changed files digest", value: audit.verification.changed_files_digest ?? "Not exposed" },
            { label: "Verification check IDs", value: audit.verification.verification_check_ids.length > 0 ? audit.verification.verification_check_ids.join(", ") : "None reported" },
            { label: "Repository head", value: audit.verification.repository_head ?? "Not exposed" },
            { label: "Verification started at", value: audit.verification.verification_started_at ?? "Not available" },
            { label: "Verification completed at", value: audit.verification.verification_completed_at ?? "Not available" },
        ],
    },
    {
        stage: "verification",
        title: "Verification Approval",
        details: (audit) => [
            { label: "Verification approval status", value: formatStatusLabel(audit.approvals.verification.status) },
            { label: "Verification approval ID", value: audit.approvals.verification.approval_id ?? "Not reached" },
            { label: "Verification evidence ID", value: audit.verification.verification_evidence_id ?? "Not reached" },
        ],
    },
    {
        stage: "verification",
        title: "Verification Evidence",
        details: (audit) => [
            { label: "Verification status", value: formatStatusLabel(audit.verification.verification_status ?? "not_reached") },
            { label: "Changed files digest", value: audit.verification.changed_files_digest ?? "Not available" },
            { label: "Repository head", value: audit.verification.repository_head ?? "Not available" },
            { label: "Verification started at", value: audit.verification.verification_started_at ?? "Not available" },
            { label: "Verification completed at", value: audit.verification.verification_completed_at ?? "Not available" },
        ],
    },
    {
        stage: "review",
        title: "Review Result",
        details: (audit) => [
            { label: "Review status", value: formatStatusLabel(audit.review.review_status ?? "not_reached") },
            { label: "Review result ID", value: audit.review.review_result_id ?? "Not reached" },
            { label: "Review report ID", value: audit.review.review_report_id ?? "Not reached" },
            { label: "Reviewed content fingerprint", value: audit.review.reviewed_content_fingerprint ?? "Not exposed" },
            { label: "Changed files", value: audit.review.changed_files.length > 0 ? audit.review.changed_files.join(", ") : "None reported" },
        ],
    },
    {
        stage: "commit",
        title: "Commit Request",
        details: (audit) => [
            { label: "Commit request ID", value: audit.commit.commit_request_id ?? "Not reached" },
            { label: "Expected branch", value: audit.commit.expected_branch ?? "Not exposed" },
            { label: "Expected HEAD", value: audit.commit.expected_head ?? "Not exposed" },
            { label: "Commit message", value: audit.commit.commit_message ?? "Not exposed" },
            { label: "Reviewed files", value: audit.commit.reviewed_files.length > 0 ? audit.commit.reviewed_files.join(", ") : "None reported" },
            { label: "Reviewed content fingerprint", value: audit.commit.reviewed_content_fingerprint ?? "Not exposed" },
        ],
    },
    {
        stage: "commit",
        title: "Commit Approval",
        details: (audit) => [
            { label: "Commit approval status", value: formatStatusLabel(audit.approvals.commit.status) },
            { label: "Commit approval ID", value: audit.approvals.commit.approval_id ?? "Not reached" },
        ],
    },
    {
        stage: "commit",
        title: "Commit Result",
        details: (audit) => [
            { label: "Commit SHA", value: audit.commit.commit_sha ?? "Not reached" },
            { label: "Commit message", value: audit.commit.commit_message ?? "Not available" },
            { label: "Committed files", value: audit.commit.committed_files.length > 0 ? audit.commit.committed_files.join(", ") : "None reported" },
        ],
    },
];

export function WorkflowAuditPage() {
    const { workflowId = "" } = useParams<{ workflowId: string }>();
    const [audit, setAudit] = useState<WorkflowAuditResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    const loadAudit = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        try {
            const detail = await getWorkflowAudit(workflowId);
            setAudit(detail);
        } catch (error) {
            setLoadError(getAtlasAgentErrorMessage(error, "Atlas Agent unavailable."));
        } finally {
            setIsLoading(false);
        }
    }, [workflowId]);

    useEffect(() => {
        void Promise.resolve().then(() => loadAudit());
    }, [loadAudit]);

    if (isLoading) {
        return (
            <main className="mx-auto max-w-6xl space-y-8 p-8">
                <p role="status" className="text-blue-200">Loading workflow audit...</p>
            </main>
        );
    }

    if (loadError) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-8">
                <Link to={`/workflows/${workflowId}`} className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">← Back to Workflow</Link>
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-lg font-semibold text-red-100">Workflow audit unavailable</h1>
                    <p className="mt-2 text-sm text-red-100">{loadError}</p>
                </section>
            </main>
        );
    }

    if (!audit) {
        return (
            <main className="mx-auto max-w-6xl space-y-4 p-8">
                <Link to="/workflows" className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">← Back to Workflow Dashboard</Link>
                <section role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <h1 className="text-lg font-semibold text-amber-100">Workflow not found</h1>
                    <p className="mt-2 text-sm text-slate-300">Atlas Agent did not find workflow {workflowId}.</p>
                </section>
            </main>
        );
    }

    const timeline = audit.timeline;
    const overallStatusLabel = formatStatusLabel(audit.validation.valid ? "completed" : "invalid");

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow Audit</p>
                <h1 className="text-3xl font-bold text-white">Workflow {audit.workflow_id}</h1>
                <p className="max-w-3xl text-sm leading-6 text-slate-400">
                    Read-only audit explorer for the candidate workflow chain. Mission Control renders only server-provided
                    fields and does not expose approval mutation, resume, execution, or commit controls.
                </p>
            </header>

            <section aria-labelledby="audit-overview-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="audit-overview-heading" className="text-lg font-semibold text-white">Overview</h2>
                <dl className="mt-4 grid gap-4 text-sm md:grid-cols-3">
                    <Detail label="Workflow ID" value={audit.workflow_id} />
                    <Detail label="Workflow State" value={formatStatusLabel(audit.workflow_state)} />
                    <Detail label="Workflow Source" value={audit.workflow_source} />
                    <Detail label="Overall audit status" value={overallStatusLabel} />
                    <Detail label="Audit validation" value={audit.validation.valid ? "Valid" : "Invalid"} />
                    <Detail label="Audit failure code" value={audit.validation.failure_code ?? "None"} />
                </dl>
                {audit.validation.failure_code !== null && (
                    <p role="alert" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                        Inconsistent audit: {audit.validation.failure_code}
                        {audit.validation.failure_stage ? ` at ${audit.validation.failure_stage}` : ""}
                    </p>
                )}
            </section>

            <section aria-labelledby="audit-stage-list-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="audit-stage-list-heading" className="text-lg font-semibold text-white">Stage status</h2>
                <ol className="mt-4 grid gap-2 text-sm md:grid-cols-3 lg:grid-cols-4">
                    {AUDIT_STAGE_ORDER.map(({ title, stage }) => (
                        <TimelineStage
                            key={title}
                            label={title}
                            status={normalizeStageStatus(findStageStatus(timeline, stage))}
                        />
                    ))}
                </ol>
            </section>

            {AUDIT_STAGE_ORDER.map(({ stage, title, details }) => {
                const status = normalizeStageStatus(findStageStatus(timeline, stage));
                const isIssue = status === "missing" || status === "inconsistent";
                return (
                    <section key={title} aria-labelledby={`audit-${title}-heading`} className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                        <h2 id={`audit-${title}-heading`} className="text-lg font-semibold text-white">{title}</h2>
                        <p className="mt-2 text-sm text-slate-300">Status: {formatStatusLabel(status)}</p>
                        {isIssue && status !== "completed" && status !== "current" && (
                            <p role="alert" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">
                                {status === "missing" ? "Required artifact is missing." : "This stage is inconsistent with audit-chain validation."}
                            </p>
                        )}
                        <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                            {details(audit).map((detail) => (
                                <Detail key={detail.label} label={detail.label} value={detail.value} />
                            ))}
                        </dl>
                    </section>
                );
            })}

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 className="text-lg font-semibold text-white">Audit trust boundary</h2>
                <p className="mt-2 text-sm text-slate-300">Stage statuses are derived from the server-provided audit timeline and validation result. Read-only fields below are not reconstructed.</p>
                <p className={`mt-4 rounded-lg p-3 text-sm ${overallStatusLabel === "Completed" ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-100" : "border border-amber-500/30 bg-amber-500/10 text-amber-100"}`}>
                    Overall chain state: {overallStatusLabel}
                </p>
                <p className="mt-3 text-xs uppercase tracking-[0.3em] text-slate-500">No mutation controls are available in this explorer.</p>
            </section>

            <Link
                to={`/workflows/${audit.workflow_id}`}
                className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
                ← Back to Workflow
            </Link>
        </main>
    );
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

function TimelineStage({ label, status }: { label: string; status: WorkflowAuditStageStatus }) {
    const displayStatus = normalizeStageStatus(status);
    return (
        <li className={"rounded-lg border px-3 py-2 " + timelineClass(displayStatus)}>
            <span className="block font-medium">{label}</span>
            <span className="text-xs">{formatStatusLabel(displayStatus)}</span>
        </li>
    );
}

function Detail({ label, value }: { label: string; value: string }) {
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
    return value
        .replaceAll("_", " ")
        .replaceAll("-", " ")
        .replace("not_reached", "Not reached")
        .replace("invalid", "Inconsistent")
        .replace("inconsistent", "Inconsistent")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
