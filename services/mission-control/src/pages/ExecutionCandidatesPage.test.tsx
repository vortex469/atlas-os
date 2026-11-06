import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listExecutionCandidates } from "../api/executionCandidates";
import type { ExecutionCandidate, ExecutionCandidatePage } from "../types/executionCandidates";
import { ExecutionCandidatesPage } from "./ExecutionCandidatesPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

vi.mock("../api/executionCandidates", () => ({
    listExecutionCandidates: vi.fn(),
}));

const mockedListExecutionCandidates = vi.mocked(listExecutionCandidates);

function candidate(overrides: Partial<ExecutionCandidate> = {}): ExecutionCandidate {
    return {
        effect_kind: "repository_change",
        id: "candidate-1",
        source_recommendation_id: "finding-1",
        source_subsystem: "orion",
        recommendation_class: "update-compose-stack",
        catalog_item_id: null,
        target_id: "stack-home-assistant",
        target_type: "compose_stack",
        execution_category: "update",
        execution_intent: "update-compose-stack",
        status: "eligible",
        required_approval_level: "standard",
        rationale: "Update the compose stack after review.",
        constraints: ["service_disruption"],
        evidence_ids: ["evidence-1", "evidence-2"],
        compatibility_assessment_id: "compat-1",
        compatibility_status: "compatible_with_warnings",
        relationship_ids: ["relationship-1"],
        created_at: "2026-01-01T00:00:00Z",
        expires_at: null,
        ...overrides,
    };
}

function page(candidates: ExecutionCandidate[], overrides: Partial<ExecutionCandidatePage> = {}): ExecutionCandidatePage {
    return {
        candidates,
        total: candidates.length,
        limit: 25,
        offset: 0,
        has_more: false,
        ...overrides,
    };
}

function renderPage(path = "/execution-candidates") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <ExecutionCandidatesPage />
        </MemoryRouter>,
    );
}

