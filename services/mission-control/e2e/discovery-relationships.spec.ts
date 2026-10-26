import { expect, test, discoveryItemsPage } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) for (const outcome of ["unavailable", "malformed", "foreign"] as const) {
    test.describe(`Discovery relationship recovery ${outcome} at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps the item visible and retries only its relationships", async ({ page, rejectedMutationRequests }) => {
            let itemReads = 0;
            let relationshipReads = 0;
            await page.route("**/api/v1/discovery/items/fixture-app", route => {
                expect(route.request().method()).toBe("GET");
                itemReads += 1;
                return route.fulfill({ json: discoveryItemsPage.entries[0] });
            });
            await page.route("**/api/v1/discovery/items/fixture-app/relationships", route => {
                expect(route.request().method()).toBe("GET");
                relationshipReads += 1;
                return route.fulfill(relationshipReads === 1
                    ? outcome === "unavailable"
                        ? { status: 503, json: { detail: "private-relationship-canary" } }
                        : outcome === "foreign"
                            ? { json: { item_id: "foreign", incoming: [], outgoing: [] } }
                            : { json: { item_id: "fixture-app", incoming: [], outgoing: [{ relationship: { type: {} }, target: "private-relationship-canary" }] } }
                    : { json: { item_id: "fixture-app", incoming: [], outgoing: [] } });
            });
            await page.goto("/discovery/items/fixture-app");
            await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
            await expect(page.getByText("Item relationships unavailable. The catalog item is still shown.", { exact: true })).toBeVisible();
            await expect(page.getByText("No outgoing relationships.", { exact: true })).toHaveCount(0);
            await expect(page.locator("main")).not.toContainText("private-relationship-canary");
            const initialItemReads = itemReads;
            expect(initialItemReads).toBeGreaterThan(0);
            await page.getByRole("button", { name: "Retry item relationships", exact: true }).click();
            await expect(page.getByText("No outgoing relationships.", { exact: true })).toBeVisible();
            await expect(page.getByText("No incoming relationships.", { exact: true })).toBeVisible();
            expect(itemReads).toBe(initialItemReads);
            expect(relationshipReads).toBe(2);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
