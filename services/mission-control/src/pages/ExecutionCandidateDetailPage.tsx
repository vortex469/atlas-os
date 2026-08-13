import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAtlasErrorMessage } from "../api/atlas";
import {
    createCandidatePlanningSession,
    getAtlasAgentErrorMessage,
} from "../api/atlas-agent";
import { getExecutionCandidate } from "../api/executionCandidates";
import type { CandidatePlanningResponse } from "../types/atlasAgent";
import type { ExecutionCandidate } from "../types/executionCandidates";
import { WorkflowRail } from "./ExecutionCandidatesPage";

export function ExecutionCandidateDetailPage() {
    const { candidateId = "" } = useParams<{ candidateId: string }>();
    const [candidate, setCandidate] = useState<ExecutionCandidate | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);
    const [planningResponse, setPlanningResponse] = useState<CandidatePlanningResponse | null>(null);
    const [planningError, setPlanningError] = useState<string | null>(null);
    const [isPlanningPending, setIsPlanningPending] = useState(false);

    useEffect(() => {
        let cancelled = false;

        getExecutionCandidate(candidateId)
            .then((nextCandidate) => {
                if (!cancelled) {
                    setCandidate(nextCandidate);
                }
            })
            .catch((requestError: unknown) => {
                if (cancelled) return;
                console.error(`Unable to load execution candidate ${candidateId}:`, requestError);
                const message = getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not load this execution candidate.",
                );
                if (message.toLowerCase().includes("not found") || message.toLowerCase().includes("not present")) {
                    setNotFound(true);
                }
                setError(message);
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [candidateId]);

    const actionState = useMemo(() => getPlanningActionState(candidate), [candidate]);

    async function askAtlasAgentToPlan() {
        if (!candidate || !actionState.enabled || isPlanningPending) {
            return;
        }

        setIsPlanningPending(true);
        setPlanningError(null);
        setPlanningResponse(null);

        try {
            const response = await createCandidatePlanningSession({
                candidate_id: candidate.id,
            });
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
            setIsPlanningPending(false);
        }
    }

    if (isLoading) {
        return <PageFrame><p className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">Loading execution candidate…</p></PageFrame>;
    }

    if (notFound) {
        return <PageFrame><section className="rounded-xl border border-slate-800 bg-slate-900/70 p-6"><h1 className="text-2xl font-bold text-white">Execution candidate not found</h1><p className="mt-2 text-sm text-slate-400">Atlas Core could not find a current candidate for {candidateId}.</p></section></PageFrame>;
    }

    if (error || candidate === null) {
        return <PageFrame><div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"><p className="font-semibold text-red-300">Execution candidate unavailable</p><p className="mt-1 text-sm text-red-200/80">{error ?? "Mission Control could not load this execution candidate."}</p></div></PageFrame>;
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <Link to="/execution-candidates" className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    ← Execution Candidates
                </Link>
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Execution Candidate</p>
                    <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h1 className="break-all text-3xl font-bold text-white">{candidate.id}</h1>
                            <p className="mt-2 text-sm text-slate-400">{statusText(candidate.status)}</p>
                        </div>
                        <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">{formatLabel(candidate.execution_intent)}</span>
                    </div>
                    <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                        Eligibility means Atlas Agent may consider this candidate for planning. It does not mean implementation, approval, or execution has occurred.
                    </p>
                </div>
                <WorkflowRail activeStep="Planning Session" />
            </header>

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5" aria-labelledby="planning-action-heading">
                <h2 id="planning-action-heading" className="text-lg font-semibold text-white">Planning session</h2>
                <p className="mt-2 text-sm text-slate-400">
                    Mission Control sends only the candidate ID to Atlas Agent. Atlas Agent revalidates the current candidate with Atlas Core before creating or reusing a planning-only session.
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button type="button" onClick={askAtlasAgentToPlan} disabled={!actionState.enabled || isPlanningPending} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                        {isPlanningPending ? "Requesting planning session…" : "Ask Atlas Agent to plan"}
                    </button>
                    {(!actionState.enabled || isPlanningPending) && <p className="text-sm text-slate-400">{isPlanningPending ? "Planning request is already pending." : actionState.reason}</p>}
                </div>
                {planningResponse && <PlanningResult response={planningResponse} />}
                {planningError && <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4"><p className="font-semibold text-red-300">Atlas Agent unavailable</p><p className="mt-1 text-sm text-red-200/80">{planningError}</p></div>}
            </section>

            <section className="grid gap-4 lg:grid-cols-2" aria-label="Execution candidate details">
                <InfoPanel title="Immutable identity">
                    <DetailField label="Candidate ID" value={candidate.id} />
                    <DetailField label="Created" value={formatTimestamp(candidate.created_at)} />
                    <DetailField label="Expires" value={candidate.expires_at ? formatTimestamp(candidate.expires_at) : "No expiry"} />
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
                    <DetailField label="Required approval level" value={formatLabel(candidate.required_approval_level)} />
                </InfoPanel>
                <InfoPanel title="Compatibility and relationships">
                    <DetailField label="Compatibility assessment ID" value={candidate.compatibility_assessment_id ?? "Not reported"} />
                    <DetailField label="Compatibility status" value={candidate.compatibility_status ? formatLabel(candidate.compatibility_status) : "Not reported"} />
                    <ListField label="Relationship IDs" values={candidate.relationship_ids} empty="No relationship IDs." />
                </InfoPanel>
            </section>

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
            <Link to="/execution-candidates" className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">← Execution Candidates</Link>
            {children}
        </main>
    );
}

function PlanningResult({ response }: { response: CandidatePlanningResponse }) {
    const message = planningMessage(response);
    const isError = !response.planning_allowed || response.planning_failure !== null || response.session_id === null;

    return (
        <div role={isError ? "alert" : "status"} className={["mt-4 rounded-lg border p-4", isError ? "border-amber-500/30 bg-amber-500/10" : "border-emerald-500/30 bg-emerald-500/10"].join(" ")}>
            <p className={isError ? "font-semibold text-amber-200" : "font-semibold text-emerald-200"}>{message}</p>
            {response.session_id && <p className="mt-1 break-all text-sm text-slate-200">Planning session ID: {response.session_id}</p>}
            {response.session_id && (
                <Link to={`/candidate-planning/${encodeURIComponent(response.session_id)}`} className="mt-3 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Open planning session
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
    if (response.status === "ready_for_planning" && response.session_id) {
        return "Planning session created. Next step: generate a candidate plan.";
    }
    if (response.status === "unsupported_intent") return "Unsupported intent. Atlas Agent cannot plan this candidate yet.";
    if (response.status.includes("stale") || response.planning_failure?.code === "candidate_stale") return "Candidate is stale. Refresh the candidate and try again.";
    if (response.status === "intake_rejected") return "Planning intake rejected by Atlas Core.";
    return "Atlas Agent returned a planning intake response.";
}

function getPlanningActionState(candidate: ExecutionCandidate | null): { enabled: boolean; reason: string } {
    if (!candidate) return { enabled: false, reason: "Candidate is not loaded." };
    if (candidate.expires_at && new Date(candidate.expires_at).getTime() <= Date.now()) {
        return { enabled: false, reason: "Candidate has expired." };
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
