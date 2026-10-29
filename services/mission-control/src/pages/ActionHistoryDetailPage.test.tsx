import {
    act,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
    createMemoryRouter,
    RouterProvider,
    MemoryRouter,
    Route,
    Routes,
} from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import type { ProviderActionAuditEntry } from "../types/actionHistory";

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

function auditEntry(id = "audit-1"): ProviderActionAuditEntry {
    return {
        id, provider_id: "ollama", provider_name: "Ollama", action_id: "unload-model",
        action_label: "Unload Model", status: "succeeded", success: true,
        message: "Model unloaded.", confirmed: true, destructive: false,
        parameter_names: ["model"], request_id: "request-123",
        started_at: "2026-07-25T17:00:00Z", completed_at: "2026-07-25T17:00:01Z", duration_ms: 12.5,
    };
}

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
        mockedGetProviderActionHistoryEntry.mockResolvedValue(auditEntry());
    });

    it("refuses an action record for a different audit link", async () => {
        mockedGetProviderActionHistoryEntry.mockResolvedValue(auditEntry("other"));
        renderPage();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("This action history record does not match this link.");
        expect(alert).not.toHaveTextContent("Try again.");
        expect(within(alert).getByRole("button", { name: "Try again" })).toBeInTheDocument();
        expect(screen.queryByText("Model unloaded.")).not.toBeInTheDocument();
    });

    it("loads once under Strict Mode and retries an unavailable read", async () => {
        mockedGetProviderActionHistoryEntry.mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(auditEntry());
        render(<StrictMode><MemoryRouter initialEntries={["/operations/actions/audit-1"]}><Routes>
            <Route path="/operations/actions/:auditId" element={<ActionHistoryDetailPage />} />
        </Routes></MemoryRouter></StrictMode>);
        const user = userEvent.setup();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Atlas couldn’t load these action details. Try again to reload them; this won’t repeat the action.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        expect(within(technicalDetails as HTMLElement).getByText("Unavailable")).not.toBeVisible();
        await user.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLElement).getByText("Unavailable")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Try again" }));
        expect(await screen.findByText("Model unloaded.")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedGetProviderActionHistoryEntry).toHaveBeenCalledTimes(2);
    });

    it("clears the old record and handles a late previous read after navigation", async () => {
        let resolveNext!: (value: ProviderActionAuditEntry) => void;
        let resolveCurrent!: (value: ProviderActionAuditEntry) => void;
        mockedGetProviderActionHistoryEntry.mockResolvedValueOnce(auditEntry())
            .mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }))
            .mockImplementationOnce(() => new Promise((resolve) => { resolveCurrent = resolve; }));
        const router = createMemoryRouter([{ path: "/operations/actions/:auditId", element: <ActionHistoryDetailPage /> }], { initialEntries: ["/operations/actions/audit-1"] });
        render(<RouterProvider router={router} />);
        await screen.findByText("Model unloaded.");
        await act(() => router.navigate("/operations/actions/audit-2"));
        expect(screen.queryByText("Model unloaded.")).not.toBeInTheDocument();
        expect(screen.getByText("Loading action details…")).toBeInTheDocument();
        await waitFor(() => expect(mockedGetProviderActionHistoryEntry).toHaveBeenCalledWith("audit-2"));
        await act(() => router.navigate("/operations/actions/audit-3"));
        await waitFor(() => expect(mockedGetProviderActionHistoryEntry).toHaveBeenCalledWith("audit-3"));
        await act(async () => resolveCurrent({ ...auditEntry("audit-3"), message: "Current action result" }));
        await act(async () => resolveNext(auditEntry("audit-2")));
        expect(screen.getByText("Current action result")).toBeInTheDocument();
        expect(screen.queryByText("Model unloaded.")).not.toBeInTheDocument();
    });

    it("shows the action outcome first and keeps technical fields collapsed", async () => {
        const user = userEvent.setup();
        mockedGetProviderActionHistoryEntry.mockResolvedValue({ ...auditEntry(), destructive: true });
        renderPage();

        expect(await screen.findByRole("heading", { name: "Action details" })).toBeVisible();
        expect(
            await screen.findByRole("heading", {
                name: "Unload Model",
            }),
        ).toBeInTheDocument();
        expect(
            mockedGetProviderActionHistoryEntry,
        ).toHaveBeenCalledWith("audit-1");
        expect(screen.getByText("Succeeded")).toBeInTheDocument();
        expect(screen.getByText("Operator confirmed")).toBeInTheDocument();
        expect(screen.getByText("Destructive action")).toBeInTheDocument();
        expect(screen.getByText("Model unloaded.")).toBeInTheDocument();
        expect(screen.getByText("Times below use your browser’s local time.")).toBeInTheDocument();
        expect(screen.getByText("Ollama")).toBeInTheDocument();
        const completedTime = screen.getByText((_, element) =>
            element?.tagName === "TIME" && element.getAttribute("datetime") === "2026-07-25T17:00:01Z",
        );
        expect(completedTime).toHaveTextContent(new Date("2026-07-25T17:00:01Z").toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
        const startedTime = screen.getByText((_, element) =>
            element?.tagName === "TIME" && element.getAttribute("datetime") === "2026-07-25T17:00:00Z",
        );
        expect(startedTime).toHaveTextContent(new Date("2026-07-25T17:00:00Z").toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        await user.click(screen.getByText("Technical details"));
        expect(technicalDetails).toHaveAttribute("open");
        expect(screen.getByText("audit-1")).toBeInTheDocument();
        expect(screen.getByText("request-123")).toBeInTheDocument();
        expect(
            screen.getByRole("link", {
                name: "← Back to action history",
            }),
        ).toHaveAttribute("href", "/operations");
    });

    it("does not normalize an impossible action timestamp into a real date", async () => {
        mockedGetProviderActionHistoryEntry.mockResolvedValue({
            ...auditEntry(),
            completed_at: "2026-02-30T17:00:01Z",
        });
        renderPage();

        expect(await screen.findByText("Model unloaded.")).toBeInTheDocument();
        expect(screen.getByText("Completed Time unavailable")).toBeInTheDocument();
        expect(screen.queryByText((_, element) =>
            element?.tagName === "TIME" && element.getAttribute("datetime") === "2026-02-30T17:00:01Z",
        )).not.toBeInTheDocument();
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
            await screen.findByText("Action history link copied."),
        ).toBeInTheDocument();
    });

    it("keeps missing-entry service details out of the main error message", async () => {
        mockedGetProviderActionHistoryEntry.mockRejectedValue(
            new Error("Action history entry not found."),
        );
        renderPage("/operations/actions/missing-entry");

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Atlas couldn’t load these action details. Try again to reload them; this won’t repeat the action.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        expect(within(technicalDetails as HTMLElement).getByText("Action history entry not found.")).not.toBeVisible();
        await waitFor(() =>
            expect(
                screen.queryByText("Loading action details…"),
            ).not.toBeInTheDocument(),
        );
    });
});
