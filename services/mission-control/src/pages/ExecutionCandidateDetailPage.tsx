import { isAxiosError } from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAtlasErrorMessage } from "../api/atlas";
import {
    createCandidatePlanningSession,
    getAtlasAgentErrorMessage,
} from "../api/atlas-agent";
import { getExecutionCandidate } from "../api/executionCandidates";
import type { CandidatePlanningResponse } from "../types/atlasAgent";
import type { ExecutionCandidate } from "../types/executionCandidates";
import { evidenceTimestamp } from "../utils/healthPresentation";
import { PlanningProgress } from "../components/PlanningProgress";
import { existingWorkflowPath, hasExistingWorkflow } from "../utils/existingWorkflow";

export function ExecutionCandidateDetailPage() {
    const { candidateId = "" } = useParams<{ candidateId: string }>();
    return <CandidateDetail key={candidateId} candidateId={candidateId} />;
}

function CandidateDetail({ candidateId }: { candidateId: string }) {
    const [candidate, setCandidate] = useState<ExecutionCandidate | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);
    const [planningResponse, setPlanningResponse] = useState<CandidatePlanningResponse | null>(null);
    const [planningError, setPlanningError] = useState<string | null>(null);
    const [isPlanningPending, setIsPlanningPending] = useState(false);
    const [readRevision, setReadRevision] = useState(0);
    const readPending = useRef(true);
    const planningPending = useRef(false);

    useEffect(() => {
        let cancelled = false;

        getExecutionCandidate(candidateId)
            .then((nextCandidate) => {
                if (cancelled) return;
                if (!nextCandidate || nextCandidate.id !== candidateId) {
                    setError("The returned proposal does not match this page.");
                    return;
                }
                setCandidate(nextCandidate);
            })
            .catch((requestError: unknown) => {
                if (cancelled) return;
                console.error(`Unable to load execution candidate ${candidateId}:`, requestError);
                const message = getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not load this change proposal.",
                );
                if (isAxiosError(requestError) && requestError.response?.status === 404) {
                    setNotFound(true);
                }
                setError(message);
            })
            .finally(() => {
                if (!cancelled) {
                    readPending.current = false;
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [candidateId, readRevision]);

    function reloadProposal() {
        if (readPending.current || planningPending.current) return;
        readPending.current = true;
        setIsLoading(true);
        setCandidate(null);
        setError(null);
        setNotFound(false);
        setPlanningResponse(null);
        setPlanningError(null);
        setReadRevision(revision => revision + 1);
    }

    const actionState = useMemo(() => getPlanningActionState(candidate), [candidate]);

    async function askAtlasAgentToPlan() {
        if (!candidate || !actionState.enabled || readPending.current || planningPending.current) {
            return;
        }

        planningPending.current = true;
        setIsPlanningPending(true);
        setPlanningError(null);
        setPlanningResponse(null);

        try {
            const response = await createCandidatePlanningSession({
                candidate_id: candidate.id,
            });
            if (!response || response.candidate_id !== candidate.id) {
                setPlanningError("The planning response did not match this proposal. No planning result was opened.");
                return;
            }
            setPlanningResponse(response);
        } catch (requestError) {
            console.error("Unable to create candidate planning session:", requestError);
            setPlanningError(
                getAtlasAgentErrorMessage(
                    requestError,
                    "Atlas Agent could not create or reuse a planning session.",
                ),
            );
        } finally {
            planningPending.current = false;
            setIsPlanningPending(false);
        }
    }

    if (isLoading) {
        return <PageFrame><p role="status" aria-live="polite" className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">Loading change proposal…</p></PageFrame>;
    }

    if (notFound) {
        return <PageFrame><section className="rounded-xl border border-slate-800 bg-slate-900/70 p-6"><h1 className="text-2xl font-bold text-white">Change proposal not found</h1><p className="mt-2 text-sm text-slate-400">Atlas Core could not find a current proposal for {candidateId}.</p><button type="button" onClick={reloadProposal} className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300">Try again</button></section></PageFrame>;
    }

    if (error || candidate === null) {
        return <PageFrame><div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"><p className="font-semibold text-red-300">Change proposal unavailable</p><p className="mt-1 text-sm text-red-200/80">{error ?? "Mission Control could not load this change proposal."}</p><button type="button" onClick={reloadProposal} className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300">Try again</button></div></PageFrame>;
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <Link to="/execution-candidates" className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">← Change proposals</Link>
                    <button type="button" onClick={reloadProposal} disabled={isPlanningPending} className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50">Refresh proposal</button>
                </div>
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Change proposal</p>
                    <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h1 className="break-all text-3xl font-bold text-white">{formatLabel(candidate.execution_intent).trim() || "Change proposal"}</h1>
                            <p className="mt-2 text-sm text-slate-400">{statusText(candidate.status)}</p>
                        </div>
                        <p className="text-sm text-slate-300">Target: {candidate.target_id}</p>
                    </div>
                    <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                        Review this proposal before planning. Planning does not approve or apply a change.
                    </p>
                </div>
                <dl className="grid gap-4 text-sm md:grid-cols-3">
                    <DetailField label="Required approval" value={formatLabel(candidate.required_approval_level)} />
                    <DetailField label="Compatibility" value={candidate.compatibility_status ? formatLabel(candidate.compatibility_status) : "Not reported"} />
                    <DetailField label="Expires" value={formatExpiry(candidate.expires_at)} />
                </dl>
                <PlanningProgress current="Execution Candidate" />
            </header>

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5" aria-labelledby="planning-action-heading">
                <h2 id="planning-action-heading" className="text-lg font-semibold text-white">Plan this change</h2>
                <p className="mt-2 text-sm text-slate-400">
                    Start planning this change. Atlas will check that the proposal is still current.
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button type="button" onClick={askAtlasAgentToPlan} disabled={!actionState.enabled || isPlanningPending} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                        {isPlanningPending ? "Requesting planning session…" : "Start planning"}
                    </button>
                    {(!actionState.enabled || isPlanningPending) && <p className="text-sm text-slate-400">{isPlanningPending ? "Planning request is already pending." : actionState.reason}</p>}
                </div>
                {planningResponse && <PlanningResult response={planningResponse} />}
                {planningError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4"><p className="font-semibold text-red-300">Planning unavailable</p><p className="mt-1 text-sm text-red-200/80">{planningError}</p></div>}
            </section>

            <details className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <summary className="cursor-pointer text-sm font-semibold text-slate-300">Technical details</summary>
                <section className="mt-4 grid gap-4 lg:grid-cols-2" aria-label="Proposal technical details">
                    <InfoPanel title="Immutable identity">
                        <DetailField label="Candidate ID" value={candidate.id} />
                        <DetailField label="Created" value={formatTimestamp(candidate.created_at)} />
                    </InfoPanel>
                    <InfoPanel title="Source recommendation">
                        <DetailField label="Source recommendation ID" value={candidate.source_recommendation_id} />
                        <DetailField label="Source subsystem" value={candidate.source_subsystem} />
                        <DetailField label="Recommendation class" value={candidate.recommendation_class} />
                        <DetailField label="Catalog item ID" value={candidate.catalog_item_id ?? "Not linked"} />
                    </InfoPanel>
                    <InfoPanel title="Target and classification">
                        <DetailField label="Target ID" value={candidate.target_id} />
                        <DetailField label="Target type" value={candidate.target_type} />
                        <DetailField label="Execution category" value={formatLabel(candidate.execution_category)} />
                        <DetailField label="Execution intent" value={formatLabel(candidate.execution_intent)} />
                        <DetailField label="Status" value={statusText(candidate.status)} />
                    </InfoPanel>
                    <InfoPanel title="Compatibility and relationships">
                        <DetailField label="Compatibility assessment ID" value={candidate.compatibility_assessment_id ?? "Not reported"} />
                        <ListField label="Relationship IDs" values={candidate.relationship_ids} empty="No relationship IDs." />
                    </InfoPanel>
                </section>
            </details>

            <InfoPanel title="Rationale">
                <p className="text-sm leading-6 text-slate-300">{candidate.rationale}</p>
            </InfoPanel>
            <section className="grid gap-4 lg:grid-cols-2">
                <InfoPanel title="Constraints"><ListField label="Constraints" values={candidate.constraints} empty="No constraints." /></InfoPanel>
                <InfoPanel title="Evidence IDs"><ListField label="Evidence IDs" values={candidate.evidence_ids} empty="No evidence IDs." /></InfoPanel>
            </section>
        </main>
    );
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTimestamp(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function statusText(status: string): string {
    if (status === "eligible") return "Eligible for planning consideration";
    if (status === "not_eligible") return "Not eligible for planning";
    if (status === "expired") return "Expired";
    return formatLabel(status);
}

function PageFrame({ children }: { children: React.ReactNode }) {
    return (
        <main className="mx-auto max-w-5xl space-y-6 p-8">
            <Link to="/execution-candidates" className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">← Change proposals</Link>
            {children}
        </main>
    );
}

function PlanningResult({ response }: { response: CandidatePlanningResponse }) {
    const message = planningMessage(response);
    const existingWorkflow = hasExistingWorkflow(response);
    const workflowPath = existingWorkflowPath(response);
    const savedPlan = response.status === "plan_ready" && response.session_id !== null && response.planning_failure === null;
    const isError = response.planning_failure !== null || response.session_id === null || (!existingWorkflow && !savedPlan && !response.planning_allowed);

    return (
        <div role={isError ? "alert" : "status"} className={["mt-4 rounded-lg border p-4", isError ? "border-amber-500/30 bg-amber-500/10" : "border-emerald-500/30 bg-emerald-500/10"].join(" ")}>
            <p className={isError ? "font-semibold text-amber-200" : "font-semibold text-emerald-200"}>{message}</p>
            {response.session_id && <p className="mt-1 break-all text-sm text-slate-200">Planning session ID: {response.session_id}</p>}
            {existingWorkflow ? (
                <Link to={workflowPath ?? "/workflows"} className="mt-3 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    {workflowPath ? "Open existing workflow" : "Browse workflows"}
                </Link>
            ) : response.session_id && (
                <Link to={`/candidate-planning/${encodeURIComponent(response.session_id)}`} className="mt-3 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    {savedPlan ? "Review saved plan" : isError ? "Review planning details" : "Continue planning"}
                </Link>
            )}
            <p className="mt-1 text-sm text-slate-400">Status: {formatLabel(response.status)}</p>
            <p className="mt-1 text-sm text-slate-400">Intake status: {formatLabel(response.intake_status)}</p>
            {response.intake_reason_codes.length > 0 && <p className="mt-1 text-sm text-slate-400">Reason codes: {response.intake_reason_codes.join(", ")}</p>}
            {response.unsupported_reason && <p className="mt-1 text-sm text-slate-400">Unsupported reason: {response.unsupported_reason}</p>}
            {response.planning_failure && <p className="mt-1 text-sm text-slate-400">Failure: {response.planning_failure.code} - {response.planning_failure.message}</p>}
        </div>
    );
}

function planningMessage(response: CandidatePlanningResponse): string {
    if (response.planning_failure?.code === "atlas_core_unavailable") return "Atlas Core unavailable during authoritative revalidation.";
    if (response.planning_failure?.code === "persistence_failed") return "Planning session could not be persisted.";
    if (hasExistingWorkflow(response)) return "A workflow already exists for this proposal. Review its progress and any remaining approvals.";
    if (response.status === "plan_ready" && response.session_id) return "A saved plan is available to review.";
    if (response.status === "ready_for_planning" && response.session_id && response.planning_allowed) {
        return "Planning session created. Next step: generate a candidate plan.";
    }
    if (response.status === "unsupported_intent") return "Unsupported intent. Atlas Agent cannot plan this candidate yet.";
    if (response.status.includes("stale") || response.planning_failure?.code === "candidate_stale") return "This proposal changed or expired. Choose Refresh proposal to check its latest state.";
    if (response.status === "intake_rejected") return "Planning intake rejected by Atlas Core.";
    return "Atlas Agent returned a planning intake response.";
}

function formatExpiry(value: string | null | undefined): string {
    if (value === null || value === undefined) return "No expiry";
    const parsed = evidenceTimestamp(value);
    return parsed === null ? "Unverified expiry" : new Date(parsed).toLocaleString();
}

function getPlanningActionState(candidate: ExecutionCandidate | null): { enabled: boolean; reason: string } {
    if (!candidate) return { enabled: false, reason: "Candidate is not loaded." };
    if (candidate.expires_at !== null && candidate.expires_at !== undefined) {
        const expiresAt = evidenceTimestamp(candidate.expires_at);
        if (expiresAt === null) return { enabled: false, reason: "The expiry time could not be confirmed. Open a current proposal to continue." };
        if (expiresAt <= Date.now()) return { enabled: false, reason: "Candidate has expired." };
    }
    if (candidate.status !== "eligible") {
        return { enabled: false, reason: "Candidate is not eligible for planning." };
    }
    return { enabled: true, reason: "" };
}

function InfoPanel({ title, children }: { title: string; children: React.ReactNode }) {
    return <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5"><h2 className="text-lg font-semibold text-white">{title}</h2><div className="mt-4 space-y-3">{children}</div></section>;
}

function DetailField({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-sm text-slate-200">{value}</dd></div>;
}

function ListField({ label, values, empty }: { label: string; values: string[]; empty: string }) {
    return <div><h3 className="sr-only">{label}</h3>{values.length > 0 ? <ul className="space-y-2 text-sm text-slate-300">{values.map((value) => <li key={value} className="break-all rounded-lg bg-slate-950/50 px-3 py-2">{value}</li>)}</ul> : <p className="text-sm text-slate-500">{empty}</p>}</div>;
}
