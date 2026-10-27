import {
    act,
    render,
    screen,
    waitFor,
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

    it.each(["2099-10-27T12:00:00Z", "2099-10-27T12:00:00+02:00"])("keeps a future completion time unknown without hiding the reported result: %s", async completed_at => {
        const response = await mockedGetProviderActionHistory({});
        mockedGetProviderActionHistory.mockClear();
        mockedGetProviderActionHistory.mockResolvedValue({ ...response, items: response.items.map(entry => ({ ...entry, completed_at })) });
        renderPage();
        expect(await screen.findByText("Unknown time")).toBeVisible();
        expect(screen.getByText("Model unloaded.")).toBeVisible();
        expect(screen.getByRole("link", { name: "View audit details" })).toHaveAttribute("href", "/operations/actions/audit-1");
        expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(1);
    });

    it("renders sanitized action audit details", async () => {
        renderPage();

        expect(
            await screen.findByText("Unload Model"),
        ).toBeInTheDocument();
        expect(screen.getAllByText("Ollama")).toHaveLength(3);
        expect(screen.getByText("model")).toBeInTheDocument();
        expect(
            screen.getByText("request-123"),
        ).toBeInTheDocument();
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

    it("hides previous results and disables cleanup while a filtered read fails", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        let rejectRead!: (reason: Error) => void;
        mockedGetProviderActionHistory.mockReturnValueOnce(new Promise((_, reject) => { rejectRead = reject; }));
        await user.click(screen.getByRole("button", { name: "Failed" }));
        await waitFor(() => expect(screen.queryByText("Unload Model")).not.toBeInTheDocument());
        expect(screen.getByRole("button", { name: "Prune expired" })).toBeDisabled();
        expect(screen.queryByRole("navigation", { name: "Action history pagination" })).not.toBeInTheDocument();
        await act(async () => { rejectRead(new Error("Filtered history unavailable")); });
        expect(await screen.findByRole("alert")).toHaveTextContent("Filtered history unavailable");
        expect(screen.queryByText("Unload Model")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Prune expired" })).toBeDisabled();
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
        expect(screen.getByText("No matching actions")).toBeInTheDocument();
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
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
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

    it("confirms and prunes expired history", async () => {
        const user = userEvent.setup();
        vi.spyOn(window, "confirm").mockReturnValue(true);
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
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
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Search and filters", { exact: true }));
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
    });

    it("searches and pages through audit results", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Search and filters", { exact: true }));
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
    it("puts readable records before tools and keeps extra controls closed", async () => {
        const user = userEvent.setup();
        renderPage();
        const action = await screen.findByText("Unload Model");
        const tools = screen.getByText("Export and cleanup", { exact: true });
        expect(action.compareDocumentPosition(tools) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(screen.getByText("request-123")).not.toBeVisible();
        expect(screen.getByRole("button", { name: "Prune expired" })).not.toBeVisible();
        expect(screen.getByRole("button", { name: "Run Doctor" })).not.toBeVisible();
        for (const label of ["Search and filters", "Technical details", "Export and cleanup", "Check Atlas health"]) {
            const summary = screen.getByText(label, { exact: true });
            expect(summary.closest("details")).not.toHaveAttribute("open");
            await user.click(summary);
        }
        expect(screen.getByText("Dates use UTC. Results below show the current search.")).toBeVisible();
        expect(screen.getByText("request-123")).toBeVisible();
        expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(1);
        expect(mockedExportProviderActionHistory).not.toHaveBeenCalled();
        expect(mockedPruneProviderActionHistory).not.toHaveBeenCalled();
    });

    it("shows records while both optional reads remain pending", async () => {
        mockedGetProviderActionHistorySummary.mockReturnValueOnce(new Promise(() => {}));
        mockedGetProviderActionHistoryProviders.mockReturnValueOnce(new Promise(() => {}));
        const user = userEvent.setup();
        const view = renderPage();
        expect(await screen.findByText("Unload Model")).toBeVisible();
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        expect(screen.getByText("Loading retention policy...")).toBeVisible();
        expect(screen.getByRole("button", { name: "Prune expired" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Refresh history" })).toBeEnabled();
        view.unmount();
    });

    it("keeps records readable when retention fails and recovers on refresh", async () => {
        mockedGetProviderActionHistorySummary.mockRejectedValueOnce(new Error("private retention exception"));
        const user = userEvent.setup();
        renderPage();
        expect(await screen.findByText("Unload Model")).toBeVisible();
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        expect(screen.getByText("Retention policy unavailable.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Prune expired" })).toBeDisabled();
        expect(screen.queryByText("private retention exception")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Refresh history" }));
        await waitFor(() => expect(screen.getByRole("button", { name: "Prune expired" })).toBeEnabled());
        expect(screen.getByText("Unload Model")).toBeVisible();
        expect(mockedPruneProviderActionHistory).not.toHaveBeenCalled();
    });

    it("retains the selected provider if the next choices lookup fails", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Search and filters", { exact: true }));
        mockedGetProviderActionHistoryProviders.mockRejectedValueOnce(new Error("private provider exception"));
        await user.selectOptions(screen.getByLabelText("Provider"), "ollama");
        expect(await screen.findByText(/Provider choices are unavailable/)).toBeVisible();
        expect(screen.getByLabelText("Provider")).toHaveValue("ollama");
        expect(screen.getByRole("option", { name: "Selected provider (ollama)" })).toBeInTheDocument();
        expect(screen.getByText("Unload Model")).toBeVisible();
        expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith(expect.objectContaining({ providerId: "ollama" }));
        expect(screen.queryByText("private provider exception")).not.toBeInTheDocument();
    });

    it.each(["resolve", "reject"] as const)("ignores old optional reads that %s after a new filter", async (outcome) => {
        const originalSummary = await mockedGetProviderActionHistorySummary();
        let resolveSummary!: (value: typeof originalSummary) => void;
        let rejectSummary!: (error: Error) => void;
        let resolveProviders!: (value: Awaited<ReturnType<typeof getProviderActionHistoryProviders>>) => void;
        let rejectProviders!: (error: Error) => void;
        mockedGetProviderActionHistorySummary.mockReturnValueOnce(new Promise((resolve, reject) => { resolveSummary = resolve; rejectSummary = reject; }));
        mockedGetProviderActionHistoryProviders.mockReturnValueOnce(new Promise((resolve, reject) => { resolveProviders = resolve; rejectProviders = reject; }));
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByRole("button", { name: "Failed" }));
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(2));
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        await waitFor(() => expect(screen.getByRole("button", { name: "Prune expired" })).toBeEnabled());
        await act(async () => {
            if (outcome === "resolve") {
                resolveSummary({ ...originalSummary, retention_days: 999 });
                resolveProviders([{ id: "foreign", name: "Outdated provider" }]);
            } else {
                rejectSummary(new Error("Old retention failure"));
                rejectProviders(new Error("Old provider failure"));
            }
        });
        expect(screen.getByText("1 of 5000 entries retained for 90 days.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Prune expired" })).toBeEnabled();
        await user.click(screen.getByText("Search and filters", { exact: true }));
        expect(screen.queryByText("Outdated provider")).not.toBeInTheDocument();
        expect(screen.queryByText(/Provider choices are unavailable/)).not.toBeInTheDocument();
    });

    it("does not hide records when an export fails", async () => {
        mockedExportProviderActionHistory.mockRejectedValueOnce(new Error("Export unavailable"));
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        await user.click(screen.getByRole("button", { name: "Export JSON" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Export unavailable");
        expect(screen.getByText("Unload Model")).toBeVisible();
        expect(screen.getByRole("navigation", { name: "Action history pagination" })).toBeVisible();
        expect(screen.queryByText("History unavailable")).not.toBeInTheDocument();
        expect(mockedExportProviderActionHistory).toHaveBeenCalledTimes(1);
    });

    it("does not hide records or retry cleanup after a cleanup failure", async () => {
        mockedPruneProviderActionHistory.mockRejectedValueOnce(new Error("Cleanup unavailable"));
        vi.spyOn(window, "confirm").mockReturnValue(true);
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        await user.click(screen.getByRole("button", { name: "Prune expired" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Cleanup unavailable");
        expect(screen.getByText("Unload Model")).toBeVisible();
        expect(mockedPruneProviderActionHistory).toHaveBeenCalledTimes(1);
        expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(1);
    });

    it("refreshes the current filter when an earlier cleanup completes", async () => {
        let finish!: (value: Awaited<ReturnType<typeof pruneProviderActionHistory>>) => void;
        mockedPruneProviderActionHistory.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
        vi.spyOn(window, "confirm").mockReturnValue(true);
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Export and cleanup", { exact: true }));
        await user.click(screen.getByRole("button", { name: "Prune expired" }));
        await user.click(screen.getByRole("button", { name: "Failed" }));
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(2));
        await act(async () => finish({ deleted_entries: 1, remaining_entries: 0, cutoff: "2026-01-01T00:00:00Z" }));
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(3));
        expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith(expect.objectContaining({ status: "failed", offset: 0 }));
        expect(screen.getByRole("button", { name: "Failed" })).toHaveAttribute("aria-pressed", "true");
        expect(mockedPruneProviderActionHistory).toHaveBeenCalledTimes(1);
    });

    it("distinguishes no matches from no history and offers a working reset", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        mockedGetProviderActionHistory.mockResolvedValueOnce({ items: [], total: 0, limit: 25, offset: 0, has_more: false });
        await user.click(screen.getByRole("button", { name: "Failed" }));
        expect(await screen.findByText("No matching actions")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Show all actions" }));
        expect(await screen.findByText("Unload Model")).toBeVisible();
        expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith(expect.objectContaining({ status: undefined, offset: 0 }));
    });

    it("offers a way back when retention leaves the current page empty", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        mockedGetProviderActionHistory.mockResolvedValueOnce({ items: [], total: 1, limit: 25, offset: 25, has_more: false });
        await user.click(screen.getByRole("button", { name: "Next" }));
        expect(await screen.findByText("No actions on this page")).toBeVisible();
        expect(screen.queryByText("No actions recorded")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Previous page" }));
        expect(await screen.findByText("Unload Model")).toBeVisible();
        expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 0 }));
    });

    it("keeps active hidden filters visible and offers a reset beside readable records", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Unload Model");
        await user.click(screen.getByText("Search and filters", { exact: true }));
        await user.selectOptions(screen.getByLabelText("Provider"), "ollama");
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(2));
        await user.click(screen.getByText("Search and filters", { exact: true }));
        expect(screen.getByLabelText("Provider")).not.toBeVisible();
        expect(screen.getByText("Filters are active.")).toBeVisible();
        expect(screen.getByText("Unload Model")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Show all actions" }));
        await waitFor(() => expect(mockedGetProviderActionHistory).toHaveBeenCalledTimes(3));
        expect(mockedGetProviderActionHistory).toHaveBeenLastCalledWith(expect.objectContaining({ providerId: undefined }));
        expect(screen.queryByText("Filters are active.")).not.toBeInTheDocument();
    });

});
