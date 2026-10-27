import { expect, test } from "@playwright/test";
import { installMissionControlMocks } from "./mission-control-fixtures";
import { installRepositoryJourney, journey } from "./repository-journey-fixture";
import { operationalPlan } from "../src/test/operationalPlanning";

const planning = { session_id: journey.session, candidate_id: journey.candidate, status: "workflow_created", planning_allowed: false,
    intake_status: "accepted_for_planning", intake_reason_codes: [], candidate_fingerprint: journey.candidateFingerprint,
    unsupported_reason: null, plan: null, planning_failure: null, workflow_session_id: journey.workflow };
for (const width of [320, 390, 1280]) {
    for (const mode of ["saved", "orphan", "legacy"] as const) test(`existing workflow from ${mode} planning at ${width}px uses reads only`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, "available", mutations);
        const fixture = await installRepositoryJourney(page, true, { maintenance: true, baseURL });
        await page.setViewportSize({ width, height: 900 });
        await page.route(`**/agent-api/candidate-planning/${journey.session}`, route => {
            expect(route.request().method()).toBe("GET");
            const response = mode === "saved" ? { ...planning, status: "plan_ready", planning_allowed: true,
                operational_plan: operationalPlan({ session_id: journey.session, candidate_id: journey.candidate,
                    candidate_fingerprint: journey.candidateFingerprint, revalidated_candidate_fingerprint: journey.candidateFingerprint }),
                predecessor_session_id: "previous-planning-session", successor_session_id: null }
                : mode === "legacy" ? { ...planning, workflow_session_id: null } : planning;
            return route.fulfill({ json: response });
        });
        await page.route("**/agent-api/api/v1/agent/workflows?*", route => {
            expect(route.request().method()).toBe("GET");
            return route.fulfill({ json: { items: [{ workflow_id: journey.workflow, workflow_source: "candidate", workflow_state: "awaiting_implementation_approval",
                effect_kind: "operational_action", execution_intent: "restart-service", candidate_id: journey.candidate, planning_session_id: journey.session,
                repository: null, target_id: "110", last_result_summary: "Waiting for operator review", timeline: [] }],
                total: 1, limit: 10, offset: 0, state_counts: { awaiting_implementation_approval: 1 } } });
        });
        await page.goto(`/candidate-planning/${journey.session}`);
        await expect(page.getByRole("heading", { name: "Review existing workflow", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Workflow already exists", exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Generate Plan", exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Create Workflow", exact: true })).toHaveCount(0);
        if (mode === "saved") await expect(page.getByRole("heading", { name: "Maintenance plan", exact: true })).toBeVisible();
        else await expect(page.getByRole("heading", { name: "Plan", exact: true, level: 2 })).toHaveCount(0);
        if (mode === "orphan" && width !== 320) await page.screenshot({ path: `/tmp/atlas-existing-workflow-review-${width}.png`, fullPage: true });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        if (mode === "legacy") {
            await page.getByRole("link", { name: "Browse workflows", exact: true }).click();
            await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
            await page.locator(`a[href="/workflows/${journey.workflow}"]`).click();
        } else await page.getByRole("link", { name: "Open existing workflow", exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/workflows/${journey.workflow}$`));
        await expect(page.getByRole("heading", { name: "Workflow summary", exact: true })).toBeVisible();
        await page.reload();
        await expect(page.getByRole("heading", { name: "Workflow summary", exact: true })).toBeVisible();
        expect(mutations).toEqual([]);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        expect(fixture.repositoryPlanReads).toBe(0);
    });
    test(`proposal opens its existing workflow at ${width}px without a conversion request`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, "available", mutations);
        const fixture = await installRepositoryJourney(page, true, { baseURL });
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/candidate-planning", route => {
            expect(route.request().method()).toBe("POST");
            expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
            expect(route.request().postDataJSON()).toEqual({ candidate_id: journey.candidate });
            return route.fulfill({ json: planning });
        });
        await page.goto(`/execution-candidates/${journey.candidate}`);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await expect(page.getByText("A workflow already exists for this proposal. Review its progress and any remaining approvals.", { exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "Continue planning", exact: true })).toHaveCount(0);
        await page.getByRole("link", { name: "Open existing workflow", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Workflow summary", exact: true })).toBeVisible();
        expect(mutations).toEqual([`POST ${new URL(baseURL!).origin}/agent-api/candidate-planning`]);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
}
