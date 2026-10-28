import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import {
    exportProviderActionHistory,
    getProviderActionHistory,
    getProviderActionHistoryProviders,
    getProviderActionHistorySummary,
    pruneProviderActionHistory,
} from "../api/atlas";
import { OperationsPage } from "./OperationsPage";

vi.mock("../api/atlas", () => ({
    getAtlasDoctorReport: vi.fn(),
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

function renderPage() {
    return render(
        <MemoryRouter>
            <OperationsPage />
        </MemoryRouter>,
    );
}

describe("OperationsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetProviderActionHistory.mockResolvedValue({
            items: [{
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
            }],
            total: 26,
            offset: 0,
            limit: 25,
            has_more: true,
        });
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

    it("distinguishes loading action history from retention details", async () => {
        renderPage();

        expect(screen.getByText("Loading action history...")).toBeInTheDocument();
        expect(screen.getByText("Loading retention details…")).toBeInTheDocument();
        await screen.findByText("Unload Model");
        expect(screen.queryByText("Loading action history...")).not.toBeInTheDocument();
        expect(screen.queryByText("Loading retention details…")).not.toBeInTheDocument();
    });

    it("keeps action records available when retention details fail to load", async () => {
        mockedGetProviderActionHistorySummary.mockRejectedValueOnce(new Error("Retention read failed"));
        renderPage();

        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        expect(screen.getByText("Retention details are unavailable.")).toBeInTheDocument();
        expect(screen.queryByText("History unavailable")).not.toBeInTheDocument();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledOnce();
    });

    it("keeps action records and date filters available when provider options fail", async () => {
        mockedGetProviderActionHistoryProviders.mockRejectedValueOnce(new Error("Provider read failed"));
        renderPage();

        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        await userEvent.setup().click(screen.getByText("More filters", { exact: true }));
        expect(screen.getByRole("status")).toHaveTextContent("Provider options could not be loaded. Date filters are still available.");
        expect(screen.getByLabelText("From date")).toBeVisible();
        expect(screen.queryByText("History unavailable")).not.toBeInTheDocument();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledOnce();
    });

    it("renders sanitized action audit details", async () => {
        renderPage();

        expect(
            await screen.findByText("Unload Model"),
        ).toBeInTheDocument();
        expect(screen.getAllByText("Ollama")).toHaveLength(1);
        expect(screen.getByText("Provider: Ollama")).toBeVisible();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        expect(screen.getByText("model")).not.toBeVisible();
        expect(screen.getByText("request-123")).not.toBeVisible();
        fireEvent.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
        expect(screen.getByText("model")).toBeVisible();
        expect(screen.getByText("request-123")).toBeVisible();
        expect(
            screen.getByText("Confirmed"),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("link", {
                name: "View audit details",
            }),
        ).toHaveAttribute(
            "href",
            "/operations/actions/audit-1",
        );
    });

    it("requests failed actions when filtered", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(
            screen.getByRole("button", { name: "Failed" }),
        );

        await waitFor(() =>
            expect(
                mockedGetProviderActionHistory,
            ).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 0,
                search: undefined,
                status: "failed",
                providerId: undefined,
                completedFrom: undefined,
                completedTo: undefined,
            }),
        );
    });

    it("keeps retention policy and provider filters when a filtered history read fails", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        let rejectRead!: (reason: Error) => void;
        mockedGetProviderActionHistory.mockReturnValueOnce(new Promise((_, reject) => { rejectRead = reject; }));
        await user.click(screen.getByRole("button", { name: "Failed" }));
        await waitFor(() => expect(screen.queryByText("Unload Model")).not.toBeInTheDocument());
        fireEvent.click(screen.getByText("Export or delete history"));
        expect(screen.getByRole("button", { name: "Delete expired entries" })).toBeDisabled();
        expect(screen.queryByRole("navigation", { name: "Action history pagination" })).not.toBeInTheDocument();
        await act(async () => { rejectRead(new Error("Filtered history unavailable")); });
        expect(await screen.findByRole("alert")).toHaveTextContent("Filtered history unavailable");
        expect(screen.queryByText("Unload Model")).not.toBeInTheDocument();
        expect(screen.getByText("Atlas is keeping 1 of 5000 entries for up to 90 days.")).toBeInTheDocument();
        fireEvent.click(screen.getByText("More filters", { exact: true }));
        expect(within(screen.getByLabelText("Provider")).getByRole("option", { name: "Ollama" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Delete expired entries" })).toBeDisabled();
        expect(screen.getByRole("status")).toHaveTextContent("Expired entries cannot be deleted until action history loads successfully.");
    });

    it("ignores a slow filtered response after a newer filter has loaded", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        const originalPage = await mockedGetProviderActionHistory.mock.results[0].value;
        let resolveRead!: (value: Awaited<ReturnType<typeof getProviderActionHistory>>) => void;
        mockedGetProviderActionHistory.mockReturnValueOnce(new Promise((resolve) => { resolveRead = resolve; }));
        await user.click(screen.getByRole("button", { name: "Failed" }));
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(2));
        mockedGetProviderActionHistory.mockResolvedValueOnce({ items: [], total: 0, offset: 0, limit: 25, has_more: false });
        await user.click(screen.getByRole("button", { name: "Succeeded" }));
        await screen.findByText("No actions recorded");
        await act(async () => { resolveRead(originalPage); });
        expect(screen.queryByText("Unload Model")).not.toBeInTheDocument();
        expect(screen.queryByRole("navigation", { name: "Action history pagination" })).not.toBeInTheDocument();
        expect(screen.getByText("No actions recorded")).toBeInTheDocument();
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
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(
            screen.getByRole("button", {
                name: "Export JSON",
            }),
        );

        expect(
            mockedExportProviderActionHistory,
        ).toHaveBeenCalledWith("json", {
            limit: 25,
            offset: 0,
            search: undefined,
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

    it("keeps loaded history visible when an export fails", async () => {
        const user = userEvent.setup();
        mockedExportProviderActionHistory.mockRejectedValueOnce(new Error("Export failed"));
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export or delete history"));
        await user.click(screen.getByRole("button", { name: "Export JSON" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Export failed");
        expect(screen.getByText("Unload Model")).toBeInTheDocument();
        expect(screen.getByText("Atlas is keeping 1 of 5000 entries for up to 90 days.")).toBeInTheDocument();
        expect(screen.queryByText("History unavailable")).not.toBeInTheDocument();
    });

    it("confirms and prunes expired history", async () => {
        const user = userEvent.setup();
        vi.spyOn(window, "confirm").mockReturnValue(true);
        renderPage();

        await screen.findByText("Unload Model");
        fireEvent.click(screen.getByText("Export or delete history"));
        await user.click(
            screen.getByRole("button", {
                name: "Delete expired entries",
            }),
        );

        expect(window.confirm).toHaveBeenCalledWith(
            "Delete history records older than 90 days? This does not undo provider actions.",
        );
        expect(
            mockedPruneProviderActionHistory,
        ).toHaveBeenCalledOnce();
        expect(
            await screen.findByText(
                "1 expired history entry deleted.",
            ),
        ).toBeInTheDocument();
    });

    it("keeps loaded history visible when pruning fails", async () => {
        const user = userEvent.setup();
        vi.spyOn(window, "confirm").mockReturnValue(true);
        mockedPruneProviderActionHistory.mockRejectedValueOnce(new Error("Delete failed"));
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export or delete history"));
        await user.click(screen.getByRole("button", { name: "Delete expired entries" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Delete failed");
        expect(screen.getByText("Unload Model")).toBeInTheDocument();
        expect(screen.getByText("Atlas is keeping 1 of 5000 entries for up to 90 days.")).toBeInTheDocument();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(1);
        expect(screen.queryByText("History unavailable")).not.toBeInTheDocument();
    });

    it("filters by provider and UTC date range", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Unload Model");
        expect(screen.getByText("Provider actions and their results. Times are shown in your browser’s local time.")).toBeVisible();
        const moreFilters = screen.getByText("More filters", { exact: true });
        expect(moreFilters.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByLabelText("From date")).not.toBeVisible();
        await user.click(moreFilters);
        expect(screen.getByText("Selected dates cover full UTC days.", { exact: true })).toBeVisible();
        expect(screen.getByLabelText("From date")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        expect(screen.getByLabelText("To date")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
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
                limit: 25,
                offset: 0,
                search: undefined,
                status: undefined,
                providerId: "ollama",
                completedFrom:
                    "2026-07-01T00:00:00.000Z",
                completedTo:
                    "2026-07-25T23:59:59.999Z",
            }),
        );
        expect(screen.getByText("Additional filters are applied")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Clear filters" }));
        expect(screen.getByLabelText("Provider")).toHaveValue("all");
        expect(screen.getByLabelText("From date")).toHaveValue("");
        expect(screen.getByLabelText("To date")).toHaveValue("");
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith({
            limit: 25,
            offset: 0,
            search: undefined,
            status: undefined,
            providerId: undefined,
            completedFrom: undefined,
            completedTo: undefined,
        }));
    });

    it("searches and pages through audit results", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Unload Model");
        await user.type(
            screen.getByLabelText("Action or request ID"),
            "request-123",
        );
        await user.click(
            screen.getByRole("button", { name: "Search" }),
        );

        await waitFor(() =>
            expect(
                mockedGetProviderActionHistory,
            ).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 0,
                search: "request-123",
                status: undefined,
                providerId: undefined,
                completedFrom: undefined,
                completedTo: undefined,
            }),
        );

        await user.click(
            screen.getByRole("button", { name: "Next" }),
        );

        await waitFor(() =>
            expect(
                mockedGetProviderActionHistory,
            ).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 25,
                search: "request-123",
                status: undefined,
                providerId: undefined,
                completedFrom: undefined,
                completedTo: undefined,
            }),
        );
    });
});