describe("ExecutionCandidatesPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedListExecutionCandidates.mockResolvedValue(page([candidate()]));
    });

    it("leads candidate cards with the change and keeps technical details collapsed", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates.mockResolvedValueOnce(page([candidate({ expires_at: "2999-01-02T00:00:00Z" })]));
        renderPage();

        expect(await screen.findByRole("link", { name: "Review Update Compose Stack proposal" })).toBeInTheDocument();
        expect(screen.getByText("Eligible for planning")).toBeInTheDocument();
        expect(screen.getByText("stack-home-assistant")).toBeVisible();
        expect(screen.getByRole("article")).toHaveTextContent("Target: stack-home-assistant · Type: Compose Stack");
        expect(screen.getByText("Compatible with warnings")).toBeInTheDocument();
        expect(screen.getByText("Expires (local time)").parentElement?.querySelector("time")).toHaveAttribute("dateTime", "2999-01-02T00:00:00Z");
        expect(screen.getByRole("link", { name: "Review Update Compose Stack proposal" })).toHaveAttribute(
            "href",
            "/execution-candidates/candidate-1",
        );
        expect(screen.getByText("candidate-1")).not.toBeVisible();
        expect(screen.getByText("2 references")).not.toBeVisible();
        await user.click(screen.getByText("More proposal details"));
        expect(screen.getByText("candidate-1")).toBeVisible();
        expect(screen.getByText("2 references")).toBeVisible();
        expect(screen.getByText("Created (local time)").parentElement?.querySelector("time")).toHaveAttribute("dateTime", "2026-01-01T00:00:00Z");
        expect(screen.getByText("Planning")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|install|apply|approve|run now/i })).not.toBeInTheDocument();
    });

    it("shows unavailable for malformed proposal timestamps", async () => {
        mockedListExecutionCandidates.mockResolvedValueOnce(page([candidate({ created_at: "invalid", expires_at: "2026-02-30T00:00:00Z" })]));
        renderPage();
        await screen.findByRole("link", { name: "Review Update Compose Stack proposal" });
        expect(screen.getByText("Expires (local time)").parentElement).toHaveTextContent("Time unavailable");
        await userEvent.click(screen.getByText("More proposal details"));
        expect(screen.getByText("Created (local time)").parentElement).toHaveTextContent("Time unavailable");
        expect(screen.queryByText("Invalid Date")).not.toBeInTheDocument();
    });

    it("offers supported eligibility and expiry filters", () => {
        renderPage();

        const eligibility = screen.getByLabelText("Eligibility");
        expect(within(eligibility).getByRole("option", { name: "Eligible" })).toHaveValue("eligible");
        expect(within(eligibility).getByRole("option", { name: "Not eligible" })).toHaveValue("not_eligible");
        expect(within(eligibility).getByRole("option", { name: "Expired" })).toHaveValue("expired");
    });

    it("restores submitted proposal filters, draft edits, and the current page from the URL", async () => {
        mockedListExecutionCandidates.mockResolvedValueOnce(page([candidate()], { total: 26, offset: 25 }));
        renderPage("/execution-candidates?eligibility=eligible&change=update-compose-stack&category=update&source=orion&target=stack-home-assistant&draftTarget=typed-target&offset=25");

        expect(await screen.findByRole("link", { name: "Review Update Compose Stack proposal" })).toBeVisible();
        expect(mockedListExecutionCandidates).toHaveBeenCalledWith({
            status: "eligible",
            category: "update",
            intent: "update-compose-stack",
            sourceSubsystem: "orion",
            targetId: "stack-home-assistant",
            limit: 25,
            offset: 25,
        });
        expect(screen.getByLabelText("Eligibility")).toHaveValue("eligible");
        expect(screen.getByLabelText("Change")).toHaveValue("update-compose-stack");
        expect(screen.getByLabelText("Target")).toHaveValue("typed-target");
        expect(screen.getByText("These filter changes haven't been searched yet. Select Search proposals to update the results.")).toBeVisible();
        expect(screen.getByRole("link", { name: "Review Update Compose Stack proposal" })).toHaveAttribute(
            "href",
            "/execution-candidates/candidate-1?eligibility=eligible&change=update-compose-stack&category=update&source=orion&target=stack-home-assistant&draftTarget=typed-target&offset=25",
        );
    });

    it("shows expired candidates by expiry and keeps unknown eligibility unavailable", async () => {
        mockedListExecutionCandidates.mockResolvedValueOnce(page([
            candidate({ id: "expired-candidate", expires_at: "2000-01-01T00:00:00Z" }),
            candidate({ id: "unknown-candidate", status: "future_state", expires_at: null }),
        ]));
        renderPage();

        const cards = await screen.findAllByRole("article");
        expect(cards).toHaveLength(2);
        expect(cards[0]).toHaveTextContent("Expired");
        expect(cards[1]).toHaveTextContent("Eligibility unavailable");
        expect(screen.queryByText("Future State")).not.toBeInTheDocument();
    });

    it("keeps newer search results when an older search completes later", async () => {
        renderPage();
        await screen.findByText("candidate-1");
        let resolveOld!: (value: ExecutionCandidatePage) => void;
        mockedListExecutionCandidates.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
            .mockResolvedValueOnce(page([candidate({ id: "latest-candidate" })]));
        fireEvent.click(screen.getByRole("button", { name: "Search proposals" }));
        expect(screen.queryByText("candidate-1")).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
        await screen.findByText("latest-candidate");
        await act(async () => resolveOld(page([candidate({ id: "older-candidate" })])));
        expect(screen.getByText("latest-candidate")).toBeInTheDocument();
        expect(screen.queryByText("older-candidate")).not.toBeInTheDocument();
    });

    it("ignores an older failure while the latest search is still loading", async () => {
        renderPage();
        await screen.findByText("candidate-1");
        let rejectOld!: (error: Error) => void;
        let resolveLatest!: (value: ExecutionCandidatePage) => void;
        mockedListExecutionCandidates.mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; }))
            .mockImplementationOnce(() => new Promise((resolve) => { resolveLatest = resolve; }));
        fireEvent.click(screen.getByRole("button", { name: "Search proposals" }));
        fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
        await act(async () => rejectOld(new Error("Old search failed")));
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.getByText("Loading change proposals…")).toBeInTheDocument();
        await act(async () => resolveLatest(page([candidate({ id: "latest-candidate" })])));
        expect(screen.getByText("latest-candidate")).toBeInTheDocument();
    });

    it("hides previous cards after the current search fails", async () => {
        renderPage();
        await screen.findByText("candidate-1");
        mockedListExecutionCandidates.mockRejectedValueOnce(new Error("Current search failed: Bearer canary-secret-value"));
        fireEvent.click(screen.getByRole("button", { name: "Search proposals" }));
        const alert = await screen.findByRole("alert");
        expect(screen.queryByText("candidate-1")).not.toBeInTheDocument();
        expect(alert).toHaveTextContent("Atlas couldn’t load the latest change proposals. Your search filters are still selected.");
        expect(alert).toHaveTextContent("Previous results are hidden until this search succeeds.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("[Sensitive text withheld]")).not.toBeVisible();
        expect(within(alert).queryByText(/canary-secret-value/)).not.toBeInTheDocument();
        await userEvent.setup().click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("[Sensitive text withheld]")).toBeVisible();
        expect(screen.queryByText("Results unavailable")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Next change proposals page" })).toBeDisabled();
    });

    it("offers a retry when the proposal list contains an unreadable entry", async () => {
        mockedListExecutionCandidates
            .mockResolvedValueOnce(page([null as unknown as ExecutionCandidate]))
            .mockResolvedValueOnce(page([candidate()]));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Change proposals unavailable");
        expect(alert).toHaveTextContent("Atlas couldn’t load the latest change proposals. Your search filters are still selected.");
        expect(alert).not.toHaveTextContent("Previous results are hidden until this search succeeds.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(screen.queryByRole("heading", { name: "This page could not load" })).not.toBeInTheDocument();

        fireEvent.click(within(alert).getByRole("button", { name: "Retry search" }));

        expect(await screen.findByRole("link", { name: "Review Update Compose Stack proposal" })).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedListExecutionCandidates).toHaveBeenCalledTimes(2);
    });

    it("retries the same proposal search after a read failure", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates
            .mockResolvedValueOnce(page([candidate()]))
            .mockRejectedValueOnce(new Error("Core unavailable"))
            .mockResolvedValueOnce(page([]));

        renderPage();
        await screen.findByText("candidate-1");
        await user.type(screen.getByLabelText("Target"), "stack-home-assistant");
        await user.click(screen.getByRole("button", { name: "Search proposals" }));
        await screen.findByRole("alert");

        await user.click(screen.getByRole("button", { name: "Retry search" }));

        expect(await screen.findByText("No change proposals match these filters.")).toBeInTheDocument();
        expect(mockedListExecutionCandidates).toHaveBeenLastCalledWith({
            status: undefined,
            category: undefined,
            intent: undefined,
            sourceSubsystem: undefined,
            targetId: "stack-home-assistant",
            limit: 25,
            offset: 0,
        });
    });

    it("does not let the initial read overwrite a submitted search", async () => {
        let resolveInitial!: (value: ExecutionCandidatePage) => void;
        mockedListExecutionCandidates.mockImplementationOnce(() => new Promise((resolve) => { resolveInitial = resolve; }))
            .mockResolvedValueOnce(page([candidate({ id: "searched-candidate" })]));
        renderPage();
        await waitFor(() => expect(mockedListExecutionCandidates).toHaveBeenCalledTimes(1));
        fireEvent.click(screen.getByRole("button", { name: "Search proposals" }));
        await screen.findByText("searched-candidate");
        await act(async () => resolveInitial(page([candidate({ id: "initial-candidate" })])));
        expect(screen.getByText("searched-candidate")).toBeInTheDocument();
        expect(screen.queryByText("initial-candidate")).not.toBeInTheDocument();
    });

    it("sends filters and supports pagination", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates
            .mockResolvedValueOnce(page([candidate()], { total: 50, has_more: true }))
            .mockResolvedValueOnce(page([candidate({ id: "candidate-2" })], { total: 50, has_more: true }))
            .mockResolvedValueOnce(page([candidate({ id: "candidate-3" })], { total: 50, offset: 25 }));

        renderPage();
        await screen.findByText("candidate-1");

        await user.selectOptions(screen.getByLabelText("Eligibility"), "eligible");
        await user.click(screen.getByText("More filters"));
        await user.selectOptions(screen.getByLabelText("Category"), "update");
        await user.selectOptions(screen.getByLabelText("Change"), "update-compose-stack");
        await user.type(screen.getByLabelText("Source"), "orion");
        await user.type(screen.getByLabelText("Target"), "stack-home-assistant");
        await user.click(screen.getByRole("button", { name: "Search proposals" }));

        await waitFor(() =>
            expect(mockedListExecutionCandidates).toHaveBeenLastCalledWith({
                status: "eligible",
                category: "update",
                intent: "update-compose-stack",
                sourceSubsystem: "orion",
                targetId: "stack-home-assistant",
                limit: 25,
                offset: 0,
            }),
        );
        expect(screen.getByText("More filters · active")).toBeVisible();
        expect(await screen.findByText("candidate-2")).toBeInTheDocument();
        expect(screen.getByRole("status", { name: "Proposal result range" })).toHaveTextContent("Showing 1–1 of 50 proposals");

        await user.click(screen.getByRole("button", { name: "Next change proposals page" }));
        expect(await screen.findByText("candidate-3")).toBeInTheDocument();
        expect(screen.getByRole("status", { name: "Proposal result range" })).toHaveTextContent("Showing 26–26 of 50 proposals");
        await waitFor(() =>
            expect(mockedListExecutionCandidates).toHaveBeenLastCalledWith({
                status: "eligible",
                category: "update",
                intent: "update-compose-stack",
                sourceSubsystem: "orion",
                targetId: "stack-home-assistant",
                limit: 25,
                offset: 25,
            }),
        );
    });

    it("explains when edited filters have not been searched and pauses paging", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates
            .mockResolvedValueOnce(page([candidate()], { total: 50, has_more: true }))
            .mockResolvedValueOnce(page([candidate()], { total: 50, has_more: true }));

        renderPage();
        await screen.findByText("candidate-1");
        await user.selectOptions(screen.getByLabelText("Eligibility"), "not_eligible");

        expect(screen.getByText(
            "These filter changes haven't been searched yet. Select Search proposals to update the results.",
        )).toHaveAttribute("role", "status");
        expect(screen.getByRole("button", { name: "Next change proposals page" })).toBeDisabled();
        expect(mockedListExecutionCandidates).toHaveBeenCalledTimes(1);

        await user.click(screen.getByRole("button", { name: "Search proposals" }));

        await waitFor(() => expect(mockedListExecutionCandidates).toHaveBeenLastCalledWith({
            status: "not_eligible",
            category: undefined,
            intent: undefined,
            sourceSubsystem: undefined,
            targetId: undefined,
            limit: 25,
            offset: 0,
        }));
        expect(screen.queryByText("These filter changes haven't been searched yet. Select Search proposals to update the results.")).not.toBeInTheDocument();
        expect(screen.getByRole("status", { name: "Proposal result range" })).toHaveTextContent("Showing 1–1 of 50 proposals");
        expect(screen.getByRole("button", { name: "Next change proposals page" })).toBeEnabled();
    });

    it("distinguishes empty, filtered empty, and error states", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates.mockResolvedValueOnce(page([]));

        renderPage();
        expect(await screen.findByText("No current change proposals.")).toBeInTheDocument();
        expect(screen.queryByText("0 proposals", { exact: true })).not.toBeInTheDocument();

        mockedListExecutionCandidates.mockResolvedValueOnce(page([]));
        await user.selectOptions(screen.getByLabelText("Eligibility"), "not_eligible");
        await user.click(screen.getByRole("button", { name: "Search proposals" }));
        expect(await screen.findByText("No change proposals match these filters.")).toBeInTheDocument();
        expect(screen.queryByText("0 proposals", { exact: true })).not.toBeInTheDocument();

        mockedListExecutionCandidates.mockRejectedValueOnce(new Error("Core unavailable"));
        await user.click(screen.getByRole("button", { name: "Reset filters" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas couldn’t load the latest change proposals. Your search filters are still selected.");
    });

    it("uses singular wording when one proposal is available", async () => {
        mockedListExecutionCandidates.mockResolvedValueOnce(page([candidate()]));
        renderPage();

        expect(await screen.findByRole("status", { name: "Proposal result range" })).toHaveTextContent("Showing 1–1 of 1 proposal");
    });

    it("explains when a later page has no rows but earlier matches remain", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates
            .mockResolvedValueOnce(page([candidate()], { total: 26, has_more: true }))
            .mockResolvedValueOnce(page([], { total: 26, offset: 25 }));
        renderPage();

        await screen.findByText("candidate-1");
        await user.click(screen.getByRole("button", { name: "Next change proposals page" }));

        expect(await screen.findByText("No proposals are on this page. Try the previous page.")).toBeInTheDocument();
    });

    it("keeps unsupported or not eligible candidates visible", async () => {
        mockedListExecutionCandidates.mockResolvedValue(page([
            candidate({ id: "candidate-unsupported", execution_intent: "restart-service", status: "not_eligible" }),
        ]));

        renderPage();

        expect(await screen.findByRole("link", { name: "Review Restart Service proposal" })).toBeInTheDocument();
        expect(screen.getByText("Not eligible for planning")).toBeInTheDocument();
    });
});
