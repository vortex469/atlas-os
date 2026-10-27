import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';

const id = 'readable-session-fixture';
const session = {
    session_id: id, candidate_id: 'proposal/é', candidate_fingerprint: 'fingerprint-fixture',
    status: 'ready_for_planning', planning_allowed: false, intake_status: 'accepted_for_planning', intake_reason_codes: [],
    unsupported_reason: null, planning_failure: null, plan: null,
};
for (const width of [320, 390, 1280]) for (const mode of ['saved', 'successor', 'generated'] as const) {
    test(`unreadable session ${mode} recovers through a read at ${width}px`, async ({ page, baseURL }) => {
        const mutations: string[] = [];
        await installMissionControlMocks(page, 'available', mutations);
        await page.setViewportSize({ width, height: 900 });
        let phase = mode === 'saved' ? 'bad' : 'initial';
        let reads = 0, posts = 0, planReads = 0;
        const malformed = mode === 'saved' ? { ...session, status: {} }
            : mode === 'successor' ? { ...session, status: 'plan_ready', successor_session_id: '..' }
                : { ...session, status: 'plan_ready', candidate_fingerprint: {} };
        await page.route(`**/agent-api/candidate-planning/${id}`, route => {
            expect(route.request().method()).toBe('GET');
            reads += 1;
            const response = phase === 'bad' ? malformed
                : phase === 'recovered' ? { ...session, status: 'future_state', successor_session_id: 'next/é', intake_status: { future: true },
                    intake_reason_codes: null, future_metadata: { extra: true } }
                    : { ...session, planning_allowed: mode === 'generated' };
            return route.fulfill({ json: response });
        });
        await page.route(`**/agent-api/candidate-planning/${id}/plan`, route => {
            if (route.request().method() === 'GET') {
                planReads += 1;
                return route.fulfill({ status: 404, json: { detail: 'No fixture plan.' } });
            }
            expect(route.request().method()).toBe('POST');
            expect(route.request().postData()).toBeNull();
            posts += 1;
            return route.fulfill({ json: malformed });
        });
        await page.goto(`/candidate-planning/${id}`);
        if (mode === 'successor') {
            await expect(page.getByRole('link', { name: 'Review original proposal', exact: true })).toBeVisible();
            phase = 'bad';
            await page.getByRole('button', { name: 'Refresh planning', exact: true }).click();
        } else if (mode === 'generated') await page.getByRole('button', { name: 'Generate Plan', exact: true }).click();
        await expect(page.getByRole('alert')).toContainText('The planning session response is incomplete or unreadable.');
        await expect(page.getByRole('button', { name: 'Create Workflow', exact: true })).toHaveCount(0);
        await expect(page.getByRole('link', { name: '..', exact: true })).toHaveCount(0);
        if (width !== 320 && mode === 'saved') {
            await page.evaluate(() => scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-readable-planning-session-${width}.png`, fullPage: true });
        }
        phase = 'recovered';
        await page.getByRole('button', { name: mode === 'generated' ? 'Check saved planning' : 'Try again', exact: true }).click();
        await expect(page.getByRole('link', { name: 'Review original proposal', exact: true })).toHaveAttribute('href', '/execution-candidates/proposal%2F%C3%A9');
        await expect(page.getByRole('link', { name: 'next/é', exact: true })).toHaveAttribute('href', '/candidate-planning/next%2F%C3%A9');
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Generate Plan', exact: true })).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Create Workflow', exact: true })).toHaveCount(0);
        expect(reads).toBe((baseURL!.includes(':4173') ? 1 : 2) + (mode === 'successor' ? 2 : 1));
        expect(planReads).toBe(0);
        expect(posts).toBe(mode === 'generated' ? 1 : 0);
        expect(mutations).toEqual(mode === 'generated' ? [`POST ${baseURL}/agent-api/candidate-planning/${id}/plan`] : []);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
