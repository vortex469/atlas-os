import {
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getProviderActionHistory } from "../api/atlas";
import { OperationsPage } from "./OperationsPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
    getProviderActionHistory: vi.fn(),
}));

const mockedGetProviderActionHistory = vi.mocked(
    getProviderActionHistory,
);

describe("OperationsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetProviderActionHistory.mockResolvedValue([
            {
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
            },
        ]);
    });

    it("renders sanitized action audit details", async () => {
        render(<OperationsPage />);

        expect(
            await screen.findByText("Unload Model"),
        ).toBeInTheDocument();
        expect(screen.getByText("Ollama")).toBeInTheDocument();
        expect(screen.getByText("model")).toBeInTheDocument();
        expect(
            screen.getByText("request-123"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Confirmed"),
        ).toBeInTheDocument();
    });

    it("requests failed actions when filtered", async () => {
        const user = userEvent.setup();
        render(<OperationsPage />);

        await screen.findByText("Unload Model");
        await user.click(
            screen.getByRole("button", { name: "Failed" }),
        );

        await waitFor(() =>
            expect(
                mockedGetProviderActionHistory,
            ).toHaveBeenLastCalledWith({
                limit: 100,
                status: "failed",
            }),
        );
    });
});
