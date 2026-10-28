import { expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`catalog keeps common filters visible and details optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/discovery");

        await expect(page.getByRole("heading", { name: "Browse the catalog" })).toBeVisible();
        await expect(page.getByLabel("Keyword search")).toBeVisible();
        await expect(page.getByLabel("Item type")).toBeVisible();
        await expect(page.getByLabel("Status")).toBeVisible();
        await expect(page.getByLabel("Tag")).toBeHidden();
        await expect(page.getByLabel("Capability")).toBeHidden();
        await expect(page.getByText("Catalog format version: v1")).toBeHidden();

        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Tag")).toBeVisible();
        await expect(page.getByLabel("Capability")).toBeVisible();
        await page.getByLabel("Tag").fill("ai");
        await page.getByRole("button", { name: "Search", exact: true }).click();
        await expect(page.getByText("More filters · active")).toBeVisible();

        await page.getByText("Technical details", { exact: true }).click();
        await expect(page.getByText("Catalog format version: v1")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
