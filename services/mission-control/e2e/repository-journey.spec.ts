import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { installRepositoryJourney, journey } from "./repository-journey-fixture";

async function fitsViewport(page: Page) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

for (const width of [390, 1280]) {
    test(`repository journey keeps every approval and resume separate at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, false, { baseURL });
        await page.setViewportSize({ width, height: 844 });
        await page.goto(`/execution-candidates/${journey.candidate}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await page.getByRole("link", { name: "Continue planning", exact: true }).click();
        await expect(page.getByRole("button", { name: "Generate Plan", exact: true })).toBeVisible();
        await fitsViewport(page);
        await page.getByRole("button", { name: "Generate Plan", exact: true }).click();
        await expect(page.getByText("Plan details", { exact: true })).toBeVisible();
        await page.getByRole("button", { name: "Create Workflow", exact: true }).click();
        await page.getByRole("link", { name: "Open Workflow", exact: true }).click();
        await expect(page.getByRole("button", { name: "Prepare exact request", exact: true })).toBeEnabled();
        await fitsViewport(page);
        await page.getByRole("button", { name: "Prepare exact request", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Implementation", exact: true })).toBeVisible();
        await fitsViewport(page);
        expect(fixture.writes).toHaveLength(4);
        await expect(page.getByRole("button", { name: /Resume Approved/ })).toHaveCount(0);
        await page.getByRole("button", { name: "Approve Implementation", exact: true }).click();
        await expect(page.getByRole("button", { name: "Resume Approved Implementation", exact: true })).toBeVisible();
        await expect(page.getByText("Implementation approved. Resume to run this change.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(5);
        await expect(page.getByRole("button", { name: "Approve Verification", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "Resume Approved Implementation", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Verification", exact: true })).toBeVisible();
        await expect(page.getByText("Implementation approved. Resume to run this change.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Resume Approved/ })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(6);
        await page.getByRole("button", { name: "Approve Verification", exact: true }).click();
        await expect(page.getByRole("button", { name: "Resume Approved Verification", exact: true })).toBeVisible();
        await expect(page.getByText("Verification approved. Resume to run the checks.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(7);
        await page.getByRole("button", { name: "Resume Approved Verification", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Commit", exact: true })).toBeVisible();
        await expect(page.getByText("Verification approved. Resume to run the checks.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Resume Approved/ })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(8);
        await page.getByRole("button", { name: "Approve Commit", exact: true }).click();
        await expect(page.getByRole("button", { name: "Resume Approved Commit", exact: true })).toBeVisible();
        await expect(page.getByText("Commit approved. Resume to finish the local commit.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(9);
        await page.getByRole("button", { name: "Resume Approved Commit", exact: true }).click();

        await expect(page.getByRole("heading", { name: "Completed workflow", exact: true })).toBeVisible();
        await expect(page.getByRole("region", { name: "Workflow summary", exact: true }).getByText("Review the recorded workflow results.", { exact: true })).toBeVisible();
        await expect(page.getByText(journey.commit, { exact: true })).toBeVisible();
        await expect(page.getByText("Commit approved. Resume to finish the local commit.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Resume Approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
        await fitsViewport(page);
        await page.getByRole("link", { name: "Open Audit", exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/workflows/${journey.workflow}/audit$`));
        await expect(page.getByRole("heading", { name: "Stage status", exact: true })).toBeVisible();
        await expect(page.getByText(journey.commit, { exact: true })).toBeVisible();
        await fitsViewport(page);
        expect(fixture.writes).toEqual(fixture.expectedWrites);
        expect(fixture.unexpected).toEqual([]);
    });
}

test("rejecting implementation leaves execution and later approvals unavailable after reload", async ({ page, baseURL }) => {
    const fixture = await installRepositoryJourney(page, true, { baseURL });
    await page.goto(`/workflows/${journey.workflow}`);
    await page.getByRole("button", { name: "Reject", exact: true }).click();
    await expect(page.getByText("Approval rejected.", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Workflow summary", exact: true }).getByText("Workflow is blocked. Review its details.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Resume Approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Review repository change", exact: true })).toBeVisible();
    await page.getByText("Workflow details", { exact: true }).click();
    await expect(page.getByRole("region", { name: "Workflow summary", exact: true }).getByText(journey.workflow, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Resume Approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
    expect(fixture.writes).toEqual(fixture.expectedWrites);
    expect(fixture.unexpected).toEqual([]);
});

test("a pending workflow refresh disables decisions without submitting a request", async ({ page, baseURL }) => {
    const fixture = await installRepositoryJourney(page, true, { baseURL });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/workflows/${journey.workflow}`);
    await expect(page.getByRole("button", { name: "Approve Implementation", exact: true })).toBeEnabled();
    const read = fixture.holdNextWorkflowRead();
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await read.requested;
    await expect(page.getByText("Checking current workflow status. Approval and resume controls are unavailable until this check finishes.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve Implementation", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Reject", exact: true })).toBeDisabled();
    expect(fixture.writes).toEqual([]);
    read.release();
    await expect(page.getByRole("button", { name: "Reject", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Reject", exact: true }).click();
    await expect(page.getByText("Approval rejected.", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Workflow summary", exact: true }).getByText("Workflow is blocked. Review its details.", { exact: true })).toBeVisible();
    expect(fixture.writes).toEqual(fixture.expectedWrites);
    expect(fixture.unexpected).toEqual([]);
    await fitsViewport(page);
});
