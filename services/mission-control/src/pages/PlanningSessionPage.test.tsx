import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
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
    it.each(["workflow-1", null])("opens an existing workflow using reads only (reference: %s)", async workflow_session_id => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "workflow_created", planning_allowed: false, workflow_session_id }));
        renderPage();
        const link = await screen.findByRole("link", { name: workflow_session_id ? "Open existing workflow" : "Browse workflows" });
        expect(link).toHaveAttribute("href", workflow_session_id ? "/workflows/workflow-1" : "/workflows");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it.each(["missing", "unavailable"])("retries a %s planning read without submitting an action", async state => {
        if (state === "missing") mockedGetCandidatePlanningSession.mockResolvedValueOnce(null);
        else mockedGetCandidatePlanningSession.mockRejectedValueOnce(new Error("Read unavailable"));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Try again" }));
        await screen.findByRole("button", { name: "Generate Plan" });
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("hides old planning actions during refresh and applies the latest read", async () => {
        let finish!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session()).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Refresh planning" }));
        expect(screen.getByRole("status")).toHaveTextContent("Loading planning session");
        expect(screen.getByRole("link", { name: "← Change proposals" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Refresh planning" })).not.toBeInTheDocument();
        await act(async () => finish(session({ status: "workflow_created", planning_allowed: false, workflow_session_id: "workflow-1" })));
        expect(await screen.findByRole("link", { name: "Open existing workflow" })).toHaveAttribute("href", "/workflows/workflow-1");
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it.each(["plan", "workflow"])("checks a saved %s after a lost reply without repeating the action", async action => {
        const ready = action === "workflow";
        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session(ready ? { status: "plan_ready", plan: plan() } : {}))
            .mockResolvedValueOnce(session({ status: ready ? "workflow_created" : "plan_ready", planning_allowed: false, plan: plan(), workflow_session_id: ready ? "workflow-1" : null }));
        if (ready) mockedCreateCandidateWorkflowShell.mockRejectedValueOnce(new Error("Reply lost"));
        else mockedGenerateCandidatePlan.mockRejectedValueOnce(new Error("Reply lost"));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: ready ? "Create Workflow" : "Generate Plan" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(ready ? "Workflow result unavailable" : "Plan result unavailable");
        await user.click(screen.getByRole("button", { name: "Check saved planning" }));
        if (ready) await screen.findByRole("link", { name: "Open existing workflow" });
        else await screen.findByText("Plan details");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedGetCandidatePlanningSession).toHaveBeenCalledTimes(2);
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(ready ? 0 : 1);
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(ready ? 1 : 0);
        expect(mockedGetCandidatePlan).not.toHaveBeenCalled();
    });

    it("keeps a converted maintenance plan available for review without offering another workflow", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", operational_plan: operationalPlan(), workflow_session_id: "workflow-1" }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance plan" });
        expect(screen.getByRole("link", { name: "Open existing workflow" })).toHaveAttribute("href", "/workflows/workflow-1");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it.each(["", "..", "invalid\u0000id", { unexpected: true }])("does not build a workflow link from an unusable reference: %j", async reference => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "workflow_created", planning_allowed: false, workflow_session_id: reference as string }));
        renderPage();
        expect(await screen.findByRole("link", { name: "Browse workflows" })).toHaveAttribute("href", "/workflows");
        expect(screen.queryByRole("link", { name: "Open existing workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

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

    it("renders planning session metadata, workflow rail, and no execution controls", async () => {
        const user = userEvent.setup();
        renderPage();

        expect(await screen.findByText("candidate-plan-1", { exact: true })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Plan this change" })).toBeVisible();
        expect(screen.getByText("candidate-1")).toBeInTheDocument();
        expect(screen.getAllByText("Ready For Planning").length).toBeGreaterThan(0);
        expect(screen.queryByText("Not exposed by Atlas Agent API")).not.toBeInTheDocument();
        expect(screen.queryByText("Supported intent")).not.toBeInTheDocument();
        expect(screen.getByText("fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("Proposal")).toBeInTheDocument();
        expect(screen.getByText("Planning").closest("li")).toHaveAttribute("aria-current", "step");
        expect(screen.getByText("Plan")).toBeInTheDocument();
        expect(screen.queryByText("Disabled")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|approve|create workflow|implementation|commit/i })).not.toBeInTheDocument();
        const disclosure = screen.getByText("Technical details", { exact: true });
        expect(disclosure.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByText("fingerprint-1")).not.toBeVisible();
        expect(screen.getByRole("button", { name: "Generate Plan" })).toBeVisible();
        await user.click(disclosure);
        expect(screen.getByText("fingerprint-1")).toBeVisible();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("renders lineage links for successor sessions and predecessor metadata", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(
            session({
                session_id: "candidate-plan-2",
                predecessor_session_id: "candidate-plan-1",
                successor_session_id: "candidate-plan-3",
            }),
        );
        renderPage("/candidate-planning/candidate-plan-2");

        expect(await screen.findByText("Successor of")).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-1")).toBeInTheDocument();
        const link = screen.getByRole("link", { name: "candidate-plan-3" });
        expect(link).toHaveAttribute("href", "/candidate-planning/candidate-plan-3");
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
        expect(screen.getAllByText("Generating plan...").length).toBeGreaterThan(0);
        expect(screen.getByRole("button", { name: "Refresh planning" })).toBeDisabled();
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
        expect(await screen.findByText("Planning failed.")).toBeInTheDocument();
        expect(screen.getByText("Plan validation failed")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "unsupported_intent", unsupported_reason: "Unsupported intent" }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Planning not supported.")).toBeInTheDocument();
        expect(screen.getByText("Unsupported intent")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "stale_before_planning" }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Stale candidate.")).toBeInTheDocument();
        expect(screen.getByText(/Candidate is stale/i)).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "atlas_core_unavailable", message: "Core unavailable" } }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Atlas Core unavailable.")).toBeInTheDocument();
        expect(screen.getByText("Atlas Core unavailable during planning.")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockResolvedValueOnce(session({ status: "planning_failed", planning_failure: { code: "persistence_failed", message: "Persistence failed" } }));
        cleanup();
        renderPage();
        expect(await screen.findByText("Persistence failure.")).toBeInTheDocument();
        expect(screen.getByText("Planning session could not be persisted.")).toBeInTheDocument();

        mockedGetCandidatePlanningSession.mockRejectedValueOnce(new Error("Agent unavailable"));
        cleanup();
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Agent unavailable");
    });

    it("creates a workflow shell from a plan-ready session", async () => {
        const user = userEvent.setup();
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));

        await waitFor(() => expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledWith("candidate-plan-1"));
        expect(mockedCreateCandidateWorkflowShell).toHaveBeenCalledTimes(1);
        expect(await screen.findByText("Workflow created.")).toBeInTheDocument();
        expect(screen.getByText("Workflow ID")).toBeInTheDocument();
        expect(screen.getByText("workflow-1")).toBeInTheDocument();
        expect(screen.getByText("Approval Pending")).toBeInTheDocument();
        expect(screen.getByText("Implementation approval pending")).toBeInTheDocument();
        expect(screen.getByText("Yes")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Open Workflow" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1/workflow");
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
        expect(screen.getByRole("button", { name: "Refresh planning" })).toBeDisabled();
        resolveRequest(workflow());
        expect(await screen.findByText("Workflow created.")).toBeInTheDocument();
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
        expect(await screen.findByText("Workflow already exists.")).toBeInTheDocument();

        mockedCreateCandidateWorkflowShell.mockRejectedValueOnce(new Error("Agent unavailable"));
        cleanup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Agent unavailable");
    });

    it("shows generation errors without creating workflow controls", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockRejectedValueOnce(new Error("Generation failed"));
        renderPage();

        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Generation failed");
        expect(screen.queryByRole("button", { name: /create workflow|approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });
    it("clears an older session while a different session is loading", async () => {
        let resolveNext!: (value: CandidatePlanningResponse) => void;
        mockedGetCandidatePlanningSession.mockImplementation((id) => id === "candidate-plan-1"
            ? Promise.resolve(session()) : new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/candidate-planning/:sessionId", element: <PlanningSessionPage /> }], { initialEntries: ["/candidate-planning/candidate-plan-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByText("candidate-plan-1", { exact: true });
        await act(() => router.navigate("/candidate-planning/candidate-plan-2"));
        expect(screen.queryByText("candidate-plan-1", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        resolveNext(session({ session_id: "candidate-plan-2" }));
        expect(await screen.findByText("candidate-plan-2", { exact: true })).toBeInTheDocument();
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
        await screen.findByText("candidate-plan-2", { exact: true });
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
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow({ candidate_planning_session_id: "other-session" }));
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Create Workflow" }));
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "Open Workflow" })).not.toBeInTheDocument();
    });

    it("does not offer generation when planning is explicitly disallowed", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ planning_allowed: false }));
        renderPage();
        await screen.findByText("candidate-plan-1", { exact: true });
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).not.toHaveBeenCalled();
    });

    it("keeps a saved plan read-only when planning is disallowed", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ planning_allowed: false, status: "plan_ready", plan: plan() }));
        renderPage();
        await screen.findByText("Update Home Assistant compose stack");
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
        expect(mockedCreateCandidateWorkflowShell).not.toHaveBeenCalled();
    });

    it("shows recovery instead of an empty ready screen when a saved plan is missing", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockResolvedValue(null);
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The saved plan could not be loaded");
        expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument();
    });

    it("does not repeat generation when the server reports ready but its plan read fails", async () => {
        const user = userEvent.setup();
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready" }));
        mockedGetCandidatePlan.mockRejectedValue(new Error("read unavailable"));
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Generate Plan" }));
        await screen.findByRole("alert");
        expect(screen.queryByRole("button", { name: "Generate Plan" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Check saved planning" })).toBeInTheDocument();
        expect(mockedGenerateCandidatePlan).toHaveBeenCalledTimes(1);
    });

});
