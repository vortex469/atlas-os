import { expect, test } from "@playwright/test";
import { installRepositoryJourney, journey, maintenanceWorkflow, workflowDetail } from "./repository-journey-fixture";
import { operationalActionRequest } from "../src/test/operationalPlanning";

for (const width of [320, 390, 1280]) for (const maintenance of [false, true]) {
    test(`saved ${maintenance ? "maintenance" : "repository"} workflow resumes preparation at ${width}px without inheriting approval`, async ({ page, baseURL }) => {
        const fixture = await installRepositoryJourney(page, true, { maintenance, baseURL });
        await page.setViewportSize({ width, height: 900 });
        let prepared = false;
        const preparationWrites: unknown[] = [];
        const saved = maintenance ? maintenanceWorkflow("implementation", false, operationalActionRequest()) : workflowDetail("implementation", false);
        const detailPath = `/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`;
        await page.route(`**${detailPath}`, route => {
            expect(route.request().method()).toBe("GET");
            return route.fulfill({ json: prepared ? saved : { ...saved, workflow_state: "awaiting_approval", implementation_request: null, operational_action_request: null } });
        });
        await page.route(`**/agent-api/candidate-planning/${journey.session}/implementation`, route => {
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            expect(route.request().method()).toBe("POST");
            expect(route.request().postDataJSON()).toEqual({ expected_candidate_fingerprint: journey.candidateFingerprint, expected_plan_fingerprint: journey.planFingerprint });
            preparationWrites.push(route.request().postDataJSON());
            prepared = true;
            return route.fulfill({ json: { candidate_planning_session_id: journey.session, workflow_session_id: journey.workflow,
                translation_status: "implementation_ready", implementation_request_id: "fixture-implementation", exact_approval_request_id: "fixture-approval",
                candidate_fingerprint: journey.candidateFingerprint, plan_fingerprint: journey.planFingerprint, repository_head: maintenance ? null : journey.head,
                translator_version: "fixture-only", reason_codes: [], failure: null } });
        });
        await page.goto(`/workflows/${journey.workflow}`);
        await expect(page.getByRole("heading", { name: "Finish preparing this change", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: /Approve|Resume|Run approved/ })).toHaveCount(0);
        if (!maintenance && width !== 320) await page.screenshot({ path: `/tmp/atlas-saved-preparation-next-step-${width}.png`, fullPage: true });
        await page.reload();
        await page.getByRole("link", { name: "Review preparation", exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/candidate-planning/${journey.session}/workflow$`));
        await expect(page.getByRole("button", { name: "Prepare exact request", exact: true })).toBeEnabled();
        expect(preparationWrites).toEqual([]);
        expect(fixture.writes).toEqual([]);
        await page.reload();
        await expect(page.getByRole("button", { name: "Prepare exact request", exact: true })).toBeEnabled();
        expect(preparationWrites).toEqual([]);
        if (width === 390) await page.screenshot({ path: `/tmp/atlas-continue-preparation-${maintenance ? "maintenance" : "repository"}-390.png`, fullPage: true });
        await page.getByRole("button", { name: "Prepare exact request", exact: true }).click();
        await expect(page.getByRole("button", { name: maintenance ? "Approve Exact Action" : "Approve Implementation", exact: true })).toBeEnabled();
        await expect(page.getByRole("button", { name: /Resume|Run approved/ })).toHaveCount(0);
        expect(preparationWrites).toHaveLength(1);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}


for (const width of [320, 390, 1280]) test(`missing preparation reference recovers through a status read at ${width}px`, async ({page, baseURL}) => {
    const fixture = await installRepositoryJourney(page, true, {baseURL});
    await page.setViewportSize({width, height: 900});
    let reads = 0;
    const saved = { ...workflowDetail("implementation", false), workflow_state: "awaiting_approval", implementation_request: null, operational_action_request: null };
    await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => {
        expect(route.request().method()).toBe("GET");
        reads += 1;
        return route.fulfill({json: {...saved, planning_session_id: reads === 1 ? null : journey.session}});
    });
    await page.goto(`/workflows/${journey.workflow}`);
    await expect(page.getByRole("heading", {name: "Preparation details unavailable", exact: true})).toBeVisible();
    await expect(page.getByRole("link", {name: "Review preparation", exact: true})).toHaveCount(0);
    await page.getByRole("button", {name: "Check workflow status", exact: true}).click();
    await expect(page.getByRole("link", {name: "Review preparation", exact: true})).toBeVisible();
    expect(reads).toBe(2);
    await expect(page.getByRole("button", {name: /Approve|Resume|Run approved/})).toHaveCount(0);
    expect(fixture.writes).toEqual([]);
    expect(fixture.unexpected).toEqual([]);
});
