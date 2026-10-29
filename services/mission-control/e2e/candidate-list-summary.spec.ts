import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test(`proposal list leads with readable change summaries at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/execution-candidates");

        const proposalCard = page.locator("article").first();
        await expect(proposalCard.getByRole("link", { name: "Review Update Compose Stack proposal" })).toBeVisible();
        await expect(proposalCard.getByText("atlas", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("Eligible for planning", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("Compatible", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("Expires (local time)", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("candidate-browser-baseline", { exact: true })).toBeHidden();
        await expect(page.getByLabel("Category")).toBeHidden();
        await expect(page.getByLabel("Source")).toBeHidden();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Category")).toBeVisible();
        await expect(page.getByLabel("Source")).toBeVisible();
        await proposalCard.getByText("More proposal details", { exact: true }).click();
        await expect(proposalCard.getByText("candidate-browser-baseline", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("Created (local time)", { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`proposal search failure offers a clear retry at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        let requestCount = 0;
        await page.route("**/api/v1/execution-candidates**", route => {
            requestCount += 1;
            return route.fulfill(requestCount === 1
                ? { status: 503, json: { detail: "Proposal service is temporarily unavailable." } }
                : { json: { candidates: [], total: 0, limit: 25, offset: 0, has_more: false } });
        });
        await page.goto("/execution-candidates");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Change proposals unavailable");
        await expect(alert).toContainText("Mission Control could not load the latest proposal results.");
        await expect(alert.getByRole("button", { name: "Retry search" })).toBeVisible();
        await expect(page.getByText("Results unavailable", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Next change proposals page" })).toBeDisabled();

        await alert.getByRole("button", { name: "Retry search" }).click();
        await expect(page.getByText("No current change proposals.")).toBeVisible();
        expect(requestCount).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed proposal data offers a read-only retry at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/execution-candidates**", route => {
            reads += 1;
            return route.fulfill(reads === 1
                ? { json: { candidates: [null], total: 1, limit: 25, offset: 0, has_more: false } }
                : { json: { candidates: [], total: 0, limit: 25, offset: 0, has_more: false } });
        });
        await page.goto("/execution-candidates");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Change proposals unavailable");
        await expect(alert).toContainText("Mission Control could not load the latest proposal results.");
        await expect(page.getByRole("heading", { name: "This page could not load" })).toHaveCount(0);
        if (width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
            await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
            await page.getByRole("button", { name: "Close navigation" }).click();
        }

        await alert.getByRole("button", { name: "Retry search" }).click();
        await expect(page.getByText("No current change proposals.", { exact: true })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
