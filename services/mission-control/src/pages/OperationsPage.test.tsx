import {
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    exportProviderActionHistory,
    getProviderActionHistory,
    getProviderActionHistoryProviders,
    getProviderActionHistorySummary,
    pruneProviderActionHistory,
} from "../api/atlas";
import { OperationsPage } from "./OperationsPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
    getProviderActionHistory: vi.fn(),
    getProviderActionHistorySummary: vi.fn(),
    getProviderActionHistoryProviders: vi.fn(),
    exportProviderActionHistory: vi.fn(),
    pruneProviderActionHistory: vi.fn(),
}));

const mockedGetProviderActionHistory = vi.mocked(
    getProviderActionHistory,
);
const mockedGetProviderActionHistorySummary = vi.mocked(
    getProviderActionHistorySummary,
);
const mockedGetProviderActionHistoryProviders = vi.mocked(
    getProviderActionHistoryProviders,
);
const mockedExportProviderActionHistory = vi.mocked(
    exportProviderActionHistory,
);
const mockedPruneProviderActionHistory = vi.mocked(
    pruneProviderActionHistory,
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
        mockedGetProviderActionHistorySummary.mockResolvedValue({
            entry_count: 1,
            max_entries: 5000,
            retention_days: 90,
            oldest_entry_at: "2026-07-25T17:00:01Z",
            newest_entry_at: "2026-07-25T17:00:01Z",
        });
        mockedGetProviderActionHistoryProviders.mockResolvedValue(
            [
                { id: "ollama", name: "Ollama" },
                { id: "docker", name: "Docker" },
            ],
        );
        mockedExportProviderActionHistory.mockResolvedValue(
            new Blob(["[]"], {
                type: "application/json",
            }),
        );
        mockedPruneProviderActionHistory.mockResolvedValue({
            deleted_entries: 1,
            remaining_entries: 0,
            cutoff: "2026-04-26T17:00:00Z",
        });
    });

    it("renders sanitized action audit details", async () => {
        render(<OperationsPage />);

        expect(
            await screen.findByText("Unload Model"),
        ).toBeInTheDocument();
        expect(screen.getAllByText("Ollama")).toHaveLength(2);
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
                providerId: undefined,
                completedFrom: undefined,
                completedTo: undefined,
            }),
        );
    });

    it("downloads a sanitized history export", async () => {
        const user = userEvent.setup();
        const click = vi
            .spyOn(HTMLAnchorElement.prototype, "click")
            .mockImplementation(() => undefined);
        const createObjectURL = vi.fn(() => "blob:audit");
        const revokeObjectURL = vi.fn();
        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL,
        });
        render(<OperationsPage />);

        await screen.findByText("Unload Model");
        await user.click(
            screen.getByRole("button", {
                name: "Export JSON",
            }),
        );

        expect(
            mockedExportProviderActionHistory,
        ).toHaveBeenCalledWith("json", {
            limit: 100,
            status: undefined,
            providerId: undefined,
            completedFrom: undefined,
            completedTo: undefined,
        });
        expect(createObjectURL).toHaveBeenCalledOnce();
        expect(click).toHaveBeenCalledOnce();
        expect(revokeObjectURL).toHaveBeenCalledWith(
            "blob:audit",
        );
        expect(
            await screen.findByText(
                "Action history exported as JSON.",
            ),
        ).toBeInTheDocument();
    });

    it("confirms and prunes expired history", async () => {
        const user = userEvent.setup();
        vi.spyOn(window, "confirm").mockReturnValue(true);
        render(<OperationsPage />);

        await screen.findByText("Unload Model");
        await user.click(
            screen.getByRole("button", {
                name: "Prune expired",
            }),
        );

        expect(window.confirm).toHaveBeenCalledWith(
            "Delete audit entries older than 90 days?",
        );
        expect(
            mockedPruneProviderActionHistory,
        ).toHaveBeenCalledOnce();
        expect(
            await screen.findByText(
                "1 expired audit entry pruned.",
            ),
        ).toBeInTheDocument();
    });

    it("filters by provider and UTC date range", async () => {
        const user = userEvent.setup();
        render(<OperationsPage />);

        await screen.findByText("Unload Model");
        await user.selectOptions(
            screen.getByLabelText("Provider"),
            "ollama",
        );
        await user.type(
            screen.getByLabelText("From date"),
            "2026-07-01",
        );
        await user.type(
            screen.getByLabelText("To date"),
            "2026-07-25",
        );

        await waitFor(() =>
            expect(
                mockedGetProviderActionHistory,
            ).toHaveBeenLastCalledWith({
                limit: 100,
                status: undefined,
                providerId: "ollama",
                completedFrom:
                    "2026-07-01T00:00:00.000Z",
                completedTo:
                    "2026-07-25T23:59:59.999Z",
            }),
        );
    });
});
