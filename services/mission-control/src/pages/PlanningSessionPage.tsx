import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PlanningProgress } from "../components/PlanningProgress";
import { existingWorkflowPath, hasExistingWorkflow } from "../utils/existingWorkflow";
import { isReadableWorkflowSummary } from "../utils/workflowSummary";

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
    OperationalCandidatePlanApiResponse,
} from "../types/atlasAgent";

export function PlanningSessionPage() {
    const { sessionId = "" } = useParams<{ sessionId: string }>();
    return <PlanningSession key={sessionId} sessionId={sessionId} />;
}

function isReadableRepositoryPlan(plan: CandidatePlanApiResponse): boolean {
    if (!plan || typeof plan !== "object" || Array.isArray(plan)) return false;
    const text = [plan.title, plan.objective];
    const lists = [plan.assumptions, plan.constraints, plan.proposed_steps, plan.likely_affected_files,
        plan.verification_strategy, plan.rollback_considerations, plan.unresolved_questions, plan.evidence_ids];
    const references = [plan.repository_branch, plan.repository_head];
    return text.every(value => typeof value === "string")
        && lists.every(value => Array.isArray(value) && value.every(item => typeof item === "string"))
        && references.every(value => value === null || value === undefined || typeof value === "string");
}

function isPlanningRouteReference(value: unknown): boolean {
    if (typeof value !== "string" || !value || value.trim() !== value || value === "." || value === ".."
        || Array.from(value).some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)) return false;
    try {
        encodeURIComponent(value);
        return true;
    } catch {
        return false;
    }
}

function isReadablePlanningSession(session: CandidatePlanningResponse): boolean {
    if (!session || typeof session !== "object" || Array.isArray(session)) return false;
    const optional = [session.candidate_fingerprint, session.predecessor_session_id, session.unsupported_reason];
    const failure = session.planning_failure;
    const readableFailure = failure === null || (typeof failure === "object" && !Array.isArray(failure)
        && typeof failure?.code === "string" && typeof failure?.message === "string");
    // Retain Browse workflows for legacy unusable references; avoid URI encoding failures.
    try {
        if (typeof session.workflow_session_id === "string") encodeURIComponent(session.workflow_session_id);
    } catch {
        return false;
    }
    return typeof session.status === "string" && session.status.trim().length > 0
        && typeof session.planning_allowed === "boolean" && isPlanningRouteReference(session.candidate_id)
        && optional.every(value => value === null || value === undefined || typeof value === "string")
        && (session.successor_session_id === null || session.successor_session_id === undefined
            || session.successor_session_id === "" || isPlanningRouteReference(session.successor_session_id))
        && readableFailure;
}

