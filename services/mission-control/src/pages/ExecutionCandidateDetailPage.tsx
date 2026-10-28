import { isAxiosError } from "axios";
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
import { evidenceTimestamp } from "../utils/healthPresentation";
import { compatibilityStatusLabel, executionConstraintLabel } from "../utils/operatorLanguage";
import { PlanningProgress } from "../components/PlanningProgress";

export function ExecutionCandidateDetailPage() {
    const { candidateId = "" } = useParams<{ candidateId: string }>();
    return <CandidateDetail key={candidateId} candidateId={candidateId} />;
}

function CandidateDetail({ candidateId }: { candidateId: string }) {
    const [candidate, setCandidate] = useState<ExecutionCandidate | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [candidateLoadAttempt, setCandidateLoadAttempt] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);
    const [planningResponse, setPlanningResponse] = useState<CandidatePlanningResponse | null>(null);
    const [planningError, setPlanningError] = useState<string | null>(null);
    const [isPlanningPending, setIsPlanningPending] = useState(false);

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
                    "Mission Control could not load this execution candidate.",
                );
                if (isAxiosError(requestError) && requestError.response?.status === 404) {
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
    }, [candidateId, candidateLoadAttempt]);

    function retryCandidateRead() {
        setCandidate(null);
        setError(null);
        setNotFound(false);
        setIsLoading(true);
        setCandidateLoadAttempt((attempt) => attempt + 1);
    }

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
            setIsPlanningPending(false);
        }
    }

    if (isLoading) {
        return <PageFrame><p className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">Loading execution candidate…</p></PageFrame>;
    }

    if (notFound) {
        return <PageFrame><section className="rounded-xl border border-slate-800 bg-slate-900/70 p-6"><h1 className="text-2xl font-bold text-white">Change proposal not found</h1><p className="mt-2 text-sm text-slate-400">This proposal is no longer available. Return to Change proposals and open a current proposal.</p><details className="mt-4"><summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary><p className="mt-2 break-all text-sm text-slate-400">Proposal ID: {candidateId}</p></details></section></PageFrame>;
    }

    if (error || candidate === null) {
        return <PageFrame><div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"><p className="font-semibold text-red-300">Execution candidate unavailable</p><p className="mt-1 text-sm text-red-200/80">{error ?? "Mission Control could not load this execution candidate."}</p><button type="button" onClick={retryCandidateRead} className="mt-4 rounded-lg border border-red-300/40 px-3 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-200">Retry loading proposal</button></div></PageFrame>;
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <Link to="/execution-candidates" className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    ← Change proposals
                </Link>
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Change proposal</p>
                    <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-bold text-white">{formatLabel(candidate.execution_intent)}</h1>
                            <p className="mt-2 text-sm text-slate-300">For {candidate.target_id} ({formatLabel(candidate.target_type)})</p>
                        </div>
                        <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">{statusText(candidate.status)}</span>
                    </div>
                    <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                        Review the proposed change and its limits before planning. Planning does not approve or apply a change.
                    </p>
                </div>
                <PlanningProgress current="Execution Candidate" />
            </header>

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5" aria-labelledby="proposal-overview-heading">
                <h2 id="proposal-overview-heading" className="text-lg font-semibold text-white">Proposal overview</h2>
                <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-3">
                    <OverviewField label="Change" value={formatLabel(candidate.execution_category)} />
                    <OverviewField label="Compatibility" value={candidate.compatibility_status ? compatibilityStatusLabel(candidate.compatibility_status) : "Not reported"} />
                    <OverviewField label="Required approval level" value={formatLabel(candidate.required_approval_level)} />
                    <OverviewField label="Expires" value={formatExpiry(candidate.expires_at)} />
                </dl>
                <div className="mt-5 grid gap-5 border-t border-slate-800 pt-5 lg:grid-cols-2">
                    <div>
                        <h3 className="text-sm font-semibold text-white">Why this is proposed</h3>
                        <p className="mt-2 text-sm leading-6 text-slate-300">{candidate.rationale}</p>
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Constraints</h3>
                        <div className="mt-2"><ListField label="Constraints" values={candidate.constraints.map(executionConstraintLabel)} empty="No constraints reported." /></div>
                    </div>
                </div>
            </section>

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
                <summary className="cursor-pointer text-sm font-semibold text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical references</summary>
                <section className="mt-5 grid gap-4 lg:grid-cols-2" aria-label="Technical references">
                    <InfoPanel title="Proposal identity">
                        <DetailField label="Candidate ID" value={candidate.id} />
                        <DetailField label="Created" value={formatTimestamp(candidate.created_at)} />
                    </InfoPanel>
                    <InfoPanel title="Source recommendation">
                        <DetailField label="Source recommendation ID" value={candidate.source_recommendation_id} />
                        <DetailField label="Source subsystem" value={candidate.source_subsystem} />
                        <DetailField label="Recommendation class" value={candidate.recommendation_class} />
                        <DetailField label="Catalog item ID" value={candidate.catalog_item_id ?? "Not linked"} />
                    </InfoPanel>
                    <InfoPanel title="Compatibility references">
                        <DetailField label="Compatibility assessment ID" value={candidate.compatibility_assessment_id ?? "Not reported"} />
                        <ListField label="Relationship IDs" values={candidate.relationship_ids} empty="No relationship IDs." />
                    </InfoPanel>
                    <InfoPanel title="Evidence references">
                        <ListField label="Evidence IDs" values={candidate.evidence_ids} empty="No evidence IDs." />
                    </InfoPanel>
                </section>
            </details>
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
    const isError = !response.planning_allowed || response.planning_failure !== null || response.session_id === null;
    const canContinuePlanning = response.planning_allowed === true && response.status === "ready_for_planning";

    return (
        <div role={isError ? "alert" : "status"} className={["mt-4 rounded-lg border p-4", isError ? "border-amber-500/30 bg-amber-500/10" : "border-emerald-500/30 bg-emerald-500/10"].join(" ")}>
            <p className={isError ? "font-semibold text-amber-200" : "font-semibold text-emerald-200"}>{message}</p>
            {response.session_id && (
                <Link to={`/candidate-planning/${encodeURIComponent(response.session_id)}`} className="mt-3 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    {canContinuePlanning ? "Continue planning" : "Open planning session"}
                </Link>
            )}
            <details className="mt-3 border-t border-slate-700 pt-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary>
                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                    <DetailField label="Planning session ID" value={response.session_id ?? "Not created"} />
                    <DetailField label="Candidate fingerprint" value={response.candidate_fingerprint ?? "Not reported"} />
                    <DetailField label="Status" value={formatLabel(response.status)} />
                    <DetailField label="Planning allowed" value={response.planning_allowed ? "Yes" : "No"} />
                    <DetailField label="Intake status" value={formatLabel(response.intake_status)} />
                    {response.intake_reason_codes.length > 0 && <DetailField label="Reason codes" value={response.intake_reason_codes.join(", ")} />}
                    {response.unsupported_reason && <DetailField label="Unsupported reason" value={response.unsupported_reason} />}
                    {response.planning_failure && <DetailField label="Failure" value={`${response.planning_failure.code} — ${response.planning_failure.message}`} />}
                </dl>
            </details>
        </div>
    );
}

