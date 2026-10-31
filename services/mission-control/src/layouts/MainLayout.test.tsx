import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "../api/atlas";
import { primaryNavigationItems } from "../app/navigation";
import { MainLayout } from "./MainLayout";

vi.mock("../api/atlas", () => ({
    atlas: {
        get: vi.fn(),
    },
}));

const navigationLabels = primaryNavigationItems.map((item) => item.label);

function renderAt(
    path = "/",
    page = <p>Dashboard content</p>,
) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/" element={<MainLayout />}>
                    <Route index element={page} />
                    <Route path="operations/actions/:auditId" element={<p>Audit detail</p>} />
                    {primaryNavigationItems.filter(
                        (item) => item.path !== "/",
                    ).map((item) => (
                        <Route
                            key={item.path}
                            path={item.path.slice(1)}
                            element={<p>{`${item.label} content`}</p>}
                        />
                    ))}
                    <Route path="*" element={<p>Not found</p>} />
                </Route>
            </Routes>
        </MemoryRouter>,
    );
}

describe("MainLayout", () => {
    let desktopChange: (() => void) | undefined;
    let desktop = false;
    afterEach(() => vi.unstubAllGlobals());
    beforeEach(() => {
        desktop = false;
        vi.stubGlobal("matchMedia", vi.fn(() => ({
            get matches() { return desktop; },
            addEventListener: (_: string, callback: () => void) => { desktopChange = callback; },
            removeEventListener: vi.fn(),
        })));
        vi.mocked(atlas.get).mockResolvedValue({
            data: {
                release: "Foundry",
            },
        });
    });

    describe("desktop shell rendering", () => {
        it("lets keyboard users skip navigation without changing the route", async () => {
            const user = userEvent.setup();
            renderAt();
            await screen.findByText("Core build: Foundry");
            await user.tab();
            const skip = screen.getByRole("link", { name: "Skip to page content" });
            expect(skip).toHaveFocus();
            await user.keyboard("{Enter}");
            expect(screen.getByText("Dashboard content").closest("#mc-page-content")).toHaveFocus();
        });

        it("renders branding, Core status, and its configured build label", async () => {
            renderAt();

            expect(screen.getAllByText("ATLAS").length).toBeGreaterThan(0);
            expect(screen.getAllByText("Mission Control", { exact: true }).length).toBeGreaterThan(0);
            expect(screen.getByText("Dashboard content")).toBeInTheDocument();
            expect(await screen.findByText("Atlas Core API connected")).toBeInTheDocument();
            expect(screen.getByText("Atlas Core API", { exact: true })).toBeInTheDocument();
            expect(screen.getByText("Core build: Foundry")).toBeInTheDocument();
            expect(atlas.get).toHaveBeenCalledWith("");
        });

        it("shows the full Core build identifier instead of clipping it", async () => {
            const build = "browser-regression-build-2026-10-31-0123456789abcdef";
            vi.mocked(atlas.get).mockResolvedValueOnce({ data: { release: build } });
            renderAt();

            const label = await screen.findByText(`Core build: ${build}`);
            expect(label).toHaveClass("break-words");
            expect(label).not.toHaveClass("truncate");
            expect(label).toHaveAttribute("title", build);
        });

        it("uses the MC 2.0 shared shell and navigation primitives", async () => {
            const { container } = renderAt();

            expect(container.querySelector(".mc-app-shell")).not.toBeNull();
            expect(container.querySelector(".mc-shell-header")).not.toBeNull();
            expect(container.querySelector(".mc-main-content")).not.toBeNull();
            expect(
                container.querySelector(".mc-focusable"),
            ).not.toBeNull();
            await screen.findByText("Core build: Foundry");
            // The shared status primitive shows API availability.
            expect(container.querySelector(".mc-status-badge")).not.toBeNull();
            expect(
                container.querySelector(".mc-status-badge")?.getAttribute(
                    "data-mc-status",
                ),
            ).toBe("success");
        });
    });

    describe("desktop navigation", () => {
        it("renders every working destination with its existing route", async () => {
            renderAt();

            const nav = screen.getAllByRole("navigation", { name: "Primary" })[0];
            for (const item of primaryNavigationItems) {
                const link = within(nav).getByRole("link", { name: item.label });
                expect(link).toHaveAttribute("href", item.path);
            }
            // The root link is exact so nested routes do not activate it.
            expect(
                within(nav).getByRole("link", { name: "Overview" }),
            ).toHaveAttribute("aria-current", "page");
        });

        it("leaves unavailable future destinations out of the menu", () => {
            renderAt();

            const nav = screen.getAllByRole("navigation", { name: "Primary" })[0];
            for (const label of ["Knowledge", "Developer", "Settings"]) {
                expect(within(nav).queryByText(label)).not.toBeInTheDocument();
            }
            expect(within(nav).queryByText("Soon")).not.toBeInTheDocument();
        });
    });

    describe("active route indication", () => {
        it.each([
            ["", ["/"]],
            ["/operations", ["/operations"]],
            ["/operations/history", ["/operations/history"]],
            ["/operations/request", ["/operations/request"]],
            ["/operations/actions/audit-1", ["/operations"]],
            ["/discovery", ["/discovery"]],
            ["/execution-candidates", ["/execution-candidates"]],
            ["/workflows", ["/workflows"]],
            ["/forge", ["/forge"]],
        ])(
            "marks the active destination at %s",
            (initialPath, expectedActiveHrefs) => {
                renderAt(initialPath);

                const links = screen
                    .getAllByRole("navigation", { name: "Primary" })
                    .flatMap((nav) =>
                        Array.from(
                            within(nav).queryAllByRole("link"),
                        ) as unknown as HTMLElement[],
                    );
                const activeHrefs = links
                    .filter((link) => link.getAttribute("aria-current") === "page")
                    .map((link) => link.getAttribute("href"));
                // Only the most specific destination is current. Audit details
                // still belong to Action history, rather than a separate menu.
                expect(activeHrefs).toEqual(expectedActiveHrefs);
            },
        );
    });

    describe("current route context", () => {
        it.each([
            ["/operations", "Action history"],
            ["/operations/actions/audit-1", "Action details"],
            ["/discovery", "Catalog"],
            ["/discovery/items/item-1", "Catalog item details"],
            ["/forge", "Deployment analysis"],
            ["/providers/proxmox", "Provider details"],
            ["/execution-candidates/proposal-1", "Proposal details"],
            ["/workflows/workflow-1", "Workflow details"],
            ["/workflows/workflow-1/audit", "Workflow history"],
            ["/candidate-planning/session-1", "Plan a change"],
            ["/candidate-planning/session-1/workflow", "Workflow setup"],
        ])("surfaces the context label for %s", (initialPath, label) => {
            renderAt(initialPath);

            const context = screen.getByTestId("mc-context");
            expect(context).toHaveAttribute("role", "status");
            expect(context).toHaveTextContent(`Current page: ${label}`);
            expect(document.title).toBe(`${label} | Atlas Mission Control`);
        });

        it("does not repeat the home screen label in the header", () => {
            renderAt("/");

            expect(screen.queryByTestId("mc-context")).not.toBeInTheDocument();
            expect(screen.getAllByText("Mission Control", { exact: true })).toHaveLength(1);
            expect(document.title).toBe("Overview | Atlas Mission Control");
        });

        it("identifies unknown routes as missing pages in the shell and browser title", () => {
            renderAt("/page-that-does-not-exist");

            expect(screen.getByTestId("mc-context")).toHaveTextContent("Current page: Page not found");
            expect(document.title).toBe("Page not found | Atlas Mission Control");
        });

        it("does not mistake an unknown nested route for its parent screen", () => {
            renderAt("/workflows/workflow-1/unknown");

            expect(screen.getByTestId("mc-context")).toHaveTextContent("Current page: Page not found");
            expect(document.title).toBe("Page not found | Atlas Mission Control");
        });
    });

    describe("mobile navigation", () => {
        it("opens from the trigger and closes with the close control", async () => {
            const user = userEvent.setup();
            renderAt();

            expect(screen.queryByRole("dialog")).toBeNull();

            await user.click(screen.getByRole("button", { name: "Open navigation" }));
            expect(screen.getByRole("dialog", { name: "Mission Control navigation" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "Open navigation", hidden: true })).toHaveAttribute(
                "aria-expanded",
                "true",
            );

            await user.click(screen.getByRole("button", { name: "Close navigation" }));
            expect(screen.queryByRole("dialog")).toBeNull();
            expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute(
                "aria-expanded",
                "false",
            );
        });

        it("is keyboard accessible: Escape closes the drawer and restores focus", async () => {
            const user = userEvent.setup();
            renderAt();

            const trigger = screen.getByRole("button", { name: "Open navigation" });
            await user.click(trigger);

            const dialog = screen.getByRole("dialog");
            // Focus moved into the drawer after it opened.
            const firstLink = within(dialog).getByRole("link", { name: "Overview" });
            expect(firstLink).toHaveFocus();

            await user.keyboard("{Escape}");

            expect(screen.queryByRole("dialog")).toBeNull();
            expect(trigger).toHaveFocus();
        });

        it("closes when the backdrop is clicked and keeps focus on the trigger", async () => {
            const user = userEvent.setup();
            renderAt();

            const trigger = screen.getByRole("button", { name: "Open navigation" });
            await user.click(trigger);

            await user.click(screen.getByTestId("mc-mobile-overlay"));

            expect(screen.queryByRole("dialog")).toBeNull();
            expect(trigger).toHaveFocus();
        });

        it("keeps the mobile drawer content in sync with the shared navigation metadata", async () => {
            const user = userEvent.setup();
            renderAt();

            await user.click(screen.getByRole("button", { name: "Open navigation" }));
            const dialog = screen.getByRole("dialog");

            for (const item of primaryNavigationItems) {
                const link = within(dialog).getByRole("link", { name: item.label });
                expect(link).toHaveAttribute("href", item.path);
            }
            expect(within(dialog).queryByText("Soon")).not.toBeInTheDocument();
        });

        it("navigates through the drawer and closes it", async () => {
            const user = userEvent.setup();
            renderAt();

            await user.click(screen.getByRole("button", { name: "Open navigation" }));
            const dialog = screen.getByRole("dialog");
            await user.click(within(dialog).getByRole("link", { name: "Deployment analysis" }));

            expect(screen.queryByRole("dialog")).toBeNull();
            expect(
                screen.getByTestId("mc-context"),
            ).toBeInTheDocument();
            expect(screen.getByTestId("mc-context")).toHaveTextContent("Current page: Deployment analysis");
        });
    });

    it("contains keyboard focus and makes background content inert", async () => {
        const user = userEvent.setup();
        renderAt();
        const trigger = screen.getByRole("button", { name: "Open navigation" });
        trigger.focus();
        await user.keyboard("{Enter}");
        const dialog = screen.getByRole("dialog");
        expect(document.querySelector(".mc-shell-header")).toHaveAttribute("inert");
        const close = within(dialog).getByRole("button", { name: "Close navigation" });
        const last = within(dialog).getByRole("link", { name: "Deployment analysis" });
        close.focus();
        await user.tab({ shift: true });
        expect(last).toHaveFocus();
        await user.tab();
        expect(close).toHaveFocus();
        await user.keyboard("{Escape}");
        expect(trigger).toHaveFocus();
        expect(document.body.style.overflow).toBe("");
    });

    it("closes on desktop resize and releases background scrolling", async () => {
        const user = userEvent.setup();
        renderAt();
        await user.click(screen.getByRole("button", { name: "Open navigation" }));
        expect(document.body.style.overflow).toBe("hidden");
        act(() => { desktop = true; desktopChange?.(); });
        expect(screen.queryByRole("dialog")).toBeNull();
        expect(document.body.style.overflow).toBe("");
    });

    it("closes on history and query changes without reopening on back", async () => {
        const user = userEvent.setup();
        const router = createMemoryRouter([{ path: "*", element: <MainLayout /> }]);
        render(<RouterProvider router={router} />);
        await user.click(screen.getByRole("button", { name: "Open navigation" }));
        await act(() => router.navigate("/?view=next"));
        expect(screen.queryByRole("dialog")).toBeNull();
        await act(() => router.navigate(-1));
        expect(screen.queryByRole("dialog")).toBeNull();
        await act(() => router.navigate(1));
        expect(router.state.location.search).toBe("?view=next");
        expect(screen.queryByRole("dialog")).toBeNull();
    });

    describe("Core connection and release-label states", () => {
        it("shows a safe unavailable state when Atlas Core does not respond", async () => {
            vi.mocked(atlas.get).mockRejectedValue(new Error("boom"));
            renderAt();

            expect(await screen.findByText("Atlas Core API unavailable")).toBeInTheDocument();
            expect(screen.getByText("Core build: Unavailable")).toBeInTheDocument();
            const badges = document.querySelectorAll(".mc-status-badge");
            expect(Array.from(badges).some((badge) => badge.getAttribute("data-mc-status") === "disabled")).toBe(true);
        });

        it.each([undefined, null, "", "   ", 42])("handles invalid release %s", async (release) => {
            vi.mocked(atlas.get).mockResolvedValue({ data: { release } });
            renderAt();

            expect(await screen.findByText("Atlas Core API connected")).toBeInTheDocument();
            expect(screen.getByText("Core build: Not reported")).toBeInTheDocument();
        });
    });

    describe("route preservation", () => {
        it("preserves the exact working destination set", () => {
            expect(navigationLabels).toEqual([
                "Overview",
                "Action history",
                "Maintenance history",
                "Request maintenance",
                "Catalog",
                "Change proposals",
                "Workflows",
                "Deployment analysis",
            ]);
            expect(
                primaryNavigationItems.map((item) => item.path),
            ).toEqual([
                "/",
                "/operations",
                "/operations/history",
                "/operations/request",
                "/discovery",
                "/execution-candidates",
                "/workflows",
                "/forge",
            ]);
        });
    });
});
