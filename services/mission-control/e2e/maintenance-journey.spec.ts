import { expect, test } from "@playwright/test";
import { installMaintenanceJourney, journey } from "./repository-journey-fixture";

for (const width of [390, 1280]) {
    test(`maintenance planning keeps approval and execution separate at ${width}px`, async ({ page }) => {
        const fixture = await installMaintenanceJourney(page);
        await page.setViewportSize({ width, height: 844 });
        await page.goto(`/execution-candidates/${journey.candidate}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await page.getByRole("link", { name: "Continue planning", exact: true }).click();
        await page.getByRole("button", { name: "Generate Plan", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Maintenance plan", exact: true })).toBeVisible();
        expect(fixture.repositoryPlanReads).toBe(0);
        await page.getByRole("button", { name: "Create Workflow", exact: true }).click();
        await page.getByRole("link", { name: "Open Workflow", exact: true }).click();
        await page.getByRole("button", { name: "Prepare exact request", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Exact action request", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Approve Exact Action", exact: true })).toBeEnabled();
        await expect(page.getByRole("button", { name: "Run approved action", exact: true })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(5);
        await page.getByRole("button", { name: "Approve Exact Action", exact: true }).click();
        await expect(page.getByRole("button", { name: "Run approved action", exact: true })).toBeEnabled();
        expect(fixture.writes).toHaveLength(6);
        await page.getByRole("button", { name: "Run approved action", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Verified", exact: true })).toBeVisible();
        await expect(page.getByText("Maintenance workflow completed. Review the recorded operational outcome.", { exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: /Approve Verification|Approve Commit|Run approved action/ })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(fixture.repositoryPlanReads).toBe(0);
        expect(fixture.writes).toEqual(fixture.expectedWrites);
        expect(fixture.unexpected).toEqual([]);
    });
}