function planningMessage(response: CandidatePlanningResponse): string {
    if (response.planning_failure?.code === "atlas_core_unavailable") return "Atlas could not check whether the proposal is current because Core is unavailable.";
    if (response.planning_failure?.code === "persistence_failed") return "Atlas could not save the planning session. No session is ready to continue.";
    if (response.planning_allowed && response.status === "ready_for_planning" && response.session_id) {
        return "Planning is ready. Continue to review the proposal plan. No approval or change has been made.";
    }
    if (response.status === "unsupported_intent") return "Atlas cannot plan this type of change yet.";
    if (response.status.includes("stale") || response.planning_failure?.code === "candidate_stale") return "This proposal is out of date. Refresh it and open the current proposal before continuing.";
    if (response.status === "intake_rejected") return "Atlas did not accept this proposal for planning. Review the recorded reason in technical details.";
    if (response.status === "plan_ready" && response.session_id) return "A plan is ready to review. Open the planning session to continue.";
    if (response.session_id && !response.planning_allowed) return "This planning session is not ready to continue. Open it to review its status.";
    if (response.planning_allowed) return "Atlas allowed planning but did not return a session to continue. Review the response details.";
    return "Planning could not start. Review the response details for the recorded reason.";
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

function OverviewField({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm text-slate-200">{value}</dd></div>;
}

function ListField({ label, values, empty }: { label: string; values: string[]; empty: string }) {
    return <div><h3 className="sr-only">{label}</h3>{values.length > 0 ? <ul className="space-y-2 text-sm text-slate-300">{values.map((value) => <li key={value} className="break-all rounded-lg bg-slate-950/50 px-3 py-2">{value}</li>)}</ul> : <p className="text-sm text-slate-500">{empty}</p>}</div>;
}
