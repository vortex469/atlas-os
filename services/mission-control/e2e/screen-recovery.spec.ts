import { expect, test } from "./mission-control-fixtures";

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    test(`unknown pages retain navigation at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.goto("/page-that-does-not-exist");
        await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
        if (viewport.width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
        }
        const navigation = page.getByRole("navigation", { name: "Primary" }).filter({ visible: true });
        await navigation.getByRole("link", { name: "Workflows", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
        await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("an empty provider catalog has a clear way back", async ({ page }) => {
    await page.route("**/api/v1/providers", (route) => route.fulfill({
        status: 200, contentType: "application/json", body: "[]",
    }));
    await page.goto("/providers/proxmox");
    await expect(page.getByRole("heading", { name: "Provider not found" })).toBeVisible();
    await expect(page.getByText("Not updated yet")).not.toBeVisible();
    await page.getByRole("link", { name: "Return to Mission Control" }).click();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
});

test("workflows recover from an initial outage without reloading", async ({ page }) => {
    let attempts = 0;
    await page.route("**/agent-api/**", async (route) => {
        if (new URL(route.request().url()).pathname.endsWith("/workflows")) {
            attempts += 1;
            if (attempts === 1) {
                await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporarily unavailable" }) });
                return;
            }
        }
        await route.fallback();
    });
    await page.goto("/workflows");
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).toBeVisible();
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).not.toBeVisible();
    expect(attempts).toBe(2);
});

test("a broken page keeps navigation and hides raw error details", async ({ page }) => {
    await page.route("**/api/v1/discovery/items?**", (route) => route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ entries: [null], total: 1, offset: 0, limit: 25, has_more: false }),
    }));
    await page.goto("/discovery");
    await expect(page.getByRole("heading", { name: "This page could not load" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
    await expect(page.getByText("Unexpected Application Error!")).toHaveCount(0);
    await expect(page.getByText(/TypeError:|Cannot read properties/)).toHaveCount(0);
    await page.getByRole("link", { name: "Return to Mission Control" }).click();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
});
