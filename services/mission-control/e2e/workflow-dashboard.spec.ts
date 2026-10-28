import { expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`workflow cards keep approval status visible and reference details optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/workflows");

        await expect(page.getByLabel("Workflow status")).toBeVisible();
        await expect(page.getByLabel("Approval status")).toBeVisible();
        await expect(page.getByLabel("Workflow ID contains")).toBeHidden();
        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("Workflow ID contains")).toBeVisible();

        const heading = page.getByRole("heading", { name: "workflow-browser-baseline" });
        await expect(heading).toBeVisible();
        const card = heading.locator("xpath=ancestor::article[1]");
        await expect(card.getByText("Stage: Implementation", { exact: true })).toBeVisible();
        await expect(card.getByText("Your approval is needed", { exact: true })).toBeVisible();
        await expect(card.getByText("Current State", { exact: true })).toHaveCount(0);
        await expect(card.getByText("Candidate ID", { exact: true })).toBeHidden();

        await card.getByText("Workflow details", { exact: true }).click();
        await expect(card.getByText("Candidate ID", { exact: true })).toBeVisible();
        await expect(card.getByText("candidate-browser-baseline", { exact: true })).toBeVisible();
        await expect(card.getByRole("link", { name: "Open workflow", exact: true })).toHaveAttribute(
            "href",
            "/workflows/workflow-browser-baseline",
        );
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
