import { expect, test } from "./mission-control-fixtures";

test("a delayed screen keeps navigation usable and pauses the previous page", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    let release!: () => void;
    const moduleReady = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/src/pages/ForgePage.tsx*", async (route) => {
        await moduleReady;
        await route.continue();
    });
    await page.goto("/");
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
    await page.getByRole("link", { name: "Forge", exact: true }).click();
    try {
        await expect(page.getByText("Loading page...", { exact: true })).toBeVisible();
        await expect(page.locator("#mc-page-content")).toHaveAttribute("inert", "");
        await expect(page.getByRole("link", { name: "Mission Control", exact: true })).toBeVisible();
    } finally {
        release();
    }
    await expect(page.getByRole("heading", { name: "Atlas Forge" })).toBeVisible();
    await expect(page.locator("#mc-page-content")).not.toHaveAttribute("inert", "");
    await expect(page.getByText("Loading page...", { exact: true })).toHaveCount(0);
});

for (const width of [390, 1280]) {
    test(`a screen module failure preserves recovery at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/src/pages/ForgePage.tsx*", (route) => route.abort("failed"));
        await page.goto("/forge");
        await expect(page.getByRole("heading", { name: "This page could not load" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
        await expect(page.getByRole("link", { name: "Return to Mission Control" })).toHaveAttribute("href", "/");
        await page.unroute("**/src/pages/ForgePage.tsx*");
        await page.getByRole("button", { name: "Reload page" }).click();
        await expect(page.getByRole("heading", { name: "Atlas Forge" })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("leaving a pending screen ignores its late module", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    let release!: () => void;
    const moduleReady = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/src/pages/ForgePage.tsx*", async (route) => {
        await moduleReady;
        await route.continue();
    });
    await page.goto("/");
    await page.getByRole("link", { name: "Forge", exact: true }).click();
    const completed = page.waitForResponse("**/src/pages/ForgePage.tsx*");
    try {
        await expect(page.getByText("Loading page...", { exact: true })).toBeVisible();
        await page.getByRole("link", { name: "Mission Control", exact: true }).click();
        await expect(page.getByText("Loading page...", { exact: true })).toHaveCount(0);
        await expect(page.locator("#mc-page-content")).not.toHaveAttribute("inert", "");
    } finally {
        release();
    }
    await completed;
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Atlas Forge" })).toHaveCount(0);
});
