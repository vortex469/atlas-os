import { executionCandidates, expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`proposal detail leads with operator information at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        const candidate = executionCandidates[0];
        await page.setViewportSize({ width, height: 900 });
        await page.route(`**/api/v1/execution-candidates/${candidate.id}`, (route) => route.fulfill({ json: candidate }));
        await page.goto(`/execution-candidates/${candidate.id}`);

        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        await expect(page.getByText("For atlas (Service)", { exact: true })).toBeVisible();
        await expect(page.getByText("Browser fixture candidate.", { exact: true })).toBeVisible();
        await expect(page.getByText("Compatible", { exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Start planning", exact: true })).toBeVisible();

        const technicalReferences = page.getByText("Technical references", { exact: true });
        await expect(technicalReferences).toBeVisible();
        await expect(page.getByText(candidate.id, { exact: true })).toBeHidden();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        await technicalReferences.click();
        await expect(page.getByText(candidate.id, { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
    });
}
