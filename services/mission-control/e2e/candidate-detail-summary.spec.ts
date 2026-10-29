import { executionCandidates, expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test(`proposal detail leads with operator information at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        const candidate = executionCandidates[0];
        await page.setViewportSize({ width, height: 900 });
        await page.route(`**/api/v1/execution-candidates/${candidate.id}`, (route) => route.fulfill({ json: candidate }));
        await page.goto(`/execution-candidates/${candidate.id}`);

        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        await expect(page.getByText("Target ID: atlas · Type: Service", { exact: true })).toBeVisible();
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

test("proposal detail retry clearly identifies unavailable current details", async ({ page, rejectedMutationRequests }) => {
    const candidate = executionCandidates[0];
    let reads = 0;
    await page.setViewportSize({ width: 390, height: 900 });
    await page.route(`**/api/v1/execution-candidates/${candidate.id}`, (route) => {
        reads += 1;
        return reads === 1
            ? route.fulfill({ status: 503, json: { detail: "PRIVATE_BACKEND_DETAIL" } })
            : route.fulfill({ json: candidate });
    });
    await page.goto(`/execution-candidates/${candidate.id}`);

    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Change proposal unavailable");
    await expect(alert).toContainText("Atlas couldn't load this proposal. Its current details are unknown.");
    await expect(alert).not.toContainText("PRIVATE_BACKEND_DETAIL");
    await alert.getByRole("button", { name: "Retry loading proposal" }).click();
    await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
    expect(reads).toBe(2);
    expect(rejectedMutationRequests).toEqual([]);
});
