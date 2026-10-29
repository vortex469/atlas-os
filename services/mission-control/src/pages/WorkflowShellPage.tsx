import { PlanningProgress } from "../components/PlanningProgress";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import {
    createCandidateWorkflowShell,
    createCandidateImplementationRequest,
    createSuccessorCandidatePlanningSession,
    getAtlasAgentErrorMessage,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidateImplementationTranslationResponse,
    CandidatePlanningResponse,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";
import { workflowStageLabel } from "../utils/workflowState";

type WorkflowLocationState = {
    workflow?: CandidateWorkflowResponse;
};

export function WorkflowShellPage() {
    const { sessionId = "" } = useParams<{ sessionId: string }>();
    const location = useLocation();
    const supplied = (location.state as WorkflowLocationState | null)?.workflow;
    const initialWorkflow = supplied && supplied.candidate_planning_session_id === sessionId ? supplied : null;
    return <WorkflowShell key={JSON.stringify([sessionId, location.key])} sessionId={sessionId} initialWorkflow={initialWorkflow} />;
}

function WorkflowShell({ sessionId, initialWorkflow }: { sessionId: string; initialWorkflow: CandidateWorkflowResponse | null }) {
    const navigate = useNavigate();
    const workflowFromLocation = initialWorkflow;
    const viewGeneration = useRef(0);
    const [workflow, setWorkflow] = useState<CandidateWorkflowResponse | null>(workflowFromLocation);
    const [isCreatingImplementation, setIsCreatingImplementation] = useState(false);
    const [isCreatingSuccessor, setIsCreatingSuccessor] = useState(false);
    const [isLoadingWorkflow, setIsLoadingWorkflow] = useState(true);
    const [workflowLoadError, setWorkflowLoadError] = useState<string | null>(null);
    const [implementationError, setImplementationError] = useState<string | null>(null);
    const [implementationOutcomeUnknown, setImplementationOutcomeUnknown] = useState(false);
    const [implementationErrorDetails, setImplementationErrorDetails] = useState<string | null>(null);
    const [successorError, setSuccessorError] = useState<string | null>(null);
    const [successorErrorDetails, setSuccessorErrorDetails] = useState<string | null>(null);
    const [successorResult, setSuccessorResult] = useState<CandidatePlanningResponse | null>(null);
    const [implementationResult, setImplementationResult] = useState<CandidateImplementationTranslationResponse | null>(null);

    useEffect(() => {
        let cancelled = false;
        viewGeneration.current += 1;

        void Promise.resolve().then(async () => {
            if (cancelled) return;
            setIsLoadingWorkflow(true);
            setWorkflowLoadError(null);

            try {
                const planningSession = workflowFromLocation === null
                    ? await getCandidatePlanningSession(sessionId)
                    : null;

                if (planningSession === null && workflowFromLocation === null) {
                    throw new Error("Planning session was not found.");
                }

                if (cancelled) {
                    return;
                }

                if (planningSession && planningSession.session_id !== sessionId) {
                    setWorkflow(null);
                    setWorkflowLoadError("The returned planning session does not match this page.");
                    return;
                }
                const response = await createCandidateWorkflowShell(sessionId, {
                    expected_candidate_fingerprint: planningSession?.candidate_fingerprint ?? workflowFromLocation?.candidate_fingerprint,
                });

                if (cancelled) {
                    return;
                }

                if (!response || response.candidate_planning_session_id !== sessionId) {
                    setWorkflow(null);
                    setWorkflowLoadError("The workflow response did not match this planning session.");
                    return;
                }
                setWorkflow(response);
            } catch (error: unknown) {
                if (cancelled) {
                    return;
                }

                setWorkflow(null);
                setWorkflowLoadError(
                    getAtlasAgentErrorMessage(
                        error,
                        "Mission Control could not load this workflow summary.",
                    ),
                );
            } finally {
                if (!cancelled) {
                    setIsLoadingWorkflow(false);
                }
            }
        });

        return () => {
            cancelled = true;
            viewGeneration.current += 1;
        };
    }, [sessionId, workflowFromLocation]);
    const canCreateImplementation =
        workflow !== null
        && workflow.workflow_status === "awaiting_approval"
        && workflow.workflow_session_id !== null
        && workflow.failure === null
        && !implementationOutcomeUnknown
        && !isLoadingWorkflow
        && workflowLoadError === null;

    const canCreateStaleRecovery =
        workflow !== null
        && workflow.workflow_session_id !== null
        && implementationResult?.failure?.code === "repository_stale"
        && workflow.candidate_planning_session_id !== null
        && workflow.candidate_fingerprint !== null;

    const canCreateBlockedRecovery =
        workflow !== null
        && workflow.workflow_status === "blocked"
        && workflow.workflow_session_id !== null
        && workflow.candidate_planning_session_id !== null
        && workflow.candidate_fingerprint !== null;

    const canCreateSuccessor =
        (canCreateStaleRecovery || canCreateBlockedRecovery)
        && !isCreatingSuccessor
        && !isLoadingWorkflow
        && workflowLoadError === null;

    function isSuccessfulImplementationResponse(
        response: CandidateImplementationTranslationResponse,
    ): response is CandidateImplementationTranslationResponse & {
        workflow_session_id: string;
        implementation_request_id: string;
        exact_approval_request_id: string;
    } {
        return (
            response.failure === null
            && response.translation_status === "implementation_ready"
            && response.workflow_session_id !== null
            && response.implementation_request_id !== null
            && response.exact_approval_request_id !== null
        );
    }

    async function createImplementation() {
        if (!workflow || !canCreateImplementation || isCreatingImplementation || isLoadingWorkflow) {
            return;
        }

        const generation = viewGeneration.current;
        setIsCreatingImplementation(true);
        setImplementationError(null);
        setImplementationOutcomeUnknown(false);
        setImplementationErrorDetails(null);
        setImplementationResult(null);
        try {
            const response = await createCandidateImplementationRequest(
                sessionId,
                {
                    expected_candidate_fingerprint: workflow.candidate_fingerprint ?? undefined,
                    expected_plan_fingerprint: workflow.candidate_plan_fingerprint ?? undefined,
                },
            );
            if (generation !== viewGeneration.current) return;
            if (!response || response.candidate_planning_session_id !== sessionId
                || (response.workflow_session_id !== null && response.workflow_session_id !== workflow.workflow_session_id)) {
                setImplementationOutcomeUnknown(true);
                setImplementationError("Mission Control could not match the change request to this workflow. Reload this workflow to check its status before continuing.");
                return;
            }
            setImplementationResult(response);
            const isSuccessfulTranslation = isSuccessfulImplementationResponse(response);

            if (isSuccessfulTranslation) {
                navigate(`/workflows/${encodeURIComponent(response.workflow_session_id)}`);
            } else if (response.failure) {
                setImplementationError(implementationFailureMessage(response));
            } else {
                setImplementationOutcomeUnknown(true);
                setImplementationError(
                    "The change request result is incomplete. Reload this workflow to check its status before continuing.",
                );
            }
        } catch (error) {
            if (generation !== viewGeneration.current) return;
            setImplementationOutcomeUnknown(true);
            setImplementationError("Mission Control could not confirm whether the change request is ready. Reload this workflow to check its status before continuing.");
            setImplementationErrorDetails(getAtlasAgentErrorMessage(error, "Request preparation returned no details."));
        } finally {
            if (generation === viewGeneration.current) setIsCreatingImplementation(false);
        }
    }

    async function createSuccessorPlanningSession() {
        if (!workflow || !canCreateSuccessor || isLoadingWorkflow) {
            return;
        }

        const generation = viewGeneration.current;
        setIsCreatingSuccessor(true);
        setSuccessorError(null);
        setSuccessorErrorDetails(null);
        setSuccessorResult(null);
        try {
            const response = await createSuccessorCandidatePlanningSession(
                workflow.candidate_planning_session_id,
                {
                    expected_candidate_fingerprint: workflow.candidate_fingerprint,
                },
            );

            if (generation !== viewGeneration.current) return;
            if (response.session_id === null) {
                setSuccessorResult(response);
                return;
            }

            navigate(`/candidate-planning/${encodeURIComponent(response.session_id)}`);
        } catch (error) {
            if (generation !== viewGeneration.current) return;
            const fallback = "Successor planning request failed without additional details.";
            const details = getAtlasAgentErrorMessage(error, fallback);
            setSuccessorError("Mission Control could not confirm whether the successor planning session was created. Check the earlier planning session for a newer session before trying again.");
            setSuccessorErrorDetails(details === fallback ? null : details);
        } finally {
            if (generation === viewGeneration.current) setIsCreatingSuccessor(false);
        }
    }

    if (isLoadingWorkflow && workflow === null) {
        return (
            <main className="mx-auto max-w-6xl p-4 sm:p-8">
                <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    Loading workflow summary…
                </p>
            </main>
        );
    }

    if (!workflow) {
        return (
            <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-8">
                <PlanningProgress current={null} />
                <div role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <p className="font-semibold text-amber-200">Workflow summary unavailable</p>
                    <p className="mt-1 text-sm text-slate-300">
                        {workflowLoadError
                            ?? "Return to the planning session to create or reopen this workflow."}
                    </p>
                    <Link to={`/candidate-planning/${encodeURIComponent(sessionId)}`} className="mt-4 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Back to planning session
                    </Link>
                </div>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow preparation</p>
                    <h1 className="mt-3 text-3xl font-bold text-white">Workflow setup</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Prepare the planned change for review. You will approve it and start it in separate steps.
                    </p>
                </div>
                <PlanningProgress current="Workflow" />
            </header>

            <section aria-labelledby="workflow-summary-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <h2 id="workflow-summary-heading" className="text-lg font-semibold text-white">Workflow summary</h2>
                        <p className="mt-1 text-sm text-slate-400">{workflow.workflow_session_id ? "Workflow created." : workflowMessage(workflow)}</p>
                    </div>
                    <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">
                        {workflow.workflow_status ? workflowStageLabel(workflow.workflow_status) : formatLabel(workflow.conversion_status)}
                    </span>
                </div>
                <details className="mt-4 rounded-lg border border-slate-800 px-4 py-3">
                    <summary className="mc-focusable cursor-pointer text-sm font-semibold text-blue-200">Workflow details</summary>
                    <dl className="mt-3 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        {workflow.workflow_session_id && <Detail label="Workflow ID" value={workflow.workflow_session_id} />}
                        <Detail label="Started from" value="Candidate planning" />
                        <Detail label="Candidate ID" value={workflow.candidate_id || "Not available"} />
                        <Detail label="Candidate fingerprint" value={workflow.candidate_fingerprint ?? "Not available"} />
                        <Detail label="Plan fingerprint" value={workflow.candidate_plan_fingerprint ?? "Not available"} />
                        <Detail label="Approval request" value={workflow.implementation_approval_request_id ? "Pending" : "Not reported"} />
                        <Detail label="Planning session" value={workflow.candidate_planning_session_id || "Not available"} />
                    </dl>
                </details>
                {(workflow.reason_codes.length > 0 || workflow.failure) && (
                    <details className="mt-3 rounded-lg border border-slate-800 px-4 py-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-semibold text-blue-200">Technical details</summary>
                        <dl className="mt-3 grid gap-4 text-sm md:grid-cols-2">
                            {workflow.reason_codes.length > 0 && <Detail label="Reason codes" value={workflow.reason_codes.join(", ")} />}
                            {workflow.failure && <Detail label="Failure code" value={workflow.failure.code} />}
                            {workflow.failure && <Detail label="Failure message" value={workflow.failure.message} />}
                        </dl>
                    </details>
                )}
                {canCreateImplementation && (
                    <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
                        <h2 className="text-base font-semibold text-emerald-200">Prepare change for review</h2>
                        <p className="mt-2 text-sm text-slate-300">
                            Atlas will create a request from this plan for you to review. It does not approve or run the change.
                        </p>
                <div className="mt-4 flex flex-wrap gap-3">
                    <button
                        type="button"
                        onClick={() => void createImplementation()}
                        disabled={isCreatingImplementation || isLoadingWorkflow}
                        className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isCreatingImplementation ? "Preparing…" : "Prepare change for review"}
                    </button>
                            {isCreatingImplementation && <p role="status" className="text-sm text-slate-200">Preparing the change request for review. This does not run it.</p>}
                        </div>
                    </div>
                )}
                {canCreateSuccessor && (
                    <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                        <h2 className="text-base font-semibold text-amber-100">
                            {canCreateBlockedRecovery
                                ? "Recovery: blocked workflow"
                                : "Recovery: stale repository for approved plan"}
                        </h2>
                        <p className="mt-2 text-sm text-slate-200">
                            {canCreateBlockedRecovery
                                ? "This workflow is preserved as historical state. Create a successor planning session against the current trusted candidate and repository state before attempting another implementation."
                                : "The trusted repository state changed after plan review. This workflow and reviewed plan are historical. Re-planning here creates a successor planning session against the current trusted repository state."}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-3">
                            <button
                                type="button"
                                onClick={() => void createSuccessorPlanningSession()}
                                disabled={isCreatingSuccessor}
                                className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-amber-950 transition hover:bg-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {isCreatingSuccessor ? "Opening successor planning session..." : "Re-plan against current repository"}
                            </button>
                            {isCreatingSuccessor && <p className="text-sm text-slate-200">Creating successor planning session...</p>}
                        </div>
                    </div>
                )}
                {workflow.workflow_status === "awaiting_implementation_approval" && (
                    <p className="mt-4 text-sm text-slate-300">A change request is ready for review and approval.</p>
                )}
                {implementationResult && isSuccessfulImplementationResponse(implementationResult) && (
                    <p className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                        Change request ready. Opening it for review and approval.
                    </p>
                )}
                {implementationResult && (
                    <details className="mt-2 rounded-lg border border-slate-700 p-4 text-sm text-slate-300">
                        <summary className="mc-focusable cursor-pointer font-semibold">Request technical details</summary>
                        <p>Translation status: {implementationResult.translation_status}</p>
                        {implementationResult.failure ? (
                            <>
                                <p>Failure code: {implementationResult.failure.code}</p>
                                <p>Failure message: {implementationResult.failure.message}</p>
                            </>
                        ) : null}
                        {implementationResult.reason_codes.length > 0 && (
                            <p>Reason codes: {implementationResult.reason_codes.join(", ")}</p>
                        )}
                    </details>
                )}
                {successorError && (
                    <div role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        <p>{successorError}</p>
                        {workflow.candidate_planning_session_id && <Link to={`/candidate-planning/${encodeURIComponent(workflow.candidate_planning_session_id)}`} className="mt-3 inline-flex font-semibold text-blue-200 underline underline-offset-2">Check the earlier planning session</Link>}
                        {successorErrorDetails && <details className="mt-3"><summary className="mc-focusable cursor-pointer font-semibold">Technical details</summary><p className="mt-2 break-words">{successorErrorDetails}</p></details>}
                    </div>
                )}
                {successorResult && (
                    <div role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
                        <p>{successorPlanningMessage(successorResult)}</p>
                        <details className="mt-3 border-t border-red-200/20 pt-3">
                            <summary className="mc-focusable cursor-pointer font-semibold">Technical details</summary>
                            <p className="mt-2">Planning status: {successorResult.status}</p>
                            <p>Intake status: {successorResult.intake_status}</p>
                            {successorResult.intake_reason_codes.length > 0 && <p>Intake reason codes: {successorResult.intake_reason_codes.join(", ")}</p>}
                            {successorResult.planning_failure && <p>Failure code: {successorResult.planning_failure.code}</p>}
                            {successorResult.planning_failure && <p>Failure message: {successorResult.planning_failure.message}</p>}
                        </details>
                    </div>
                )}
                {implementationError && (
                    <div role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        <p>{implementationError}</p>
                        {implementationOutcomeUnknown && (
                            <>
                                <button type="button" onClick={() => window.location.reload()} className="mc-control mc-focusable mt-3 px-3 py-2 font-semibold">Reload workflow</button>
                                {implementationErrorDetails && (
                                    <details className="mt-3">
                                        <summary className="mc-focusable cursor-pointer font-semibold">Technical details</summary>
                                        <p className="mt-2 break-words">{implementationErrorDetails}</p>
                                    </details>
                                )}
                            </>
                        )}
                    </div>
                )}
                {workflow.workflow_session_id && (
                    <Link to={`/workflows/${encodeURIComponent(workflow.workflow_session_id)}`} className="mt-5 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Open Workflow
                    </Link>
                )}
            </section>
        </main>
    );
}

function Detail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value}</dd></div>;
}

