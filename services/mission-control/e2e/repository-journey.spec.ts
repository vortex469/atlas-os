import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { installRepositoryJourney, journey } from "./repository-journey-fixture";

async function fitsViewport(page: Page) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

async function expectResponsiveMainPadding(page: Page, heading: string, width: number) {
    const padding = await page.getByRole("heading", { name: heading, exact: true }).evaluate((element) => {
        const main = element.closest("main");
        return main ? getComputedStyle(main).paddingLeft : null;
    });
    if (width < 640) {
        expect(padding).toBe("16px");
    } else {
        expect(Number.parseFloat(padding ?? "0px")).toBeGreaterThan(16);
    }
}

for (const width of [320, 390, 1280]) {
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
        await expect(page.getByRole("button", { name: "Run approved change", exact: true })).toBeVisible();
        expect(fixture.writes).toEqual(fixture.expectedWrites.slice(0, 6));
        expect(fixture.unexpected).toEqual([]);
        await fitsViewport(page);
    });

    test(`repository journey keeps every approval and resume separate at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, false, { baseURL });
        await page.setViewportSize({ width, height: 844 });
        const proposalSearch = "?eligibility=eligible&change=update-compose-stack&offset=25";
        await page.goto(`/execution-candidates/${journey.candidate}${proposalSearch}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await page.getByRole("link", { name: "Continue planning", exact: true }).click();
        await expect(page.getByRole("button", { name: "Generate Plan", exact: true })).toBeVisible();
        await fitsViewport(page);
        await page.getByRole("button", { name: "Generate Plan", exact: true }).click();
        const planCard = page.locator("article").filter({ hasText: "Plan details" });
        await expect(planCard.getByText("Plan details", { exact: true })).toBeVisible();
        await expect(planCard.getByText("fixture-branch", { exact: true })).toBeVisible();
        await expect(planCard.getByText(journey.head, { exact: true })).toBeHidden();
        await expect(planCard.getByText("evidence-browser-journey", { exact: true })).toBeHidden();
        await planCard.getByText("Technical details", { exact: true }).click();
        await expect(planCard.getByText(journey.head, { exact: true })).toBeVisible();
        await expect(planCard.getByText("evidence-browser-journey", { exact: true })).toBeVisible();
        await planCard.getByText("Technical details", { exact: true }).click();
        await expect(planCard.getByText(journey.head, { exact: true })).toBeHidden();
        await page.getByRole("button", { name: "Create Workflow", exact: true }).click();
        await page.getByRole("link", { name: "Open Workflow", exact: true }).click();
        await expect(page.getByRole("button", { name: "Prepare change for review", exact: true })).toBeEnabled();
        const workflowSetupHeading = page.getByRole("heading", { name: "Workflow setup", exact: true });
        await expect(workflowSetupHeading).toBeVisible();
        const workflowSetupPadding = await workflowSetupHeading.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(workflowSetupPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(workflowSetupPadding ?? "0px")).toBeGreaterThan(16);
        }
        const workflowShellSummary = page.getByRole("region", { name: "Workflow summary" });
        await expect(workflowShellSummary.getByText("Workflow ID", { exact: true })).toBeHidden();
        await expect(workflowShellSummary.getByText("Candidate ID", { exact: true })).toBeHidden();
        await workflowShellSummary.getByText("Workflow details", { exact: true }).click();
        await expect(workflowShellSummary.getByText("Workflow ID", { exact: true })).toBeVisible();
        await expect(workflowShellSummary.getByText(journey.workflow, { exact: true })).toBeVisible();
        await expect(workflowShellSummary.getByText("Candidate fingerprint", { exact: true })).toBeVisible();
        await fitsViewport(page);
        await page.getByRole("button", { name: "Prepare change for review", exact: true }).click();
        await expectResponsiveMainPadding(page, "Review workflow", width);

        await expect(page.getByRole("button", { name: "Approve Implementation", exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "← Change proposals", exact: true })).toHaveAttribute(
            "href",
            `/execution-candidates${proposalSearch}`,
        );
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
        await expect(page.getByRole("button", { name: /Run approved|Record approved/ })).toHaveCount(0);
        const changeDetails = page.getByRole("region", { name: "Change details" });
        await expect(changeDetails.getByText("compose.production.yaml", { exact: true })).toBeVisible();
        await expect(changeDetails.getByText("implementation-browser-journey", { exact: true })).toBeHidden();
        await changeDetails.getByText("Technical details", { exact: true }).click();
        await expect(changeDetails.getByText("implementation-browser-journey", { exact: true })).toBeVisible();
        await changeDetails.getByText("Technical details", { exact: true }).click();
        await expect(changeDetails.getByText("implementation-browser-journey", { exact: true })).toBeHidden();
        await page.getByRole("button", { name: "Approve Implementation", exact: true }).click();
        await expect(page.getByRole("button", { name: "Run approved change", exact: true })).toBeVisible();
        await expect(page.getByText("Change approved. Run it when you are ready.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(6);
        await expect(page.getByRole("button", { name: "Approve Verification", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "Run approved change", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Verification", exact: true })).toBeVisible();
        const executionSummary = changeProgress.getByRole("region", { name: "Execution" });
        await expect(executionSummary.getByText("Files changed: 1", { exact: true })).toBeVisible();
        const executionDetails = executionSummary.locator("details");
        await expect(executionDetails).not.toHaveAttribute("open");
        await expect(executionDetails.getByText("execution-browser-journey", { exact: true })).toBeHidden();
        await executionDetails.getByText("Technical details", { exact: true }).click();
        await expect(executionDetails.getByText("execution-browser-journey", { exact: true })).toBeVisible();
        await executionDetails.getByText("Technical details", { exact: true }).click();
        await expect(executionDetails.getByText("execution-browser-journey", { exact: true })).toBeHidden();
        const outputNotice = page.getByRole("region", { name: "Worker output was shortened" });
        await expect(outputNotice.getByText("Only part of the worker's output is shown. Verification and commit each need separate approval.", { exact: true })).toBeVisible();
        const outputDetails = outputNotice.getByText("Output details", { exact: true });
        const outputCounts = outputNotice.getByText("stdout: 1024 bytes retained; 4096 bytes observed.", { exact: true });
        await expect(outputCounts).toBeHidden();
        await outputDetails.click();
        await expect(outputCounts).toBeVisible();
        await outputDetails.click();
        await expect(outputCounts).toBeHidden();
        await expect(page.getByText("Change approved. Run it when you are ready.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Run approved|Record approved/ })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(7);
        const verificationReview = page.getByRole("region", { name: "Verification and review" });
        const plannedCheck = verificationReview.getByRole("definition").filter({ hasText: "compose-config" }).last();
        await expect(plannedCheck).toBeVisible();
        await expect(page.getByRole("region", { name: "Check results" }).getByText("Review these checks. Approve them before Atlas runs them.", { exact: true })).toBeVisible();
        await expect(page.getByRole("region", { name: "Review" }).getByText("Review results will appear after verification runs.", { exact: true })).toBeVisible();
        await expect(verificationReview.getByText("Verification check IDs", { exact: true })).toBeHidden();
        await expect(verificationReview.getByText("verification-browser-journey", { exact: true })).toBeHidden();
        await verificationReview.getByText("Technical details", { exact: true }).click();
        await expect(verificationReview.getByText("verification-browser-journey", { exact: true })).toBeVisible();
        await verificationReview.getByText("Technical details", { exact: true }).click();
        await expect(verificationReview.getByText("verification-browser-journey", { exact: true })).toBeHidden();
        await page.getByRole("button", { name: "Approve Verification", exact: true }).click();
        await expect(page.getByRole("button", { name: "Run approved checks", exact: true })).toBeVisible();
        await expect(page.getByText("Checks approved. Run them when you are ready.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(8);
        await page.getByRole("button", { name: "Run approved checks", exact: true }).click();

        await expect(page.getByRole("button", { name: "Approve Commit", exact: true })).toBeVisible();
        await expect(page.getByRole("region", { name: "Check results" }).getByText("compose-config: passed", { exact: true })).toBeVisible();
        await expect(page.getByText("Checks approved. Run them when you are ready.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Run approved|Record approved/ })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(9);
        const commitDetails = page.getByRole("region", { name: "Commit details" });
        await expect(commitDetails.getByText("test: update fixture compose configuration", { exact: true })).toBeVisible();
        await expect(commitDetails.getByText("compose.production.yaml", { exact: true })).toBeVisible();
        await expect(commitDetails.getByText("commit-request-browser-journey", { exact: true })).toBeHidden();
        await commitDetails.getByText("Technical details", { exact: true }).click();
        await expect(commitDetails.getByText("commit-request-browser-journey", { exact: true })).toBeVisible();
        await commitDetails.getByText("Technical details", { exact: true }).click();
        await expect(commitDetails.getByText("commit-request-browser-journey", { exact: true })).toBeHidden();
        await page.getByRole("button", { name: "Approve Commit", exact: true }).click();
        await expect(page.getByRole("button", { name: "Record approved commit", exact: true })).toBeVisible();
        await expect(page.getByText("Commit approved. Record it when you are ready.", { exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(10);
        await page.getByRole("button", { name: "Record approved commit", exact: true }).click();

        await expect(page.getByRole("heading", { name: "Completed workflow", exact: true })).toBeVisible();
        await expect(page.getByText(journey.commit, { exact: true })).toBeVisible();
        await expect(page.getByText("Commit approved. Record it when you are ready.", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Run approved|Record approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
        await fitsViewport(page);
        await page.getByRole("link", { name: "Open Audit", exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/workflows/${journey.workflow}/audit\\?eligibility=eligible&change=update-compose-stack&offset=25&returnTo=%2Fexecution-candidates$`));
        await expectResponsiveMainPadding(page, "Workflow audit", width);
        await expect(page.getByText("Workflow status", { exact: true })).toBeVisible();
        await expect(page.getByText("Audit validation", { exact: true })).toBeVisible();
        await expect(page.getByText("Overall audit status", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Review the recorded stages and results. Open a stage to inspect its details; this page does not change the workflow.", { exact: true })).toBeVisible();
        for (const label of ["Change proposal", "Planning", "Change plan", "Workflow setup", "Change request", "Change approval", "Apply change", "Checks to run", "Verification approval", "Check results", "Review results", "Commit details", "Commit approval", "Commit result"]) {
            await expect(page.getByRole("region", { name: new RegExp(`^${label},`) })).toBeVisible();
        }
        await expect(page.getByRole("region", { name: /Candidate Plan/ })).toHaveCount(0);
        const commitResult = page.getByRole("region", { name: /Commit result, Completed/ });
        await expect(commitResult.getByText(journey.commit, { exact: true })).toBeHidden();
        await commitResult.getByText("Commit result", { exact: true }).click();
        await expect(page.getByText(journey.commit, { exact: true })).toBeVisible();
        await fitsViewport(page);
        await page.getByRole("link", { name: "← Back to Workflow", exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/workflows/${journey.workflow}\\?eligibility=eligible&change=update-compose-stack&offset=25&returnTo=%2Fexecution-candidates$`));
        await expect(page.getByRole("link", { name: "← Change proposals", exact: true })).toHaveAttribute(
            "href",
            `/execution-candidates${proposalSearch}`,
        );
        await page.getByRole("link", { name: "← Change proposals", exact: true }).click();
        await expect(page).toHaveURL(`/execution-candidates${proposalSearch}`);
        const proposalFilters = page.getByRole("form", { name: "Filter change proposals" });
        await expect(proposalFilters.getByRole("combobox", { name: "Eligibility" })).toHaveValue("eligible");
        await expect(proposalFilters.getByRole("combobox", { name: "Change" })).toHaveValue("update-compose-stack");
        await expect(page.getByText("Showing 26–26 of 26 proposals", { exact: true })).toBeVisible();
        expect(fixture.writes).toEqual(fixture.expectedWrites);
        expect(fixture.unexpected).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
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

for (const width of [390, 1280]) {
    test(`an unavailable planning session can be checked again at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, false, { baseURL });
        await page.setViewportSize({ width, height: 844 });
        let sessionReads = 0;
        let allowRecovery = false;
        await page.route(`**/agent-api/candidate-planning/${journey.session}`, async (route) => {
            if (route.request().method() !== "GET") return route.fallback();
            sessionReads += 1;
            if (!allowRecovery) {
                return route.fulfill({ status: 503, json: { detail: "Planning session fixture is unavailable." } });
            }
            return route.fallback();
        });

        await page.goto(`/candidate-planning/${journey.session}`);
        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Planning session unavailable");
        await expect(alert).toContainText("Atlas couldn’t load this planning session. Try again to check its status.");
        await expect(alert.locator("details")).not.toHaveAttribute("open");
        await expect(page.getByRole("button", { name: "Generate Plan" })).toHaveCount(0);
        allowRecovery = true;
        await page.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("heading", { name: "Plan this change" })).toBeVisible();
        expect(sessionReads).toBeGreaterThanOrEqual(2);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        await fitsViewport(page);
    });

    test(`an unreadable workflow shows a clear retry and recovers at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, true, { baseURL });
        await page.setViewportSize({ width, height: 844 });
        let detailReads = 0;
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, async (route) => {
            if (route.request().method() !== "GET") return route.fallback();
            detailReads += 1;
            if (detailReads === 1) return route.fulfill({ json: { workflow_id: journey.workflow } });
            return route.fallback();
        });

        await page.goto(`/workflows/${journey.workflow}`);
        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Atlas couldn’t read this workflow’s details. Try again to reload them.");
        await expect(alert.locator("details")).not.toHaveAttribute("open");
        await expect(page.getByRole("button", { name: "Approve Implementation" })).toHaveCount(0);
        await page.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("region", { name: "Workflow summary" })).toBeVisible();
        expect(detailReads).toBe(2);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        await fitsViewport(page);
    });
}

test("rejecting implementation leaves execution and later approvals unavailable after reload", async ({ page, baseURL }) => {
    const fixture = await installRepositoryJourney(page, true, { baseURL });
    await page.goto(`/workflows/${journey.workflow}`);
    await page.getByRole("button", { name: "Reject implementation", exact: true }).click();
    await expect(page.getByText("Implementation request rejected.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Run approved|Record approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Review workflow", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Run approved|Record approved|Approve Implementation|Approve Verification|Approve Commit/ })).toHaveCount(0);
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
    await expect(page.getByText("Checking current workflow status. Approval and action buttons are unavailable until this check finishes.", { exact: true })).toBeVisible();
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
