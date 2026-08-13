import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createCandidatePlanningSession } from "../api/atlas-agent";
import { getExecutionCandidate } from "../api/executionCandidates";
import type { CandidatePlanningResponse } from "../types/atlasAgent";
import type { ExecutionCandidate } from "../types/executionCandidates";
import { ExecutionCandidateDetailPage } from "./ExecutionCandidateDetailPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

vi.mock("../api/atlas-agent", () => ({
    createCandidatePlanningSession: vi.fn(),
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

vi.mock("../api/executionCandidates", () => ({
    getExecutionCandidate: vi.fn(),
}));

const mockedGetExecutionCandidate = vi.mocked(getExecutionCandidate);
const mockedCreateCandidatePlanningSession = vi.mocked(createCandidatePlanningSession);

function candidate(overrides: Partial<ExecutionCandidate> = {}): ExecutionCandidate {
    return {
        id: "candidate-1",
        source_recommendation_id: "finding-1",
        source_subsystem: "orion",
        recommendation_class: "update-compose-stack",
        catalog_item_id: "catalog-home-assistant",
        target_id: "stack-home-assistant",
        target_type: "compose_stack",
        execution_category: "update",
        execution_intent: "update-compose-stack",
        status: "eligible",
        required_approval_level: "standard",
        rationale: "Update the compose stack after review.",
        constraints: ["service_disruption"],
        evidence_ids: ["evidence-1"],
        compatibility_assessment_id: "compat-1",
        compatibility_status: "compatible_with_warnings",
        relationship_ids: ["relationship-1"],
        created_at: "2026-01-01T00:00:00Z",
        expires_at: "2999-01-01T00:00:00Z",
        ...overrides,
    };
}

function planningResponse(overrides: Partial<CandidatePlanningResponse> = {}): CandidatePlanningResponse {
    return {
        session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        status: "ready_for_planning",
        planning_allowed: true,
        intake_status: "accepted_for_planning",
        intake_reason_codes: [],
        candidate_fingerprint: "fingerprint-from-agent",
        unsupported_reason: null,
        plan: null,
        planning_failure: null,
        ...overrides,
    };
}

function renderPage(path = "/execution-candidates/candidate-1") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/execution-candidates/:candidateId" element={<ExecutionCandidateDetailPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("ExecutionCandidateDetailPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetExecutionCandidate.mockResolvedValue(candidate());
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse());
    });

    it("renders all public candidate fields and boundary wording", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "candidate-1" })).toBeInTheDocument();
        expect(screen.getByText("finding-1")).toBeInTheDocument();
        expect(screen.getByText("orion")).toBeInTheDocument();
        expect(screen.getByText("update-compose-stack")).toBeInTheDocument();
        expect(screen.getByText("catalog-home-assistant")).toBeInTheDocument();
        expect(screen.getByText("stack-home-assistant")).toBeInTheDocument();
        expect(screen.getByText("compose_stack")).toBeInTheDocument();
        expect(screen.getAllByText("Update Compose Stack").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Eligible for planning consideration").length).toBeGreaterThan(0);
        expect(screen.getByText("Standard")).toBeInTheDocument();
        expect(screen.getByText("Update the compose stack after review.")).toBeInTheDocument();
        expect(screen.getByText("service_disruption")).toBeInTheDocument();
        expect(screen.getByText("evidence-1")).toBeInTheDocument();
        expect(screen.getByText("compat-1")).toBeInTheDocument();
        expect(screen.getByText("Compatible With Warnings")).toBeInTheDocument();
        expect(screen.getByText("relationship-1")).toBeInTheDocument();
        expect(screen.getByText(/Eligibility means Atlas Agent may consider this candidate for planning/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|install|apply|approve|run now/i })).not.toBeInTheDocument();
    });

    it("submits only candidate_id and displays planning session success", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByRole("heading", { name: "candidate-1" });
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));

        await waitFor(() =>
            expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledWith({
                candidate_id: "candidate-1",
            }),
        );
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
        expect(await screen.findByText("Planning session created. Next step: generate a candidate plan.")).toBeInTheDocument();
        expect(screen.getByText("Planning session ID: candidate-plan-1")).toBeInTheDocument();
    });

    it("prevents duplicate planning submissions", async () => {
        const user = userEvent.setup();
        let resolveRequest!: (value: CandidatePlanningResponse) => void;
        mockedCreateCandidatePlanningSession.mockReturnValue(
            new Promise((resolve) => {
                resolveRequest = resolve;
            }),
        );

        renderPage();
        await screen.findByRole("heading", { name: "candidate-1" });
        const button = screen.getByRole("button", { name: "Ask Atlas Agent to plan" });
        await user.dblClick(button);

        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
        expect(screen.getByText("Planning request is already pending.")).toBeInTheDocument();
        resolveRequest(planningResponse());
        expect(await screen.findByText("Planning session ID: candidate-plan-1")).toBeInTheDocument();
    });

    it("disables planning for not eligible and expired candidates with visible reasons", async () => {
        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ status: "not_eligible" }));
        renderPage();

        expect(await screen.findByText("Candidate is not eligible for planning.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Ask Atlas Agent to plan" })).toBeDisabled();

        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ expires_at: "2000-01-01T00:00:00Z" }));
        renderPage("/execution-candidates/candidate-expired");

        expect(await screen.findByText("Candidate has expired.")).toBeInTheDocument();
        expect(screen.getAllByRole("button", { name: "Ask Atlas Agent to plan" }).at(-1)).toBeDisabled();
    });

    it("handles unsupported, rejected, stale, Core unavailable, Agent unavailable, and persistence failures", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByRole("heading", { name: "candidate-1" });

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({
            session_id: null,
            status: "unsupported_intent",
            planning_allowed: false,
            intake_status: "accepted_for_planning",
            unsupported_reason: "Only update-compose-stack is supported.",
        }));
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));
        expect(await screen.findByText("Unsupported intent. Atlas Agent cannot plan this candidate yet.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "intake_rejected", planning_allowed: false, intake_status: "policy_denied", intake_reason_codes: ["policy_denied"] }));
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));
        expect(await screen.findByText("Planning intake rejected by Atlas Core.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "stale_before_planning", planning_allowed: false, intake_status: "stale" }));
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));
        expect(await screen.findByText("Candidate is stale. Refresh the candidate and try again.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "intake_rejected", planning_allowed: false, intake_status: "rejected", planning_failure: { code: "atlas_core_unavailable", message: "Core unavailable" } }));
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));
        expect(await screen.findByText("Atlas Core unavailable during authoritative revalidation.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "intake_rejected", planning_allowed: false, intake_status: "rejected", planning_failure: { code: "persistence_failed", message: "Persistence failed" } }));
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));
        expect(await screen.findByText("Planning session could not be persisted.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockRejectedValueOnce(new Error("Agent unavailable"));
        await user.click(screen.getByRole("button", { name: "Ask Atlas Agent to plan" }));
        expect(await screen.findByText("Agent unavailable")).toBeInTheDocument();
    });
});
