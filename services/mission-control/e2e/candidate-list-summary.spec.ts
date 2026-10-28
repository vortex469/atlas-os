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
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        await proposalCard.getByText("More proposal details", { exact: true }).click();
        await expect(proposalCard.getByText("candidate-browser-baseline", { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    });
}
