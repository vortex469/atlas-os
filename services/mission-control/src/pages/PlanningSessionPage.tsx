import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PlanningProgress } from "../components/PlanningProgress";

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
    const hasPlan = Boolean(plan || operationalPlan);

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
                let loadedPlan = nextSession?.plan ?? null;
                const loadedOperationalPlan = nextSession?.operational_plan ?? null;
                if (loadedPlan && loadedOperationalPlan) {
                    setError("The planning response contains conflicting plan types.");
                    return;
                }
                if (loadedOperationalPlan !== null && (!nextSession || !validOperationalPlan(loadedOperationalPlan, nextSession))) {
                    setError("The maintenance plan does not match this planning session or target.");
                    return;
                }
                if (!loadedPlan && !loadedOperationalPlan && nextSession?.status === "plan_ready") loadedPlan = await getCandidatePlan(sessionId);
                if (cancelled) return;
                if (loadedPlan && (!nextSession || loadedPlan.session_id !== sessionId || loadedPlan.candidate_id !== nextSession.candidate_id)) {
                    setError("The returned plan does not match this planning session.");
                    return;
                }
                if (nextSession?.status === "plan_ready" && loadedPlan === null && loadedOperationalPlan === null) {
                    setError("The saved plan could not be loaded.");
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
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    async function generatePlan() {
        if (!session || session.planning_allowed !== true || session.status !== "ready_for_planning" || isGenerating) {
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
            setSession(response);
            const generatedOperationalPlan = response.operational_plan ?? null;
            if (response.plan && generatedOperationalPlan) {
                setGenerateError("The planning response contains conflicting plan types.");
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
            if (response.status === "plan_ready" && generatedPlan === null && generatedOperationalPlan === null) {
                setGenerateError("The generated plan could not be loaded.");
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
        if (!session || session.planning_allowed !== true || session.status !== "plan_ready" || isCreatingWorkflow) {
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
                <Link to="/execution-candidates" className="text-sm text-blue-300">← Change proposals</Link>
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-xl font-semibold text-red-100">{error ? "Planning unavailable" : "Planning session not found"}</h1>
                    <p className="mt-2 text-sm text-slate-300">{error ?? "Planning session was not found."}</p>
                    <button type="button" onClick={() => window.location.reload()} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Reload page</button>
                </section>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Change plan</p>
                    <h1 className="mt-3 text-3xl font-bold text-white">{hasPlan ? "Review the plan" : "Plan this change"}</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        {hasPlan
                            ? "Review the proposed steps before creating a workflow. No implementation is run here; it still needs separate approval."
                            : "Generate a plan to review before creating a workflow. Planning does not apply changes or grant approval."}
                    </p>
                </div>
                <PlanningProgress current={workflow ? "Workflow" : hasPlan ? "Candidate Plan" : "Planning Session"} />
            </header>

            <section aria-labelledby="planning-context-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                    <h2 id="planning-context-heading" className="text-lg font-semibold text-white">Planning context</h2>
                    <Link to={`/execution-candidates/${encodeURIComponent(session.candidate_id)}`} className="text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">Review original proposal</Link>
                </div>
                {session.successor_session_id && (
                    <p className="mt-3 text-sm text-slate-300">
                        A newer planning session is available. <Link to={`/candidate-planning/${encodeURIComponent(session.successor_session_id)}`} className="font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">Open the latest session</Link>.
                    </p>
                )}
                <details className="mt-4 border-t border-slate-800 pt-4">
                    <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                    <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Planning session ID" value={session.session_id ?? sessionId} />
                        <Detail label="Candidate ID" value={session.candidate_id} />
                        <Detail label="Planning status" value={formatLabel(session.status)} />
                        <Detail label="Planning allowed" value={session.planning_allowed ? "Yes" : "No"} />
                        <Detail label="Candidate fingerprint" value={session.candidate_fingerprint ?? "Not available"} />
                        {session.predecessor_session_id && <Detail label="Previous session ID" value={session.predecessor_session_id} />}
                        {session.successor_session_id && <Detail label="Newer session ID" value={session.successor_session_id} />}
                        {session.intake_status && <Detail label="Intake status" value={formatLabel(session.intake_status)} />}
                        {session.intake_reason_codes.length > 0 && <Detail label="Reason codes" value={session.intake_reason_codes.join(", ")} />}
                        {session.unsupported_reason && <Detail label="Unsupported reason" value={session.unsupported_reason} />}
                        {session.planning_failure && <Detail label="Failure" value={`${session.planning_failure.code} — ${session.planning_failure.message}`} />}
                    </dl>
                </details>
            </section>

            <section aria-labelledby="generate-plan-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="generate-plan-heading" className="text-lg font-semibold text-white">Candidate plan</h2>
                <p className="mt-2 text-sm text-slate-400">{planSectionDescription(session, hasPlan)}</p>
                {session.status === "ready_for_planning" && session.planning_allowed === true && !hasPlan && !generateError && (
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button type="button" onClick={generatePlan} disabled={isGenerating} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                            {isGenerating ? "Generating plan..." : "Generate Plan"}
                        </button>
                    </div>
                )}
                {generateError && (
                    <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                        <p className="font-semibold text-red-300">Plan generation failed</p>
                        <p className="mt-1 text-sm text-red-200/80">{generateError}</p>
                        <p className="mt-2 text-sm text-red-200/80">Reload to check whether Atlas saved the plan before trying again.</p>
                        <button type="button" onClick={() => window.location.reload()} className="mc-control mc-focusable mt-3 px-3 py-2 text-sm font-semibold">Reload page</button>
                    </div>
                )}
                {plan && <PlanViewer plan={plan} />}
                {operationalPlan && <MaintenancePlanViewer plan={operationalPlan} />}
            </section>

            {hasPlan && (
                <section aria-labelledby="workflow-shell-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <h2 id="workflow-shell-heading" className="text-lg font-semibold text-white">Create a workflow</h2>
                    <p className="mt-2 text-sm text-slate-400">
                        Create a workflow from this plan. You will approve any later changes separately.
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
                            <p className="font-semibold text-red-300">Workflow creation failed</p>
                            <p className="mt-1 text-sm text-red-200/80">{workflowError}</p>
                        </div>
                    )}
                    {workflow && <WorkflowCreationResult workflow={workflow} />}
                    {hasPlan && session.planning_allowed !== true && (
                        <p className="mt-4 text-sm text-slate-300">You can review this plan, but this session cannot create a workflow.</p>
                    )}
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
            {workflow.workflow_session_id && (
                <Link to={`/candidate-planning/${encodeURIComponent(workflow.candidate_planning_session_id)}/workflow`} state={{ workflow }} className="mt-3 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Open Workflow
                </Link>
            )}
            <details className="mt-3 border-t border-slate-700 pt-3">
                <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                    <Detail label="Workflow ID" value={workflow.workflow_session_id ?? "Not available"} />
                    <Detail label="Workflow status" value={workflow.workflow_status ? formatLabel(workflow.workflow_status) : "Not available"} />
                    <Detail label="Implementation approval request" value={workflow.implementation_approval_request_id ?? "Not reported"} />
                    <Detail label="Conversion status" value={formatLabel(workflow.conversion_status)} />
                    <Detail label="Core revalidation status" value={workflow.core_revalidation_status ? formatLabel(workflow.core_revalidation_status) : "Not reported"} />
                </dl>
                {workflow.reason_codes.length > 0 && <p className="mt-3 break-words text-sm text-slate-400">Reason codes: {workflow.reason_codes.join(", ")}</p>}
                {workflow.failure && <p className="mt-3 break-words text-sm text-slate-400">Failure: {workflow.failure.code} — {workflow.failure.message}</p>}
            </details>
        </div>
    );
}

function workflowMessage(workflow: CandidateWorkflowResponse): string {
    if (workflow.workflow_session_id && workflow.failure === null) return "Workflow created. Implementation has not run and still needs separate approval.";
    if (workflow.conversion_status === "workflow_exists") return workflow.workflow_session_id ? "A workflow already exists for this plan. Open it to review." : "A workflow already exists for this plan, but no session was returned to open.";
    if (workflow.failure?.code === "candidate_stale" || workflow.conversion_status.includes("stale")) return "This proposal is out of date. Open it again and refresh before creating a workflow.";
    if (workflow.failure?.code === "candidate_fingerprint_mismatch" || workflow.failure?.code === "plan_fingerprint_mismatch") return "This plan no longer matches the proposal. Refresh the proposal and create a new plan before continuing.";
    if (workflow.failure?.code === "workflow_translation_unsupported" || workflow.failure?.code === "unsupported_intent") return "Atlas cannot create a workflow for this type of change yet.";
    if (workflow.failure?.code === "atlas_core_unavailable") return "Atlas could not check whether the proposal is current because Core is unavailable.";
    if (workflow.failure?.code === "persistence_failed") return "Atlas could not save the workflow. No workflow is ready to open.";
    return "Atlas could not create the workflow. Review technical details for the recorded reason.";
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
        <article className="mt-5 space-y-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-5">
            <div>
                <p className="text-sm font-semibold text-emerald-200">Plan details</p>
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

function planSectionDescription(session: CandidatePlanningResponse, hasPlan: boolean): string {
    if (hasPlan) return "Review this read-only plan. No approval or change has been made.";
    if (session.planning_failure?.code === "atlas_core_unavailable") return "Atlas could not check whether this proposal is current because Core is unavailable.";
    if (session.planning_failure?.code === "persistence_failed") return "Atlas could not save the planning session. No plan is ready to review.";
    if (session.status.includes("stale") || session.planning_failure?.code === "candidate_stale") return "This proposal is out of date. Return to the proposal and refresh before trying again.";
    if (session.status === "planning_not_supported" || session.status === "unsupported_intent") return "Atlas cannot plan this type of change yet.";
    if (session.status === "planning_failed") return "Atlas could not create a plan. Review Technical details above for the recorded reason.";
    if (session.status === "planning") return "Atlas is still creating the plan. Refresh this page to check the result.";
    if (session.status === "ready_for_planning" && session.planning_allowed === true) return "Generate a plan for review. It will not apply changes or grant approval.";
    return "Planning is unavailable for this session.";
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
