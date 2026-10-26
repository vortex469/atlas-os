import { expect, test, discoveryItemsPage } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test.describe(`Discovery recovery at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("retries submitted search without showing old results or applying draft edits", async ({ page, rejectedMutationRequests }) => {
            const queries: string[] = [];
            await page.route("**/api/v1/discovery/search**", async route => {
                expect(route.request().method()).toBe("GET");
                queries.push(new URL(route.request().url()).searchParams.get("q")!);
                if (queries.length === 1) return route.fulfill({ status: 503, json: { detail: "Search temporarily unavailable." } });
                const entry = { ...discoveryItemsPage.entries[0], item: { ...discoveryItemsPage.entries[0].item, id: "redis", name: "Redis" } };
                return route.fulfill({ json: { results: [{ entry, item: entry.item, evidence: [] }], total: 1, limit: 25, offset: 0, has_more: false } });
            });
            await page.goto("/discovery");
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toBeVisible();
            await page.getByLabel("Keyword search").fill("redis");
            await page.getByRole("button", { name: "Search", exact: true }).click();
            await expect(page.getByText("Discovery catalog unavailable", { exact: true })).toBeVisible();
            await expect(page.getByText("Results unavailable", { exact: true })).toBeVisible();
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toHaveCount(0);
            await expect(page.getByText("1 item found", { exact: true })).toHaveCount(0);
            await page.getByLabel("Keyword search").fill("draft-change");
            await page.getByRole("button", { name: "Retry catalog request", exact: true }).click();
            await expect(page.getByRole("link", { name: "Redis", exact: true })).toBeVisible();
            await expect(page.getByLabel("Keyword search")).toHaveValue("draft-change");
            expect(queries).toEqual(["redis", "redis"]);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
