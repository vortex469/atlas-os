import { expect, test, discoveryItemsPage } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test.describe(`Discovery recovery at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("retries submitted search without showing old results or applying draft edits", async ({ page, rejectedMutationRequests }) => {
            const queries: string[] = [];
            const typeQueries: Array<string | null> = [];
            let itemReads = 0;
            let summaryReads = 0;
            page.on("request", request => {
                const path = new URL(request.url()).pathname;
                if (path === "/api/v1/discovery/items") itemReads += 1;
                if (path === "/api/v1/discovery") summaryReads += 1;
            });
            await page.route("**/api/v1/discovery/search**", async route => {
                expect(route.request().method()).toBe("GET");
                queries.push(new URL(route.request().url()).searchParams.get("q")!);
                typeQueries.push(new URL(route.request().url()).searchParams.get("type"));
                if (queries.length === 1) return route.fulfill({ status: 503, json: { detail: "Search temporarily unavailable." } });
                const entry = { ...discoveryItemsPage.entries[0], item: { ...discoveryItemsPage.entries[0].item, id: "redis", name: "Redis" } };
                return route.fulfill({ json: { results: [{ entry, item: entry.item, evidence: [] }], total: 1, limit: 25, offset: 0, has_more: false } });
            });
            await page.goto("/discovery");
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Browse the catalog", exact: true })).toBeVisible();
            const itemType = page.getByRole("combobox", { name: "Item type", exact: true, includeHidden: true });
            await expect(itemType).toHaveCount(1);
            await expect(itemType).toBeHidden();
            const catalogDetails = page.getByText("Catalog details", { exact: true });
            await catalogDetails.focus();
            await page.keyboard.press("Enter");
            await expect(page.getByText("v1", { exact: true })).toBeVisible();
            await page.keyboard.press("Enter");
            await expect(page.getByText("v1", { exact: true })).toBeHidden();
            const moreFilters = page.getByText("More filters", { exact: true });
            await moreFilters.focus();
            await page.keyboard.press("Enter");
            await expect(itemType).toBeVisible();
            await itemType.selectOption("application");
            await expect(page.getByText("Search to apply your changes.", { exact: true })).toBeVisible();
            await moreFilters.focus();
            await page.keyboard.press("Enter");
            await expect(itemType).toBeHidden();
            expect(itemReads).toBe(1);
            expect(summaryReads).toBe(1);
            expect(queries).toEqual([]);
            await page.evaluate(() => window.scrollTo(0, 0));
            if (width !== 320) await page.screenshot({ path: `/tmp/atlas-compact-discovery-${width}.png`, fullPage: true });
            await page.getByLabel("Keyword search").fill("redis");
            await page.getByRole("button", { name: "Search", exact: true }).click();
            await expect(page.getByText("Discovery catalog unavailable", { exact: true })).toBeVisible();
            await expect(page.getByText("Results unavailable", { exact: true })).toBeVisible();
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toHaveCount(0);
            await expect(page.getByText("1 item found", { exact: true })).toHaveCount(0);
            await expect(page.getByText("Filters applied to these results.", { exact: true })).toHaveCount(0);
            await page.getByLabel("Keyword search").fill("draft-change");
            await expect(page.getByText("Search to apply your changes.", { exact: true })).toBeVisible();
            await page.getByRole("button", { name: "Retry catalog request", exact: true }).click();
            await expect(page.getByRole("link", { name: "Redis", exact: true })).toBeVisible();
            await expect(page.getByLabel("Keyword search")).toHaveValue("draft-change");
            await expect(page.getByText("Filters applied to these results.", { exact: true })).toBeVisible();
            await expect(page.getByText("Search to apply your changes.", { exact: true })).toBeVisible();
            expect(queries).toEqual(["redis", "redis"]);
            expect(typeQueries).toEqual(["application", "application"]);
            expect(itemReads).toBe(1);
            expect(summaryReads).toBe(3);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
