import {
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
    MemoryRouter,
    Route,
    Routes,
} from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getProviderActionHistoryEntry } from "../api/atlas";
import { ActionHistoryDetailPage } from "./ActionHistoryDetailPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
    getProviderActionHistoryEntry: vi.fn(),
}));

const mockedGetProviderActionHistoryEntry = vi.mocked(
    getProviderActionHistoryEntry,
);

function renderPage(path = "/operations/actions/audit-1") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route
                    path="/operations/actions/:auditId"
                    element={<ActionHistoryDetailPage />}
                />
            </Routes>
        </MemoryRouter>,
    );
}

describe("ActionHistoryDetailPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetProviderActionHistoryEntry.mockResolvedValue({
            id: "audit-1",
            provider_id: "ollama",
            provider_name: "Ollama",
            action_id: "unload-model",
            action_label: "Unload Model",
            status: "succeeded",
            success: true,
            message: "Model unloaded.",
            confirmed: true,
            destructive: false,
            parameter_names: ["model"],
            request_id: "request-123",
            started_at: "2026-07-25T17:00:00Z",
            completed_at: "2026-07-25T17:00:01Z",
            duration_ms: 12.5,
        });
    });

    it("loads a directly linked audit entry", async () => {
        renderPage();

        expect(
            await screen.findByRole("heading", {
                name: "Unload Model",
            }),
        ).toBeInTheDocument();
        expect(
            mockedGetProviderActionHistoryEntry,
        ).toHaveBeenCalledWith("audit-1");
        expect(screen.getByText("audit-1")).toBeInTheDocument();
        expect(
            screen.getByText("request-123"),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("link", {
                name: "← Back to Operations",
            }),
        ).toHaveAttribute("href", "/operations");
    });

    it("copies the current deep link", async () => {
        const user = userEvent.setup();
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        renderPage();

        await screen.findByText("Model unloaded.");
        await user.click(
            screen.getByRole("button", { name: "Copy link" }),
        );

        expect(writeText).toHaveBeenCalledWith(
            window.location.href,
        );
        expect(
            await screen.findByText("Audit link copied."),
        ).toBeInTheDocument();
    });

    it("shows an API error for a missing audit entry", async () => {
        mockedGetProviderActionHistoryEntry.mockRejectedValue(
            new Error("Provider action audit entry not found."),
        );
        renderPage("/operations/actions/missing-entry");

        expect(
            await screen.findByRole("alert"),
        ).toHaveTextContent(
            "Provider action audit entry not found.",
        );
        await waitFor(() =>
            expect(
                screen.queryByText("Loading audit details..."),
            ).not.toBeInTheDocument(),
        );
    });
});
