import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";

import {
    createCandidateWorkflowShell,
    createCandidateImplementationRequest,
    createSuccessorCandidatePlanningSession,
    getAtlasAgentErrorMessage,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidateImplementationTranslationResponse,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";

type WorkflowLocationState = {
    workflow?: CandidateWorkflowResponse;
};

export function WorkflowShellPage() {
    const { sessionId = "" } = useParams<{ sessionId: string }>();
    const location = useLocation();
    const navigate = useNavigate();
    const workflowFromLocation = (location.state as WorkflowLocationState | null)?.workflow ?? null;
    const [workflow, setWorkflow] = useState<CandidateWorkflowResponse | null>(workflowFromLocation);
    const [isCreatingImplementation, setIsCreatingImplementation] = useState(false);
    const [isCreatingSuccessor, setIsCreatingSuccessor] = useState(false);
    const [isLoadingWorkflow, setIsLoadingWorkflow] = useState(workflowFromLocation === null);
    const [workflowLoadError, setWorkflowLoadError] = useState<string | null>(null);
    const [implementationError, setImplementationError] = useState<string | null>(null);
    const [successorError, setSuccessorError] = useState<string | null>(null);
    const [implementationResult, setImplementationResult] = useState<CandidateImplementationTranslationResponse | null>(null);

    useEffect(() => {
        if (workflowFromLocation !== null) {
            return;
        }

        let cancelled = false;

        void (async () => {
            setIsLoadingWorkflow(true);
            setWorkflowLoadError(null);

            try {
                const planningSession = await getCandidatePlanningSession(sessionId);

                if (cancelled) {
                    return;
                }

                if (planningSession === null) {
                    throw new Error("Planning session was not found.");
                }

                const response = await createCandidateWorkflowShell(sessionId, {
                    expected_candidate_fingerprint: planningSession.candidate_fingerprint,
                });

                if (!cancelled && response) {
                    setWorkflow(response);
                }
            } catch (error: unknown) {
                if (cancelled) {
                    return;
                }

                setWorkflowLoadError(
                    getAtlasAgentErrorMessage(
                        error,
                        "Mission Control could not load this workflow shell summary.",
                    ),
                );
            } finally {
                if (!cancelled) {
                    setIsLoadingWorkflow(false);
                }
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [sessionId, workflowFromLocation]);
    const canCreateImplementation =
        workflow !== null
        && workflow.workflow_status === "awaiting_approval"
        && workflow.workflow_session_id !== null
        && workflow.failure === null;

    const canCreateSuccessor =
        workflow !== null
        && workflow.workflow_session_id !== null
        && implementationResult?.failure?.code === "repository_stale"
        && workflow.candidate_planning_session_id !== null
        && workflow.candidate_fingerprint !== null
        && !isCreatingSuccessor;

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
        if (!workflow || !canCreateImplementation || isCreatingImplementation) {
            return;
        }

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
            setImplementationResult(response);
            const isSuccessfulTranslation = isSuccessfulImplementationResponse(response);

            if (isSuccessfulTranslation) {
                navigate(`/workflows/${encodeURIComponent(response.workflow_session_id)}`);
            } else if (response.failure) {
                setImplementationError(
                    `Implementation request failed with ${response.failure.code}: ${response.failure.message}`,
                );
            } else {
                setImplementationError(
                    "Implementation request did not include a complete translation contract. Please retry after refreshing the workflow shell.",
                );
            }
        } catch (error) {
            setImplementationError(
                getAtlasAgentErrorMessage(error, "Candidate implementation request could not be created."),
            );
        } finally {
            setIsCreatingImplementation(false);
        }
    }

    async function createSuccessorPlanningSession() {
        if (!workflow || !canCreateSuccessor) {
            return;
        }

        setIsCreatingSuccessor(true);
        setSuccessorError(null);
        try {
            const response = await createSuccessorCandidatePlanningSession(
                workflow.candidate_planning_session_id,
                {
                    expected_candidate_fingerprint: workflow.candidate_fingerprint,
                },
            );

            if (response.session_id === null) {
                setSuccessorError(
                    response.planning_failure
                        ? `Unable to create successor planning session: ${response.planning_failure.code}: ${response.planning_failure.message}`
                        : "Unable to create successor planning session. No session ID was returned.",
                );
                return;
            }

            navigate(`/candidate-planning/${encodeURIComponent(response.session_id)}`);
        } catch (error) {
            setSuccessorError(
                getAtlasAgentErrorMessage(
                    error,
                    "Could not create a successor planning session for repository_stale recovery.",
                ),
            );
        } finally {
            setIsCreatingSuccessor(false);
        }
    }

    if (isLoadingWorkflow) {
        return (
            <main className="mx-auto max-w-6xl p-8">
                <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    Loading workflow shell…
                </p>
            </main>
        );
    }

    if (!workflow) {
        return (
            <main className="mx-auto max-w-6xl space-y-6 p-8">
                <WorkflowRail />
                <div role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <p className="font-semibold text-amber-200">Workflow summary unavailable</p>
                    <p className="mt-1 text-sm text-slate-300">
                        {workflowLoadError
                            ?? "Mission Control can display the workflow shell summary returned by Create Workflow. Return to the planning session and create or reopen the workflow from that response."}
                    </p>
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
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow Shell</p>
                    <h1 className="mt-3 break-all text-3xl font-bold text-white">
                        Workflow {workflow.workflow_session_id ?? "not created"}
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Read-only workflow shell summary from Atlas Agent. Mission Control does not execute changes, verify changes, review changes, or commit code from this page.
                    </p>
                </div>
                <WorkflowRail />
            </header>

            <section aria-labelledby="workflow-summary-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <h2 id="workflow-summary-heading" className="text-lg font-semibold text-white">Workflow summary</h2>
                        <p className="mt-1 text-sm text-slate-400">{workflow.workflow_session_id ? "Workflow created." : workflowMessage(workflow)}</p>
                    </div>
                    <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">
                        {workflow.workflow_status ? formatLabel(workflow.workflow_status) : formatLabel(workflow.conversion_status)}
                    </span>
                </div>
                <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <Detail label="Workflow ID" value={workflow.workflow_session_id ?? "Not available"} />
                    <Detail label="Workflow source" value="Atlas Agent candidate planning" />
                    <Detail label="Workflow state" value={workflow.workflow_status ? formatLabel(workflow.workflow_status) : "Not available"} />
                    <Detail label="Candidate ID" value={workflow.candidate_id} />
                    <Detail label="Candidate fingerprint" value={workflow.candidate_fingerprint ?? "Not available"} />
                    <Detail label="Plan fingerprint" value={workflow.candidate_plan_fingerprint ?? "Not available"} />
                    <Detail label="Implementation approval status" value={workflow.implementation_approval_request_id ? "Pending" : "Not reported"} />
                    <Detail label="Planning Session ID" value={workflow.candidate_planning_session_id} />
                    <Detail label="Creation time" value="Not exposed by Atlas Agent API" />
                </dl>
                {canCreateImplementation && (
                    <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
                        <h2 className="text-base font-semibold text-emerald-200">Create implementation request</h2>
                        <p className="mt-2 text-sm text-slate-300">
                            Translate the approval-gated shell into the immutable implementation request required for execution approval.
                        </p>
                        <div className="mt-4 flex flex-wrap gap-3">
                            <button
                                type="button"
                                onClick={() => void createImplementation()}
                                disabled={isCreatingImplementation}
                                className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {isCreatingImplementation ? "Creating implementation request..." : "Create Implementation Request"}
                            </button>
                            {isCreatingImplementation && <p className="text-sm text-slate-200">Creating implementation request...</p>}
                        </div>
                    </div>
                )}
                {canCreateSuccessor && (
                    <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                        <h2 className="text-base font-semibold text-amber-100">Recovery: stale repository for approved plan</h2>
                        <p className="mt-2 text-sm text-slate-200">
                            The trusted repository state changed after plan review. This workflow and reviewed plan are historical. Re-planning here creates a successor planning session against the current trusted repository state.
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
                    <p className="mt-4 text-sm text-slate-300">Implementation request has already been created.</p>
                )}
                {implementationResult && isSuccessfulImplementationResponse(implementationResult) && (
                    <p className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                        Implementation request is ready. Redirecting to execution workflow.
                    </p>
                )}
                {implementationResult && (
                    <div role="status" className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
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
                    </div>
                )}
                {implementationResult && implementationResult.failure?.code === "repository_stale" && (
                    <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                        Trusted repository state changed after plan review. Use the recovery action to open a successor planning session.
                    </p>
                )}
                {successorError && (
                    <p role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        {successorError}
                    </p>
                )}
                {implementationError && (
                    <p role="alert" className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        {implementationError}
                    </p>
                )}
                {workflow.reason_codes.length > 0 && <p className="mt-4 text-sm text-slate-400">Reason codes: {workflow.reason_codes.join(", ")}</p>}
                {workflow.failure && <p className="mt-4 text-sm text-slate-400">Failure: {workflow.failure.code} - {workflow.failure.message}</p>}
                {workflow.workflow_session_id && (
                    <Link to={`/workflows/${encodeURIComponent(workflow.workflow_session_id)}`} className="mt-5 inline-flex text-sm font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Open Workflow
                    </Link>
                )}
            </section>
        </main>
    );
}

function WorkflowRail() {
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
    const complete = new Set(["Execution Candidate", "Planning Session", "Candidate Plan", "Workflow"]);

    return (
        <section aria-label="Read-only workflow rail" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <ol className="grid gap-2 text-sm md:grid-cols-4 xl:grid-cols-8">
                {steps.map((step) => {
                    const isWorkflow = step === "Workflow";
                    const isComplete = complete.has(step);
                    return (
                        <li key={step} className={[
                            "rounded-lg border px-3 py-2",
                            isWorkflow ? "border-blue-400 bg-blue-500/10 text-blue-200" : isComplete ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-slate-800 bg-slate-950/50 text-slate-500",
                        ].join(" ")}
                        >
                            <span className="block font-medium">{step}{isComplete ? " ✔" : " ○"}</span>
                            <span className="text-xs">{isComplete ? "Read-only" : "Disabled"}</span>
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

function workflowMessage(workflow: CandidateWorkflowResponse): string {
    if (workflow.conversion_status === "workflow_exists") return "Workflow already exists.";
    if (workflow.failure?.code === "candidate_stale" || workflow.conversion_status.includes("stale")) return "Stale candidate.";
    if (workflow.failure?.code === "candidate_fingerprint_mismatch" || workflow.failure?.code === "plan_fingerprint_mismatch") return "Plan mismatch.";
    if (workflow.failure?.code === "workflow_translation_unsupported" || workflow.failure?.code === "unsupported_intent") return "Unsupported intent.";
    if (workflow.failure?.code === "atlas_core_unavailable") return "Atlas Core unavailable.";
    if (workflow.failure?.code === "persistence_failed") return "Persistence failure.";
    return "Workflow creation did not complete.";
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
