import { StrictMode } from "react";
import { act, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes, useLocation } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    createCandidateImplementationRequest,
    createCandidateWorkflowShell,
    createSuccessorCandidatePlanningSession,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidateImplementationTranslationResponse,
    CandidatePlanningResponse,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";
import { WorkflowShellPage } from "./WorkflowShellPage";

vi.mock("../api/atlas-agent", () => ({
    createCandidateImplementationRequest: vi.fn(),
    createCandidateWorkflowShell: vi.fn(),
    createSuccessorCandidatePlanningSession: vi.fn(),
    getCandidatePlanningSession: vi.fn(),
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

const mockedCreateCandidateImplementationRequest = vi.mocked(createCandidateImplementationRequest);
const mockedCreateCandidateWorkflowShell = vi.mocked(createCandidateWorkflowShell);
const mockedCreateSuccessorCandidatePlanningSession = vi.mocked(createSuccessorCandidatePlanningSession);
const mockedGetCandidatePlanningSession = vi.mocked(getCandidatePlanningSession);

function workflow(overrides: Partial<CandidateWorkflowResponse> = {}): CandidateWorkflowResponse {
    return {
        candidate_planning_session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1",
        candidate_plan_id: "plan-1",
        candidate_plan_fingerprint: "plan-fingerprint-1",
        workflow_session_id: "workflow-1",
        workflow_status: "awaiting_approval",
        implementation_approval_request_id: "approval-1",
        conversion_status: "workflow_created",
        core_revalidation_status: "accepted_for_planning",
        reason_codes: [],
        failure: null,
        ...overrides,
    };
}

function implementationTranslationResponse(
    overrides: Partial<CandidateImplementationTranslationResponse> = {},
): CandidateImplementationTranslationResponse {
    return {
        candidate_planning_session_id: "candidate-plan-1",
        workflow_session_id: "workflow-1",
        translation_status: "implementation_ready",
        implementation_request_id: "implementation-1",
        exact_approval_request_id: "approval-1",
        candidate_fingerprint: "fingerprint-1",
        plan_fingerprint: "plan-fingerprint-1",
        repository_head: "head-1",
        translator_version: "candidate-update-compose-stack-v1",
        reason_codes: [],
        failure: null,
        ...overrides,
    };
}

function planningSession(overrides: Partial<CandidatePlanningResponse> = {}): CandidatePlanningResponse {
    return {
        session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        status: "plan_ready",
        planning_allowed: true,
        intake_status: "accepted_for_planning",
        intake_reason_codes: [],
        candidate_fingerprint: "fingerprint-1",
        unsupported_reason: null,
        plan: null,
        planning_failure: null,
        ...overrides,
    };
}

function renderPage(state?: { workflow: CandidateWorkflowResponse }, search = "") {
    return render(
        <MemoryRouter initialEntries={[{ pathname: "/candidate-planning/candidate-plan-1/workflow", search, state }]}>
            <Routes>
                <Route path="/candidate-planning/:sessionId/workflow" element={<WorkflowShellPage />} />
                <Route path="/workflows/:workflowId" element={<NavigationProbe label="Workflow detail" />} />
                <Route path="/candidate-planning/:sessionId" element={<NavigationProbe label="Candidate planning session" />} />
            </Routes>
        </MemoryRouter>,
    );
}

function NavigationProbe({ label }: { label: string }) {
    const location = useLocation();
    return <><div>{label}</div><output data-testid="navigation-location">{location.pathname}{location.search}</output></>;
}

describe("WorkflowShellPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedCreateCandidateImplementationRequest.mockResolvedValue(
            implementationTranslationResponse(),
        );
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow());
        mockedCreateSuccessorCandidatePlanningSession.mockResolvedValue(
            planningSession({
                session_id: "candidate-plan-2",
                status: "ready_for_planning",
            }),
        );
        mockedGetCandidatePlanningSession.mockResolvedValue(planningSession());
    });

    it("renders from route state while still reconciling against server state", async () => {
        renderPage({ workflow: workflow() });

        expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
        expect(screen.getAllByText("Workflow created.").length).toBeGreaterThan(0);
        const summary = within(screen.getByRole("region", { name: "Workflow summary" }));
        expect(summary.getByText("Prepare change", { exact: true })).toBeVisible();
        expect(summary.queryByText("Awaiting Approval", { exact: true })).not.toBeInTheDocument();
        const disclosure = summary.getByText("Workflow details", { exact: true });
        expect(disclosure.closest("details")).not.toHaveAttribute("open");
        expect(summary.getByText("Workflow ID", { exact: true })).not.toBeVisible();
        expect(summary.getByText("Candidate ID", { exact: true })).not.toBeVisible();
        expect(screen.queryByText("Not exposed by Atlas Agent API", { exact: true })).not.toBeInTheDocument();
        await userEvent.setup().click(disclosure);
        expect(summary.getByText("Workflow ID", { exact: true })).toBeVisible();
        expect(summary.getByText("workflow-1")).toBeVisible();
        expect(summary.getByText("Candidate ID", { exact: true })).toBeVisible();
        expect(screen.getByText("candidate-1")).toBeInTheDocument();
        expect(screen.getByText("fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("plan-fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("Pending")).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-1")).toBeInTheDocument();
        expect(screen.getByText("Workflow").closest("li")).toHaveAttribute("aria-current", "step");
        expect(screen.queryByText("Implementation ○")).not.toBeInTheDocument();
        expect(screen.queryByText("Verification ○")).not.toBeInTheDocument();
        expect(screen.queryByText("Review ○")).not.toBeInTheDocument();
        expect(screen.queryByText("Commit ○")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve|execute|verify|commit/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/argv|commands|execution metadata/i)).not.toBeInTheDocument();
        expect(await screen.findByRole("button", { name: /prepare change for review/i })).toBeInTheDocument();
        expect(mockedGetCandidatePlanningSession).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1", {
            expected_candidate_fingerprint: "fingerprint-1",
        });
    });

    it("reconciles stale location state against a blocked authoritative server response", async () => {
        mockedCreateCandidateWorkflowShell.mockResolvedValue(
            workflow({
                workflow_status: "blocked",
                implementation_approval_request_id: "approval-shell",
                reason_codes: ["approval_evidence_mismatch"],
            }),
        );

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
        expect((await screen.findAllByText("Blocked")).length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
        expect(screen.getByText("Recovery: blocked workflow")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1", {
            expected_candidate_fingerprint: "fingerprint-1",
        });
    });

    it("does not render mutation actions before authoritative state reconciliation", async () => {
        let resolveShell!: (value: CandidateWorkflowResponse) => void;
        mockedCreateCandidateWorkflowShell.mockReturnValue(new Promise((resolve) => {
            resolveShell = resolve;
        }));

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();

        resolveShell(workflow({ workflow_status: "awaiting_approval", implementation_approval_request_id: "approval-shell" }));
        expect(await screen.findByRole("button", { name: /prepare change for review/i })).toBeInTheDocument();
        expect(mockedCreateCandidateImplementationRequest).not.toHaveBeenCalled();
    });

    it("loads the workflow shell when opened directly from planning session URL", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledWith("candidate-plan-1");
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1", {
            expected_candidate_fingerprint: "fingerprint-1",
        });
    });

    it("shows loading state while resolving workflow shell summary", async () => {
        let resolveSession!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(() => new Promise((resolve) => {
            resolveSession = resolve;
        }));

        renderPage();

        expect(await screen.findByText(/Loading workflow summary/i)).toBeInTheDocument();
        resolveSession(planningSession());
    });

	it("prepares a change request for separate review and approval", async () => {
		const user = userEvent.setup();
        const search = "?eligibility=eligible&offset=25";
        const currentWorkflow = workflow({
            workflow_status: "awaiting_approval",
            conversion_status: "workflow_created",
            implementation_approval_request_id: "approval-shell",
        });
        renderPage({ workflow: currentWorkflow }, search);

        expect(await screen.findByRole("heading", { name: "Prepare change for review" })).toBeVisible();
        expect(screen.getByText("Atlas will create a request from this plan for you to review. It does not approve or run the change.")).toBeVisible();
        const button = await screen.findByRole("button", { name: /prepare change for review/i });

        await user.click(button);

        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledWith(
            "candidate-plan-1",
            {
                expected_candidate_fingerprint: currentWorkflow.candidate_fingerprint,
                expected_plan_fingerprint: currentWorkflow.candidate_plan_fingerprint,
            },
        );
		expect(await screen.findByText("Workflow detail")).toBeInTheDocument();
		expect(screen.getByTestId("navigation-location")).toHaveTextContent(
			"/workflows/workflow-1?eligibility=eligible&offset=25&returnTo=%2Fexecution-candidates",
		);
	});

		it("does not navigate on repository_stale translation failure and renders structured failure details", async () => {
		const user = userEvent.setup();
		mockedCreateCandidateImplementationRequest.mockResolvedValue(
			implementationTranslationResponse({
				translation_status: "implementation_translation_failed",
				implementation_request_id: null,
				exact_approval_request_id: null,
				repository_head: "55f1cb905856153d669fa838596a169cd0f18353",
				reason_codes: ["repository_stale"],
				failure: { code: "repository_stale", message: "Trusted repository HEAD differs from the reviewed candidate plan." },
			}),
		);

		renderPage({
			workflow: workflow({
				workflow_status: "awaiting_approval",
				implementation_approval_request_id: "approval-shell",
			}),
		});

		await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));

		expect(await screen.findByRole("alert")).toHaveTextContent("The repository changed after plan review. Start a new planning session before preparing again.");
		const requestDetails = screen.getByText("Request technical details").closest("details");
		expect(requestDetails).not.toHaveAttribute("open");
		expect(within(requestDetails as HTMLElement).getByText("Failure code: repository_stale")).not.toBeVisible();
		expect(within(requestDetails as HTMLElement).getByText("Failure message: Trusted repository HEAD differs from the reviewed candidate plan.")).not.toBeVisible();
		expect(within(requestDetails as HTMLElement).getByText("Reason codes: repository_stale")).not.toBeVisible();
		await user.click(within(requestDetails as HTMLElement).getByText("Request technical details"));
		expect(within(requestDetails as HTMLElement).getByText("Failure code: repository_stale")).toBeVisible();
		expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
		expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
			expect(screen.getByRole("button", { name: /prepare change for review/i })).toBeInTheDocument();
			expect(screen.getByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
		});

		it("only shows a stale-recovery action for repository_stale failures", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateImplementationRequest.mockResolvedValue(
				implementationTranslationResponse({
					translation_status: "implementation_translation_failed",
					implementation_request_id: null,
					exact_approval_request_id: null,
					failure: { code: "plan_fingerprint_mismatch", message: "Fingerprint mismatch." },
				}),
			);

			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));

			expect(await screen.findByRole("alert")).toHaveTextContent("The plan no longer matches the proposal. Return to planning and review the current version.");
			const requestDetails = screen.getByText("Request technical details").closest("details");
			expect(within(requestDetails as HTMLElement).getByText("Failure code: plan_fingerprint_mismatch")).not.toBeVisible();
			expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();
		});

		it("re-plans from stale failure and navigates to successor planning session", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateImplementationRequest.mockResolvedValue(
				implementationTranslationResponse({
					translation_status: "implementation_translation_failed",
					implementation_request_id: null,
					exact_approval_request_id: null,
					failure: { code: "repository_stale", message: "Trusted repository HEAD differs from the reviewed candidate plan." },
				}),
			);
			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /re-plan against current repository/i }));

			expect(mockedCreateSuccessorCandidatePlanningSession).toHaveBeenCalledWith("candidate-plan-1", {
				expected_candidate_fingerprint: "fingerprint-1",
			});
			expect(await screen.findByText("Candidate planning session")).toBeInTheDocument();
		});

		it("does not navigate when successor is missing a session id and shows error", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateImplementationRequest.mockResolvedValue(
				implementationTranslationResponse({
					translation_status: "implementation_translation_failed",
					implementation_request_id: null,
					exact_approval_request_id: null,
					failure: { code: "repository_stale", message: "Trusted repository HEAD differs from the reviewed candidate plan." },
				}),
			);
			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();

			mockedCreateSuccessorCandidatePlanningSession.mockResolvedValue(
				planningSession({
					session_id: null,
					planning_failure: { code: "conflicting_active_session", message: "No successor." },
				}),
			);

			await user.click(screen.getByRole("button", { name: /re-plan against current repository/i }));

			const successorAlert = (await screen.findAllByRole("alert")).find((alert) => alert.textContent?.includes("Another planning session is already active for this proposal."));
			expect(successorAlert).toBeDefined();
			const technicalDetails = within(successorAlert as HTMLElement).getByText("Technical details").closest("details");
			expect(technicalDetails).not.toHaveAttribute("open");
			expect(within(technicalDetails as HTMLElement).getByText(/conflicting_active_session/)).not.toBeVisible();
			await user.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
			expect(technicalDetails).toHaveAttribute("open");
			expect(technicalDetails).toHaveTextContent("conflicting_active_session");
			expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
		});

		it("keeps successor creation errors plain and links to the source session", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateImplementationRequest.mockResolvedValue(
				implementationTranslationResponse({
					translation_status: "implementation_translation_failed",
					implementation_request_id: null,
					exact_approval_request_id: null,
					failure: { code: "repository_stale", message: "Trusted repository HEAD differs from the reviewed candidate plan." },
				}),
			);
			mockedCreateSuccessorCandidatePlanningSession.mockRejectedValueOnce(new Error("Successor failed"));
			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /re-plan against current repository/i }));

			const successorAlert = (await screen.findAllByRole("alert")).find((alert) => alert.textContent?.includes("Mission Control could not confirm whether the successor planning session was created."));
			expect(successorAlert).toBeDefined();
			expect(successorAlert).toHaveTextContent("Check the earlier planning session for a newer session before trying again.");
			expect(within(successorAlert as HTMLElement).getByRole("link", { name: "Check the earlier planning session" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1");
			const technicalDetails = within(successorAlert as HTMLElement).getByText("Technical details").closest("details");
			expect(technicalDetails).not.toHaveAttribute("open");
			expect(within(technicalDetails as HTMLElement).getByText("Successor failed")).not.toBeVisible();
			expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
		});

		it("blocks duplicate successor creation submissions", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateImplementationRequest.mockResolvedValue(
				implementationTranslationResponse({
					translation_status: "implementation_translation_failed",
					implementation_request_id: null,
					exact_approval_request_id: null,
					failure: { code: "repository_stale", message: "Trusted repository HEAD differs from the reviewed candidate plan." },
				}),
			);
			let resolveRequest!: (value: CandidatePlanningResponse) => void;
			mockedCreateSuccessorCandidatePlanningSession.mockReturnValue(new Promise((resolve) => {
				resolveRequest = resolve;
			}));
			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
			await user.dblClick(screen.getByRole("button", { name: /re-plan against current repository/i }));

			expect(mockedCreateSuccessorCandidatePlanningSession).toHaveBeenCalledTimes(1);
			expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();
			resolveRequest(planningSession({ session_id: "candidate-plan-2", status: "ready_for_planning" }));
		});

		it("shows blocked recovery and preserves shared successor behavior", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateWorkflowShell.mockResolvedValue(
				workflow({
					workflow_status: "blocked",
					implementation_approval_request_id: "approval-shell",
				}),
			);

			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
			await user.click(screen.getByRole("button", { name: /re-plan against current repository/i }));

			expect(mockedCreateSuccessorCandidatePlanningSession).toHaveBeenCalledWith("candidate-plan-1", {
				expected_candidate_fingerprint: "fingerprint-1",
			});
			expect(await screen.findByText("Candidate planning session")).toBeInTheDocument();
		});

		it("blocks duplicate blocked-workflow successor submissions", async () => {
			const user = userEvent.setup();
			mockedCreateCandidateWorkflowShell.mockResolvedValue(
				workflow({
					workflow_status: "blocked",
					implementation_approval_request_id: "approval-shell",
				}),
			);
			mockedCreateSuccessorCandidatePlanningSession.mockReturnValue(new Promise((resolve) => {
				setTimeout(() => {
					resolve(planningSession({ session_id: "candidate-plan-2", status: "ready_for_planning" }));
				}, 10);
			}));

			renderPage({
				workflow: workflow({
					workflow_status: "awaiting_approval",
					implementation_approval_request_id: "approval-shell",
				}),
			});

			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
			await user.dblClick(screen.getByRole("button", { name: /re-plan against current repository/i }));
			expect(mockedCreateSuccessorCandidatePlanningSession).toHaveBeenCalledTimes(1);
		});

	it("retries remain available after a structured failure response", async () => {
		const user = userEvent.setup();
		mockedCreateCandidateImplementationRequest.mockResolvedValue(
			implementationTranslationResponse({
				translation_status: "implementation_translation_failed",
				implementation_request_id: null,
				exact_approval_request_id: null,
				reason_codes: ["repository_stale"],
				failure: { code: "repository_stale", message: "Trusted repository HEAD differs from the reviewed candidate plan." },
			}),
		);

		renderPage({
			workflow: workflow({
				workflow_status: "awaiting_approval",
				implementation_approval_request_id: "approval-shell",
			}),
		});

		const button = await screen.findByRole("button", { name: /prepare change for review/i });
		await user.click(button);

		expect(await screen.findByRole("alert"))
			.toHaveTextContent("The repository changed after plan review. Start a new planning session before preparing again.");
		expect(button).not.toBeDisabled();
		expect(screen.getByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
	});

	it("does not navigate when implementation_request_id is missing", async () => {
		const user = userEvent.setup();
		mockedCreateCandidateImplementationRequest.mockResolvedValue(
			implementationTranslationResponse({
				implementation_request_id: null,
			}),
		);

		renderPage({
			workflow: workflow({
				workflow_status: "awaiting_approval",
				implementation_approval_request_id: "approval-shell",
			}),
		});

		await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));

        expect(await screen.findByText("The change request result is incomplete. Reload this workflow to check its status before continuing.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Reload workflow" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
		expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
	});

	it("does not navigate when exact_approval_request_id is missing", async () => {
		const user = userEvent.setup();
		mockedCreateCandidateImplementationRequest.mockResolvedValue(
			implementationTranslationResponse({
				exact_approval_request_id: null,
			}),
		);

		renderPage({
			workflow: workflow({
				workflow_status: "awaiting_approval",
				implementation_approval_request_id: "approval-shell",
			}),
		});

		await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));

        expect(await screen.findByText("The change request result is incomplete. Reload this workflow to check its status before continuing.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Reload workflow" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
		expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
	});

	it("blocks duplicate implementation request submissions", async () => {
		const user = userEvent.setup();
        let resolveRequest!: (value: CandidateImplementationTranslationResponse) => void;
        mockedCreateCandidateImplementationRequest.mockReturnValue(
            new Promise((resolve) => {
                resolveRequest = resolve;
            }),
        );

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        const button = await screen.findByRole("button", { name: /prepare change for review/i });
        await user.dblClick(button);

        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("button", { name: /preparing…/i })).toBeDisabled();
        expect(await screen.findByText("Preparing the change request for review. This does not run it.")).toBeVisible();
        resolveRequest(implementationTranslationResponse());
    });

    it("shows an error when creating the implementation request fails", async () => {
        const user = userEvent.setup();
        mockedCreateCandidateImplementationRequest.mockRejectedValueOnce(new Error("Implementation unavailable"));

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Implementation unavailable");
    });

    it("shows an error when no workflow shell can be loaded from the planning session ID", async () => {
        mockedCreateCandidateWorkflowShell.mockRejectedValueOnce(new Error("Workflow unavailable"));
        const search = "?eligibility=eligible&offset=25";
        renderPage(undefined, search);

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Workflow summary unavailable");
        expect(alert).toHaveTextContent("Atlas couldn’t load the workflow setup. Check the planning session before trying again.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Workflow unavailable", { exact: true })).not.toBeVisible();
        expect(screen.getByRole("link", { name: "Back to planning session" })).toHaveAttribute(
            "href",
            `/candidate-planning/candidate-plan-1${search}`,
        );
    });

	it("renders workflow conversion failures in plain language with codes collapsed", async () => {
		const user = userEvent.setup();
        renderPage({
            workflow: workflow({
                workflow_session_id: null,
                workflow_status: null,
                conversion_status: "stale_before_workflow",
                implementation_approval_request_id: null,
                reason_codes: ["stale"],
                failure: { code: "candidate_stale", message: "Candidate changed" },
            }),
        });

        expect(screen.getByRole("heading", { name: "Workflow setup" })).toBeInTheDocument();
		expect(screen.getByText("This proposal changed after review. Open the current proposal and plan it again.")).toBeInTheDocument();
		const technicalDetails = screen.getByText("Technical details").closest("details");
		expect(technicalDetails).not.toHaveAttribute("open");
		expect(within(technicalDetails as HTMLElement).getByText("stale")).not.toBeVisible();
		expect(within(technicalDetails as HTMLElement).getByText("candidate_stale")).not.toBeVisible();
		await user.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
		expect(technicalDetails).toHaveAttribute("open");
		expect(technicalDetails).toHaveTextContent("candidate_stale");
        expect(screen.queryByRole("button", { name: /approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });
    it.each(["awaiting_approval", "blocked"])("does not offer cached %s actions after server validation fails", async (workflow_status) => {
        mockedCreateCandidateWorkflowShell.mockRejectedValue(new Error("unavailable"));
        renderPage({ workflow: workflow({ workflow_status }) });
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();
    });

    it("ignores cached workflow data for a different planning session", async () => {
        renderPage({ workflow: workflow({ candidate_planning_session_id: "other-session", workflow_session_id: "other-workflow", candidate_fingerprint: "other-fingerprint" }) });
        expect(screen.queryByText("other-workflow", { exact: true })).not.toBeInTheDocument();
        await screen.findByRole("heading", { name: "Workflow setup" });
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledWith("candidate-plan-1");
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1", { expected_candidate_fingerprint: "fingerprint-1" });
    });

    it("does not create a workflow from a mismatched planning-session read", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(planningSession({ session_id: "other-session" }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("rejects an authoritative workflow response for a different session", async () => {
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow({ candidate_planning_session_id: "other-session" }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
    });

    it("does not let a late implementation response navigate away from another session", async () => {
        const user = userEvent.setup();
        let resolveTranslation!: (value: CandidateImplementationTranslationResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(async (id) => planningSession({ session_id: id }));
        mockedCreateCandidateWorkflowShell.mockImplementation(async (id) => workflow({ candidate_planning_session_id: id, workflow_session_id: `workflow-${id}` }));
        mockedCreateCandidateImplementationRequest.mockImplementationOnce(() => new Promise((resolve) => { resolveTranslation = resolve; }));
        const router = createMemoryRouter([
            { path: "/candidate-planning/:sessionId/workflow", element: <WorkflowShellPage /> },
            { path: "/workflows/:workflowId", element: <div>Wrong workflow navigation</div> },
        ], { initialEntries: ["/candidate-planning/candidate-plan-1/workflow"] });
        render(<RouterProvider router={router} />);
        await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));
        await act(() => router.navigate("/candidate-planning/candidate-plan-2/workflow"));
        await screen.findByRole("heading", { name: "Workflow setup" });
        await act(async () => resolveTranslation(implementationTranslationResponse({ workflow_session_id: "workflow-candidate-plan-1" })));
        expect(router.state.location.pathname).toBe("/candidate-planning/candidate-plan-2/workflow");
        expect(screen.queryByText("Wrong workflow navigation")).not.toBeInTheDocument();
    });

    it("does not navigate to a translation for a different workflow", async () => {
        const user = userEvent.setup();
        mockedCreateCandidateImplementationRequest.mockResolvedValue(implementationTranslationResponse({ workflow_session_id: "other-workflow" }));
        renderPage({ workflow: workflow() });
        await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not match the change request to this workflow.");
        expect(screen.getByRole("button", { name: "Reload workflow" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
        expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
    });

    it("requires a reload after an unreadable preparation result", async () => {
        const user = userEvent.setup();
        mockedCreateCandidateImplementationRequest.mockRejectedValue(new Error("Malformed candidate implementation response."));
        renderPage({ workflow: workflow() });

        await user.click(await screen.findByRole("button", { name: /prepare change for review/i }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not confirm whether the change request is ready.");
        expect(screen.getByRole("button", { name: "Reload workflow" })).toBeInTheDocument();
        expect(within(alert).getByText("Technical details").closest("details")).not.toHaveAttribute("open");
        expect(screen.queryByRole("button", { name: /prepare change for review/i })).not.toBeInTheDocument();
        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledTimes(1);
        expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
    });

    it("revalidates a cached workflow once under Strict Mode", async () => {
        render(<StrictMode><MemoryRouter initialEntries={[{ pathname: "/candidate-planning/candidate-plan-1/workflow", state: { workflow: workflow() } }]}>
            <Routes><Route path="/candidate-planning/:sessionId/workflow" element={<WorkflowShellPage />} /></Routes>
        </MemoryRouter></StrictMode>);
        await screen.findByRole("button", { name: /prepare change for review/i });
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
    });

    it("does not let a late recovery response navigate away from another session", async () => {
        const user = userEvent.setup();
        let resolveSuccessor!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(async (id) => planningSession({ session_id: id }));
        mockedCreateCandidateWorkflowShell.mockImplementation(async (id) => workflow({ candidate_planning_session_id: id, workflow_session_id: `workflow-${id}`, workflow_status: "blocked" }));
        mockedCreateSuccessorCandidatePlanningSession.mockImplementationOnce(() => new Promise((resolve) => { resolveSuccessor = resolve; }));
        const router = createMemoryRouter([
            { path: "/candidate-planning/:sessionId/workflow", element: <WorkflowShellPage /> },
            { path: "/candidate-planning/:sessionId", element: <div>Wrong recovery navigation</div> },
        ], { initialEntries: ["/candidate-planning/candidate-plan-1/workflow"] });
        render(<RouterProvider router={router} />);
        await user.click(await screen.findByRole("button", { name: /re-plan against current repository/i }));
        await act(() => router.navigate("/candidate-planning/candidate-plan-2/workflow"));
        await screen.findByRole("heading", { name: "Workflow setup" });
        await act(async () => resolveSuccessor(planningSession({ session_id: "successor-session" })));
        expect(router.state.location.pathname).toBe("/candidate-planning/candidate-plan-2/workflow");
        expect(screen.queryByText("Wrong recovery navigation")).not.toBeInTheDocument();
    });

});
