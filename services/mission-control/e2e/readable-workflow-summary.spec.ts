import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';
import { operationalPlan } from '../src/test/operationalPlanning';

const id = 'readable-workflow-fixture';
const summary = {
    candidate_planning_session_id: id, candidate_id: 'candidate-workflow-fixture', candidate_fingerprint: 'candidate-fingerprint',
    candidate_plan_id: { future: true }, candidate_plan_fingerprint: 'plan-fingerprint', workflow_session_id: 'workflow-fixture',
    workflow_status: 'future_state', implementation_approval_request_id: null, conversion_status: 'future_conversion',
    core_revalidation_status: { future: true }, reason_codes: ['future_reason'], failure: null,
};
const planning = {
    session_id: id, candidate_id: summary.candidate_id, candidate_fingerprint: summary.candidate_fingerprint,
    status: 'plan_ready', planning_allowed: true, intake_status: 'accepted_for_planning', intake_reason_codes: [],
    unsupported_reason: null, planning_failure: null, plan: null,
    operational_plan: operationalPlan({ session_id: id, candidate_id: summary.candidate_id,
        candidate_fingerprint: summary.candidate_fingerprint, revalidated_candidate_fingerprint: summary.candidate_fingerprint }),
};
for (const width of [320, 390, 1280]) for (const mode of ['creation', 'summary', 'cached'] as const) {
    test(`unreadable workflow ${mode} recovers through reads at ${width}px`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, 'available', mutations);
        await page.setViewportSize({ width, height: 900 });
        let recovered = false, sessionReads = 0, workflowReads = 0, posts = 0, planReads = 0;
        let release!: () => void;
        const pending = new Promise<void>(resolve => { release = resolve; });
        const path = `/candidate-planning/${id}/workflow`;
        if (mode === 'cached') await page.addInitScript(({ path, summary }) => {
            if (location.pathname === path) history.replaceState({ usr: { workflow: { ...summary, candidate_fingerprint: {} } }, key: 'cached-workflow', idx: 0 }, '');
        }, { path, summary });
        await page.route(`**/agent-api/candidate-planning/${id}`, route => {
            expect(route.request().method()).toBe('GET');
            sessionReads += 1;
            return route.fulfill({ json: recovered ? { ...planning, status: 'workflow_created', planning_allowed: false,
                workflow_session_id: summary.workflow_session_id } : planning });
        });
        await page.route(`**/agent-api/candidate-planning/${id}/plan`, route => {
            planReads += 1;
            return route.fulfill({ status: 404, json: { detail: 'No repository plan in this fixture.' } });
        });
        await page.route(`**/agent-api/candidate-planning/${id}/workflow`, async route => {
            if (route.request().method() === 'POST') {
                expect(route.request().postData()).toBeNull();
                posts += 1;
                return route.fulfill({ json: { ...summary, reason_codes: null } });
            }
            expect(route.request().method()).toBe('GET');
            workflowReads += 1;
            if (mode === 'cached') await pending;
            return route.fulfill({ json: mode === 'summary' && !recovered ? { ...summary, workflow_status: {} } : summary });
        });
        await page.goto(mode === 'creation' ? `/candidate-planning/${id}` : path);
        if (mode === 'cached') {
            await expect(page.getByText('Loading workflow summary…', { exact: true })).toBeVisible();
            await expect(page.getByRole('button', { name: /prepare exact request|re-plan/i })).toHaveCount(0);
            release();
        } else {
            if (mode === 'creation') await page.getByRole('button', { name: 'Create Workflow', exact: true }).click();
            await expect(page.getByRole('alert')).toContainText('The workflow summary response is incomplete or unreadable.');
            await expect(page.getByRole('link', { name: 'Open Workflow', exact: true })).toHaveCount(0);
            await expect(page.getByRole('button', { name: /prepare exact request|re-plan/i })).toHaveCount(0);
            if (width !== 320) {
                await page.evaluate(() => scrollTo(0, 0));
                await page.screenshot({ path: `/tmp/atlas-readable-workflow-${mode}-${width}.png`, fullPage: true });
            }
            recovered = true;
            await page.getByRole('button', { name: mode === 'creation' ? 'Check saved planning' : 'Try again', exact: true }).click();
        }
        if (mode === 'creation') await expect(page.getByRole('link', { name: 'Open existing workflow', exact: true })).toHaveAttribute('href', '/workflows/workflow-fixture');
        else await expect(page.getByRole('heading', { name: 'Workflow summary', exact: true })).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(page.getByRole('button', { name: /prepare exact request|re-plan/i })).toHaveCount(0);
        expect(sessionReads).toBe(mode === 'creation' ? (baseURL!.includes(':4173') ? 2 : 3) : 0);
        expect(workflowReads).toBe(mode === 'summary' ? 2 : mode === 'cached' ? 1 : 0);
        expect(posts).toBe(mode === 'creation' ? 1 : 0);
        expect(planReads).toBe(0);
        expect(mutations).toEqual(mode === 'creation' ? [`POST ${baseURL}/agent-api/candidate-planning/${id}/workflow`] : []);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
