import { render, screen, waitFor } from "@testing-library/react";
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

function renderPage() {
    return render(
        <MemoryRouter>
            <ExecutionCandidatesPage />
        </MemoryRouter>,
    );
}

describe("ExecutionCandidatesPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedListExecutionCandidates.mockResolvedValue(page([candidate()]));
    });

    it("renders candidate cards, workflow rail, and no execution controls", async () => {
        renderPage();

        expect(await screen.findByText("candidate-1")).toBeInTheDocument();
        expect(screen.getByText("Eligible for planning consideration")).toBeInTheDocument();
        expect(screen.getByText("stack-home-assistant")).toBeInTheDocument();
        expect(screen.getByText("Update Compose Stack")).toBeInTheDocument();
        expect(screen.getByText("2 references")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "candidate-1" })).toHaveAttribute(
            "href",
            "/execution-candidates/candidate-1",
        );
        expect(screen.getByText("Planning Session")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute|install|apply|approve|run now/i })).not.toBeInTheDocument();
    });

    it("sends filters and supports pagination", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates
            .mockResolvedValueOnce(page([candidate()], { total: 50, has_more: true }))
            .mockResolvedValueOnce(page([candidate({ id: "candidate-2" })], { total: 50, has_more: true }))
            .mockResolvedValueOnce(page([candidate({ id: "candidate-3" })], { total: 50, offset: 25 }));

        renderPage();
        await screen.findByText("candidate-1");

        await user.selectOptions(screen.getByLabelText("Status"), "eligible");
        await user.selectOptions(screen.getByLabelText("Category"), "update");
        await user.selectOptions(screen.getByLabelText("Intent"), "update-compose-stack");
        await user.type(screen.getByLabelText("Source subsystem"), "orion");
        await user.type(screen.getByLabelText("Target ID"), "stack-home-assistant");
        await user.click(screen.getByRole("button", { name: "Search" }));

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

        await user.click(screen.getByRole("button", { name: "Next execution candidates page" }));
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

    it("distinguishes empty, filtered empty, and error states", async () => {
        const user = userEvent.setup();
        mockedListExecutionCandidates.mockResolvedValueOnce(page([]));

        renderPage();
        expect(await screen.findByText("No current execution candidates.")).toBeInTheDocument();

        mockedListExecutionCandidates.mockResolvedValueOnce(page([]));
        await user.selectOptions(screen.getByLabelText("Status"), "not_eligible");
        await user.click(screen.getByRole("button", { name: "Search" }));
        expect(await screen.findByText("No execution candidates match these filters.")).toBeInTheDocument();

        mockedListExecutionCandidates.mockRejectedValueOnce(new Error("Core unavailable"));
        await user.click(screen.getByRole("button", { name: "Clear" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Core unavailable");
    });

    it("keeps unsupported or not eligible candidates visible", async () => {
        mockedListExecutionCandidates.mockResolvedValue(page([
            candidate({ id: "candidate-unsupported", execution_intent: "restart-service", status: "not_eligible" }),
        ]));

        renderPage();

        expect(await screen.findByText("candidate-unsupported")).toBeInTheDocument();
        expect(screen.getByText("Not eligible for planning")).toBeInTheDocument();
        expect(screen.getByText("Restart Service")).toBeInTheDocument();
    });
});