function PlanningSession({ sessionId }: { sessionId: string }) {
    const [session, setSession] = useState<CandidatePlanningResponse | null>(null);
    const [plan, setPlan] = useState<CandidatePlanApiResponse | null>(null);
    const [operationalPlan, setOperationalPlan] = useState<OperationalCandidatePlanApiResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generateError, setGenerateError] = useState<string | null>(null);
    const [workflow, setWorkflow] = useState<CandidateWorkflowResponse | null>(null);
    const [isCreatingWorkflow, setIsCreatingWorkflow] = useState(false);
    const [workflowError, setWorkflowError] = useState<string | null>(null);
    const [readRevision, setReadRevision] = useState(0);
    const readPending = useRef(true);
    const hasPlan = Boolean(plan || operationalPlan);

    function refreshPlanning() {
        if (readPending.current || isGenerating || isCreatingWorkflow) return;
        readPending.current = true;
        setIsLoading(true);
        setError(null);
        setSession(null);
        setPlan(null);
        setOperationalPlan(null);
        setWorkflow(null);
        setGenerateError(null);
        setWorkflowError(null);
        setReadRevision(revision => revision + 1);
    }

    useEffect(() => {
        let cancelled = false;

        getCandidatePlanningSession(sessionId)
            .then(async (nextSession) => {
                if (cancelled) {
                    return;
                }
                if (nextSession && nextSession.session_id !== sessionId) {
                    setError("The returned planning session does not match this page.");
                    return;
                }
                if (nextSession !== null && !isReadablePlanningSession(nextSession)) {
                    setError("The planning session response is incomplete or unreadable.");
                    return;
                }
                let loadedPlan = nextSession?.plan ?? null;
                const loadedOperationalPlan = nextSession?.operational_plan ?? null;
                if (loadedPlan !== null && loadedOperationalPlan !== null) {
                    setError("The planning response contains conflicting plan types. Reload to check again.");
                    return;
                }
                if (loadedOperationalPlan !== null && (!nextSession || !validOperationalPlan(loadedOperationalPlan, nextSession))) {
                    setError("The maintenance plan does not match this planning session or target.");
                    return;
                }
                if (loadedPlan === null && loadedOperationalPlan === null && nextSession?.status === "plan_ready") loadedPlan = await getCandidatePlan(sessionId);
                if (cancelled) return;
                if (loadedPlan && (!nextSession || loadedPlan.session_id !== sessionId || loadedPlan.candidate_id !== nextSession.candidate_id)) {
                    setError("The returned plan does not match this planning session.");
                    return;
                }
                if (loadedPlan !== null && !isReadableRepositoryPlan(loadedPlan)) {
                    setError("The repository plan response is incomplete or unreadable.");
                    return;
                }
                if (nextSession?.status === "plan_ready" && loadedPlan === null && loadedOperationalPlan === null) {
                    setError("The saved plan could not be loaded. Reload to check again.");
                    return;
                }
                setSession(nextSession);
                setPlan(loadedPlan);
                setOperationalPlan(loadedOperationalPlan);
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
                    readPending.current = false;
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId, readRevision]);

    const sessionState = useMemo(() => describeSessionState(session, error), [session, error]);

    async function generatePlan() {
        if (readPending.current || !session || session.planning_allowed !== true || session.status !== "ready_for_planning" || isGenerating) {
            return;
        }

        setIsGenerating(true);
        setGenerateError(null);

        try {
            const response = await generateCandidatePlan(sessionId);
            if (!response || response.session_id !== sessionId || response.candidate_id !== session.candidate_id) {
                setGenerateError("The planning response did not match this session. No plan was opened.");
                return;
            }
            if (!isReadablePlanningSession(response)) {
                setGenerateError("The planning session response is incomplete or unreadable.");
                return;
            }
            setSession(response);
            const generatedOperationalPlan = response.operational_plan ?? null;
            if (response.plan && generatedOperationalPlan) {
                setGenerateError("The planning response contains conflicting plan types. Reload to check again.");
                return;
            }
            if (generatedOperationalPlan !== null && !validOperationalPlan(generatedOperationalPlan, response)) {
                setGenerateError("The maintenance plan does not match this planning session or target.");
                return;
            }
            const generatedPlan = response.plan ?? (generatedOperationalPlan ? null : await getCandidatePlan(sessionId));
            if (generatedPlan && (generatedPlan.session_id !== sessionId || generatedPlan.candidate_id !== session.candidate_id)) {
                setGenerateError("The returned plan does not match this planning session.");
                return;
            }
            if (generatedPlan !== null && !isReadableRepositoryPlan(generatedPlan)) {
                setGenerateError("The repository plan response is incomplete or unreadable.");
                return;
            }
            if (response.status === "plan_ready" && generatedPlan === null && generatedOperationalPlan === null) {
                setGenerateError("The generated plan could not be loaded. Reload to check again.");
                return;
            }
            setPlan(generatedPlan);
            setOperationalPlan(generatedOperationalPlan);
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
        if (readPending.current || !session || session.planning_allowed !== true || session.status !== "plan_ready" || isCreatingWorkflow) {
            return;
        }

        setIsCreatingWorkflow(true);
        setWorkflowError(null);

        try {
            const response = await createCandidateWorkflowShell(sessionId);
            if (!response || response.candidate_planning_session_id !== sessionId || response.candidate_id !== session.candidate_id) {
                setWorkflowError("The workflow response did not match this planning session. No workflow was opened.");
                return;
            }
            if (!isReadableWorkflowSummary(response)) {
                setWorkflowError("The workflow summary response is incomplete or unreadable.");
                return;
            }
            setWorkflow(response);
        } catch (requestError) {
            console.error(`Unable to create workflow shell for ${sessionId}:`, requestError);
            setWorkflowError(
                getAtlasAgentErrorMessage(
                    requestError,
                    "Atlas Agent could not create this workflow.",
                ),
            );
        } finally {
            setIsCreatingWorkflow(false);
        }
    }

    if (isLoading) {
        return (
            <main className="mx-auto max-w-6xl space-y-6 p-8">
                <Link to="/execution-candidates" className="text-sm text-blue-300">← Change proposals</Link>
                <p role="status" className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    Loading planning session…
                </p>
            </main>
        );
    }

    if (error || session === null) {
        return (
            <main className="mx-auto max-w-6xl space-y-6 p-8">
                <Link to="/execution-candidates" className="text-sm text-blue-300">← Change proposals</Link>
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-xl font-semibold text-red-100">{error ? "Planning unavailable" : "Planning session not found"}</h1>
                    <p className="mt-2 text-sm text-slate-300">{error ?? "Planning session was not found."}</p>
                    <button type="button" onClick={refreshPlanning} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>
                </section>
            </main>
        );
    }

    const existingWorkflow = hasExistingWorkflow(session);
    const workflowPath = existingWorkflowPath(session);

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1 basis-80">
                        <p className="text-xs uppercase tracking-[0.3em] text-blue-300">
                            Change planning
                        </p>
                        <h1 className="mt-3 break-words text-3xl font-bold text-white">
                            {existingWorkflow ? "Review existing workflow" : hasPlan ? "Review saved plan" : "Plan this change"}
                        </h1>
                        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                            {existingWorkflow ? "This proposal already has a workflow. Review its progress; any remaining changes still need separate approvals." : hasPlan ? "This session has a saved plan. Review its details below; any later changes still need separate approvals." : "Review or generate a plan for this proposal. A ready plan can be passed to a workflow; changes still need separate approvals."}
                        </p>
                    </div>
                    <button type="button" onClick={refreshPlanning} disabled={isGenerating || isCreatingWorkflow} className="mc-control mc-focusable rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50">Refresh planning</button>
                </div>
                <PlanningProgress current={workflow || existingWorkflow ? "Workflow" : hasPlan ? "Candidate Plan" : "Planning Session"} />
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
                <details className="mt-5 rounded-lg border border-slate-800 p-3">
                    <summary className="cursor-pointer text-sm text-slate-300">Technical details</summary>
                    <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Planning Session ID" value={session.session_id ?? sessionId} />
                        <Detail label="Candidate ID" value={session.candidate_id} />
                        <Detail label="Planning status" value={formatLabel(session.status)} />
                        <Detail label="Candidate fingerprint" value={session.candidate_fingerprint ?? "Not available"} />
                    </dl>
                </details>
                <Link to={`/execution-candidates/${encodeURIComponent(session.candidate_id)}`} className="mt-4 inline-flex text-sm text-blue-300">Review original proposal</Link>
            </section>

            {existingWorkflow && <section role="status" aria-label="Existing workflow" className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-5">
                <h2 className="text-lg font-semibold text-white">Workflow already exists</h2>
                <p className="mt-2 text-sm text-slate-300">Review the workflow’s progress and any remaining approvals. Opening it does not approve or run anything.</p>
                <Link to={workflowPath ?? "/workflows"} className="mt-3 inline-flex text-sm font-semibold text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300">{workflowPath ? "Open existing workflow" : "Browse workflows"}</Link>
            </section>}

            {(!existingWorkflow || hasPlan) && <section aria-labelledby="generate-plan-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="generate-plan-heading" className="text-lg font-semibold text-white">{hasPlan ? "Saved plan" : "Plan"}</h2>
                {!generateError && <p className="mt-2 text-sm text-slate-400">
                    {existingWorkflow ? "Planning has already led to a workflow. Any saved plan below is for review." : hasPlan ? "Review the saved plan below. Later changes still need separate approvals." : "Generate a plan to review. This does not apply changes or grant approval."}
                </p>}
                {!existingWorkflow && session.status === "ready_for_planning" && session.planning_allowed === true && !hasPlan && (
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button type="button" onClick={generatePlan} disabled={isGenerating} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                            {isGenerating ? "Generating plan..." : "Generate Plan"}
                        </button>
                        {isGenerating && <p className="text-sm text-slate-400">Generating plan...</p>}
                    </div>
                )}
                {!existingWorkflow && (session.status !== "ready_for_planning" || session.planning_allowed !== true) && !hasPlan && !generateError && (
                    <p className="mt-4 text-sm text-slate-400">{nonReadyMessage(session)}</p>
                )}
                {generateError && (
                    <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                        <p className="font-semibold text-red-300">Plan result unavailable</p>
                        <p className="mt-1 text-sm text-red-200/80">{generateError}</p>
                        <p className="mt-2 text-sm text-slate-300">Check saved planning before trying again. This only reloads saved information.</p>
                        <button type="button" onClick={refreshPlanning} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Check saved planning</button>
                    </div>
                )}
                {plan && <PlanViewer plan={plan} />}
                {operationalPlan && <MaintenancePlanViewer plan={operationalPlan} />}
            </section>}

            {hasPlan && !existingWorkflow && (
                <section aria-labelledby="workflow-shell-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <h2 id="workflow-shell-heading" className="text-lg font-semibold text-white">{workflow ? "Workflow result" : session.status === "plan_ready" && session.planning_allowed === true ? "Create a workflow" : "Workflow creation unavailable"}</h2>
                    <p className="mt-2 text-sm text-slate-400">
                        {workflow ? "Review the returned workflow details below. Later changes still need separate approvals." : session.status === "plan_ready" && session.planning_allowed === true ? "Create a workflow from this plan. You will approve any later changes separately." : "Creating a workflow is not available for this session. You can review this plan and refresh planning to check the latest status."}
                    </p>
                    {session.status === "plan_ready" && session.planning_allowed === true && !workflow && (
                        <div className="mt-4 flex flex-wrap items-center gap-3">
                            <button type="button" onClick={createWorkflow} disabled={isCreatingWorkflow} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                                {isCreatingWorkflow ? "Creating workflow..." : "Create Workflow"}
                            </button>
                            {isCreatingWorkflow && <p className="text-sm text-slate-400">Creating workflow...</p>}
                        </div>
                    )}
                    {workflowError && (
                        <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                            <p className="font-semibold text-red-300">Workflow result unavailable</p>
                            <p className="mt-1 text-sm text-red-200/80">{workflowError}</p>
                            <p className="mt-2 text-sm text-slate-300">Check saved planning before trying again. This only reloads saved information.</p>
                            <button type="button" onClick={refreshPlanning} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Check saved planning</button>
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
            {workflow.reason_codes.length > 0 && <p className="mt-3 text-sm text-slate-400">Reason codes: {workflow.reason_codes.join(", ")}</p>}
            {workflow.failure && <p className="mt-3 text-sm text-slate-400">Failure: {workflow.failure.code} - {workflow.failure.message}</p>}
            {workflow.workflow_session_id && (
                <Link to={`/candidate-planning/${encodeURIComponent(workflow.candidate_planning_session_id)}/workflow`} state={{ workflow }} className="mt-4 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Review workflow
                </Link>
            )}
            <details className="mt-4 rounded-lg border border-slate-700/70 p-3">
                <summary className="mc-focusable cursor-pointer text-sm text-blue-300">Workflow details</summary>
                <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                    <Detail label="Workflow ID" value={workflow.workflow_session_id ?? "Not available"} />
                    <Detail label="Workflow status" value={workflow.workflow_status ? formatLabel(workflow.workflow_status) : "Not available"} />
                    <Detail label="Implementation approval pending" value={workflow.implementation_approval_request_id ? "Yes" : "Not reported"} />
                    <Detail label="Conversion status" value={formatLabel(workflow.conversion_status)} />
                </dl>
            </details>
        </div>
    );
}

function workflowMessage(workflow: CandidateWorkflowResponse): string {
    if (workflow.conversion_status === "workflow_exists") return "Workflow already exists.";
    if (workflow.workflow_session_id && workflow.failure === null) return "Workflow available for review.";
    if (workflow.failure?.code === "candidate_stale" || workflow.conversion_status.includes("stale")) return "Stale candidate.";
    if (workflow.failure?.code === "candidate_fingerprint_mismatch" || workflow.failure?.code === "plan_fingerprint_mismatch") return "Plan mismatch.";
    if (workflow.failure?.code === "workflow_translation_unsupported" || workflow.failure?.code === "unsupported_intent") return "Unsupported intent.";
    if (workflow.failure?.code === "atlas_core_unavailable") return "Atlas Core unavailable.";
    if (workflow.failure?.code === "persistence_failed") return "Persistence failure.";
    return "Workflow creation did not complete.";
}

function validOperationalPlan(plan: OperationalCandidatePlanApiResponse, session: CandidatePlanningResponse): boolean {
    if (!plan || typeof plan !== "object" || plan.effect_kind !== "operational_action"
        || plan.session_id !== session.session_id || plan.candidate_id !== session.candidate_id) return false;
    const fields = [plan.identifier, plan.candidate_fingerprint, plan.execution_intent, plan.provider_id,
        plan.resource_id, plan.resource_type, plan.target_fingerprint, plan.expected_pre_state,
        plan.intended_action, plan.disruption_scope, plan.created_at, plan.revalidated_candidate_fingerprint,
        plan.verification?.pre_state, plan.verification?.expected_post_state,
        plan.verification?.identity_fingerprint, plan.verification?.health_requirement, plan.verification?.unknown_outcome_policy];
    return fields.every((value) => typeof value === "string" && value.trim().length > 0)
        && (plan.target_version === null || typeof plan.target_version === "string")
        && plan.verification.identity_fingerprint === plan.target_fingerprint
        && plan.verification.pre_state === plan.expected_pre_state
        && Array.isArray(plan.failure_considerations) && plan.failure_considerations.every((value) => typeof value === "string")
        && Array.isArray(plan.evidence_ids) && plan.evidence_ids.every((value) => typeof value === "string");
}

function MaintenancePlanViewer({ plan }: { plan: OperationalCandidatePlanApiResponse }) {
    return <article className="mt-5 space-y-5 rounded-xl border border-blue-400/30 bg-blue-400/5 p-5">
        <h3 className="text-xl font-bold text-white">Maintenance plan</h3>
        <p className="text-sm text-slate-300">Review this plan before creating a workflow. This does not restart anything; the action still needs a separate exact approval.</p>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <Detail label="Action" value={formatLabel(plan.intended_action)} />
            <Detail label="Target" value={`${plan.provider_id}/${plan.resource_type}/${plan.resource_id}`} />
            <Detail label="Expected starting state" value={plan.expected_pre_state} />
            <Detail label="Expected disruption" value={plan.disruption_scope} />
        </dl>
        <section aria-labelledby="maintenance-verification-heading">
            <h4 id="maintenance-verification-heading" className="font-semibold text-white">Verification after the action</h4>
            <dl className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
                <Detail label="Expected outcome" value={plan.verification.expected_post_state} />
                <Detail label="Health check" value={plan.verification.health_requirement} />
                <Detail label="Uncertain outcome" value={plan.verification.unknown_outcome_policy} />
            </dl>
        </section>
        <ListPanel title="Failure considerations" values={plan.failure_considerations} empty="No failure considerations supplied." />
        <details>
            <summary className="mc-focusable cursor-pointer text-sm text-blue-300">Plan references</summary>
            <dl className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
                <Detail label="Plan ID" value={plan.identifier} />
                <Detail label="Execution intent" value={plan.execution_intent} />
                <Detail label="Target fingerprint" value={plan.target_fingerprint} />
                <Detail label="Target version" value={plan.target_version ?? "Not supplied"} />
                <Detail label="Candidate fingerprint" value={plan.candidate_fingerprint} />
                <Detail label="Created time" value={plan.created_at} />
            </dl>
            <ListPanel title="Evidence IDs" values={plan.evidence_ids} empty="No evidence IDs listed." />
        </details>
    </article>;
}

function PlanViewer({ plan }: { plan: CandidatePlanApiResponse }) {
    return (
        <article className="mt-5 min-w-0 space-y-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-5 [overflow-wrap:anywhere]">
            <div>
                <p className="text-sm font-semibold text-emerald-200">Plan details</p>
                <h3 className="mt-2 text-xl font-bold text-white">{plan.title}</h3>
                <p className="mt-2 text-sm text-slate-300">Objective: {plan.objective}</p>
            </div>
            <section className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
                <ListPanel title="Planning assumptions" values={plan.assumptions} empty="No assumptions listed." />
                <ListPanel title="Constraints" values={plan.constraints} empty="No constraints listed." />
                <ListPanel title="Proposed steps" values={plan.proposed_steps} empty="No proposed steps listed." ordered />
                <ListPanel title="Affected files" values={plan.likely_affected_files} empty="No affected files listed." />
                <ListPanel title="Verification strategy" values={plan.verification_strategy} empty="No verification strategy listed." />
                <ListPanel title="Rollback considerations" values={plan.rollback_considerations} empty="No rollback considerations listed." />
                <ListPanel title="Unresolved questions" values={plan.unresolved_questions} empty="No unresolved questions." />
            </section>
            <details className="min-w-0 rounded-lg border border-slate-700/70 p-3">
                <summary className="mc-focusable cursor-pointer text-sm text-blue-300">Plan references</summary>
                <section className="mt-3 grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
                    <ListPanel title="Affected repository" values={[plan.repository_branch ? `Branch: ${plan.repository_branch}` : "Branch: unknown", plan.repository_head ? `Commit: ${plan.repository_head}` : "Commit: unknown"]} empty="Repository context unavailable." />
                    <ListPanel title="Evidence IDs" values={plan.evidence_ids} empty="No evidence IDs listed." />
                </section>
            </details>
        </article>
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
    if (session.planning_allowed !== true) return "Planning is not available for this session.";
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
