import { discoveryItemsPage, expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`catalog keeps common filters visible and details optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items?**", (route) => route.fulfill({ json: { ...discoveryItemsPage, total: 26, has_more: true } }));
        await page.goto("/discovery");

        await expect(page.getByRole("heading", { name: "Browse the catalog" })).toBeVisible();
        await expect(page.getByLabel("Keyword search")).toBeVisible();
        await expect(page.getByLabel("Item type")).toBeVisible();
        await expect(page.getByLabel("Status")).toBeVisible();
        await expect(page.getByLabel("Tag")).toBeHidden();
        await expect(page.getByLabel("Capability")).toBeHidden();
        await expect(page.getByText("Catalog format version: v1")).toBeHidden();
        const itemCard = page.locator("article").filter({ has: page.getByRole("link", { name: "Fixture Application" }) });
        await expect(itemCard.getByText("Catalog item ID: fixture-app", { exact: true })).toBeHidden();
        await expect(itemCard.getByText("Read only", { exact: true })).toBeVisible();
        await expect(itemCard.getByText("Browser fixture", { exact: true })).toBeVisible();
        await expect(itemCard.getByText("read-only", { exact: true })).toHaveCount(0);
        await itemCard.getByText("Technical details", { exact: true }).click();
        await expect(itemCard.getByText("Catalog item ID: fixture-app", { exact: true })).toBeVisible();

        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Tag")).toBeVisible();
        await expect(page.getByLabel("Capability")).toBeVisible();
        await page.getByLabel("Tag").fill("ai");
        await expect(page.getByText("These filter changes haven't been searched yet. Select Search to update the results.")).toBeVisible();
        await expect(page.getByRole("button", { name: "Next page" })).toBeDisabled();
        await page.getByRole("button", { name: "Search", exact: true }).click();
        await expect(page.getByText("These filter changes haven't been searched yet. Select Search to update the results.")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Next page" })).toBeEnabled();
        await expect(page.getByText("More filters · active")).toBeVisible();
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await expect(page.getByText("More filters · active")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Clear filters", exact: true })).toHaveCount(0);

        await page.locator("details").filter({ hasText: "Catalog format version" }).getByText("Technical details", { exact: true }).click();
        await expect(page.getByText("Catalog format version: v1")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });

    test(`empty catalog has no filter recovery prompt at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery", (route) => route.fulfill({ json: {
            catalog_loaded: true, entry_count: 0, schema_version: 1,
        } }));
        await page.route("**/api/v1/discovery/items?**", (route) => route.fulfill({ json: {
            entries: [], total: 0, limit: 25, offset: 0, has_more: false,
        } }));

        await page.goto("/discovery");

        await expect(page.getByText("No catalog items are available.")).toBeVisible();
        await expect(page.getByText("Try clearing filters or using a broader keyword.")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Clear filters" })).toHaveCount(0);
        await expect(page.getByText("Catalog total").locator("..").getByText("0")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}
