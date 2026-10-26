import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test.describe(`Independent Discovery summary at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps items readable and retries only the unavailable summary", async ({ page, rejectedMutationRequests }) => {
            let summaryReads = 0;
            let itemReads = 0;
            page.on("request", request => { if (new URL(request.url()).pathname === "/api/v1/discovery/items") itemReads += 1; });
            await page.route("**/api/v1/discovery", route => {
                expect(route.request().method()).toBe("GET");
                summaryReads += 1;
                return route.fulfill(summaryReads === 1
                    ? { status: 503, json: { detail: "private-summary-canary" } }
                    : { json: { catalog_loaded: true, entry_count: 1, schema_version: 1 } });
            });
            await page.goto("/discovery");
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toBeVisible();
            await expect(page.getByText("Catalog summary unavailable. Item results are shown separately.", { exact: true })).toBeVisible();
            await expect(page.getByRole("button", { name: "Search", exact: true })).toBeEnabled();
            await expect(page.getByText("Discovery catalog unavailable", { exact: true })).toHaveCount(0);
            await expect(page.locator("main")).not.toContainText("private-summary-canary");
            await page.getByRole("button", { name: "Retry catalog summary", exact: true }).click();
            await expect(page.getByText("Catalog loaded", { exact: true })).toBeVisible();
            await expect(page.getByRole("button", { name: "Retry catalog summary", exact: true })).toHaveCount(0);
            expect(summaryReads).toBe(2);
            expect(itemReads).toBe(1);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
