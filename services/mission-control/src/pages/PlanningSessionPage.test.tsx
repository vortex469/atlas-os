import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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
} from "../types/atlasAgent";
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

function renderPage() {
    return render(
        <MemoryRouter initialEntries={["/candidate-planning/candidate-plan-1"]}>
            <Routes>
                <Route path="/candidate-planning/:sessionId" element={<PlanningSessionPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("PlanningSessionPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetCandidatePlanningSession.mockResolvedValue(session());
        mockedGenerateCandidatePlan.mockResolvedValue(session({ status: "plan_ready", plan: plan() }));
        mockedCreateCandidateWorkflowShell.mockResolvedValue(workflow());
        mockedGetCandidatePlan.mockResolvedValue(plan());
    });

    it("renders planning session metadata, workflow rail, and no execution controls", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: /Planning Session candidate-plan-1/i })).toBeInTheDocument();
        expect(screen.getByText("candidate-1")).toBeInTheDocument();
        expect(screen.getAllByText("Ready For Planning").length).toBeGreaterThan(0);
        expect(screen.getByText("Not exposed by Atlas Agent API")).toBeInTheDocument();
        expect(screen.getByText("update-compose-stack")).toBeInTheDocument();
        expect(screen.getByText("fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("Execution Candidate ✔")).toBeInTheDocument();
        expect(screen.getByText("Planning Session ✔")).toBeInTheDocument();
        expect(screen.getByText("Candidate Plan ○")).toBeInTheDocument();
        expect(screen.getAllByText("Disabled").length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: /execute|approve|create workflow|implementation|commit/i })).not.toBeInTheDocument();
    });

    it("renders lineage links for successor sessions and predecessor metadata", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(
            session({
                session_id: "candidate-plan-2",
                predecessor_session_id: "candidate-plan-1",
                successor_session_id: "candidate-plan-3",
            }),
        );
        renderPage();

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
        expect(await screen.findByText("Plan ready")).toBeInTheDocument();
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
        resolveRequest(session({ status: "plan_ready", plan: plan() }));
        expect(await screen.findByText("Plan ready")).toBeInTheDocument();
    });

    it("loads an existing plan when session is already plan_ready", async () => {
        mockedGetCandidatePlanningSession.mockResolvedValue(session({ status: "plan_ready" }));
        renderPage();

        expect(await screen.findByText("Plan ready")).toBeInTheDocument();
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
        expect(screen.getByText("Workflow ✔")).toBeInTheDocument();
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
});
