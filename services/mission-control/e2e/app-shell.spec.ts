import { expect, test } from "./mission-control-fixtures";

test("Mission Control application shell renders with primary navigation", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Mission Control", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Mission Control 2.0", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("main", { name: "Overview" })).toBeVisible();
    await expect(page.getByText("Core build: browser-regression-baseline", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Overview", exact: true })).toBeVisible();
    await expect(page).toHaveTitle("Overview | Atlas Mission Control");

    await expect(page.getByRole("link", { name: "Overview", exact: true })).toHaveAttribute("href", "/");
    await expect(page.getByRole("link", { name: "Action history", exact: true })).toHaveAttribute("href", "/operations");
    await expect(page.getByRole("link", { name: "Maintenance history", exact: true })).toHaveAttribute("href", "/operations/history");
    await expect(page.getByRole("link", { name: "Request maintenance", exact: true })).toHaveAttribute("href", "/operations/request");
    await expect(page.getByRole("link", { name: "Catalog", exact: true })).toHaveAttribute("href", "/discovery");
    await expect(page.getByRole("link", { name: "Change proposals", exact: true })).toHaveAttribute("href", "/execution-candidates");
    await expect(page.getByRole("link", { name: "Workflows", exact: true })).toHaveAttribute("href", "/workflows");
    await expect(page.getByRole("link", { name: "Deployment analysis", exact: true })).toHaveAttribute("href", "/forge");

    const navigation = page.getByRole("navigation", { name: "Primary" }).first();
    for (const unavailable of ["Knowledge", "Developer", "Settings", "Soon"]) {
        await expect(navigation.getByText(unavailable)).toHaveCount(0);
    }
});

for (const width of [390, 1280]) {
    test(`long Core build identifiers wrap instead of disappearing at ${width}px`, async ({ page }) => {
        const build = "browser-regression-build-2026-10-31-0123456789abcdef";
        await page.setViewportSize({ width, height: 800 });
        await page.route("**/api/v1", (route) => route.fulfill({ json: { release: build } }));
        await page.goto("/");

        const label = width < 1024
            ? page.getByRole("dialog", { name: "Mission Control navigation" }).getByText(`Core build: ${build}`, { exact: true })
            : page.getByText(`Core build: ${build}`, { exact: true });
        if (width < 1024) await page.getByRole("button", { name: "Open navigation" }).click();
        await expect(label).toBeVisible();
        await expect(label).toHaveCSS("overflow-wrap", "break-word");
        await expect(label).toHaveAttribute("title", build);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("Mission Control dashboard loads from controlled Core and Agent responses", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Needs attention" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Update Compose Stack" })).toBeVisible();
    await expect(page.getByText("Action needed: Review the change. If approved, choose Run approved change.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Review workflows →", exact: true })).toHaveAttribute("href", "/workflows");
    await expect(page.getByRole("heading", { name: "Agent details" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent provider actions" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Providers" })).toBeVisible();
    await expect(page.getByText("Proxmox").first()).toBeVisible();
});

test("provider check details open from the keyboard and show local time", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto("/providers/proxmox");

    const disclosure = page.getByText("Check details", { exact: true });
    await expect(disclosure).toBeVisible();
    await disclosure.focus();
    await expect(disclosure).toBeFocused();
    await page.keyboard.press("Enter");

    const details = page.getByRole("list", { name: "Provider check details" });
    await expect(details).toBeVisible();
    await expect(details.locator("time")).toHaveAttribute(
        "datetime",
        "2026-09-06T12:00:00.000Z",
    );
    await expect(details).toContainText("local time");
});

test("provider initial load announces which details are loading", async ({ page }) => {
    let releaseProviderRead!: () => void;
    const providerRead = new Promise<void>((resolve) => { releaseProviderRead = resolve; });
    await page.route("**/api/v1/providers", async (route) => {
        await providerRead;
        await route.fallback();
    });
    await page.goto("/providers/proxmox");

    await expect(page.getByRole("status").getByText("Loading provider details…", { exact: true })).toBeVisible();
    await expect(page.getByText("Connecting...", { exact: true })).toHaveCount(0);
    releaseProviderRead();
    await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
});

test("catalog retry keeps the selected search filters", async ({ page, rejectedMutationRequests }) => {
    let searchAttempts = 0;
    await page.route("**/api/v1/discovery/search**", (route) => {
        searchAttempts += 1;
        return searchAttempts === 1
            ? route.fulfill({ status: 503, json: { detail: "PRIVATE_BACKEND_DETAIL" } })
            : route.fulfill({ json: { results: [], total: 0, offset: 0, has_more: false } });
    });
    await page.goto("/discovery");
    const search = page.getByRole("searchbox", { name: "Keyword search" });
    await search.fill("frigate");
    await page.getByRole("button", { name: "Search", exact: true }).click();

    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Atlas couldn't load these results. Your search filters are still selected.");
    await expect(alert).not.toContainText("PRIVATE_BACKEND_DETAIL");
    await expect(alert.getByRole("button", { name: "Retry search" })).toBeVisible();
    await expect(page.getByText("Select Retry search above to try again.", { exact: true })).toBeVisible();
    await alert.getByRole("button", { name: "Retry search" }).click();

    await expect(alert).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Search results", exact: true })).toBeVisible();
    await expect(search).toHaveValue("frigate");
    await expect(page.getByText("No items matched these filters.", { exact: true })).toBeVisible();
    expect(searchAttempts).toBe(2);
    expect(rejectedMutationRequests).toEqual([]);
});