function workflowMessage(workflow: CandidateWorkflowResponse): string {
    if (workflow.conversion_status === "workflow_exists") return "Workflow already exists.";
    if (workflow.failure?.code === "candidate_stale" || workflow.conversion_status.includes("stale")) return "This proposal changed after review. Open the current proposal and plan it again.";
    if (workflow.failure?.code === "candidate_fingerprint_mismatch" || workflow.failure?.code === "plan_fingerprint_mismatch") return "The proposal or plan changed after review. Return to planning and review the current version.";
    if (workflow.failure?.code === "workflow_translation_unsupported" || workflow.failure?.code === "unsupported_intent") return "Atlas cannot create a workflow for this type of change yet.";
    if (workflow.failure?.code === "atlas_core_unavailable") return "Atlas Core could not confirm the current proposal. Try again when Core is available.";
    if (workflow.failure?.code === "persistence_failed") return "Atlas could not save the workflow. No workflow is ready to open.";
    return "Atlas could not create this workflow. Review technical details before trying again.";
}

function implementationFailureMessage(response: CandidateImplementationTranslationResponse): string {
    switch (response.failure?.code) {
        case "repository_stale":
            return "The repository changed after plan review. Start a new planning session before preparing again.";
        case "candidate_fingerprint_mismatch":
            return "The proposal changed after review. Open the current proposal and plan it again.";
        case "plan_fingerprint_mismatch":
            return "The plan no longer matches the proposal. Return to planning and review the current version.";
        case "workflow_translation_unsupported":
        case "unsupported_intent":
            return "Atlas cannot prepare an approval request for this type of change yet.";
        case "atlas_core_unavailable":
            return "Atlas Core could not confirm the current proposal and plan. Try again when Core is available.";
        case "persistence_failed":
            return "Atlas could not save the change request. Reload this workflow before trying again.";
        default:
            return "Atlas could not prepare the change request. Review technical details before trying again.";
    }
}

function successorPlanningMessage(response: CandidatePlanningResponse): string {
    switch (response.planning_failure?.code) {
        case "conflicting_active_session":
            return "Another planning session is already active for this proposal. Review your planning sessions before trying again.";
        case "candidate_stale":
            return "The proposal changed after review. Open the current proposal and plan it again.";
        case "candidate_expired":
            return "This proposal has expired. Open a current proposal before continuing.";
        case "atlas_core_unavailable":
            return "Atlas Core could not confirm the current proposal. Try again when Core is available.";
        case "persistence_failed":
            return "Atlas could not save the new planning session. No session is ready to open.";
        default:
            return "Atlas could not start a new planning session. Review technical details before trying again.";
    }
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
