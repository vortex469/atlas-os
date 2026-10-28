import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
        effect_kind: "repository_change",
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
    afterEach(() => vi.useRealTimers());
    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetExecutionCandidate.mockResolvedValue(candidate());
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse());
    });

    it.each([
        ["execution_intent", {}], ["execution_intent", ""], ["execution_category", null],
        ["status", {}], ["required_approval_level", []], ["target_id", {}], ["target_id", " "],
        ["target_type", 42], ["rationale", {}], ["constraints", null], ["constraints", [{}]],
        ["evidence_ids", undefined], ["relationship_ids", [{}]], ["compatibility_status", {}],
        ["compatibility_assessment_id", {}], ["catalog_item_id", {}], ["created_at", {}],
        ["source_recommendation_id", null], ["source_subsystem", {}], ["recommendation_class", []],
    ] as Array<[keyof ExecutionCandidate, unknown]>)("keeps unreadable %s out of proposal review and recovers by GET", async (field, value) => {
        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ [field]: value } as unknown as Partial<ExecutionCandidate>));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("The proposal response is incomplete or unreadable. Choose Try again to reload it.");
        expect(screen.queryByRole("button", { name: "Start planning" })).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
        await userEvent.click(screen.getByRole("button", { name: "Try again" }));
        expect(await screen.findByRole("button", { name: "Start planning" })).toBeEnabled();
        expect(mockedGetExecutionCandidate).toHaveBeenCalledTimes(2);
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("accepts readable future labels, nullable optional metadata, and extra fields", async () => {
        mockedGetExecutionCandidate.mockResolvedValue({ ...candidate({ execution_intent: "future-operation", status: "future_state", required_approval_level: "future_level", rationale: "", catalog_item_id: null, compatibility_assessment_id: null, compatibility_status: null, constraints: [], evidence_ids: [], relationship_ids: [] }), effect_kind: "future_effect", extra_metadata: { future: true } } as unknown as ExecutionCandidate);
        renderPage();
        expect(await screen.findByRole("heading", { name: "Future Operation", level: 1 })).toBeVisible();
        expect(screen.getByText("Future Level", { exact: true })).toBeVisible();
        expect(screen.getByText("No explanation was provided.", { exact: true })).toBeVisible();
        expect(screen.getByText("No constraints were reported.", { exact: true })).toBeVisible();
        expect(screen.getByRole("button", { name: "Start planning" })).toBeDisabled();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it.each(["2026-02-30T00:00:00Z", "2026-08-16T00:00:00", "2026-08-16", "2099-01-01T00:00:00Z", "not-a-time"])("does not invent a creation time for %s", async (createdAt) => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ created_at: createdAt }));
        renderPage();
        await screen.findByRole("heading", { name: "Update Compose Stack", level: 1 });
        await userEvent.click(screen.getByText("Technical details", { exact: true }));
        expect(screen.getByText("Created", { exact: true }).parentElement).toHaveTextContent("Unknown time");
        expect(screen.getByRole("button", { name: "Start planning" })).toBeEnabled();
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("reports an absent creation time without inventing an epoch date", async () => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ created_at: "" }));
        renderPage();
        await screen.findByRole("heading", { name: "Update Compose Stack", level: 1 });
        await userEvent.click(screen.getByText("Technical details", { exact: true }));
        expect(screen.getByText("Created", { exact: true }).parentElement).toHaveTextContent("Not reported");
    });

    it.each(["2024-02-29T12:00:00.123456Z", "2026-08-16T14:00:00+02:00", "1970-01-01T00:00:00Z"])("preserves confirmed creation time %s", async (createdAt) => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ created_at: createdAt }));
        renderPage();
        await screen.findByRole("heading", { name: "Update Compose Stack", level: 1 });
        await userEvent.click(screen.getByText("Technical details", { exact: true }));
        expect(screen.getByText("Created", { exact: true }).parentElement).toHaveTextContent(new Date(createdAt).toLocaleString());
    });

    it("renders all public candidate fields and boundary wording", async () => {
        const user = userEvent.setup();
        renderPage();

        expect(await screen.findByText("candidate-1", { exact: true })).toBeInTheDocument();
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
        expect(screen.getByRole("heading", { name: "Update Compose Stack", level: 1 })).toBeVisible();
        expect(screen.getByText("Standard")).toBeVisible();
        expect(screen.getByText("Compatible With Warnings")).toBeVisible();
        expect(screen.getByText("service_disruption")).toBeVisible();
        const planning = screen.getByRole("region", { name: "Plan this change" });
        const why = screen.getByRole("heading", { name: "Why this change", level: 2 });
        const constraints = screen.getByRole("heading", { name: "Constraints", level: 2 });
        expect(why.compareDocumentPosition(planning) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(constraints.compareDocumentPosition(planning) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(screen.getByText("evidence-1", { exact: true })).not.toBeVisible();
        const disclosure = screen.getByText("Technical details", { exact: true });
        expect(disclosure.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByText("candidate-1", { exact: true })).not.toBeVisible();
        await user.click(disclosure);
        expect(screen.getByText("candidate-1", { exact: true })).toBeVisible();
        expect(screen.getByText("evidence-1", { exact: true })).toBeVisible();
        expect(mockedGetExecutionCandidate).toHaveBeenCalledTimes(1);
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("submits only candidate_id and displays planning session success", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("candidate-1", { exact: true });
        await user.click(screen.getByRole("button", { name: "Start planning" }));

        await waitFor(() =>
            expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledWith({
                candidate_id: "candidate-1",
            }),
        );
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
        expect(await screen.findByText("Planning session created. Next step: generate a candidate plan.")).toBeInTheDocument();
        const details = screen.getByText("Planning details", { exact: true });
        expect(screen.getByText("Planning session ID: candidate-plan-1")).not.toBeVisible();
        await user.click(details);
        expect(screen.getByText("Planning session ID: candidate-plan-1")).toBeVisible();
        expect(screen.getByText("Status: Ready For Planning")).toBeVisible();
    });

    it.each([
        { status: null }, { status: " " }, { intake_status: {} },
        { planning_allowed: "true" }, { intake_reason_codes: null },
        { intake_reason_codes: [{}] }, { unsupported_reason: {} },
        { planning_failure: undefined }, { planning_failure: {} },
        { planning_failure: { code: "failed", message: {} } },
        { workflow_session_id: "\ud800" },
    ])("offers read-only recovery for an unreadable planning result: %j", async fields => {
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse(fields as unknown as Partial<CandidatePlanningResponse>));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("The planning response could not be read. A session may have been saved.");
        expect(screen.getByRole("link", { name: "Review planning details" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1");
        expect(screen.queryByRole("link", { name: "Continue planning" })).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledExactlyOnceWith({ candidate_id: "candidate-1" });
        await user.click(screen.getByRole("button", { name: "Refresh proposal" }));
        await screen.findByRole("button", { name: "Start planning" });
        expect(screen.queryByRole("link", { name: "Review planning details" })).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
    });

    it.each([{}, "", "..", " leading", "bad\nref", "\ud800"])("withholds unreadable planning references: %j", async session_id => {
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse({ session_id } as unknown as Partial<CandidatePlanningResponse>));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("The planning response could not be read.");
        expect(screen.queryByRole("link", { name: "Review planning details" })).not.toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "Continue planning" })).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
    });

    it("accepts readable future planning labels and unused metadata", async () => {
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse({ status: "future_status", intake_status: "future_intake", intake_reason_codes: ["future_reason"], candidate_fingerprint: {} } as unknown as Partial<CandidatePlanningResponse>));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("link", { name: "Continue planning" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1");
        expect(screen.getByText("Reason codes: future_reason")).not.toBeVisible();
        await user.click(screen.getByText("Planning details", { exact: true }));
        expect(screen.getByText("Reason codes: future_reason")).toBeVisible();
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
        await screen.findByText("candidate-1", { exact: true });
        const button = screen.getByRole("button", { name: "Start planning" });
        await user.dblClick(button);

        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
        expect(screen.getByText("Planning request is already pending.")).toBeInTheDocument();
        resolveRequest(planningResponse());
        expect(await screen.findByText("Planning session ID: candidate-plan-1")).not.toBeVisible();
    });

    it("disables planning when the proposal expires while open without another read", async () => {
        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ expires_at: new Date(Date.now() + 60_000).toISOString() }));
        renderPage();
        await screen.findByRole("button", { name: "Start planning" });
        vi.useFakeTimers();
        // Refresh after installing the controlled clock so the expiry timer is controlled too.
        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ expires_at: new Date(Date.now() + 60_000).toISOString() }));
        await act(async () => fireEvent.click(screen.getByRole("button", { name: "Refresh proposal" })));
        expect(screen.getByRole("button", { name: "Start planning" })).toBeEnabled();
        await act(async () => vi.advanceTimersByTime(60_000));
        expect(screen.getByRole("button", { name: "Start planning" })).toBeDisabled();
        expect(screen.getByText("Candidate has expired.")).toBeInTheDocument();
        expect(mockedGetExecutionCandidate).toHaveBeenCalledTimes(2);
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("rechecks expiry at the click boundary before the expiry timer fires", async () => {
        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ expires_at: new Date(Date.now() + 60_000).toISOString() }));
        renderPage();
        const button = await screen.findByRole("button", { name: "Start planning" });
        expect(button).toBeEnabled();
        vi.useFakeTimers();
        vi.setSystemTime(Date.now() + 120_000);
        await act(async () => fireEvent.click(button));
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
        expect(screen.getByText("Candidate has expired.")).toBeInTheDocument();
        expect(mockedGetExecutionCandidate).toHaveBeenCalledTimes(1);
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
        await screen.findByText("candidate-1", { exact: true });

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
        expect(await screen.findByText("This proposal changed or expired. Choose Refresh proposal to check its latest state.")).toBeInTheDocument();

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
        await screen.findByText("candidate-1", { exact: true });
        await act(() => router.navigate("/execution-candidates/candidate-2"));
        expect(screen.queryByText("candidate-1", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Start planning" })).not.toBeInTheDocument();
        resolveNext(candidate({ id: "candidate-2" }));
        expect(await screen.findByText("candidate-2", { exact: true })).toBeInTheDocument();
    });

    it("recovers when navigating from a missing proposal to a valid one", async () => {
        mockedGetExecutionCandidate.mockRejectedValueOnce(Object.assign(new Error("not found"), { isAxiosError: true, response: { status: 404 } }))
            .mockResolvedValueOnce(candidate({ id: "candidate-2" }));
        const router = createMemoryRouter([{ path: "/execution-candidates/:candidateId", element: <ExecutionCandidateDetailPage /> }], { initialEntries: ["/execution-candidates/missing"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "Change proposal not found" });
        await act(() => router.navigate("/execution-candidates/candidate-2"));
        expect(await screen.findByText("candidate-2", { exact: true })).toBeInTheDocument();
    });

    it("does not apply a late planning response to a different proposal", async () => {
        const user = userEvent.setup();
        let resolvePlanning!: (value: CandidatePlanningResponse) => void;
        mockedGetExecutionCandidate.mockImplementation(async (id) => candidate({ id }));
        mockedCreateCandidatePlanningSession.mockImplementationOnce(() => new Promise((resolve) => { resolvePlanning = resolve; }))
            .mockResolvedValueOnce(planningResponse({ candidate_id: "candidate-2", session_id: "candidate-plan-2" }));
        const router = createMemoryRouter([{ path: "/execution-candidates/:candidateId", element: <ExecutionCandidateDetailPage /> }], { initialEntries: ["/execution-candidates/candidate-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByText("candidate-1", { exact: true });
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        await act(() => router.navigate("/execution-candidates/candidate-2"));
        await screen.findByText("candidate-2", { exact: true });
        await act(async () => resolvePlanning(planningResponse()));
        expect(screen.queryByText("Planning session ID: candidate-plan-1")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByText("Planning session ID: candidate-plan-2")).toBeInTheDocument();
        expect(screen.getByText("Planning session ID: candidate-plan-2")).not.toBeVisible();
        await user.click(screen.getByText("Planning details", { exact: true }));
        expect(screen.getByText("Planning session ID: candidate-plan-2")).toBeVisible();
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
        await screen.findByText("candidate-1", { exact: true });
        await user.click(screen.getByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("The planning response did not match this proposal.");
        expect(screen.queryByRole("link", { name: "Continue planning" })).not.toBeInTheDocument();
    });

    it.each(["not-a-time", "2999-02-30T00:00:00Z", "2999-01-01T00:00:00", ""])("keeps planning disabled for an unverified expiry: %j", async (expires_at) => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ expires_at }));
        renderPage();
        await screen.findByText("candidate-1", { exact: true });
        expect(screen.getByRole("button", { name: "Start planning" })).toBeDisabled();
        expect(screen.getByText("Unverified expiry")).toBeInTheDocument();
    });

    it.each([null, undefined])("preserves planning eligibility when expiry is optional: %j", async (expires_at) => {
        mockedGetExecutionCandidate.mockResolvedValue(candidate({ expires_at }));
        renderPage();
        await screen.findByText("candidate-1", { exact: true });
        expect(screen.getByRole("button", { name: "Start planning" })).toBeEnabled();
    });

    it.each(["missing", "unavailable", "foreign"] as const)("retries the same proposal after an initial %s response", async failure => {
        if (failure === "foreign") mockedGetExecutionCandidate.mockResolvedValueOnce(candidate({ id: "foreign-candidate" }));
        else mockedGetExecutionCandidate.mockRejectedValueOnce(Object.assign(new Error("read unavailable"), { isAxiosError: true, response: { status: failure === "missing" ? 404 : 503 } }));
        const user = userEvent.setup();
        renderPage();
        const retry = await screen.findByRole("button", { name: "Try again" });
        expect(screen.queryByRole("button", { name: "Start planning" })).not.toBeInTheDocument();
        await user.click(retry);
        expect(await screen.findByRole("button", { name: "Start planning" })).toBeEnabled();
        expect(mockedGetExecutionCandidate).toHaveBeenCalledTimes(2);
        expect(mockedGetExecutionCandidate).toHaveBeenLastCalledWith("candidate-1");
        expect(mockedCreateCandidatePlanningSession).not.toHaveBeenCalled();
    });

    it("clears a stale planning result while refreshing and uses the new proposal eligibility", async () => {
        let finish!: (value: ExecutionCandidate) => void;
        mockedGetExecutionCandidate.mockResolvedValueOnce(candidate()).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
        mockedCreateCandidatePlanningSession.mockResolvedValueOnce(planningResponse({ session_id: null, status: "candidate_stale", planning_allowed: false, planning_failure: { code: "candidate_stale", message: "Read the latest proposal" } }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        await screen.findByText(/This proposal changed or expired/);
        await user.click(screen.getByRole("button", { name: "Refresh proposal" }));
        expect(screen.queryByText(/This proposal changed or expired/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Start planning" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Change proposals/ })).toBeInTheDocument();
        await act(async () => finish(candidate({ status: "expired" })));
        expect(await screen.findByRole("button", { name: "Start planning" })).toBeDisabled();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
    });

    it("pauses proposal refresh during an explicit planning request", async () => {
        let finish!: (value: CandidatePlanningResponse) => void;
        mockedCreateCandidatePlanningSession.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        expect(screen.getByRole("button", { name: "Refresh proposal" })).toBeDisabled();
        await user.click(screen.getByRole("button", { name: "Refresh proposal" }));
        expect(mockedGetExecutionCandidate).toHaveBeenCalledTimes(1);
        await act(async () => finish(planningResponse()));
        expect(screen.getByRole("button", { name: "Refresh proposal" })).toBeEnabled();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
    });

    it.each(["workflow-1", null])("reviews an existing workflow without treating it as a planning failure (reference: %s)", async workflow_session_id => {
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse({ status: "workflow_created", planning_allowed: false, workflow_session_id }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        const link = await screen.findByRole("link", { name: workflow_session_id ? "Open existing workflow" : "Browse workflows" });
        expect(link).toHaveAttribute("href", workflow_session_id ? "/workflows/workflow-1" : "/workflows");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "Continue planning" })).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
    });

    it("reviews the linked workflow when a persisted plan is already converted", async () => {
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse({ status: "plan_ready", planning_allowed: true, workflow_session_id: "workflow-1" }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("link", { name: "Open existing workflow" })).toHaveAttribute("href", "/workflows/workflow-1");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedCreateCandidatePlanningSession).toHaveBeenCalledTimes(1);
    });

    it("offers saved-plan review without reporting a denied planning action as failure", async () => {
        mockedCreateCandidatePlanningSession.mockResolvedValue(planningResponse({ status: "plan_ready", planning_allowed: false }));
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Start planning" }));
        expect(await screen.findByRole("link", { name: "Review saved plan" })).toHaveAttribute("href", "/candidate-planning/candidate-plan-1");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("uses HTTP status instead of error wording to classify a missing proposal", async () => {
        mockedGetExecutionCandidate.mockRejectedValue(Object.assign(new Error("A dependency was not found"), {
            isAxiosError: true, response: { status: 503 },
        }));
        renderPage();
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Change proposal not found" })).not.toBeInTheDocument();
    });

});
