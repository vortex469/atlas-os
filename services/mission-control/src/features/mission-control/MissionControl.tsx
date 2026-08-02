import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AtlasAgentPanel } from "../../components/AtlasAgentPanel";
import { DashboardHeader } from "../../components/DashboardHeader";
import { HealthCard } from "../../components/HealthCard";
import { ProviderCard } from "../../components/ProviderCard";
import { SectionHeader } from "../../components/SectionHeader";
import { useMissionControl } from "../../hooks/useMissionControl";
import { listExecutionCandidates } from "../../api/executionCandidates";
import { listWorkflows } from "../../api/atlas-agent";
import {
    workflowActionRequired,
    workflowStatusGroup,
} from "../../utils/workflowState";
import type { ExecutionCandidate, ExecutionCandidatePage } from "../../types/executionCandidates";
import type { WorkflowListResponse, WorkflowSummary } from "../../types/atlasAgent";
import { FindingsSection } from "./FindingsSection";
import { IntelligenceTelemetrySection } from "./IntelligenceTelemetrySection";
import { IntelligenceTrendSection } from "./IntelligenceTrendSection";
import { PolicyVisibilitySection } from "./PolicyVisibilitySection";
import { RecommendationsSection } from "./RecommendationsSection";
import { ServiceHealthSection } from "./ServiceHealthSection";

type DashboardMetric = {
    label: string;
    count: number;
    filterQuery: string;
};

type CandidateSummary = {
    eligible: number;
    notEligible: number;
    unsupported: number;
    expired: number;
};

function isUnsupportedCandidate(candidate: ExecutionCandidate): boolean {
    const rawCompatibility = candidate.compatibility_status?.toLowerCase() ?? "";
    return (
        candidate.status.toLowerCase() === "unsupported" ||
        candidate.status.toLowerCase() === "unsupported_intent" ||
        rawCompatibility.includes("unsupported")
    );
}

function getWorkflowInboxRows(workflows: WorkflowSummary[]): WorkflowSummary[] {
    return workflows
        .filter(
            (workflow) =>
                workflowActionRequired(workflow.workflow_state) ||
                workflow.workflow_state === "blocked",
        )
        .slice(0, 5);
}

