import { expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`proposal list leads with readable change summaries at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/execution-candidates");

        const proposalCard = page.locator("article").first();
        await expect(proposalCard.getByRole("link", { name: "Review Update Compose Stack proposal" })).toBeVisible();
        await expect(proposalCard.getByText("atlas", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("Eligible for planning consideration", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("Compatible", { exact: true })).toBeVisible();
        await expect(proposalCard.getByText("candidate-browser-baseline", { exact: true })).toBeHidden();
        await expect(page.getByLabel("Category")).toBeHidden();
        await expect(page.getByLabel("Source")).toBeHidden();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Category")).toBeVisible();
        await expect(page.getByLabel("Source")).toBeVisible();
        await proposalCard.getByText("More proposal details", { exact: true }).click();
        await expect(proposalCard.getByText("candidate-browser-baseline", { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`proposal search failure shows one clear error at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/execution-candidates**", route => route.fulfill({
            status: 503,
            json: { detail: "Proposal service is temporarily unavailable." },
        }));
        await page.goto("/execution-candidates");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Change proposals unavailable");
        await expect(alert).toContainText("Mission Control could not load change proposals.");
        await expect(page.getByText("Results unavailable", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Next change proposals page" })).toBeDisabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}
