import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    createCandidateWorkflowShell,
    generateCandidatePlan,
    getCandidatePlan,
    getCandidatePlanningSession,
} from "../api/atlas-agent";
import type {
    CandidatePlanApiResponse,
    CandidatePlanningResponse,
    CandidateWorkflowResponse,
    OperationalCandidatePlanApiResponse,
} from "../types/atlasAgent";
import { operationalPlan } from "../test/operationalPlanning";
import { PlanningSessionPage } from "./PlanningSessionPage";

vi.mock("../api/atlas-agent", () => ({
    createCandidateWorkflowShell: vi.fn(),
    generateCandidatePlan: vi.fn(),
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
    getCandidatePlan: vi.fn(),
    getCandidatePlanningSession: vi.fn(),
}));

const mockedGetCandidatePlanningSession = vi.mocked(getCandidatePlanningSession);
const mockedCreateCandidateWorkflowShell = vi.mocked(createCandidateWorkflowShell);
const mockedGenerateCandidatePlan = vi.mocked(generateCandidatePlan);
const mockedGetCandidatePlan = vi.mocked(getCandidatePlan);

function session(overrides: Partial<CandidatePlanningResponse> = {}): CandidatePlanningResponse {
    return {
        session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        status: "ready_for_planning",
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

function plan(overrides: Partial<CandidatePlanApiResponse> = {}): CandidatePlanApiResponse {
    return {
        identifier: "plan-1",
        session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1",
        title: "Update Home Assistant compose stack",
        objective: "Update the compose stack safely.",
        assumptions: ["Operator has reviewed the candidate."],
        constraints: ["No implementation commands are included."],
        proposed_steps: ["Review compose changes.", "Prepare validation."],
        likely_affected_components: ["home-assistant"],
        likely_affected_files: ["compose/home-assistant.yaml"],
        verification_strategy: ["Run configuration validation."],
        rollback_considerations: ["Restore previous compose file."],
        unresolved_questions: ["Confirm maintenance window."],
        evidence_ids: ["evidence-1"],
        created_at: "2026-01-01T00:00:00Z",
        repository_branch: "feature/atlas-agent",
        repository_head: "abc123",
        revalidated_candidate_fingerprint: "fingerprint-1",
        ...overrides,
    };
}

function workflow(overrides: Partial<CandidateWorkflowResponse> = {}): CandidateWorkflowResponse {
    return {
        candidate_planning_session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1",
        candidate_plan_id: "plan-1",
        candidate_plan_fingerprint: "plan-fingerprint-1",
        workflow_session_id: "workflow-1",
        workflow_status: "approval_pending",
        implementation_approval_request_id: "approval-1",
        conversion_status: "workflow_created",
        core_revalidation_status: "accepted_for_planning",
        reason_codes: [],
        failure: null,
        ...overrides,
    };
}

function renderPage(path = "/candidate-planning/candidate-plan-1") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/candidate-planning/:sessionId" element={<PlanningSessionPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("PlanningSessionPage", () => {
    it("renders the existing maintenance plan without requesting a repository plan", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan() }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(screen.getByText("proxmox/qemu/110")).toBeVisible();
        expect(screen.getByText("Temporary service interruption.")).toBeVisible();
        expect(screen.getByText(/Stop and require operator review/)).toBeVisible();
        expect(screen.getByRole("link", { name: "Review original proposal" })).toHaveAttribute("href", "/execution-candidates/candidate-1");
        expect(screen.queryByText("Supported intent")).not.toBeInTheDocument();
        expect(screen.queryByText("update-compose-stack")).not.toBeInTheDocument();
        expect(screen.queryByText("Affected repository")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Create Workflow" })).toBeEnabled();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("displays a generated maintenance plan without falling back to the repository endpoint", async () => {
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan() }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
        await user.click(screen.getByRole("button", { name: "Create Workflow" }));
        await screen.findByRole("link", { name: "Open Workflow" });
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledExactlyOnceWith("candidate-plan-1");
    });

    it("keeps maintenance review read-only when planning is unavailable", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", planning_allowed: false, operational_plan: operationalPlan() }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it.each([
        ["session", { session_id: "different-session" }],
        ["candidate", { candidate_id: "different-candidate" }],
        ["effect", { effect_kind: "repository_change" }],
        ["verification identity", { verification: { ...operationalPlan().verification, identity_fingerprint: "different-target" } }],
        ["starting state", { verification: { ...operationalPlan().verification, pre_state: "stopped" } }],
        ["missing verification", { verification: null }],
        ["malformed considerations", { failure_considerations: null }],
    ])("refuses an invalid maintenance plan %s without creating a workflow", async (_name, override) => {
        const untrusted = { ...operationalPlan(), ...override } as OperationalCandidatePlanApiResponse;
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", operational_plan: untrusted }));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("does not match this planning session or target");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it("refuses conflicting repository and maintenance plans", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan(), operational_plan: operationalPlan() }));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("conflicting plan types");
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("refuses mismatched maintenance verification returned by generation", async () => {
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan({ verification: { ...operationalPlan().verification, identity_fingerprint: "different-target" } }) }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("does not match this planning session or target");
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetCandidatePlanningSession.mockResolvedValue(session());
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow());
        mockedGetCandidatePlan.mockResolvedValue(plan());
    });

    it("leads with the next planning step and keeps identifiers in collapsed details", async () => {
        const user = userEvent.setup();
        renderPage();

        expect(await screen.findByRole("heading", { name: "Plan this change" })).toBeInTheDocument();
        expect(screen.getByText("Generate a plan for review. It will not apply changes or grant approval.")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Review original proposal" })).toHaveAttribute("href", "/execution-candidates/candidate-1");
        expect(screen.queryByText("Not exposed by Atlas Agent API")).not.toBeInTheDocument();
        expect(screen.queryByText("Supported intent")).not.toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toBeNull();
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("candidate-plan-1")).not.toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Ready For Planning")).not.toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("fingerprint-1")).not.toBeVisible();
        await user.click(screen.getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("candidate-plan-1")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Ready For Planning")).toBeVisible();
        expect(screen.getByText("Proposal")).toBeInTheDocument();
        expect(screen.getByText("Planning").closest("li")).toHaveAttribute("aria-current", "step");
        expect(screen.getByText("Plan")).toBeInTheDocument();
        expect(screen.queryByText("Disabled")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|approve|create workflow|implementation|commit/i })).not.toBeInTheDocument();
    });

    it("checks a pending plan with a read-only session refresh", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession
            .mockResolvedValueOnce(session({ status: "planning" }))
            .mockResolvedValueOnce(session({ status: "plan_ready", plan: plan() }));
        renderPage();

        expect(await screen.findByText("Atlas is still creating the plan. Check the status again to see whether it is ready.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Check plan status" })).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Check plan status" }));

        expect(await screen.findByRole("heading", { name: "Review the plan" })).toBeVisible();
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it("links to the latest session and keeps session lineage IDs technical", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(
            session({
                session_id: "candidate-plan-2",
                predecessor_session_id: "candidate-plan-1",
                successor_session_id: "candidate-plan-3",
            }),
        );
        renderPage("/candidate-planning/candidate-plan-2");

        expect(await screen.findByText(/A newer planning session is available/)).toBeInTheDocument();
        const link = screen.getByRole("link", { name: "Open the latest session" });
        expect(link).toHaveAttribute("href", "/candidate-planning/candidate-plan-3");
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        await user.click(screen.getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("candidate-plan-1")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("candidate-plan-3")).toBeVisible();
    });

    it("generates a plan and renders the read-only plan viewer", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByRole("button", { name: "Generate Plan" });
        await user.click(screen.getByRole("button", { name: "Generate Plan" }));

        await waitFor(() => expect(mockedGenerateCandidatePlan).toHaveBeenCalledWith("candidate-plan-1"));
        expect(await screen.findByText("Plan details")).toBeInTheDocument();
        expect(screen.getByText("Update Home Assistant compose stack")).toBeInTheDocument();
        expect(screen.getByText("Objective: Update the compose stack safely.")).toBeInTheDocument();
        expect(screen.getByText("Operator has reviewed the candidate.")).toBeInTheDocument();
        expect(screen.getByText("No implementation commands are included.")).toBeInTheDocument();
        expect(screen.getByText("Review compose changes.")).toBeInTheDocument();
        expect(screen.getByText("Branch: feature/atlas-agent")).toBeInTheDocument();
        expect(screen.getByText("compose/home-assistant.yaml")).toBeInTheDocument();
        expect(screen.getByText("Run configuration validation.")).toBeInTheDocument();
        expect(screen.getByText("Restore previous compose file.")).toBeInTheDocument();
        expect(screen.getByText("Confirm maintenance window.")).toBeInTheDocument();
        expect(screen.getByText("evidence-1")).toBeInTheDocument();
        expect(screen.queryByText(/argv|execution metadata/i)).not.toBeInTheDocument();
    });

    it("blocks duplicate Generate Plan requests", async () => {
        const user = userEvent.setup();
        let resolveRequest!: (value: CandidatePlanningResponse) => void;
        mockedGenerateCandidatePlan.mockReturnValue(new Promise((resolve) => {
            resolveRequest = resolve;
        }));

        renderPage();
        const button = await screen.findByRole("button", { name: "Generate Plan" });
        await user.dblClick(button);

        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("button", { name: "Generating plan..." })).toBeDisabled();
        resolveRequest(session({ status: "plan_ready", plan: plan() }));
        expect(await screen.findByText("Plan details")).toBeInTheDocument();
    });

    it("loads an existing plan when session is already plan_ready", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        renderPage();

        expect(await screen.findByText("Plan details")).toBeInTheDocument();
        expect(mockedGetCandidatePlan).toHaveBeenCalledWith("candidate-plan-1");
    });

    it("renders planning failure, unsupported, stale, Core unavailable, persistence, and Agent unavailable states", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "planning_validation_failed", message: "Plan validation failed" } }));
        renderPage();
        expect(await screen.findByText("Atlas could not create a plan. Review Technical details above for the recorded reason.")).toBeInTheDocument();
        let technicalDetails = screen.getByText("Technical details").closest("details");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Plan validation failed", { exact: false })).not.toBeVisible();
        await userEvent.setup().click(screen.getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Plan validation failed", { exact: false })).toBeVisible();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "unsupported_intent", unsupported_reason: "Unsupported intent" }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Atlas cannot plan this type of change yet.")).toBeInTheDocument();
        technicalDetails = screen.getByText("Technical details").closest("details");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Unsupported intent")).not.toBeVisible();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "stale_before_planning" }));
        cleanup();
        renderPage();
        expect(await screen.findByText("This proposal is out of date. Return to the proposal and refresh before trying again.")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "atlas_core_unavailable", message: "Core unavailable" } }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Atlas could not check whether this proposal is current because Core is unavailable.")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "persistence_failed", message: "Persistence failed" } }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Atlas could not save the planning session. No plan is ready to review.")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockRejectedValueOnce(new Error("Agent unavailable"));
        cleanup();
        renderPage();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Planning session unavailable");
        expect(alert).toHaveTextContent("Mission Control could not load this planning session, so its current status is unknown.");
        expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
        const readError = within(alert).getByText("Agent unavailable");
        const readErrorDetails = readError.closest("details");
        expect(readErrorDetails).not.toHaveAttribute("open");
        expect(readError).not.toBeVisible();
        await userEvent.setup().click(within(alert).getByText("Technical details"));
        expect(readError).toBeVisible();
    });

    it("creates a workflow shell from a plan-ready session", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));

        await waitFor(() => expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1"));
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
        const successMessage = "Workflow created. Implementation has not run and still needs separate approval.";
        expect(await screen.findByText(successMessage)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Open Workflow" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1/workflow");
        const workflowResult = screen.getByText(successMessage).closest("[role='status']");
        const technicalDetails = within(workflowResult as HTMLElement).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("workflow-1")).not.toBeVisible();
        await user.click(within(workflowResult as HTMLElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("workflow-1")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Approval Pending")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Implementation approval request")).toBeVisible();
        expect(screen.getByText("Workflow").closest("li")).toHaveAttribute("aria-current", "step");
        expect(screen.queryByRole("button", { name: /approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });

    it("blocks duplicate Create Workflow submissions", async () => {
        const user = userEvent.setup();
        let resolveRequest!: (value: CandidateWorkflowResponse) => void;
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockReturnValue(new Promise((resolve) => {
            resolveRequest = resolve;
        }));
        renderPage();

        const button = await screen.findByRole("button", { name: "Create Workflow" });
        await user.dblClick(button);

        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
        expect(screen.getAllByText("Creating workflow...").length).toBeGreaterThan(0);
        resolveRequest(workflow());
        expect(await screen.findByText("Workflow created. Implementation has not run and still needs separate approval.")).toBeInTheDocument();
    });

    it("handles workflow creation errors and rejected conversion states", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValueOnce(workflow({
            workflow_session_id: null,
            workflow_status: null,
            conversion_status: "workflow_exists",
            implementation_approval_request_id: null,
            failure: { code: "conflicting_active_session", message: "Workflow already exists" },
        }));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByText("A workflow already exists for this plan, but no session was returned to open.")).toBeInTheDocument();

        mockedCreateCandidateWorkflowShell.mockRejectedValueOnce(new Error("Agent unavailable"))
            .mockResolvedValueOnce(workflow());
        cleanup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Workflow result not confirmed");
        expect(alert).toHaveTextContent("The request may have created a workflow, but Mission Control did not receive confirmation.");
        expect(alert).toHaveTextContent("Select Create Workflow again to retrieve or reuse this plan’s workflow.");
        expect(alert).toHaveTextContent("Any implementation still needs separate approval; no infrastructure change has run.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Agent unavailable")).not.toBeVisible();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Agent unavailable")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("link", { name: "Open Workflow" })).toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(3);
    });

    it("requires a reload before retrying a failed plan generation", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockRejectedValueOnce(new Error("Generation failed"));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Plan result unavailable");
        expect(alert).toHaveTextContent("Mission Control could not verify the plan result. Reload this page to check whether Atlas saved the plan before trying again.");
        expect(alert).toHaveTextContent("No approval or infrastructure change was made.");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(1);
        expect(screen.queryByRole("button", { name: /create workflow|approve|execute|implementation|commit/i })).not.toBeInTheDocument();
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Generation failed")).not.toBeVisible();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Generation failed")).toBeVisible();
    });
    it("clears an older session while a different session is loading", async () => {
        let resolveNext!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation((id) => id === "candidate-plan-1"
            ? Promise.resolve(session()) : new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/candidate-planning/:sessionId", element: <PlanningSessionPage /> }], { initialEntries: ["/candidate-planning/candidate-plan-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "Plan this change" });
        await act(() => router.navigate("/candidate-planning/candidate-plan-2"));
        expect(screen.getByText("Loading planning session…")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        resolveNext(session({ session_id: "candidate-plan-2" }));
        expect(await screen.findByRole("heading", { name: "Plan this change" })).toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        await userEvent.setup().click(screen.getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("candidate-plan-2")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).queryByText("candidate-plan-1")).not.toBeInTheDocument();
    });

    it("does not attach a late generated plan to the next session", async () => {
        const user = userEvent.setup();
        let resolvePlan!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation(async (id) => session({ session_id: id }));
        mockedGenerateCandidatePlan.mockImplementationOnce(() => new Promise((resolve) => { resolvePlan = resolve; }));
        const router = createMemoryRouter([{ path: "/candidate-planning/:sessionId", element: <PlanningSessionPage /> }], { initialEntries: ["/candidate-planning/candidate-plan-1"] });
        render(<RouterProvider router={router} />);
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        await act(() => router.navigate("/candidate-planning/candidate-plan-2"));
        await screen.findByRole("heading", { name: "Plan this change" });
        await act(async () => resolvePlan(session({ status: "plan_ready", plan: plan() })));
        expect(screen.queryByText("Update Home Assistant compose stack")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Generate Plan" })).toBeEnabled();
    });

    it("rejects a planning session returned for a different URL identity", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ session_id: "other-session" }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
    });

    it("keeps planning controls hidden when the session response is unreadable", async () => {
        mockedGetCandidatePlanningSession.mockRejectedValue(new Error("Malformed candidate planning response."));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not load this planning session, so its current status is unknown.");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("does not offer workflow creation when the generated plan response is unreadable", async () => {
        mockedGenerateCandidatePlan.mockRejectedValue(new Error("Malformed candidate planning response."));
        const user = userEvent.setup();
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Plan result unavailable");
        expect(alert).toHaveTextContent("Mission Control could not verify the plan result.");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("does not show a ready plan belonging to another session", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan({ session_id: "other-session" }) }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByText("Update Home Assistant compose stack")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("rejects a generated result for a different session", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockResolvedValue(session({ session_id: "other-session", status: "plan_ready", plan: plan({ session_id: "other-session" }) }));
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByText("Update Home Assistant compose stack")).not.toBeInTheDocument();
    });

    it("does not open a workflow result from another planning session", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValueOnce(workflow({ candidate_planning_session_id: "other-session" }))
            .mockResolvedValueOnce(workflow());
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Workflow not opened");
        expect(alert).toHaveTextContent("Atlas returned a workflow for another planning session.");
        expect(alert).toHaveTextContent("Select Create Workflow again to request the result for this session.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(screen.queryByRole("link", { name: "Open Workflow" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("link", { name: "Open Workflow" })).toBeInTheDocument();
    });

    it("does not offer generation when planning is explicitly disallowed", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ planning_allowed: false }));
        renderPage();
        await screen.findByRole("heading", { name: "Plan this change" });
        expect(screen.getByText("Planning is unavailable for this session.")).toBeInTheDocument();
        expect(screen.queryByText(/Review Technical details above/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it("keeps a saved plan read-only when planning is disallowed", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ planning_allowed: false, status: "plan_ready", plan: plan() }));
        renderPage();
        await screen.findByText("Update Home Assistant compose stack");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(screen.getByText("You can review this plan, but this session cannot create a workflow.")).toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("shows recovery instead of an empty ready screen when a saved plan is missing", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockResolvedValue(null);
        renderPage();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("The saved plan could not be loaded.");
        expect(alert).not.toHaveTextContent("Reload to check again");
        expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("does not repeat generation when the server reports ready but its plan is missing", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockResolvedValue(null);
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("The generated plan could not be loaded.");
        expect(alert).not.toHaveTextContent("Reload to check again");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(1);
    });

});