function formatStateLabel(value: string): string {
    return value
        .replaceAll("_", " ")
        .replaceAll("-", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

async function fetchAllWorkflowSummary(): Promise<WorkflowListResponse> {
    const pageSize = 200;
    let offset = 0;
    let total = 0;
    const collected: WorkflowSummary[] = [];

    do {
        const page = await listWorkflows({ limit: pageSize, offset });
        collected.push(...page.items);
        total = page.total;
        offset += page.items.length;
        if (page.items.length === 0) {
            break;
        }
    } while (offset < total);

    return {
        items: collected,
        total: collected.length,
        limit: pageSize,
        offset: 0,
    };
}

async function fetchExecutionCandidateSummary(): Promise<ExecutionCandidatePage> {
    const pageSize = 200;
    let offset = 0;
    let hasMore = true;
    const aggregated: ExecutionCandidatePage = {
        candidates: [],
        total: 0,
        limit: pageSize,
        offset: 0,
        has_more: true,
    };

    while (hasMore) {
        const page = await listExecutionCandidates({ limit: pageSize, offset });
        aggregated.candidates.push(...page.candidates);
        aggregated.total = aggregated.candidates.length;
        aggregated.offset = page.offset;
        aggregated.limit = page.limit;
        hasMore = page.has_more;
        offset += page.candidates.length;
    }

    aggregated.has_more = hasMore;
    return aggregated;
}

export function MissionControl() {
    const {
        summary,
        health,
        providers,
        policies,
        policyHealth,
        telemetryHistory,
        telemetryRetention,
        lastUpdated,
        error,
        isLoading,
        isRefreshing,
        refresh,
    } = useMissionControl();

    const [workflowSummary, setWorkflowSummary] =
        useState<WorkflowListResponse | null>(null);
    const [candidateSummary, setCandidateSummary] =
        useState<CandidateSummary | null>(null);
    const [overviewLoading, setOverviewLoading] = useState(false);
    const [overviewError, setOverviewError] = useState<string | null>(null);

    const loadOperationalOverview = useCallback(async () => {
        if (overviewLoading) {
            return;
        }

        setOverviewLoading(true);
        setOverviewError(null);

        try {
            const [workflows, candidates] = await Promise.all([
                fetchAllWorkflowSummary(),
                fetchExecutionCandidateSummary(),
            ]);

            setWorkflowSummary(workflows);

            const eligible = candidates.candidates.filter(
                (candidate) => candidate.status === "eligible",
            ).length;
            const notEligible = candidates.candidates.filter(
                (candidate) => candidate.status === "not_eligible",
            ).length;
            const expired = candidates.candidates.filter(
                (candidate) => candidate.status === "expired",
            ).length;
            const unsupported = candidates.candidates.filter(
                isUnsupportedCandidate,
            ).length;

            setCandidateSummary({
                eligible,
                notEligible,
                unsupported,
                expired,
            });
        } catch {
            setOverviewError(
                "Operator command center could not load workflow and candidate summaries.",
            );
        } finally {
            setOverviewLoading(false);
        }
    }, [overviewLoading]);

    useEffect(() => {
        if (lastUpdated !== null) {
            void loadOperationalOverview();
        }
    }, [lastUpdated, loadOperationalOverview]);

    async function handleRefresh() {
        await Promise.all([refresh(), loadOperationalOverview()]);
    }

    const workflows = workflowSummary?.items ?? [];
    const workflowInboxRows = useMemo(
        () => getWorkflowInboxRows(workflows),
        [workflows],
    );

    const workflowOverview: DashboardMetric[] = useMemo(
        () => [
            {
                label: "Running",
                filterQuery: "/workflows?group=running",
                count: workflows.filter(
                    (workflow) =>
                        workflowStatusGroup(workflow.workflow_state) === "running",
                ).length,
            },
            {
                label: "Waiting",
                filterQuery: "/workflows?group=waiting",
                count: workflows.filter((workflow) => {
                    const group = workflowStatusGroup(workflow.workflow_state);
                    return (
                        group === "waiting_approval" ||
                        group === "waiting_implementation_approval" ||
                        group === "waiting_verification_approval" ||
                        group === "waiting_commit_approval"
                    );
                }).length,
            },
            {
                label: "Blocked",
                filterQuery: "/workflows?state=blocked",
                count: workflows.filter(
                    (workflow) => workflow.workflow_state === "blocked",
                ).length,
            },
            {
                label: "Completed",
                filterQuery: "/workflows?state=completed",
                count: workflows.filter(
                    (workflow) => workflow.workflow_state === "completed",
                ).length,
            },
        ],
        [workflows],
    );

    const actionRequired: DashboardMetric[] = useMemo(
        () => [
            {
                label: "Waiting Implementation Approval",
                filterQuery: "/workflows?state=awaiting_implementation_approval",
                count: workflows.filter(
                    (workflow) =>
                        workflow.workflow_state ===
                        "awaiting_implementation_approval",
                ).length,
            },
            {
                label: "Waiting Verification Approval",
                filterQuery: "/workflows?state=awaiting_verification_approval",
                count: workflows.filter(
                    (workflow) =>
                        workflow.workflow_state ===
                        "awaiting_verification_approval",
                ).length,
            },
            {
                label: "Waiting Commit Approval",
                filterQuery: "/workflows?state=awaiting_commit_approval",
                count: workflows.filter(
                    (workflow) =>
                        workflow.workflow_state === "awaiting_commit_approval",
                ).length,
            },
            {
                label: "Blocked Workflows",
                filterQuery: "/workflows?state=blocked",
                count: workflows.filter(
                    (workflow) => workflow.workflow_state === "blocked",
                ).length,
            },
        ],
        [workflows],
    );

    const actionRequiredCount = useMemo(
        () =>
            workflows.filter(
                (workflow) =>
                    workflowActionRequired(workflow.workflow_state) ||
                    workflow.workflow_state === "blocked",
            ).length,
        [workflows],
    );

    return (
        <div className="min-h-screen">
            <DashboardHeader
                lastUpdated={lastUpdated}
                atlasStatus={health?.atlas ?? null}
                isRefreshing={isRefreshing}
                onRefresh={handleRefresh}
            />

            <main
                aria-labelledby="mission-control-heading"
                className="mx-auto max-w-7xl space-y-8 p-8"
                role="main"
            >
                <h1 id="mission-control-heading" className="sr-only">
                    Mission Control command center
                </h1>

                {overviewLoading && !workflowSummary && (
                    <p role="status" className="text-sm text-slate-300">
                        Loading operator command center summary...
                    </p>
                )}

                {overviewError && (
                    <section
                        role="alert"
                        aria-live="polite"
                        className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100"
                    >
                        {overviewError}
                    </section>
                )}

                {error && (
                    <div
                        role="alert"
                        className="flex items-center justify-between gap-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
                    >
                        <div>
                            <p className="font-semibold text-red-300">
                                Atlas Core unavailable
                            </p>
                            <p className="mt-1 text-sm text-red-200/80">
                                {error}
                            </p>
                        </div>

                        <button
                            type="button"
                            onClick={() => void handleRefresh()}
                            disabled={isRefreshing}
                            className="rounded-lg border border-red-400/30 px-4 py-2 text-sm font-medium text-red-200 transition hover:bg-red-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {isLoading &&
                    !summary &&
                    !health &&
                    providers.length === 0 && (
                        <div className="rounded-lg border border-slate-800 bg-slate-900 p-8">
                            <p className="text-sm font-medium text-slate-300">
                                Connecting to Atlas Core...
                            </p>
                            <p className="mt-2 text-sm text-slate-500">
                                Loading the current ACE situation report,
                                platform health, and provider catalog.
                            </p>
                        </div>
                    )}

                <section
                    aria-label="Action required"
                    className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4"
                >
                    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="text-sm uppercase tracking-wider text-slate-500">
                            Needs attention
                        </p>
                        <p className="mt-2 text-3xl font-bold text-white">
                            {actionRequiredCount}
                        </p>
                        <p className="mt-2 text-sm text-slate-400">
                            workflows currently require operator action.
                        </p>
                    </article>

                    {actionRequired.map((metric) => (
                        <Link
                            key={metric.label}
                            to={metric.filterQuery}
                            className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 transition hover:bg-slate-900/90 focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            <p className="text-sm uppercase tracking-wider text-slate-500">
                                {metric.label}
                            </p>
                            <p className="mt-2 text-3xl font-bold text-white">
                                {metric.count}
                            </p>
                        </Link>
                    ))}

                    {actionRequiredCount === 0 && (
                        <article className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                            <p className="text-sm text-emerald-100">
                                No workflows currently require operator action.
                            </p>
                        </article>
                    )}
                </section>

                <section
                    aria-label="Workflow overview"
                    className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
                >
                    <h2 className="sr-only">Workflow overview</h2>
                    {workflowOverview.map((group) => (
                        <Link
                            key={group.label}
                            to={group.filterQuery}
                            className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 transition hover:bg-slate-900/90 focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            <p className="text-sm text-slate-400">{group.label}</p>
                            <p className="mt-2 text-3xl font-bold text-white">
                                {group.count}
                            </p>
                        </Link>
                    ))}
                </section>

                <section
                    aria-label="Execution candidates"
                    className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
                >
                    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="text-sm uppercase tracking-wider text-slate-500">
                            Eligible
                        </p>
                        <p className="mt-2 text-3xl font-bold text-white">
                            {candidateSummary?.eligible ?? 0}
                        </p>
                    </article>
                    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="text-sm uppercase tracking-wider text-slate-500">
                            Not Eligible
                        </p>
                        <p className="mt-2 text-3xl font-bold text-white">
                            {candidateSummary?.notEligible ?? 0}
                        </p>
                    </article>
                    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="text-sm uppercase tracking-wider text-slate-500">
                            Unsupported
                        </p>
                        <p className="mt-2 text-3xl font-bold text-white">
                            {candidateSummary?.unsupported ?? 0}
                        </p>
                    </article>
                    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="text-sm uppercase tracking-wider text-slate-500">
                            Expired
                        </p>
                        <p className="mt-2 text-3xl font-bold text-white">
                            {candidateSummary?.expired ?? 0}
                        </p>
                    </article>

                    <div className="sm:col-span-2 lg:col-span-4">
                        <Link
                            to="/execution-candidates"
                            className="inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            View Execution Candidates
                        </Link>
                    </div>
                </section>

                <section aria-label="Workflow inbox" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <h2 className="text-lg font-semibold text-white">
                            Workflow Inbox
                        </h2>
                        <Link
                            to="/workflows"
                            className="text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            View all workflows
                        </Link>
                    </div>

                    <div className="mt-4 space-y-3">
                        {workflowInboxRows.length === 0 ? (
                            <p className="text-sm text-slate-300">
                                No workflows currently require operator action.
                            </p>
                        ) : (
                            <>
                                <div className="grid grid-cols-6 gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                                    <span>Workflow ID</span>
                                    <span>Stage</span>
                                    <span className="col-span-2">Repository</span>
                                    <span>Current State</span>
                                    <span>Action Required</span>
                                    <span>Open</span>
                                </div>
                                {workflowInboxRows.map((workflow) => (
                                    <div
                                        key={workflow.workflow_id}
                                        className="grid grid-cols-1 gap-2 rounded-lg border border-slate-800 px-3 py-3 md:grid-cols-6 md:gap-2"
                                    >
                                        <p className="break-all text-sm text-slate-200">
                                            {workflow.workflow_id}
                                        </p>
                                        <p className="text-sm text-slate-300">
                                            {formatStateLabel(
                                                workflowStatusGroup(
                                                    workflow.workflow_state,
                                                ),
                                            )}
                                        </p>
                                        <p className="break-all text-sm text-slate-300 md:col-span-2">
                                            {workflow.repository ?? workflow.target_id ?? "Not exposed"}
                                        </p>
                                        <p className="text-sm text-slate-200">
                                            {formatStateLabel(workflow.workflow_state)}
                                        </p>
                                        <p className="text-sm text-slate-300">
                                            {workflowActionRequired(workflow.workflow_state)
                                                ? "Yes"
                                                : "No"}
                                        </p>
                                        <Link
                                            to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`}
                                            className="inline-flex text-sm text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
                                        >
                                            Open
                                        </Link>
                                    </div>
                                ))}
                            </>
                        )}
                    </div>
                </section>

                {summary && (
                    <>
                        <HealthCard
                            score={summary.score}
                            status={summary.status}
                            summary={summary.summary}
                        />

                        <RecommendationsSection
                            recommendations={summary.recommendations}
                        />
                    </>
                )}

                {health && (
                    <ServiceHealthSection
                        services={health.services}
                        providers={providers}
                        isRefreshing={isRefreshing}
                        onRefresh={() => void handleRefresh()}
                    />
                )}
                <AtlasAgentPanel />

                {(health || providers.length > 0) && (
                    <section>
                        <SectionHeader
                            title="Providers"
                            description="Registry-backed Atlas capabilities and connected infrastructure."
                        />

                        {providers.length > 0 ? (
                            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                                {providers.map((provider) => (
                                    <ProviderCard
                                        key={provider.id}
                                        provider={provider}
                                    />
                                ))}
                            </div>
                        ) : (
                            !isLoading && (
                                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                                    <p className="text-sm font-medium text-slate-300">
                                        No providers registered
                                    </p>
                                    <p className="mt-2 text-sm text-slate-500">
                                        Atlas Core did not return any providers from
                                        the registry.
                                    </p>
                                </div>
                            )
                        )}
                    </section>
                )}

                {summary && (
                    <IntelligenceTelemetrySection
                        telemetry={summary.telemetry}
                    />
                )}

                <IntelligenceTrendSection
                    snapshots={telemetryHistory}
                    retention={telemetryRetention}
                    onPruned={handleRefresh}
                />

                {policyHealth && (
                    <PolicyVisibilitySection
                        policies={policies}
                        health={policyHealth}
                    />
                )}

                {summary && <FindingsSection findings={summary.findings} />}
            </main>
        </div>
    );
}