test.describe("Mobile navigation", () => {
    test.use({
        viewport: { width: 320, height: 844 },
    });

    test("mobile navigation opens, closes, and stays reachable at narrow widths", async ({ page }) => {
        await page.goto("/");

        await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
        await expect(page.getByRole("dialog")).toHaveCount(0);

        await page.getByRole("button", { name: "Open navigation" }).click();

        const dialog = page.getByRole("dialog", { name: "Mission Control navigation" });
        await expect(dialog).toBeVisible();
        for (const label of [
            "Overview",
            "Action history",
            "Maintenance history",
            "Request maintenance",
            "Catalog",
            "Change proposals",
            "Workflows",
            "Deployment analysis",
        ]) {
            await expect(dialog.getByRole("link", { name: label, exact: true })).toBeVisible();
        }

        await page.getByRole("button", { name: "Close navigation" }).click();
        await expect(page.getByRole("dialog")).toHaveCount(0);

        // The main content stays reachable and unobstructed at narrow widths.
        await expect(page.getByRole("main", { name: "Overview" })).toBeVisible();
        await expect(page.getByTestId("mc-context")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("mobile links preserve history and resize clears the drawer", async ({ page }) => {
        await page.goto("/forge");
        await expect(page).toHaveTitle("Deployment analysis | Atlas Mission Control");
        const trigger = page.getByRole("button", { name: "Open navigation" });
        await trigger.click();
        await page.getByRole("dialog").getByRole("link", { name: "Catalog", exact: true }).click();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Catalog");
        await expect(page).toHaveTitle("Catalog | Atlas Mission Control");
        await trigger.click();
        await page.goBack();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Deployment analysis");
        await expect(page).toHaveTitle("Deployment analysis | Atlas Mission Control");
        await page.goForward();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await trigger.click();
        await page.setViewportSize({ width: 1280, height: 800 });
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(page.getByRole("complementary", { name: "Primary sidebar" })).toBeVisible();
        await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe("");
        await page.setViewportSize({ width: 320, height: 844 });
        await expect(trigger).toBeVisible();
        await expect(page.getByRole("dialog")).toHaveCount(0);
    });

    test("mobile navigation closes on Escape with focus returned to the trigger", async ({ page }) => {
        await page.goto("/");

        const trigger = page.getByRole("button", { name: "Open navigation" });
        await trigger.focus();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("dialog")).toBeVisible();

        const dialog = page.getByRole("dialog");
        await dialog.getByRole("button", { name: "Close navigation" }).focus();
        await page.keyboard.press("Shift+Tab");
        await expect(dialog.getByRole("link", { name: "Deployment analysis", exact: true })).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(dialog.getByRole("button", { name: "Close navigation" })).toBeFocused();
        await page.keyboard.press("Escape");

        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(trigger).toBeFocused();
    });
});

test.describe("Atlas Core unavailable", () => {
    test.use({ mockMode: "core-unavailable" });

    test("renders the unavailable state safely", async ({ page }) => {
        await page.goto("/");

        const systemHealth = page.getByRole("region", { name: "System health" });
        await expect(systemHealth).toContainText("Current information could not be loaded.");
        await expect(systemHealth).toContainText("Atlas shows each report separately and doesn't combine them into one score.");
        await expect(systemHealth).not.toContainText("Healthy");
        await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeVisible();
        await expect(page.getByText("Atlas Core API unavailable", { exact: true })).toBeVisible();
        await expect(page.getByText("Core build: Unavailable", { exact: true })).toBeVisible();
    });
});

for (const width of [390, 1280]) {
    test(`keyboard users can skip navigation at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 844 });
        await page.goto("/providers?view=all");
        await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
        await page.keyboard.press("Tab");
        const skip = page.getByRole("link", { name: "Skip to page content" });
        await expect(skip).toBeFocused();
        await expect(skip).toBeInViewport();
        await page.keyboard.press("Enter");
        await expect(page.locator("#mc-page-content")).toBeFocused();
        await expect(page).toHaveURL(/\/providers\?view=all$/);
        await page.keyboard.press("Tab");
        expect(await page.evaluate(() => Boolean(document.activeElement?.closest("#mc-page-content")))).toBe(true);
    });
}

test("links without page-specific focus classes remain clearly visible to keyboard users", async ({ page }) => {
    await page.goto("/operator/login");

    const homeLink = page.getByRole("link", { name: "← Mission Control" });
    await page.keyboard.press("Tab");
    for (let tab = 0; tab < 30 && !(await homeLink.evaluate((element) => element === document.activeElement)); tab += 1) {
        await page.keyboard.press("Tab");
    }
    await expect(homeLink).toBeFocused();
    await expect(homeLink).toHaveCSS("outline-style", "solid");
    await expect(homeLink).toHaveCSS("outline-width", "2px");
    await expect(homeLink).toHaveCSS("outline-color", "rgb(34, 211, 238)");
});

test("operator login fields and sign-in button show keyboard focus", async ({ page }) => {
    await page.goto("/operator/login");

    const controls = [
        page.getByLabel("Operator ID"),
        page.getByLabel("Password"),
        page.getByRole("button", { name: "Sign in", exact: true }),
    ];
    for (const control of controls) {
        for (let tab = 0; tab < 40; tab += 1) {
            await page.keyboard.press("Tab");
            if (await control.evaluate((element) => element === document.activeElement)) break;
        }

        await expect(control).toBeFocused();
        await expect(control).toHaveCSS("outline-style", "solid");
        await expect(control).toHaveCSS("outline-width", "2px");
        await expect(control).toHaveCSS("outline-color", "rgb(34, 211, 238)");
    }
});
