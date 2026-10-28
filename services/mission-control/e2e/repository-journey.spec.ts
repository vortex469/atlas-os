import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { installRepositoryJourney, journey } from "./repository-journey-fixture";

async function fitsViewport(page: Page) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

for (const width of [390, 1280]) {
    test(`an uncertain implementation approval refreshes before allowing another decision at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, false, { baseURL, uncertainApproval: true });
        await page.setViewportSize({ width, height: 844 });
        await page.goto(`/execution-candidates/${journey.candidate}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await page.getByRole("link", { name: "Continue planning", exact: true }).click();
        await page.getByRole("button", { name: "Generate Plan", exact: true }).click();
        await page.getByRole("button", { name: "Create Workflow", exact: true }).click();
        await page.getByRole("link", { name: "Open Workflow", exact: true }).click();
        await page.getByRole("button", { name: "Prepare change for review", exact: true }).click();
        await page.getByRole("button", { name: "Approve Implementation", exact: true }).click();

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Mission Control could not confirm the implementation approval decision.");
        await expect(alert).toContainText("The workflow status was refreshed; check its current approval status before taking another step.");
        const technicalDetails = alert.locator("details");
        await expect(technicalDetails).not.toHaveAttribute("open");
        await expect(technicalDetails).toContainText("Approval may have been recorded. Check the current workflow status before trying again.");
        await expect(page.getByRole("button", { name: "Approve Implementation", exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Reject implementation", exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Resume Approved Implementation", exact: true })).toBeVisible();
        expect(fixture.writes).toEqual(fixture.expectedWrites.slice(0, 6));
        expect(fixture.unexpected).toEqual([]);
        await fitsViewport(page);
    });

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
        await expect(page.getByRole("button", { name: "Prepare change for review", exact: true })).toBeEnabled();
        await expect(page.getByRole("heading", { name: "Workflow setup", exact: true })).toBeVisible();
        const workflowShellSummary = page.getByRole("region", { name: "Workflow summary" });
        await expect(workflowShellSummary.getByText("Workflow ID", { exact: true })).toBeHidden();
        await expect(workflowShellSummary.getByText("Candidate ID", { exact: true })).toBeHidden();
        await workflowShellSummary.getByText("Workflow details", { exact: true }).click();
        await expect(workflowShellSummary.getByText("Workflow ID", { exact: true })).toBeVisible();
        await expect(workflowShellSummary.getByText(journey.workflow, { exact: true })).toBeVisible();
        await expect(workflowShellSummary.getByText("Candidate fingerprint", { exact: true })).toBeVisible();
        await fitsViewport(page);
        await page.getByRole("button", { name: "Prepare change for review", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Implementation", exact: true })).toBeVisible();
        const workflowSummary = page.getByRole("region", { name: "Workflow summary" });
        await expect(workflowSummary.getByText("Implementation needs approval.", { exact: true })).toBeVisible();
        await expect(workflowSummary.getByText("Candidate fingerprint", { exact: true })).toBeHidden();
        await workflowSummary.getByText("Workflow details", { exact: true }).click();
        await expect(workflowSummary.getByText("Candidate fingerprint", { exact: true })).toBeVisible();
        await fitsViewport(page);
        const changeProgress = page.getByRole("region", { name: "Change progress" });
        const changeStages = changeProgress.getByRole("list", { name: "Change stages" });
        for (const label of ["Change proposal", "Planning", "Change plan", "Workflow created", "Change approval", "Apply change", "Verify change", "Review results", "Commit"]) {
            await expect(changeStages.getByText(label, { exact: true })).toBeVisible();
        }
        await expect(changeStages.getByText("Current step", { exact: true })).toBeVisible();
        await expect(changeStages.getByText("Not started", { exact: true })).toHaveCount(4);
        await expect(changeStages.getByText("Implementation Approval", { exact: true })).toHaveCount(0);
        await fitsViewport(page);
        expect(fixture.writes).toHaveLength(5);
        await expect(page.getByRole("button", { name: /Resume Approved/ })).toHaveCount(0);
        await page.getByRole("button", { name: "Approve Implementation", exact: true }).click();
        await expect(page.getByRole("button", { name: "Resume Approved Implementation", exact: true })).toBeVisible();
        await expect(page.getByText("Implementation approved. Resume to run this change.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(6);
        await expect(page.getByRole("button", { name: "Approve Verification", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "Resume Approved Implementation", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Verification", exact: true })).toBeVisible();
        await expect(page.getByText("Implementation approved. Resume to run this change.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Resume Approved/ })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(7);
        const verificationReview = page.getByRole("region", { name: "Verification and review" });
        const plannedCheck = verificationReview.getByRole("definition").filter({ hasText: "compose-config" }).last();
        await expect(plannedCheck).toBeVisible();
        await expect(verificationReview.getByText("Verification check IDs", { exact: true })).toBeHidden();
        await expect(verificationReview.getByText("verification-browser-journey", { exact: true })).toBeHidden();
        await verificationReview.getByText("Technical details", { exact: true }).click();
        await expect(verificationReview.getByText("verification-browser-journey", { exact: true })).toBeVisible();
        await verificationReview.getByText("Technical details", { exact: true }).click();
        await expect(verificationReview.getByText("verification-browser-journey", { exact: true })).toBeHidden();
        await page.getByRole("button", { name: "Approve Verification", exact: true }).click();
        await expect(page.getByRole("button", { name: "Resume Approved Verification", exact: true })).toBeVisible();
        await expect(page.getByText("Verification approved. Resume to run the checks.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(8);
        await page.getByRole("button", { name: "Resume Approved Verification", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Commit", exact: true })).toBeVisible();
        await expect(page.getByText("Verification approved. Resume to run the checks.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Resume Approved/ })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(9);
        await page.getByRole("button", { name: "Approve Commit", exact: true }).click();
        await expect(page.getByRole("button", { name: "Resume Approved Commit", exact: true })).toBeVisible();
        await expect(page.getByText("Commit approved. Resume to finish the local commit.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(10);
        await page.getByRole("button", { name: "Resume Approved Commit", exact: true }).click();

        await expect(page.getByRole("heading", { name: "Completed workflow", exact: true })).toBeVisible();
        await expect(page.getByText(journey.commit, { exact: true })).toBeVisible();
        await expect(page.getByText("Commit approved. Resume to finish the local commit.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Resume Approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
        await fitsViewport(page);
        await page.getByRole("link", { name: "Open Audit", exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/workflows/${journey.workflow}/audit$`));
        await expect(page.getByRole("heading", { name: "Stage status", exact: true })).toBeVisible();
        await expect(page.getByText("Workflow status", { exact: true })).toBeVisible();
        await expect(page.getByText("Audit validation", { exact: true })).toBeVisible();
        await expect(page.getByText("Overall audit status", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("heading", { name: "How to read this audit", exact: true })).toBeVisible();
        await expect(page.getByText("This page is read-only.", { exact: true })).toBeVisible();
        const commitResult = page.getByRole("region", { name: "Commit Result" });
        await expect(commitResult.getByText(journey.commit, { exact: true })).toBeHidden();
        await commitResult.getByText("Recorded details", { exact: true }).click();
        await expect(page.getByText(journey.commit, { exact: true })).toBeVisible();
        await fitsViewport(page);
        expect(fixture.writes).toEqual(fixture.expectedWrites);
        expect(fixture.unexpected).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`unreadable preparation results require a fresh workflow read at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, false, { baseURL });
        let preparationCalls = 0;
        let preparationBody: unknown;
        await page.setViewportSize({ width, height: 844 });
        await page.route(`**/candidate-planning/${journey.session}/implementation`, async (route) => {
            preparationCalls += 1;
            preparationBody = route.request().postDataJSON();
            return route.fulfill({ json: {
                candidate_planning_session_id: journey.session,
                workflow_session_id: journey.workflow,
                translation_status: "implementation_ready",
                implementation_request_id: "implementation-browser-journey",
                exact_approval_request_id: null,
                candidate_fingerprint: journey.candidateFingerprint,
                plan_fingerprint: journey.planFingerprint,
                repository_head: journey.head,
                translator_version: "fixture-translator-v1",
                reason_codes: [],
                failure: null,
            } });
        });

        await page.goto(`/execution-candidates/${journey.candidate}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await page.getByRole("link", { name: "Continue planning", exact: true }).click();
        await page.getByRole("button", { name: "Generate Plan", exact: true }).click();
        await page.getByRole("button", { name: "Create Workflow", exact: true }).click();
        await page.getByRole("link", { name: "Open Workflow", exact: true }).click();
        await page.getByRole("button", { name: "Prepare change for review", exact: true }).click();

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Mission Control could not confirm whether the change request is ready.");
        await expect(alert.getByRole("button", { name: "Reload workflow", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Prepare change for review", exact: true })).toHaveCount(0);
        expect(preparationCalls).toBe(1);
        expect(preparationBody).toEqual({
            expected_candidate_fingerprint: journey.candidateFingerprint,
            expected_plan_fingerprint: journey.planFingerprint,
        });
        expect(fixture.writes).toEqual(fixture.expectedWrites.slice(0, 4));
        expect(fixture.unexpected).toEqual([]);
        await fitsViewport(page);
    });
}

test("rejecting implementation leaves execution and later approvals unavailable after reload", async ({ page, baseURL }) => {
    const fixture = await installRepositoryJourney(page, true, { baseURL });
    await page.goto(`/workflows/${journey.workflow}`);
    await page.getByRole("button", { name: "Reject implementation", exact: true }).click();
    await expect(page.getByText("Implementation request rejected.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Resume Approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Review workflow", exact: true })).toBeVisible();
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
    await expect(page.getByRole("button", { name: "Reject implementation", exact: true })).toBeDisabled();
    expect(fixture.writes).toEqual([]);
    read.release();
    await expect(page.getByRole("button", { name: "Reject implementation", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Reject implementation", exact: true }).click();
    await expect(page.getByText("Implementation request rejected.", { exact: true })).toBeVisible();
    expect(fixture.writes).toEqual(fixture.expectedWrites);
    expect(fixture.unexpected).toEqual([]);
    await fitsViewport(page);
});
