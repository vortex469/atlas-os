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

        expect(screen.getByRole("heading", { name: "Action history" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Loading history…" })).toBeDisabled();
        expect(screen.getByRole("status")).toHaveTextContent("Loading action history…");
        expect(screen.getByText("Loading retention details…")).toBeInTheDocument();
        await screen.findByText("Unload Model");
        expect(screen.getByRole("button", { name: "Refresh history" })).toBeEnabled();
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
        expect(screen.queryByText("Loading retention details…")).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Atlas Doctor" })).not.toBeInTheDocument();
    });

    it("labels a later history request as refreshing", async () => {
        renderPage();
        await screen.findByText("Unload Model");

        let resolveRefresh!: (value: Awaited<ReturnType<typeof getProviderActionHistory>>) => void;
        mockedGetProviderActionHistory.mockReturnValueOnce(new Promise((resolve) => { resolveRefresh = resolve; }));
        fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));

        expect(screen.getByRole("button", { name: "Refreshing history…" })).toBeDisabled();
        expect(screen.getByRole("status")).toHaveTextContent("Refreshing action history…");
        await act(async () => resolveRefresh({
            items: [],
            total: 0,
            offset: 0,
            limit: 25,
            has_more: false,
        }));
        expect(screen.getByRole("button", { name: "Refresh history" })).toBeEnabled();
    });

    it("keeps action records available when retention details fail to load", async () => {
        mockedGetProviderActionHistorySummary.mockRejectedValueOnce(new Error("Retention read failed"));
        renderPage();

        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        expect(screen.getByText("Retention details are unavailable.")).toBeInTheDocument();
        expect(screen.queryByText("Action history unavailable")).not.toBeInTheDocument();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledOnce();
        fireEvent.click(screen.getByText("Export or delete history"));
        expect(screen.getByRole("button", { name: "Delete expired entries" })).toBeDisabled();
    });

    it("keeps action records and date filters available when provider options fail", async () => {
        mockedGetProviderActionHistoryProviders.mockRejectedValueOnce(new Error("Provider read failed"));
        renderPage();

        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        await userEvent.setup().click(screen.getByText("More filters", { exact: true }));
        expect(screen.getByRole("status")).toHaveTextContent("Provider options could not be loaded. Date filters are still available.");
        expect(screen.getByLabelText("From date (UTC)")).toBeVisible();
        expect(screen.queryByText("Action history unavailable")).not.toBeInTheDocument();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledOnce();
    });

    it("renders sanitized action history details", async () => {
        renderPage();

        expect(
            await screen.findByText("Unload Model"),
        ).toBeInTheDocument();
        const completionTime = screen.getByText(new Date("2026-07-25T17:00:01Z").toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
        expect(completionTime.closest("time")).toHaveAttribute("datetime", "2026-07-25T17:00:01Z");
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
            screen.getByText("Operator confirmed"),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("link", {
                name: "View action details",
            }),
        ).toHaveAttribute(
            "href",
            "/operations/actions/audit-1",
        );
    });

    it("does not expose malformed history timestamps as verified times", async () => {
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
                parameter_names: [],
                request_id: "request-123",
                started_at: "2026-07-25T17:00:00Z",
                completed_at: "2026-02-30T17:00:01Z",
                duration_ms: 12.5,
            }],
            total: 1,
            offset: 0,
            limit: 25,
            has_more: false,
        });
        renderPage();

        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        const unavailableTime = screen.getByText("Time unavailable");
        expect(unavailableTime.closest("time")).toBeNull();
    });

    it("requests failed actions when filtered", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Unload Model");
        const filters = screen.getByRole("group", { name: "Filter action history" });
        expect(within(filters).getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
        expect(within(filters).getByRole("button", { name: "Succeeded" })).toHaveAttribute("aria-pressed", "false");
        expect(within(filters).getByRole("button", { name: "Failed" })).toHaveAttribute("aria-pressed", "false");
        await user.click(
            screen.getByRole("button", { name: "Failed" }),
        );
        expect(within(filters).getByRole("button", { name: "Failed" })).toHaveAttribute("aria-pressed", "true");
        expect(within(filters).getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "false");

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
        const historyAlert = await screen.findByRole("alert");
        expect(historyAlert).toHaveTextContent("Atlas couldn’t load action history. Refresh history to try again; this won’t run any actions.");
        const technicalDetails = within(historyAlert).getByText("Why action history couldn't load").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        expect(within(historyAlert).queryByText("Filtered history unavailable")).not.toBeVisible();
        fireEvent.click(within(technicalDetails as HTMLElement).getByText("Why action history couldn't load"));
        expect(within(historyAlert).getByText("Filtered history unavailable")).toBeVisible();
        expect(screen.queryByText("Unload Model")).not.toBeInTheDocument();
        expect(screen.getByText("Atlas is keeping 1 of 5000 entries for up to 90 days.")).toBeInTheDocument();
        fireEvent.click(screen.getByText("More filters", { exact: true }));
        expect(within(screen.getByLabelText("Provider")).getByRole("option", { name: "Ollama" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Delete expired entries" })).toBeDisabled();
        expect(screen.getByRole("status")).toHaveTextContent("Expired entries cannot be deleted until action history loads successfully.");
        await user.click(screen.getByRole("button", { name: "Refresh history" }));
        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(3);
        expect(mockedExportProviderActionHistory).not.toHaveBeenCalled();
        expect(mockedPruneProviderActionHistory).not.toHaveBeenCalled();
    });

    it("shows the empty-history state when no filters are applied", async () => {
        mockedGetProviderActionHistory.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 25, has_more: false });
        renderPage();

        expect(await screen.findByText("No actions recorded")).toBeVisible();
        expect(screen.getByText("Atlas has not recorded any actions yet.")).toBeVisible();
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
        await screen.findByText("No matching actions");
        await act(async () => { resolveRead(originalPage); });
        expect(screen.queryByText("Unload Model")).not.toBeInTheDocument();
        expect(screen.queryByRole("navigation", { name: "Action history pagination" })).not.toBeInTheDocument();
        expect(screen.getByText("No matching actions")).toBeVisible();
        expect(screen.getByText("No actions match the filters you applied. Change or clear filters to see other history.")).toBeVisible();
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

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Action history could not be exported. Try exporting again.");
        const technicalDetails = within(alert).getByText("Why the export failed").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        expect(within(technicalDetails as HTMLElement).getByText("Export failed")).not.toBeVisible();
        expect(screen.getByText("Unload Model")).toBeInTheDocument();
        expect(screen.getByText("Atlas is keeping 1 of 5000 entries for up to 90 days.")).toBeInTheDocument();
        expect(screen.queryByText("Action history unavailable")).not.toBeInTheDocument();
    });

    it("distinguishes export and history read errors when both are visible", async () => {
        const user = userEvent.setup();
        mockedExportProviderActionHistory.mockRejectedValueOnce(new Error("Export failed"));
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export or delete history"));
        await user.click(screen.getByRole("button", { name: "Export JSON" }));
        const exportAlert = await screen.findByRole("alert");
        expect(within(exportAlert).getByText("Why the export failed")).toBeInTheDocument();

        mockedGetProviderActionHistory.mockRejectedValueOnce(new Error("History refresh failed"));
        await user.click(screen.getByRole("button", { name: "Refresh history" }));
        const historyTitle = await screen.findByText("Action history unavailable");
        const historyAlert = historyTitle.closest("[role='alert']");

        expect(historyAlert).not.toBeNull();
        expect(within(historyAlert as HTMLElement).getByText("Why action history couldn't load")).toBeInTheDocument();
        expect(within(exportAlert).queryByText("Why action history couldn't load")).not.toBeInTheDocument();
        expect(within(historyAlert as HTMLElement).queryByText("Why the export failed")).not.toBeInTheDocument();
        expect(within(exportAlert).getByText("Export failed")).not.toBeVisible();
        expect(within(historyAlert as HTMLElement).getByText("History refresh failed")).not.toBeVisible();
    });

    it("confirms and prunes expired history", async () => {
        const user = userEvent.setup();
        vi.spyOn(window, "confirm").mockReturnValue(true);
        renderPage();

        await screen.findByText("Unload Model");
        fireEvent.click(screen.getByText("Export or delete history"));
        expect(screen.getByText("Removing expired records only clears the history. It does not undo provider actions.")).toBeVisible();
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

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Atlas could not confirm whether expired entries were deleted. Refresh history before trying again.");
        const technicalDetails = within(alert).getByText("Why deletion could not be confirmed").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        expect(within(technicalDetails as HTMLElement).getByText("Delete failed")).not.toBeVisible();
        expect(screen.getByText("Unload Model")).toBeInTheDocument();
        expect(screen.getByText("Atlas is keeping 1 of 5000 entries for up to 90 days.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Delete expired entries" })).toBeDisabled();
        expect(screen.getByRole("status")).toHaveTextContent("Deleting expired entries is paused until Refresh history confirms the latest records and retention details.");
        expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(1);
        await user.click(screen.getByRole("button", { name: "Refresh history" }));
        expect(await screen.findByText("Unload Model")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Delete expired entries" })).toBeEnabled();
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(2));
        expect(mockedPruneProviderActionHistory).toHaveBeenCalledOnce();
        expect(screen.queryByText("Action history unavailable")).not.toBeInTheDocument();
    });

    it("filters by provider and UTC date range", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Unload Model");
        expect(screen.getByText("Completed actions and their results. Times use your local time.")).toBeVisible();
        const moreFilters = screen.getByText("More filters", { exact: true });
        expect(moreFilters.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByLabelText("From date (UTC)")).not.toBeVisible();
        await user.click(moreFilters);
        expect(screen.getByText("Date filters use full UTC days; action times use your local time.", { exact: true })).toBeVisible();
        expect(screen.getByLabelText("From date (UTC)")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        expect(screen.getByLabelText("To date (UTC)")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        await user.selectOptions(
            screen.getByLabelText("Provider"),
            "ollama",
        );
        await user.type(
            screen.getByLabelText("From date (UTC)"),
            "2026-07-01",
        );
        await user.type(
            screen.getByLabelText("To date (UTC)"),
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
        expect(screen.getByLabelText("From date (UTC)")).toHaveValue("");
        expect(screen.getByLabelText("To date (UTC)")).toHaveValue("");
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
        expect(screen.getByText("Search text has changed. Select Search to update the results.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
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
        expect(screen.queryByText("Search text has changed. Select Search to update the results.")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();

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

        await user.type(screen.getByLabelText("Action or request ID"), "-new");
        expect(screen.getByText("Search text has changed. Select Search to update the results.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
        await user.click(screen.getByRole("button", { name: "Search" }));
        await waitFor(() =>
            expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 0,
                search: "request-123-new",
                status: undefined,
                providerId: undefined,
                completedFrom: undefined,
                completedTo: undefined,
            }),
        );
        expect(screen.queryByText("Search text has changed. Select Search to update the results.")).not.toBeInTheDocument();
    });
});
