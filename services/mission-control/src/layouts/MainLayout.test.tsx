import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "../api/atlas";
import {
    disabledNavigationItems,
    primaryNavigationItems,
} from "../app/navigation";
import { MainLayout } from "./MainLayout";

vi.mock("../api/atlas", () => ({
    atlas: {
        get: vi.fn(),
    },
}));

const enabledLabels = primaryNavigationItems.map((item) => item.label);
const disabledLabels = disabledNavigationItems.map((item) => item.label);

function renderAt(
    path = "/",
    page = <p>Dashboard content</p>,
) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/" element={<MainLayout />}>
                    <Route index element={page} />
                    {primaryNavigationItems.filter(
                        (item) => item.path !== "/",
                    ).map((item) => (
                        <Route
                            key={item.path}
                            path={item.path.slice(1)}
                            element={<p>{`${item.label} content`}</p>}
                        />
                    ))}
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
        it("renders branding, the primary content region, and the release", async () => {
            renderAt();

            expect(screen.getAllByText("ATLAS").length).toBeGreaterThan(0);
            expect(screen.getAllByText("Mission Control 2.0").length).toBeGreaterThan(0);
            expect(screen.getByText("Dashboard content")).toBeInTheDocument();
            expect(await screen.findByText("Foundry")).toBeInTheDocument();
            expect(atlas.get).toHaveBeenCalledWith("");
        });

        it("uses the MC 2.0 shared shell and navigation primitives", async () => {
            const { container } = renderAt();

            expect(container.querySelector(".mc-app-shell")).not.toBeNull();
            expect(container.querySelector(".mc-shell-header")).not.toBeNull();
            expect(container.querySelector(".mc-main-content")).not.toBeNull();
            expect(
                container.querySelector(".mc-focusable"),
            ).not.toBeNull();
            await screen.findByText("Foundry");
            // StatusBadge is the Task 3 shared primitive for the release area.
            expect(container.querySelector(".mc-status-badge")).not.toBeNull();
            expect(
                container.querySelector(".mc-status-badge")?.getAttribute(
                    "data-mc-status",
                ),
            ).toBe("neutral");
        });
    });

    describe("desktop navigation", () => {
        it("renders every enabled destination with its existing route", async () => {
            renderAt();

            const nav = screen.getAllByRole("navigation", { name: "Primary" })[0];
            for (const item of primaryNavigationItems) {
                const link = within(nav).getByRole("link", { name: item.label });
                expect(link).toHaveAttribute("href", item.path);
            }
            // The root link is exact so nested routes do not activate it.
            expect(
                within(nav).getByRole("link", { name: "Mission Control" }),
            ).toHaveAttribute("aria-current", "page");
        });

        it("keeps disabled future destinations visible but inert", () => {
            renderAt();

            for (const label of disabledLabels) {
                const placeholder = screen.getByText(label);
                expect(placeholder.closest("a")).toBeNull();
                expect(placeholder.closest("li")).toHaveClass("mc-disabled");
                expect(within(placeholder.closest("li")!).getByText("Soon")).toBeInTheDocument();
            }
            expect(screen.queryByRole("link", { name: "Knowledge" })).toBeNull();
            expect(screen.queryByRole("link", { name: "Developer" })).toBeNull();
            expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
        });
    });

    describe("active route indication", () => {
        it.each([
            ["", ["/"]],
            ["/operations", ["/operations"]],
            ["/operations/history", ["/operations", "/operations/history"]],
            ["/operations/request", ["/operations", "/operations/request"]],
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
                // Parent sections stay active on child routes (NavLink
                // prefix matching); the leaf destination is always active.
                expect(activeHrefs).toEqual(expectedActiveHrefs);
            },
        );
    });

    describe("current route context", () => {
        it.each([
            ["/", "Mission Control"],
            ["/operations", "Operations"],
            ["/discovery", "Discovery"],
            ["/forge", "Forge"],
        ])("surfaces the context label for %s", (initialPath, label) => {
            renderAt(initialPath);

            const context = screen.getByLabelText(`Current page: ${label}`);
            expect(context).toHaveTextContent(label);
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
            const firstLink = within(dialog).getByRole("link", { name: "Mission Control" });
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
            for (const label of disabledLabels) {
                expect(within(dialog).queryByRole("link", { name: label })).toBeNull();
            }
        });

        it("navigates through the drawer and closes it", async () => {
            const user = userEvent.setup();
            renderAt();

            await user.click(screen.getByRole("button", { name: "Open navigation" }));
            const dialog = screen.getByRole("dialog");
            await user.click(within(dialog).getByRole("link", { name: "Forge" }));

            expect(screen.queryByRole("dialog")).toBeNull();
            expect(
                screen.getByLabelText("Current page: Forge"),
            ).toBeInTheDocument();
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
        const last = within(dialog).getByRole("link", { name: "Forge" });
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

    describe("release unavailable fallback", () => {
        it("shows a safe unavailable state when Atlas Core does not respond", async () => {
            vi.mocked(atlas.get).mockRejectedValue(new Error("boom"));
            renderAt();

            expect(await screen.findByText("Release unavailable")).toBeInTheDocument();
            expect(screen.getAllByText("Release unavailable").length).toBeGreaterThan(0);
            // The release badge degrades to the Task 3 unavailable treatment.
            const badges = document.querySelectorAll(".mc-status-badge");
            expect(Array.from(badges).some((badge) => badge.getAttribute("data-mc-status") === "disabled")).toBe(true);
        });

        it.each([undefined, null, "", "   ", 42])("handles invalid release %s", async (release) => {
            vi.mocked(atlas.get).mockResolvedValue({ data: { release } });
            renderAt();

            expect(await screen.findByText("Release unavailable")).toBeInTheDocument();
        });
    });

    describe("route preservation", () => {
        it("preserves the exact enabled destination set", () => {
            expect(enabledLabels).toEqual([
                "Mission Control",
                "Operations",
                "Operational History",
                "Maintenance",
                "Discovery",
                "Execution Candidates",
                "Workflows",
                "Forge",
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
