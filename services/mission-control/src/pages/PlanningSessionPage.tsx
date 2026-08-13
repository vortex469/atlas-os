import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
    createCandidateWorkflowShell,
    generateCandidatePlan,
    getAtlasAgentErrorMessage,
    getCandidatePlan,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidatePlanApiResponse,
    CandidatePlanningResponse,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";

const SUPPORTED_INTENT = "update-compose-stack";

export function PlanningSessionPage() {
    const { sessionId = "" } = useParams<{ sessionId: string }>();
    const [session, setSession] = useState<CandidatePlanningResponse | null>(null);
    const [plan, setPlan] = useState<CandidatePlanApiResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generateError, setGenerateError] = useState<string | null>(null);
    const [workflow, setWorkflow] = useState<CandidateWorkflowResponse | null>(null);
    const [isCreatingWorkflow, setIsCreatingWorkflow] = useState(false);
    const [workflowError, setWorkflowError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        getCandidatePlanningSession(sessionId)
            .then(async (nextSession) => {
                if (cancelled) {
                    return;
                }
                setSession(nextSession);
                if (nextSession?.plan) {
                    setPlan(nextSession.plan);
                    return;
                }
                if (nextSession?.status === "plan_ready") {
                    const existingPlan = await getCandidatePlan(sessionId);
                    if (!cancelled) {
                        setPlan(existingPlan);
                    }
                }
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }
                console.error(`Unable to load planning session ${sessionId}:`, requestError);
                setError(
                    getAtlasAgentErrorMessage(
                        requestError,
                        "Mission Control could not load this planning session.",
                    ),
                );
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    const sessionState = useMemo(() => describeSessionState(session, error), [session, error]);

    async function generatePlan() {
        if (!session || session.status !== "ready_for_planning" || isGenerating) {
            return;
        }

        setIsGenerating(true);
        setGenerateError(null);

        try {
            const response = await generateCandidatePlan(sessionId);
            setSession(response);
            const generatedPlan = response.plan ?? await getCandidatePlan(sessionId);
            setPlan(generatedPlan);
        } catch (requestError) {
            console.error(`Unable to generate plan for ${sessionId}:`, requestError);
            setGenerateError(
                getAtlasAgentErrorMessage(
                    requestError,
                    "Atlas Agent could not generate a candidate plan.",
                ),
            );
        } finally {
            setIsGenerating(false);
        }
    }

    async function createWorkflow() {
        if (!session || session.status !== "plan_ready" || isCreatingWorkflow) {
            return;
        }

        setIsCreatingWorkflow(true);
        setWorkflowError(null);

        try {
            const response = await createCandidateWorkflowShell(sessionId);
            setWorkflow(response);
        } catch (requestError) {
            console.error(`Unable to create workflow shell for ${sessionId}:`, requestError);
            setWorkflowError(
                getAtlasAgentErrorMessage(
                    requestError,
                    "Atlas Agent could not create a workflow shell.",
                ),
            );
        } finally {
            setIsCreatingWorkflow(false);
        }
    }

    if (isLoading) {
        return (
            <main className="mx-auto max-w-6xl p-8">
                <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    Loading planning session…
                </p>
            </main>
        );
    }

    if (error || session === null) {
        return (
            <main className="mx-auto max-w-6xl space-y-6 p-8">
                <PlanningRail current="Planning Session" />
                <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <p className="font-semibold text-red-300">Atlas Agent unavailable</p>
                    <p className="mt-1 text-sm text-red-200/80">
                        {error ?? "Planning session was not found."}
                    </p>
                </div>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">
                        Candidate Planning
                    </p>
                    <h1 className="mt-3 break-all text-3xl font-bold text-white">
                        Planning Session {session.session_id ?? sessionId}
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        This page can generate and display a read-only candidate plan. It cannot create workflows, approve changes, execute changes, generate implementation requests, verify changes, or commit code.
                    </p>
                </div>
                <PlanningRail current={workflow ? "Workflow" : plan ? "Candidate Plan" : "Planning Session"} />
            </header>

            <section aria-labelledby="session-summary-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                    <h2 id="session-summary-heading" className="text-lg font-semibold text-white">
                        Planning session
                    </h2>
                    <p className="mt-1 text-sm text-slate-400">{sessionState}</p>
                    </div>
                    <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">
                        {formatLabel(session.status)}
                    </span>
                </div>
                {session.predecessor_session_id && (
                    <p className="mt-3 text-sm text-slate-300">
                        Successor of <span className="font-mono">{session.predecessor_session_id}</span>
                    </p>
                )}
                {session.successor_session_id && (
                    <p className="mt-2 text-sm text-slate-300">
                        <span>Successor planning session: </span>
                        <Link to={`/candidate-planning/${encodeURIComponent(session.successor_session_id)}`} className="font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                            {session.successor_session_id}
                        </Link>
                    </p>
                )}
                <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Planning Session ID" value={session.session_id ?? sessionId} />
                    <Detail label="Candidate ID" value={session.candidate_id} />
                    <Detail label="Planning status" value={formatLabel(session.status)} />
                    <Detail label="Created time" value="Not exposed by Atlas Agent API" />
                    <Detail label="Supported intent" value={SUPPORTED_INTENT} />
                    <Detail label="Candidate fingerprint" value={session.candidate_fingerprint ?? "Not available"} />
                </dl>
            </section>

            <section aria-labelledby="generate-plan-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="generate-plan-heading" className="text-lg font-semibold text-white">Candidate plan</h2>
                <p className="mt-2 text-sm text-slate-400">
                    Generate Plan asks Atlas Agent for a read-only plan only. Mission Control does not send workflow, approval, implementation, execution, verification, or commit requests.
                </p>
                {session.status === "ready_for_planning" && !plan && (
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button type="button" onClick={generatePlan} disabled={isGenerating} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                            {isGenerating ? "Generating plan..." : "Generate Plan"}
                        </button>
                        {isGenerating && <p className="text-sm text-slate-400">Generating plan...</p>}
                    </div>
                )}
                {session.status !== "ready_for_planning" && !plan && (
                    <p className="mt-4 text-sm text-slate-400">{nonReadyMessage(session)}</p>
                )}
                {generateError && (
                    <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                        <p className="font-semibold text-red-300">Plan generation failed</p>
                        <p className="mt-1 text-sm text-red-200/80">{generateError}</p>
                    </div>
                )}
                {plan && <PlanViewer plan={plan} />}
            </section>

            {plan && (
                <section aria-labelledby="workflow-shell-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <h2 id="workflow-shell-heading" className="text-lg font-semibold text-white">Workflow shell</h2>
                    <p className="mt-2 text-sm text-slate-400">
                        Create Workflow asks Atlas Agent to create or return an approval-gated workflow shell. Mission Control sends only the planning session ID and does not send commands, workflow payloads, implementation requests, approval fields, or repository paths.
                    </p>
                    {session.status === "plan_ready" && !workflow && (
                        <div className="mt-4 flex flex-wrap items-center gap-3">
                            <button type="button" onClick={createWorkflow} disabled={isCreatingWorkflow} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                                {isCreatingWorkflow ? "Creating workflow..." : "Create Workflow"}
                            </button>
                            {isCreatingWorkflow && <p className="text-sm text-slate-400">Creating workflow...</p>}
                        </div>
                    )}
                    {workflowError && (
                        <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                            <p className="font-semibold text-red-300">Workflow creation failed</p>
                            <p className="mt-1 text-sm text-red-200/80">{workflowError}</p>
                        </div>
                    )}
                    {workflow && <WorkflowCreationResult workflow={workflow} />}
                </section>
            )}
        </main>
    );
}

function WorkflowCreationResult({ workflow }: { workflow: CandidateWorkflowResponse }) {
    const isSuccessful = workflow.workflow_session_id !== null && workflow.failure === null;

    return (
        <div role={isSuccessful ? "status" : "alert"} className={["mt-4 rounded-lg border p-4", isSuccessful ? "border-emerald-500/30 bg-emerald-500/10" : "border-amber-500/30 bg-amber-500/10"].join(" ")}>
            <p className={isSuccessful ? "font-semibold text-emerald-200" : "font-semibold text-amber-200"}>{workflowMessage(workflow)}</p>
            <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                <Detail label="Workflow ID" value={workflow.workflow_session_id ?? "Not available"} />
                <Detail label="Workflow status" value={workflow.workflow_status ? formatLabel(workflow.workflow_status) : "Not available"} />
                <Detail label="Implementation approval pending" value={workflow.implementation_approval_request_id ? "Yes" : "Not reported"} />
                <Detail label="Conversion status" value={formatLabel(workflow.conversion_status)} />
            </dl>
            {workflow.reason_codes.length > 0 && <p className="mt-3 text-sm text-slate-400">Reason codes: {workflow.reason_codes.join(", ")}</p>}
            {workflow.failure && <p className="mt-3 text-sm text-slate-400">Failure: {workflow.failure.code} - {workflow.failure.message}</p>}
            {workflow.workflow_session_id && (
                <Link to={`/candidate-planning/${encodeURIComponent(workflow.candidate_planning_session_id)}/workflow`} state={{ workflow }} className="mt-4 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Open Workflow
                </Link>
            )}
        </div>
    );
}

function workflowMessage(workflow: CandidateWorkflowResponse): string {
    if (workflow.workflow_session_id && workflow.failure === null) return "Workflow created.";
    if (workflow.conversion_status === "workflow_exists") return "Workflow already exists.";
    if (workflow.failure?.code === "candidate_stale" || workflow.conversion_status.includes("stale")) return "Stale candidate.";
    if (workflow.failure?.code === "candidate_fingerprint_mismatch" || workflow.failure?.code === "plan_fingerprint_mismatch") return "Plan mismatch.";
    if (workflow.failure?.code === "workflow_translation_unsupported" || workflow.failure?.code === "unsupported_intent") return "Unsupported intent.";
    if (workflow.failure?.code === "atlas_core_unavailable") return "Atlas Core unavailable.";
    if (workflow.failure?.code === "persistence_failed") return "Persistence failure.";
    return "Workflow creation did not complete.";
}

function PlanViewer({ plan }: { plan: CandidatePlanApiResponse }) {
    return (
        <article className="mt-5 space-y-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-5">
            <div>
                <p className="text-sm font-semibold text-emerald-200">Plan ready</p>
                <h3 className="mt-2 text-xl font-bold text-white">{plan.title}</h3>
                <p className="mt-2 text-sm text-slate-300">Objective: {plan.objective}</p>
            </div>
            <section className="grid gap-4 lg:grid-cols-2">
                <ListPanel title="Planning assumptions" values={plan.assumptions} empty="No assumptions listed." />
                <ListPanel title="Constraints" values={plan.constraints} empty="No constraints listed." />
                <ListPanel title="Proposed steps" values={plan.proposed_steps} empty="No proposed steps listed." ordered />
                <ListPanel title="Affected repository" values={[plan.repository_branch ? `Branch: ${plan.repository_branch}` : "Branch: unknown", plan.repository_head ? `Commit: ${plan.repository_head}` : "Commit: unknown"]} empty="Repository context unavailable." />
                <ListPanel title="Affected files" values={plan.likely_affected_files} empty="No affected files listed." />
                <ListPanel title="Verification strategy" values={plan.verification_strategy} empty="No verification strategy listed." />
                <ListPanel title="Rollback considerations" values={plan.rollback_considerations} empty="No rollback considerations listed." />
                <ListPanel title="Unresolved questions" values={plan.unresolved_questions} empty="No unresolved questions." />
                <ListPanel title="Evidence IDs" values={plan.evidence_ids} empty="No evidence IDs listed." />
            </section>
        </article>
    );
}

function PlanningRail({ current }: { current: "Planning Session" | "Candidate Plan" | "Workflow" }) {
    const steps = [
        "Execution Candidate",
        "Planning Session",
        "Candidate Plan",
        "Workflow",
        "Implementation",
        "Verification",
        "Review",
        "Commit",
    ];
    const complete = new Set(["Execution Candidate", "Planning Session"]);
    if (current === "Candidate Plan" || current === "Workflow") {
        complete.add("Candidate Plan");
    }
    if (current === "Workflow") {
        complete.add("Workflow");
    }

    return (
        <section aria-label="Read-only workflow rail" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <ol className="grid gap-2 text-sm md:grid-cols-4 xl:grid-cols-8">
                {steps.map((step) => {
                    const isActive = step === current;
                    const isDisabled = !complete.has(step);
                    return (
                        <li key={step} className={[
                            "rounded-lg border px-3 py-2",
                            isActive ? "border-blue-400 bg-blue-500/10 text-blue-200" : complete.has(step) ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-slate-800 bg-slate-950/50 text-slate-500",
                        ].join(" ")}
                        >
                            <span className="block font-medium">{step}{complete.has(step) ? " ✔" : " ○"}</span>
                            <span className="text-xs">{isDisabled ? "Disabled" : "Read-only"}</span>
                        </li>
                    );
                })}
            </ol>
        </section>
    );
}

function Detail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}

function ListPanel({ title, values, empty, ordered = false }: { title: string; values: string[]; empty: string; ordered?: boolean }) {
    const List = ordered ? "ol" : "ul";
    return (
        <section className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h4 className="font-semibold text-slate-100">{title}</h4>
            {values.length > 0 ? (
                <List className="mt-3 space-y-2 text-sm text-slate-300">
                    {values.map((value) => <li key={value} className="break-words">{value}</li>)}
                </List>
            ) : <p className="mt-3 text-sm text-slate-500">{empty}</p>}
        </section>
    );
}

function describeSessionState(session: CandidatePlanningResponse | null, error: string | null): string {
    if (error) return "Atlas Agent unavailable.";
    if (!session) return "Planning session not found.";
    if (session.status === "ready_for_planning") return "Planning ready.";
    if (session.status === "planning") return "Generating plan...";
    if (session.status === "plan_ready") return "Plan ready.";
    if (session.planning_failure?.code === "atlas_core_unavailable") return "Atlas Core unavailable.";
    if (session.planning_failure?.code === "persistence_failed") return "Persistence failure.";
    if (session.status.includes("stale") || session.planning_failure?.code === "candidate_stale") return "Stale candidate.";
    if (session.status === "planning_failed") return "Planning failed.";
    if (session.status === "planning_not_supported" || session.status === "unsupported_intent") return "Planning not supported.";
    return formatLabel(session.status);
}

function nonReadyMessage(session: CandidatePlanningResponse): string {
    if (session.status === "plan_ready") return "Plan is ready.";
    if (session.planning_failure?.code === "atlas_core_unavailable") return "Atlas Core unavailable during planning.";
    if (session.planning_failure?.code === "persistence_failed") return "Planning session could not be persisted.";
    if (session.status.includes("stale") || session.planning_failure?.code === "candidate_stale") return "Candidate is stale. Refresh from the execution candidate view and try again.";
    if (session.status === "planning_failed") return session.planning_failure?.message ?? "Planning failed.";
    if (session.status === "planning_not_supported" || session.status === "unsupported_intent") return session.unsupported_reason ?? "Planning is not supported for this candidate.";
    return "Generate Plan is unavailable for this planning session state.";
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
