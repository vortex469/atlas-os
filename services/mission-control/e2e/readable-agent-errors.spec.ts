import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';
import { operationalPlan } from '../src/test/operationalPlanning';

const id = 'readable-agent-error-fixture';
const publicMessage = `Saved planning is temporarily unavailable for planning-${'a'.repeat(96)}.`;
const session = {
    session_id: id, candidate_id: 'candidate-error-fixture', candidate_fingerprint: 'candidate-fingerprint',
    status: 'plan_ready', planning_allowed: true, intake_status: 'accepted_for_planning', intake_reason_codes: [],
    unsupported_reason: null, planning_failure: null, plan: null,
    operational_plan: operationalPlan({ session_id: id, candidate_id: 'candidate-error-fixture',
        candidate_fingerprint: 'candidate-fingerprint', revalidated_candidate_fingerprint: 'candidate-fingerprint' }),
};
for (const width of [320, 390, 1280]) for (const mode of ['message', 'validation', 'creation'] as const) {
    test(`structured Agent ${mode} error stays readable at ${width}px`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, 'available', mutations);
        await page.setViewportSize({ width, height: 900 });
        let recovered = false, reads = 0, posts = 0;
        await page.route(`**/agent-api/candidate-planning/${id}`, route => {
            expect(route.request().method()).toBe('GET');
            reads += 1;
            if (!recovered && mode !== 'creation') return route.fulfill({ status: mode === 'validation' ? 422 : 503, json: {
                detail: mode === 'validation' ? [{ loc: ['body', 'credential'], msg: 'Input rejected', input: 'SECRET-CANARY', ctx: { private: true } }]
                    : { code: 'fixture_unavailable', message: publicMessage },
            } });
            return route.fulfill({ json: recovered ? { ...session, planning_allowed: false,
                status: mode === 'creation' ? 'workflow_created' : 'future_state', workflow_session_id: mode === 'creation' ? 'workflow-error-fixture' : null } : session });
        });
        await page.route(`**/agent-api/candidate-planning/${id}/workflow`, route => {
            expect(route.request().method()).toBe('POST');
            expect(route.request().postData()).toBeNull();
            posts += 1;
            return route.fulfill({ status: 503, json: { detail: { code: 'fixture_unavailable', message: 'The saved workflow response is unavailable.' } } });
        });
        await page.goto(`/candidate-planning/${id}`);
        if (mode === 'creation') await page.getByRole('button', { name: 'Create Workflow', exact: true }).click();
        const expected = mode === 'message' ? publicMessage
            : mode === 'validation' ? 'Mission Control could not load this planning session.' : 'The saved workflow response is unavailable.';
        await expect(page.getByRole('alert')).toContainText(expected);
        expect(await page.getByRole('alert').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
        await expect(page.getByRole('heading', { name: 'This page could not load', exact: true })).toHaveCount(0);
        await expect(page.getByText(/SECRET-CANARY|\[object Object\]|Request failed with status code/)).toHaveCount(0);
        if (width !== 320) {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-readable-agent-error-${mode}-${width}.png`, fullPage: true });
        }
        recovered = true;
        await page.getByRole('button', { name: mode === 'creation' ? 'Check saved planning' : 'Try again', exact: true }).click();
        if (mode === 'creation') await expect(page.getByRole('link', { name: 'Open existing workflow', exact: true })).toHaveAttribute('href', '/workflows/workflow-error-fixture');
        else await expect(page.getByRole('heading', { name: 'Maintenance plan', exact: true })).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        expect(reads).toBe(baseURL!.includes(':4173') ? 2 : 3);
        expect(posts).toBe(mode === 'creation' ? 1 : 0);
        expect(mutations).toEqual(mode === 'creation' ? [`POST ${baseURL}/agent-api/candidate-planning/${id}/workflow`] : []);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
