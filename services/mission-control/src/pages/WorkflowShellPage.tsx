import { PlanningProgress } from "../components/PlanningProgress";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { isReadableWorkflowSummary } from "../utils/workflowSummary";

import {
    getCandidateWorkflowShell,
    createCandidateImplementationRequest,
    createSuccessorCandidatePlanningSession,
    getAtlasAgentErrorMessage,
} from "../api/atlas-agent";
import type {
    CandidateImplementationTranslationResponse,
    CandidatePlanningFailure,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";

type WorkflowLocationState = {
    workflow?: CandidateWorkflowResponse;
};

export function WorkflowShellPage() {
    const { sessionId = "" } = useParams<{ sessionId: string }>();
    const location = useLocation();
    const supplied = (location.state as WorkflowLocationState | null)?.workflow;
    const initialWorkflow = supplied && supplied.candidate_planning_session_id === sessionId && isReadableWorkflowSummary(supplied) ? supplied : null;
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
    const [readAttempt, setReadAttempt] = useState(0);
    const [workflowLoadError, setWorkflowLoadError] = useState<string | null>(null);
    const [implementationError, setImplementationError] = useState<string | null>(null);
    const [successorError, setSuccessorError] = useState<string | null>(null);
    const [successorFailure, setSuccessorFailure] = useState<CandidatePlanningFailure | null>(null);
    const [implementationResult, setImplementationResult] = useState<CandidateImplementationTranslationResponse | null>(null);

    useEffect(() => {
        let cancelled = false;
        viewGeneration.current += 1;

        void Promise.resolve().then(async () => {
            if (cancelled) return;
            setIsLoadingWorkflow(true);
            setWorkflowLoadError(null);

            try {
                const response = await getCandidateWorkflowShell(sessionId);

                if (cancelled) {
                    return;
                }

                if (!response || response.candidate_planning_session_id !== sessionId) {
                    setWorkflow(null);
                    setWorkflowLoadError("The workflow response did not match this planning session.");
                    return;
                }
                if (!isReadableWorkflowSummary(response)) {
                    setWorkflow(null);
                    setWorkflowLoadError("The workflow summary response is incomplete or unreadable.");
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
    }, [sessionId, workflowFromLocation, readAttempt]);
    const canCreateImplementation =
        workflow !== null
        && workflow.workflow_status === "awaiting_approval"
        && workflow.workflow_session_id !== null
        && workflow.failure === null
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
                setImplementationError("The implementation response did not match this workflow. No workflow was opened.");
                return;
            }
            setImplementationResult(response);
            const isSuccessfulTranslation = isSuccessfulImplementationResponse(response);

            if (isSuccessfulTranslation) {
                navigate(`/workflows/${encodeURIComponent(response.workflow_session_id)}`);
            } else if (response.failure) {
                setImplementationError(implementationFailureMessage(response.failure.code));
            } else {
                setImplementationError(
                    "The exact request is incomplete. Reload this workflow before preparing the request again.",
                );
            }
        } catch (error) {
            if (generation !== viewGeneration.current) return;
            setImplementationError(
                getAtlasAgentErrorMessage(error, "The exact request could not be prepared."),
            );
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
        setSuccessorFailure(null);
        try {
            const response = await createSuccessorCandidatePlanningSession(
                workflow.candidate_planning_session_id,
                {
                    expected_candidate_fingerprint: workflow.candidate_fingerprint,
                },
            );

            if (generation !== viewGeneration.current) return;
            if (response.session_id === null) {
                setSuccessorFailure(response.planning_failure);
                setSuccessorError(successorFailureMessage(response.planning_failure));
                return;
            }

            navigate(`/candidate-planning/${encodeURIComponent(response.session_id)}`);
        } catch (error) {
            if (generation !== viewGeneration.current) return;
            setSuccessorError(
                getAtlasAgentErrorMessage(
                    error,
                    "Could not create a successor planning session for repository_stale recovery.",
                ),
            );
        } finally {
            if (generation === viewGeneration.current) setIsCreatingSuccessor(false);
        }
    }

    if (isLoadingWorkflow && workflow === null) {
        return (
            <main className="mx-auto max-w-6xl p-8">
                <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    Loading workflow summary…
                </p>
            </main>
        );
    }

    if (!workflow) {
        return (
            <main className="mx-auto max-w-6xl space-y-6 p-8">
                <PlanningProgress current={null} />
                <div role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <p className="font-semibold text-amber-200">Workflow summary unavailable</p>
                    <p className="mt-1 text-sm text-slate-300">
                        {workflowLoadError
                            ?? "Return to the planning session to create or reopen this workflow."}
                    </p>
                    <button type="button" onClick={() => setReadAttempt(value => value + 1)} className="mt-4 mr-4 rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Try again
                    </button>
                    <Link to={`/candidate-planning/${encodeURIComponent(sessionId)}`} className="mt-4 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Back to planning session
                    </Link>
                </div>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-6xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow review</p>
                    <h1 className="mt-3 break-all text-3xl font-bold text-white">
                        Review workflow
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Review this workflow and prepare its exact request for approval. Preparing a request does not run the change.
                    </p>
                </div>
                <PlanningProgress current="Workflow" />
            </header>

            <section aria-labelledby="workflow-summary-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <h2 id="workflow-summary-heading" className="text-lg font-semibold text-white">Workflow summary</h2>
                        <p className="mt-1 text-sm text-slate-400">{workflowMessage(workflow)}</p>
                    </div>
                    <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">
                        {workflowStatusLabel(workflow)}
                    </span>
                </div>
                <details className="mt-5 rounded-lg border border-slate-800 p-3">
                    <summary className="cursor-pointer text-sm text-slate-300">Technical details</summary>
                    <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                        <Detail label="Workflow ID" value={workflow.workflow_session_id ?? "Not available"} />
                        <Detail label="Workflow source" value="Atlas Agent candidate planning" />
                        <Detail label="Workflow state" value={workflow.workflow_status ? formatLabel(workflow.workflow_status) : "Not available"} />
                        <Detail label="Candidate ID" value={workflow.candidate_id} />
                        <Detail label="Candidate fingerprint" value={workflow.candidate_fingerprint ?? "Not available"} />
                        <Detail label="Plan fingerprint" value={workflow.candidate_plan_fingerprint ?? "Not available"} />
                        <Detail label="Implementation approval status" value={workflow.implementation_approval_request_id ? "Pending" : "Not reported"} />
                        <Detail label="Planning Session ID" value={workflow.candidate_planning_session_id} />
                        {workflow.reason_codes.length > 0 && <Detail label="Reason codes" value={workflow.reason_codes.join(", ")} />}
                        {workflow.failure && <Detail label="Failure details" value={`${workflow.failure.code} - ${workflow.failure.message}`} />}
                    </dl>
                </details>
                {canCreateImplementation && (
                    <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
                        <h2 className="text-base font-semibold text-emerald-200">Prepare exact request</h2>
                        <p className="mt-2 text-sm text-slate-300">
                            Prepare the exact request from this plan. You will review and approve it separately before running the change.
                        </p>
                <div className="mt-4 flex flex-wrap gap-3">
                    <button
                        type="button"
                        onClick={() => void createImplementation()}
                        disabled={isCreatingImplementation || isLoadingWorkflow}
                        className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isCreatingImplementation ? "Preparing exact request..." : "Prepare exact request"}
                    </button>
                            {isCreatingImplementation && <p className="text-sm text-slate-200">Preparing exact request...</p>}
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
                    <p className="mt-4 text-sm text-slate-300">The exact request has already been prepared.</p>
                )}
                {implementationResult && isSuccessfulImplementationResponse(implementationResult) && (
                    <p className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                        The exact request is ready. Opening the workflow for review and approval.
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
                {implementationResult && implementationResult.failure?.code === "repository_stale" && (
                    <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                        Trusted repository state changed after plan review. Use the recovery action to open a successor planning session.
                    </p>
                )}
                {successorError && (
                    <div role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        <p>{successorError}</p>
                        {successorFailure && <details className="mt-3">
                            <summary className="mc-focusable cursor-pointer font-semibold">Technical details</summary>
                            <p className="mt-2">Failure code: {successorFailure.code}</p>
                            <p className="mt-1">{successorFailure.message}</p>
                        </details>}
                    </div>
                )}
                {implementationError && (
                    <p role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        {implementationError}
                    </p>
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
    if (workflow.conversion_status === "workflow_exists") return "A workflow already exists for this plan.";
    if (workflow.workflow_session_id) return "This workflow is ready for review.";
    if (workflow.failure?.code === "candidate_stale" || workflow.conversion_status.includes("stale")) return "The proposal changed after this plan was created. Review the current proposal before planning again.";
    if (workflow.failure?.code === "candidate_fingerprint_mismatch" || workflow.failure?.code === "plan_fingerprint_mismatch") return "This plan no longer matches the latest proposal. Review both before continuing.";
    if (workflow.failure?.code === "workflow_translation_unsupported" || workflow.failure?.code === "unsupported_intent") return "This type of change cannot be prepared through this workflow.";
    if (workflow.failure?.code === "atlas_core_unavailable") return "Atlas Core is unavailable. Try again later.";
    if (workflow.failure?.code === "persistence_failed") return "Atlas Agent could not save the workflow. Check the latest status before retrying.";
    return "Workflow preparation could not be completed.";
}

function workflowStatusLabel(workflow: CandidateWorkflowResponse): string {
    if (workflow.workflow_status) return formatLabel(workflow.workflow_status);
    if (workflow.conversion_status === "workflow_exists") return "Existing workflow";
    if (workflow.workflow_session_id) return "Ready for review";
    if (workflow.failure?.code === "candidate_stale" || workflow.failure?.code === "candidate_fingerprint_mismatch"
        || workflow.failure?.code === "plan_fingerprint_mismatch" || workflow.conversion_status.includes("stale")) return "Needs review";
    return "Unavailable";
}

function implementationFailureMessage(code: string): string {
    switch (code) {
        case "repository_stale":
            return "The repository changed after review. Re-plan against the current repository before preparing this request again.";
        case "candidate_stale":
        case "candidate_expired":
        case "candidate_fingerprint_mismatch":
            return "The proposal changed or expired. Refresh it and review a new plan before preparing this request.";
        case "plan_fingerprint_mismatch":
        case "plan_integrity_failed":
            return "The saved plan no longer matches the proposal. Review or recreate the plan before preparing this request.";
        case "workflow_translation_unsupported":
        case "unsupported_intent":
        case "implementation_not_supported":
            return "This type of change cannot be prepared through this workflow.";
        case "atlas_core_unavailable":
            return "Atlas Core is unavailable. Try again later.";
        case "persistence_failed":
            return "Atlas Agent could not save the request. Reload this workflow to check its status before retrying.";
        default:
            return "Atlas could not prepare the exact request. Review the technical details before trying again.";
    }
}

function successorFailureMessage(failure: CandidatePlanningFailure | null): string {
    if (failure === null) return "Unable to open a new planning session. No session ID was returned.";
    switch (failure.code) {
        case "conflicting_active_session":
            return "A planning session is already active for this proposal. Refresh the planning page before trying again.";
        case "candidate_stale":
        case "candidate_expired":
        case "candidate_fingerprint_mismatch":
            return "The proposal changed or expired. Refresh it before opening a new planning session.";
        case "atlas_core_unavailable":
            return "Atlas Core is unavailable. Try again later.";
        case "persistence_failed":
            return "Atlas Agent could not save the planning session. Reload before trying again.";
        default:
            return "Atlas could not open a new planning session. Review the technical details before trying again.";
    }
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
