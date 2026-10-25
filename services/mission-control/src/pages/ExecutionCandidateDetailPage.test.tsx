import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
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
        expect(screen.getByText(/Planning does not approve or apply a change/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|install|apply|approve|run now/i })).not.toBeInTheDocument();
    });

    it("submits only candidate_id and displays planning session success", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByRole("heading", { name: "candidate-1" });
        await user.click(screen.getByRole("button", { name: "Start planning" }));

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
        const button = screen.getByRole("button", { name: "Start planning" });
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
        expect(screen.getByRole("button", { name: "Start planning" })).toBeDisabled();

        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ id: "candidate-expired", expires_at: "2000-01-01T00:00:00Z" }));
        renderPage("/execution-candidates/candidate-expired");

        expect(await screen.findByText("Candidate has expired.")).toBeInTheDocument();
        expect(screen.getAllByRole("button", { name: "Start planning" }).at(-1)).toBeDisabled();
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
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Unsupported intent. Atlas Agent cannot plan this candidate yet.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "intake_rejected", planning_allowed: false, intake_status: "policy_denied", intake_reason_codes: ["policy_denied"] }));
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Planning intake rejected by Atlas Core.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "stale_before_planning", planning_allowed: false, intake_status: "stale" }));
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Candidate is stale. Refresh the candidate and try again.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "intake_rejected", planning_allowed: false, intake_status: "rejected", planning_failure: { code: "atlas_core_unavailable", message: "Core unavailable" } }));
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Atlas Core unavailable during authoritative revalidation.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "intake_rejected", planning_allowed: false, intake_status: "rejected", planning_failure: { code: "persistence_failed", message: "Persistence failed" } }));
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Planning session could not be persisted.")).toBeInTheDocument();

        mockedCreateCandidatePlanningSession.mockRejectedValueOnce(new Error("Agent unavailable"));
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Agent unavailable")).toBeInTheDocument();
    });
    it("does not show a previous proposal or its planning action while the next loads", async () => {
        let resolveNext!: (value: ExecutionCandidate) => void;
        mockedGetExecutionCandidate.mockImplementation((id) => id === "candidate-1"
            ? Promise.resolve(candidate()) : new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/execution-candidates/:candidateId", element: <ExecutionCandidateDetailPage /> }], { initialEntries: ["/execution-candidates/candidate-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "candidate-1" });
        await act(() => router.navigate("/execution-candidates/candidate-2"));
        expect(screen.queryByRole("heading", { name: "candidate-1" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Start planning" })).not.toBeInTheDocument();
        resolveNext(candidate({ id: "candidate-2" }));
        expect(await screen.findByRole("heading", { name: "candidate-2" })).toBeInTheDocument();
    });

    it("recovers when navigating from a missing proposal to a valid one", async () => {
        mockedGetExecutionCandidate.mockRejectedValueOnce(Object.assign(new Error("not found"), { isAxiosError: true, response: { status: 404 } }))
            .mockResolvedValueOnce(candidate({ id: "candidate-2" }));
        const router = createMemoryRouter([{ path: "/execution-candidates/:candidateId", element: <ExecutionCandidateDetailPage /> }], { initialEntries: ["/execution-candidates/missing"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "Execution candidate not found" });
        await act(() => router.navigate("/execution-candidates/candidate-2"));
        expect(await screen.findByRole("heading", { name: "candidate-2" })).toBeInTheDocument();
    });

    it("does not apply a late planning response to a different proposal", async () => {
        const user = userEvent.setup();
        let resolvePlanning!: (value: CandidatePlanningResponse) => void;
        mockedGetExecutionCandidate.mockImplementation(async (id) => candidate({ id }));
        mockedCreateCandidatePlanningSession.mockImplementationOnce(() => new Promise((resolve) => { resolvePlanning = resolve; }))
            .mockResolvedValueOnce(planningResponse({ candidate_id: "candidate-2", session_id: "candidate-plan-2" }));
        const router = createMemoryRouter([{ path: "/execution-candidates/:candidateId", element: <ExecutionCandidateDetailPage /> }], { initialEntries: ["/execution-candidates/candidate-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "candidate-1" });
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        await act(() => router.navigate("/execution-candidates/candidate-2"));
        await screen.findByRole("heading", { name: "candidate-2" });
        await act(async () => resolvePlanning(planningResponse()));
        expect(screen.queryByText("Planning session ID: candidate-plan-1")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Planning session ID: candidate-plan-2")).toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenLastCalledWith({ candidate_id: "candidate-2" });
    });

    it("refuses candidate details whose identity does not match the URL", async () => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ id: "different-candidate" }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Start planning" })).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("does not link a planning response for a different proposal", async () => {
        const user = userEvent.setup();
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse({ candidate_id: "different-candidate" }));
        renderPage();
        await screen.findByRole("heading", { name: "candidate-1" });
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("The planning response did not match this proposal.");
        expect(screen.queryByRole("link", { name: "Continue planning" })).not.toBeInTheDocument();
    });

    it.each(["not-a-time", "2999-02-30T00:00:00Z", "2999-01-01T00:00:00", ""])("keeps planning disabled for an unverified expiry: %j", async (expires_at) => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ expires_at }));
        renderPage();
        await screen.findByRole("heading", { name: "candidate-1" });
        expect(screen.getByRole("button", { name: "Start planning" })).toBeDisabled();
        expect(screen.getByText("Unverified expiry")).toBeInTheDocument();
    });

    it.each([null, undefined])("preserves planning eligibility when expiry is optional: %j", async (expires_at) => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ expires_at }));
        renderPage();
        await screen.findByRole("heading", { name: "candidate-1" });
        expect(screen.getByRole("button", { name: "Start planning" })).toBeEnabled();
    });

    it("uses HTTP status instead of error wording to classify a missing proposal", async () => {
        mockedGetExecutionCandidate.mockRejectedValue(Object.assign(new Error("A dependency was not found"), {
            isAxiosError: true, response: { status: 503 },
        }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Execution candidate not found" })).not.toBeInTheDocument();
    });

});
