import { StrictMode } from "react";
import { act, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    createCandidateImplementationRequest,
    getCandidateWorkflowShell,
    createSuccessorCandidatePlanningSession,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidateImplementationTranslationResponse,
    CandidatePlanningResponse,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";
import { unreadableWorkflowFields } from "../test/workflowSummary";
import { WorkflowShellPage } from "./WorkflowShellPage";

vi.mock("../api/atlas-agent", () => ({
    createCandidateImplementationRequest: vi.fn(),
    getCandidateWorkflowShell: vi.fn(),
    createSuccessorCandidatePlanningSession: vi.fn(),
    getCandidatePlanningSession: vi.fn(),
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

const mockedCreateCandidateImplementationRequest = vi.mocked(createCandidateImplementationRequest);
const mockedGetCandidateWorkflowShell = vi.mocked(getCandidateWorkflowShell);
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

function renderPage(state?: { workflow: CandidateWorkflowResponse }) {
    return render(
        <MemoryRouter initialEntries={[{ pathname: "/candidate-planning/candidate-plan-1/workflow", state }]}>
            <Routes>
                <Route path="/candidate-planning/:sessionId/workflow" element={<WorkflowShellPage />} />
                <Route path="/workflows/:workflowId" element={<div>Workflow detail</div>} />
                <Route path="/candidate-planning/:sessionId" element={<div>Candidate planning session</div>} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowShellPage", () => {
    it.each(unreadableWorkflowFields)("recovers an unreadable workflow summary %s through a read", async (_field, fields) => {
        mockedGetCandidateWorkflowShell.mockResolvedValueOnce(workflow(fields as Partial<CandidateWorkflowResponse>));
        const user = userEvent.setup();
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The workflow summary response is incomplete or unreadable.");
        expect(screen.queryByRole("button", { name: "Prepare exact request" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Try again" }));
        await screen.findByRole("heading", { name: "Workflow summary" });
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledTimes(2);
        expect(mockedCreateCandidateImplementationRequest).not.toHaveBeenCalled();
        expect(mockedCreateSuccessorCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it.each(["..", "bad\u0000id"])("does not accept an unusable proposal reference: %j", async candidate_id => {
        mockedGetCandidateWorkflowShell.mockResolvedValue(workflow({ candidate_id }));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The workflow summary response is incomplete or unreadable.");
        expect(mockedCreateCandidateImplementationRequest).not.toHaveBeenCalled();
    });

    it("ignores unreadable cached data while awaiting a fresh summary", async () => {
        let finish!: (value: CandidateWorkflowResponse) => void;
        mockedGetCandidateWorkflowShell.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
        renderPage({ workflow: workflow({ candidate_fingerprint: {} } as unknown as Partial<CandidateWorkflowResponse>) });
        expect(await screen.findByText("Loading workflow summary…")).toBeVisible();
        expect(screen.queryByRole("button", { name: "Prepare exact request" })).not.toBeInTheDocument();
        await act(async () => finish(workflow()));
        await screen.findByRole("heading", { name: "Workflow summary" });
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledTimes(1);
    });

    it("accepts readable future workflow labels with unused metadata", async () => {
        mockedGetCandidateWorkflowShell.mockResolvedValue(workflow({ workflow_status: "future_state", conversion_status: "future_conversion",
            candidate_plan_id: {}, core_revalidation_status: {}, future_metadata: { extra: true } } as unknown as Partial<CandidateWorkflowResponse>));
        renderPage();
        await screen.findByRole("heading", { name: "Workflow summary" });
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Prepare exact request" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateImplementationRequest).not.toHaveBeenCalled();
    });

    beforeEach(() => {
        vi.resetAllMocks();
        mockedCreateCandidateImplementationRequest.mockResolvedValue(
            implementationTranslationResponse(),
        );
        mockedGetCandidateWorkflowShell.mockResolvedValue(workflow());
        mockedCreateSuccessorCandidatePlanningSession.mockResolvedValue(
            planningSession({
                session_id: "candidate-plan-2",
                status: "ready_for_planning",
            }),
        );
        mockedGetCandidatePlanningSession.mockResolvedValue(planningSession());
    });

    it("renders from route state while still reconciling against server state", async () => {
        const user = userEvent.setup();
        renderPage({ workflow: workflow() });

        expect(screen.getByRole("heading", { name: "Review workflow" })).toBeVisible();
        expect(screen.getByText("workflow-1", { exact: true })).toBeInTheDocument();
        expect(screen.getAllByText("This workflow is ready for review.").length).toBeGreaterThan(0);
        expect(screen.getByText("workflow-1")).toBeInTheDocument();
        expect(screen.getByText("Atlas Agent candidate planning")).toBeInTheDocument();
        expect((await screen.findAllByText(/Awaiting Approval|Approval Pending/)).length).toBeGreaterThan(0);
        expect(screen.getByText("candidate-1")).toBeInTheDocument();
        expect(screen.getByText("fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("plan-fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("Pending")).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-1")).toBeInTheDocument();
        expect(screen.queryByText("Not exposed by Atlas Agent API")).not.toBeInTheDocument();
        expect(screen.getByText("Workflow").closest("li")).toHaveAttribute("aria-current", "step");
        expect(screen.queryByText("Implementation ○")).not.toBeInTheDocument();
        expect(screen.queryByText("Verification ○")).not.toBeInTheDocument();
        expect(screen.queryByText("Review ○")).not.toBeInTheDocument();
        expect(screen.queryByText("Commit ○")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve|execute|verify|review|commit/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/argv|commands|execution metadata/i)).not.toBeInTheDocument();
        expect(await screen.findByRole("button", { name: /prepare exact request/i })).toBeInTheDocument();
        expect(mockedGetCandidatePlanningSession).not.toHaveBeenCalled();
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1");
        const disclosure = screen.getByText("Technical details", { exact: true });
        expect(disclosure.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByText("plan-fingerprint-1")).not.toBeVisible();
        const shellReads = mockedGetCandidateWorkflowShell.mock.calls.length;
        await user.click(disclosure);
        expect(screen.getByText("plan-fingerprint-1")).toBeVisible();
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledTimes(shellReads);
        expect(mockedCreateCandidateImplementationRequest).not.toHaveBeenCalled();
        expect(mockedCreateSuccessorCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("reconciles stale location state against a blocked authoritative server response", async () => {
        mockedGetCandidateWorkflowShell.mockResolvedValue(
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

        expect(screen.getByText("workflow-1", { exact: true })).toBeInTheDocument();
        expect((await screen.findAllByText("Blocked")).length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: /prepare exact request/i })).not.toBeInTheDocument();
        expect(screen.getByText("Recovery: blocked workflow")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1");
    });

    it("does not render mutation actions before authoritative state reconciliation", async () => {
        let resolveShell!: (value: CandidateWorkflowResponse) => void;
        mockedGetCandidateWorkflowShell.mockReturnValue(new Promise((resolve) => {
            resolveShell = resolve;
        }));

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        expect(screen.getByText("workflow-1", { exact: true })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare exact request/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();

        resolveShell(workflow({ workflow_status: "awaiting_approval", implementation_approval_request_id: "approval-shell" }));
        expect(await screen.findByRole("button", { name: /prepare exact request/i })).toBeInTheDocument();
        expect(mockedCreateCandidateImplementationRequest).not.toHaveBeenCalled();
    });

    it("loads the workflow shell when opened directly from planning session URL", async () => {
        renderPage();

        expect(await screen.findByText("workflow-1", { exact: true })).toBeInTheDocument();
        expect(mockedGetCandidatePlanningSession).not.toHaveBeenCalled();
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1");
    });

    it("shows loading state while resolving workflow shell summary", async () => {
        let resolveSession!: (value: CandidateWorkflowResponse) => void;
        mockedGetCandidateWorkflowShell.mockImplementation(() => new Promise((resolve) => {
            resolveSession = resolve;
        }));

        renderPage();

        expect(await screen.findByText(/Loading workflow summary/i)).toBeInTheDocument();
        resolveSession(workflow());
    });

	it("renders a prepare exact request button for awaiting_approval shells", async () => {
		const user = userEvent.setup();
        const currentWorkflow = workflow({
            workflow_status: "awaiting_approval",
            conversion_status: "workflow_created",
            implementation_approval_request_id: "approval-shell",
        });
        renderPage({ workflow: currentWorkflow });

        const button = await screen.findByRole("button", { name: /prepare exact request/i });

        await user.click(button);

        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledWith(
            "candidate-plan-1",
            {
                expected_candidate_fingerprint: currentWorkflow.candidate_fingerprint,
                expected_plan_fingerprint: currentWorkflow.candidate_plan_fingerprint,
            },
        );
		expect(await screen.findByText("Workflow detail")).toBeInTheDocument();
	});

		it("explains a stale repository failure and keeps its code in collapsed request details", async () => {
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

		await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));

		const alert = await screen.findByRole("alert");
		expect(alert).toHaveTextContent("The repository changed after review. Re-plan against the current repository before preparing this request again.");
		expect(alert).not.toHaveTextContent("repository_stale");
		const details = screen.getByText("Request technical details", { exact: true });
		expect(details.closest("details")).not.toHaveAttribute("open");
		expect(screen.getByText("Failure code: repository_stale")).not.toBeVisible();
		await user.click(details);
		expect(screen.getByText("Translation status: implementation_translation_failed")).toBeVisible();
		expect(screen.getByText("Failure code: repository_stale")).toBeVisible();
		expect(screen.getByText("Failure message: Trusted repository HEAD differs from the reviewed candidate plan.")).toBeVisible();
		expect(screen.getByText("Reason codes: repository_stale")).toBeVisible();
		expect(screen.getByText("workflow-1", { exact: true })).toBeInTheDocument();
		expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
			expect(screen.getByRole("button", { name: /prepare exact request/i })).toBeInTheDocument();
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

			await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));

			expect(await screen.findByText("Failure code: plan_fingerprint_mismatch")).not.toBeVisible();
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

			await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));
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

			await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();

			mockedCreateSuccessorCandidatePlanningSession.mockResolvedValue(
				planningSession({
					session_id: null,
					planning_failure: { code: "conflicting_active_session", message: "No successor." },
				}),
			);

			await user.click(screen.getByRole("button", { name: /re-plan against current repository/i }));

			const message = await screen.findByText("A planning session is already active for this proposal. Refresh the planning page before trying again.");
			const alert = message.closest<HTMLElement>('[role="alert"]');
			expect(alert).not.toBeNull();
			expect(alert!).toHaveTextContent("A planning session is already active for this proposal. Refresh the planning page before trying again.");
			const scopedAlert = within(alert!);
			const technicalDetails = scopedAlert.getByText("Technical details", { exact: true });
			expect(scopedAlert.getByText("Failure code: conflicting_active_session", { exact: true })).not.toBeVisible();
			await user.click(technicalDetails);
			expect(scopedAlert.getByText("Failure code: conflicting_active_session", { exact: true })).toBeVisible();
			expect(scopedAlert.getByText("No successor.", { exact: true })).toBeVisible();
			expect(screen.getByText("workflow-1", { exact: true })).toBeInTheDocument();
		});

		it("does not navigate when successor call errors", async () => {
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

			await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();

			await user.click(screen.getByRole("button", { name: /re-plan against current repository/i }));

			expect((await screen.findAllByRole("alert")).some((alert) => alert.textContent === "Successor failed")).toBe(true);
			expect(screen.getByText("workflow-1", { exact: true })).toBeInTheDocument();
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

			await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));
			expect(await screen.findByRole("button", { name: /re-plan against current repository/i })).toBeInTheDocument();
			await user.dblClick(screen.getByRole("button", { name: /re-plan against current repository/i }));

			expect(mockedCreateSuccessorCandidatePlanningSession).toHaveBeenCalledTimes(1);
			expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();
			resolveRequest(planningSession({ session_id: "candidate-plan-2", status: "ready_for_planning" }));
		});

		it("shows blocked recovery and preserves shared successor behavior", async () => {
			const user = userEvent.setup();
			mockedGetCandidateWorkflowShell.mockResolvedValue(
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
			mockedGetCandidateWorkflowShell.mockResolvedValue(
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

		const button = await screen.findByRole("button", { name: /prepare exact request/i });
		await user.click(button);

		expect(await screen.findByRole("alert")).toHaveTextContent("The repository changed after review. Re-plan against the current repository before preparing this request again.");
		expect(button).not.toBeDisabled();
		expect(screen.getByText(/Trusted repository state changed after plan review/)).toBeInTheDocument();
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

		await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));

		expect(await screen.findByText("The exact request is incomplete. Reload this workflow before preparing the request again.")).toBeInTheDocument();
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

		await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));

		expect(await screen.findByText("The exact request is incomplete. Reload this workflow before preparing the request again.")).toBeInTheDocument();
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

        const button = await screen.findByRole("button", { name: /prepare exact request/i });
        await user.dblClick(button);

        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("button", { name: /preparing exact request/i })).toBeDisabled();
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

        await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Implementation unavailable");
    });

    it("shows an error when no workflow shell can be loaded from the planning session ID", async () => {
        mockedGetCandidateWorkflowShell.mockRejectedValueOnce(new Error("Workflow unavailable"));

        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow summary unavailable");
        expect(screen.getByText("Workflow unavailable")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Back to planning session" })).toHaveAttribute(
            "href",
            "/candidate-planning/candidate-plan-1",
        );
    });

    it("explains a stale proposal in plain language and keeps diagnostic codes in details", async () => {
        const user = userEvent.setup();
        const staleWorkflow = workflow({
            workflow_session_id: null,
            workflow_status: null,
            conversion_status: "stale_before_workflow",
            implementation_approval_request_id: null,
            reason_codes: ["stale"],
            failure: { code: "candidate_stale", message: "Candidate changed" },
        });
        mockedGetCandidateWorkflowShell.mockResolvedValue(staleWorkflow);
        renderPage({ workflow: staleWorkflow });

        expect(screen.getByRole("heading", { name: "Review workflow" })).toBeInTheDocument();
        expect(screen.getByText("The proposal changed after this plan was created. Review the current proposal before planning again.")).toBeVisible();
        expect(screen.getByText("Needs review", { exact: true })).toBeVisible();
        expect(screen.getByText("stale", { exact: true })).not.toBeVisible();
        expect(screen.getByText("candidate_stale - Candidate changed", { exact: true })).not.toBeVisible();
        const details = screen.getByText("Technical details", { exact: true });
        expect(details.closest("details")).not.toHaveAttribute("open");
        await user.click(details);
        expect(screen.getByText("stale", { exact: true })).toBeVisible();
        expect(screen.getByText("candidate_stale - Candidate changed", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: /approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });
    it.each(["awaiting_approval", "blocked"])("does not offer cached %s actions after server validation fails", async (workflow_status) => {
        mockedGetCandidateWorkflowShell.mockRejectedValue(new Error("unavailable"));
        renderPage({ workflow: workflow({ workflow_status }) });
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: /prepare exact request/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /re-plan against current repository/i })).not.toBeInTheDocument();
    });

    it("ignores cached workflow data for a different planning session", async () => {
        renderPage({ workflow: workflow({ candidate_planning_session_id: "other-session", workflow_session_id: "other-workflow", candidate_fingerprint: "other-fingerprint" }) });
        expect(screen.queryByText("other-workflow", { exact: true })).not.toBeInTheDocument();
        await screen.findByText("workflow-1", { exact: true });
        expect(mockedGetCandidatePlanningSession).not.toHaveBeenCalled();
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1");
    });

    it("rejects an authoritative workflow response for a different session", async () => {
        mockedGetCandidateWorkflowShell.mockResolvedValue(workflow({ candidate_planning_session_id: "other-session" }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /prepare exact request/i })).not.toBeInTheDocument();
    });

    it("does not let a late implementation response navigate away from another session", async () => {
        const user = userEvent.setup();
        let resolveTranslation!: (value: CandidateImplementationTranslationResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(async (id) => planningSession({ session_id: id }));
        mockedGetCandidateWorkflowShell.mockImplementation(async (id) => workflow({ candidate_planning_session_id: id, workflow_session_id: `workflow-${id}` }));
        mockedCreateCandidateImplementationRequest.mockImplementationOnce(() => new Promise((resolve) => { resolveTranslation = resolve; }));
        const router = createMemoryRouter([
            { path: "/candidate-planning/:sessionId/workflow", element: <WorkflowShellPage /> },
            { path: "/workflows/:workflowId", element: <div>Wrong workflow navigation</div> },
        ], { initialEntries: ["/candidate-planning/candidate-plan-1/workflow"] });
        render(<RouterProvider router={router} />);
        await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));
        await act(() => router.navigate("/candidate-planning/candidate-plan-2/workflow"));
        await screen.findByText("workflow-candidate-plan-2", { exact: true });
        await act(async () => resolveTranslation(implementationTranslationResponse({ workflow_session_id: "workflow-candidate-plan-1" })));
        expect(router.state.location.pathname).toBe("/candidate-planning/candidate-plan-2/workflow");
        expect(screen.queryByText("Wrong workflow navigation")).not.toBeInTheDocument();
    });

    it("does not navigate to a translation for a different workflow", async () => {
        const user = userEvent.setup();
        mockedCreateCandidateImplementationRequest.mockResolvedValue(implementationTranslationResponse({ workflow_session_id: "other-workflow" }));
        renderPage({ workflow: workflow() });
        await user.click(await screen.findByRole("button", { name: /prepare exact request/i }));
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByText("Workflow detail")).not.toBeInTheDocument();
    });

    it("revalidates a cached workflow once under Strict Mode", async () => {
        render(<StrictMode><MemoryRouter initialEntries={[{ pathname: "/candidate-planning/candidate-plan-1/workflow", state: { workflow: workflow() } }]}>
            <Routes><Route path="/candidate-planning/:sessionId/workflow" element={<WorkflowShellPage />} /></Routes>
        </MemoryRouter></StrictMode>);
        await screen.findByRole("button", { name: /prepare exact request/i });
        expect(mockedGetCandidateWorkflowShell).toHaveBeenCalledTimes(1);
    });

    it("does not let a late recovery response navigate away from another session", async () => {
        const user = userEvent.setup();
        let resolveSuccessor!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(async (id) => planningSession({ session_id: id }));
        mockedGetCandidateWorkflowShell.mockImplementation(async (id) => workflow({ candidate_planning_session_id: id, workflow_session_id: `workflow-${id}`, workflow_status: "blocked" }));
        mockedCreateSuccessorCandidatePlanningSession.mockImplementationOnce(() => new Promise((resolve) => { resolveSuccessor = resolve; }));
        const router = createMemoryRouter([
            { path: "/candidate-planning/:sessionId/workflow", element: <WorkflowShellPage /> },
            { path: "/candidate-planning/:sessionId", element: <div>Wrong recovery navigation</div> },
        ], { initialEntries: ["/candidate-planning/candidate-plan-1/workflow"] });
        render(<RouterProvider router={router} />);
        await user.click(await screen.findByRole("button", { name: /re-plan against current repository/i }));
        await act(() => router.navigate("/candidate-planning/candidate-plan-2/workflow"));
        await screen.findByText("workflow-candidate-plan-2", { exact: true });
        await act(async () => resolveSuccessor(planningSession({ session_id: "successor-session" })));
        expect(router.state.location.pathname).toBe("/candidate-planning/candidate-plan-2/workflow");
        expect(screen.queryByText("Wrong recovery navigation")).not.toBeInTheDocument();
    });

});
