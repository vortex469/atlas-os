import {
    act,
    render,
    screen,
    waitFor,
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
        expect(await screen.findByRole("alert")).toHaveTextContent("does not match this audit link");
        expect(screen.queryByText("Model unloaded.")).not.toBeInTheDocument();
    });

    it("loads once under Strict Mode and retries an unavailable read", async () => {
        mockedGetProviderActionHistoryEntry.mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(auditEntry());
        render(<StrictMode><MemoryRouter initialEntries={["/operations/actions/audit-1"]}><Routes>
            <Route path="/operations/actions/:auditId" element={<ActionHistoryDetailPage />} />
        </Routes></MemoryRouter></StrictMode>);
        const user = userEvent.setup();
        await user.click(await screen.findByRole("button", { name: "Try again" }));
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
        expect(screen.getByText("Loading audit details...")).toBeInTheDocument();
        await waitFor(() => expect(mockedGetProviderActionHistoryEntry).toHaveBeenCalledWith("audit-2"));
        await act(() => router.navigate("/operations/actions/audit-3"));
        await waitFor(() => expect(mockedGetProviderActionHistoryEntry).toHaveBeenCalledWith("audit-3"));
        await act(async () => resolveCurrent({ ...auditEntry("audit-3"), message: "Current action result" }));
        await act(async () => resolveNext(auditEntry("audit-2")));
        expect(screen.getByText("Current action result")).toBeInTheDocument();
        expect(screen.queryByText("Model unloaded.")).not.toBeInTheDocument();
    });

    it.each(["2099-10-27T12:00:00Z", "2099-10-27T12:00:00+02:00"])("keeps future audit times unknown while retaining the reported result: %s", async timestamp => {
        mockedGetProviderActionHistoryEntry.mockResolvedValue({ ...auditEntry(), started_at: timestamp, completed_at: timestamp });
        renderPage();
        expect(await screen.findByText("Model unloaded.")).toBeVisible();
        expect(screen.getAllByText("Unknown time")).toHaveLength(3);
        expect(mockedGetProviderActionHistoryEntry).toHaveBeenCalledTimes(1);
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
                name: "← Back to action history",
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
